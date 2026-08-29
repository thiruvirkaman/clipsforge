"""Pydantic schemas for authentication requests/responses."""
from pydantic import BaseModel, EmailStr, field_validator

#: MVP minimum -- long enough to rule out trivial/empty passwords without
#: imposing complexity rules (uppercase/digit/symbol requirements) this pass
#: doesn't need.
MIN_PASSWORD_LENGTH = 8


class RegisterRequest(BaseModel):
    """Payload for POST /auth/register."""

    email: EmailStr
    password: str
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def _password_min_length(cls, value: str) -> str:
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")
        return value


class Token(BaseModel):
    """Access/refresh token pair returned by login, refresh, and register flows."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Payload for POST /auth/refresh and POST /auth/logout."""

    refresh_token: str
