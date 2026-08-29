"""Project model for ClipForge: a single long-form video being processed."""
import enum
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class SourceType(str, enum.Enum):
    upload = "upload"
    url = "url"


class ProjectStatus(str, enum.Enum):
    pending = "pending"
    transcribing = "transcribing"
    analyzing = "analyzing"
    ready = "ready"
    failed = "failed"


class Project(Base, TimestampMixin):
    """A long-form video source and its processing pipeline state."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.pending, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Timestamped ASR transcript, persisted so the render step can slice out
    # sentence/segment-level captions for each clip's own [start, end]
    # window rather than rendering one caption for the whole clip.
    # List[{"start": float, "end": float, "text": str}], JSON-serializable.
    transcript_segments: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    user = relationship("User", back_populates="projects")
    processing_jobs = relationship(
        "ProcessingJob", back_populates="project", cascade="all, delete-orphan"
    )
    clips = relationship(
        "Clip", back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_projects_user_id_status", "user_id", "status"),
    )
