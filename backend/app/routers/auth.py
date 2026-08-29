"""Authentication endpoints for ClipForge (email/password + JWT, no OAuth)."""
import logging

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import RefreshRequest, RegisterRequest, Token
from app.schemas.user import UserResponse
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> User:
    """Register a new user account."""
    user = auth_service.register_user(
        db, email=payload.email, password=payload.password, full_name=payload.full_name
    )
    return user


@router.post("/login", response_model=Token)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """Authenticate with email (as `username`) and password, returning a token pair."""
    user = auth_service.authenticate_user(db, email=form.username, password=form.password)
    return auth_service.issue_tokens(db, user)


@router.post("/refresh", response_model=Token)
async def refresh(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
) -> Token:
    """Exchange a valid refresh token for a new access/refresh token pair."""
    return auth_service.refresh_access_token(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> None:
    """Revoke the given refresh token, ending that session."""
    auth_service.revoke_refresh_token(db, payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user's profile."""
    return current_user
