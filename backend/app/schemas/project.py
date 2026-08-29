"""Pydantic schemas for ClipForge project endpoints."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.processing_job import JobStatus, JobType
from app.models.project import ProjectStatus, SourceType


class ProjectCreate(BaseModel):
    """Fields for creating a project. File upload itself is multipart and is
    handled separately in the router (not through this schema)."""

    title: str
    source_type: Literal["upload", "url"]
    source_url: str | None = None


class ProjectResponse(BaseModel):
    """A project as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source_type: SourceType
    source_url: str | None
    source_file_path: str | None
    duration_seconds: int | None
    status: ProjectStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime | None


class ProcessingJobResponse(BaseModel):
    """A single processing-pipeline step, for polling a project's progress."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: JobType
    status: JobStatus
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
