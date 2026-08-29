"""Shared FastAPI dependencies for ClipForge."""
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_token
from app.database import get_db
from app.exceptions import UnauthorizedError
from app.models.user import User

__all__ = ["get_current_user", "get_db"]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Resolve the current authenticated user from a bearer JWT access token."""
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("Invalid token")

    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("Invalid token")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise UnauthorizedError("User not found")
    return user
