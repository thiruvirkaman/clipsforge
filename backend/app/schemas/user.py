"""Pydantic schemas for user responses."""
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    """Public-facing representation of a ClipForge user."""

    id: int
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True
