"""Business logic for authentication: registration, login, and token lifecycle.

Access tokens are short-lived and stateless (JWT only). Refresh tokens are
also JWTs, but every issued refresh token is additionally persisted as a
`RefreshToken` row so it can be looked up, expired, and revoked (logout,
rotation on refresh) independently of its cryptographic validity. Only a
SHA-256 hash of the token is ever stored -- a database read leak (backup,
replica, injection, etc.) must not hand over live, usable credentials. The
client's own JWT is still the real bearer credential; we just never persist
it in a directly-reusable form.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings
from app.exceptions import ConflictError, UnauthorizedError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import Token

logger = logging.getLogger(__name__)


def _to_utc(value: datetime) -> datetime:
    """Normalize a datetime to timezone-aware UTC (SQLite may return naive values)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash_token(token: str) -> str:
    """One-way SHA-256 hex digest used as the DB lookup key for a refresh
    token, so the raw (directly reusable) JWT is never persisted."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register_user(
    db: Session, email: str, password: str, full_name: str | None = None
) -> User:
    """Create a new user account.

    Raises:
        ConflictError: If a user with this email already exists.
    """
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise ConflictError("A user with this email already exists")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Registered new user id=%s", user.id)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Validate credentials and return the matching, active user.

    Raises:
        UnauthorizedError: If the email/password combination is invalid,
            or the account is inactive.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is inactive")
    return user


def _persist_refresh_token(db: Session, user: User, refresh_token: str) -> None:
    """Persist an issued refresh token so it can later be validated/revoked."""
    payload = decode_token(refresh_token)
    if payload and "exp" in payload:
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    else:
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

    record = RefreshToken(user_id=user.id, token=_hash_token(refresh_token), expires_at=expires_at)
    db.add(record)
    db.commit()


def issue_tokens(db: Session, user: User) -> Token:
    """Create a new access/refresh token pair for a user and persist the refresh token.

    A random `jti` claim is embedded in the refresh token so that two
    tokens issued for the same user within the same second (`exp` has
    only second-level resolution) never collide - the `token` column is
    unique, and JWT encoding is otherwise deterministic for identical
    payloads.
    """
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token(
        {"sub": str(user.id), "jti": secrets.token_urlsafe(16)}
    )
    _persist_refresh_token(db, user, refresh_token)
    return Token(access_token=access_token, refresh_token=refresh_token)


def refresh_access_token(db: Session, refresh_token: str) -> Token:
    """Validate a refresh token against stored records and issue a new token pair.

    The presented refresh token is revoked (rotated) once it has been used
    successfully, so it cannot be replayed.

    Raises:
        UnauthorizedError: If the token is malformed/expired/of the wrong
            type, not found, already revoked, or its owning user is gone
            or inactive.
    """
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh" or not payload.get("sub"):
        raise UnauthorizedError("Invalid refresh token")

    stored = db.query(RefreshToken).filter(RefreshToken.token == _hash_token(refresh_token)).first()
    if not stored or stored.revoked:
        raise UnauthorizedError("Refresh token has been revoked or is unknown")

    if _to_utc(stored.expires_at) < datetime.now(timezone.utc):
        raise UnauthorizedError("Refresh token has expired")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise UnauthorizedError("User not found")

    # Rotate: the used refresh token is revoked before a new pair is issued.
    stored.revoked = True
    db.add(stored)
    db.commit()

    return issue_tokens(db, user)


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    """Revoke a stored refresh token (logout). Silently no-ops if unknown/already revoked."""
    stored = db.query(RefreshToken).filter(RefreshToken.token == _hash_token(refresh_token)).first()
    if stored and not stored.revoked:
        stored.revoked = True
        db.add(stored)
        db.commit()
