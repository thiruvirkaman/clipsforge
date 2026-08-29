"""Project endpoints for ClipForge: create, list, and kick off processing for
long-form video projects."""
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.processing_job import ProcessingJob
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProcessingJobResponse, ProjectResponse
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Project]:
    """List the current user's projects."""
    return project_service.list_projects(db, current_user.id, skip, limit)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    title: str = Form(...),
    source_type: Literal["upload", "url"] = Form(...),
    source_url: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """Create a project, either from an uploaded video file or a source URL.

    Submitted as multipart form data in both cases: pass `file` for an
    upload, or `source_url` (and no `file`) for a URL-only project.
    """
    return project_service.create_project(
        db, current_user.id, title, source_type, source_url, file
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """Get a single project owned by the current user."""
    return project_service.get_project(db, current_user.id, project_id)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a project. Processing jobs and clips cascade via DB FK."""
    project_service.delete_project(db, current_user.id, project_id)


@router.post("/{project_id}/process", response_model=ProjectResponse)
async def process_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """Kick off the processing pipeline (transcription -> highlight
    detection -> render) for a project."""
    return project_service.start_processing(db, current_user.id, project_id)


@router.get("/{project_id}/jobs", response_model=list[ProcessingJobResponse])
async def list_project_jobs(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProcessingJob]:
    """List processing jobs for a project, for polling pipeline progress."""
    project_service.get_project(db, current_user.id, project_id)
    return project_service.list_jobs(db, project_id)
