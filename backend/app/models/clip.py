"""Clip model for ClipForge: a rendered short-form vertical clip.

Business rule: clips are a SELECTIVE subset of a project (the top-N detected
highlights, not full-video coverage). start_time/end_time are
semantically-snapped to natural highlight boundaries (not clamped to a fixed
60s window), so clip duration varies roughly 40-90s depending on content.
"""
import enum

from sqlalchemy import Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class ClipStatus(str, enum.Enum):
    queued = "queued"
    rendering = "rendering"
    ready = "ready"
    failed = "failed"


class Clip(Base, TimestampMixin):
    """A single short-form clip rendered from a highlight in a project."""

    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    transcript_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String(10), default="9:16", nullable=False)
    caption_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[ClipStatus] = mapped_column(
        Enum(ClipStatus), default=ClipStatus.queued, nullable=False
    )
    video_file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="clips")
    user = relationship("User")

    __table_args__ = (
        Index("ix_clips_project_id_status", "project_id", "status"),
    )
