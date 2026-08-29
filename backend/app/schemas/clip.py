"""Pydantic schemas for clip responses."""
from datetime import datetime

from pydantic import BaseModel

from app.models.clip import ClipStatus


class ClipResponse(BaseModel):
    """Public-facing representation of a rendered (or in-progress) clip."""

    id: int
    project_id: int
    title: str
    start_time: float
    end_time: float
    transcript_snippet: str | None
    relevance_score: float | None
    aspect_ratio: str
    caption_style: str | None
    status: ClipStatus
    video_file_path: str | None
    thumbnail_path: str | None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True
