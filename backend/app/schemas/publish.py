"""Pydantic schemas for the export & publish module."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.publish_connection import Platform
from app.models.scheduled_post import PostStatus

PlatformLiteral = Literal["tiktok", "instagram", "youtube_shorts"]


class PublishConnectionResponse(BaseModel):
    """Public-facing representation of a user's linked platform account."""

    id: int
    platform: Platform
    account_handle: str | None
    connected_at: datetime

    class Config:
        from_attributes = True


class PublishRequest(BaseModel):
    """Payload for POST /clips/{id}/publish."""

    platform: PlatformLiteral
    scheduled_at: datetime | None = None


class ScheduledPostResponse(BaseModel):
    """Public-facing representation of a scheduled/published post."""

    id: int
    clip_id: int
    platform: Platform
    scheduled_at: datetime | None
    status: PostStatus
    published_url: str | None
    error_message: str | None
    created_at: datetime

    class Config:
        from_attributes = True
