"""Business logic for ClipForge project management: creating projects from an
uploaded file or a source URL, and kicking off the async processing pipeline
(transcription -> highlight detection -> render), which lives in `app.tasks`
(owned by the Clip Generation module).
"""
import logging
import os

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.exceptions import (
    ConflictError,
    EnqueueError,
    ForbiddenError,
    NotFoundError,
    QuotaExceededError,
    ValidationError,
)
from app.models.clip import Clip
from app.models.processing_job import ProcessingJob
from app.models.project import Project, ProjectStatus, SourceType
from app.services import usage_service
from app.services.media_cleanup import delete_clip_media, delete_project_media
from app.services.media_probe import MediaProbeError, probe_media
from app.services.youtube_service import MAX_SOURCE_DURATION_SECONDS, is_supported_youtube_url
from app.storage import UploadTooLargeError, get_media_storage

logger = logging.getLogger(__name__)

# Statuses in which a project already has a pipeline run in flight.
_ACTIVE_STATUSES = {ProjectStatus.transcribing, ProjectStatus.analyzing}

# Extensions accepted for uploaded source video. Rejects arbitrary file types
# (e.g. .html/.svg/.exe) up front, as a cheap first filter before the real
# ffprobe-based content check below.
_ALLOWED_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}

# Hard ceiling on a single upload. Enforced while streaming (see
# `storage.save_stream`), so an oversized upload is rejected without ever
# buffering the full payload into memory. Sized for up to a ~3 hour source
# video (matching MAX_SOURCE_DURATION_SECONDS below) at a generous bitrate;
# also requires nginx's `client_max_body_size` (see frontend/nginx.conf) to
# be at least this large, or it never reaches the backend at all.
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB -- MVP sanity bound


def create_project(
    db: Session,
    user_id: int,
    title: str,
    source_type: str,
    source_url: str | None,
    upload_file: UploadFile | None,
) -> Project:
    """Create a new project from either an uploaded file or a source URL."""
    source_file_path: str | None = None
    duration_seconds: int | None = None

    if source_type == SourceType.upload.value:
        source_file_path, duration_seconds = _ingest_upload(upload_file)
    elif source_type == SourceType.url.value:
        if not source_url:
            raise ValidationError("source_url is required when source_type is 'url'")
        if not is_supported_youtube_url(source_url):
            raise ValidationError(
                "Only single-video YouTube URLs (youtube.com or youtu.be) are supported."
            )
    else:
        raise ValidationError(f"Invalid source_type: {source_type}")

    project = Project(
        user_id=user_id,
        title=title,
        source_type=SourceType(source_type),
        source_url=source_url,
        source_file_path=source_file_path,
        duration_seconds=duration_seconds,
        status=ProjectStatus.pending,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("Created project %s for user %s", project.id, user_id)
    return project


def _ingest_upload(upload_file: UploadFile | None) -> tuple[str, int]:
    """Validate, stream to storage, and probe an uploaded video file.

    Returns (stored_path, duration_seconds). Raises `ValidationError` for
    any problem with the upload (missing, wrong type, too large, or not
    actually a playable video once probed).
    """
    if upload_file is None:
        raise ValidationError("A file is required when source_type is 'upload'")

    filename = upload_file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext or '(none)'}'. Allowed types: "
            f"{', '.join(sorted(_ALLOWED_UPLOAD_EXTENSIONS))}"
        )

    storage = get_media_storage()
    try:
        stored_path = storage.save_stream(
            upload_file.file, filename, max_bytes=MAX_UPLOAD_SIZE_BYTES
        )
    except UploadTooLargeError as exc:
        raise ValidationError(
            f"Uploaded file exceeds the maximum allowed size of "
            f"{MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB"
        ) from exc

    if os.path.getsize(storage.get_path(stored_path)) == 0:
        storage.delete(stored_path)
        raise ValidationError("Uploaded file is empty")

    # Validate the file is actually a playable video (not just an allowed
    # extension) and read its real duration via ffprobe.
    try:
        probe = probe_media(storage.get_path(stored_path))
    except MediaProbeError as exc:
        storage.delete(stored_path)
        raise ValidationError(f"Uploaded file is not a valid video: {exc}") from exc

    # Same duration ceiling as YouTube sources (MAX_SOURCE_DURATION_SECONDS),
    # so a direct upload can't bypass the limit URL ingestion enforces.
    if probe.duration_seconds > MAX_SOURCE_DURATION_SECONDS:
        storage.delete(stored_path)
        raise ValidationError(
            f"Video exceeds the maximum supported duration of "
            f"{MAX_SOURCE_DURATION_SECONDS // 60} minutes."
        )

    return stored_path, int(probe.duration_seconds)


def get_project(db: Session, user_id: int, project_id: int) -> Project:
    """Fetch a single project by id, enforcing ownership.

    Raises `NotFoundError` if no such project exists at all, and
    `ForbiddenError` if it exists but belongs to a different user.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise NotFoundError("Project")
    if project.user_id != user_id:
        raise ForbiddenError("You do not have access to this project")
    return project


def list_projects(
    db: Session, user_id: int, skip: int = 0, limit: int = 100
) -> list[Project]:
    """List a user's projects, most recently created first."""
    return (
        db.query(Project)
        .filter(Project.user_id == user_id)
        .order_by(Project.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def delete_project(db: Session, user_id: int, project_id: int) -> None:
    """Delete a project: its clips' media, its own source media, then the
    row itself (jobs/clips cascade via DB FK)."""
    project = get_project(db, user_id, project_id)
    for clip in project.clips:
        delete_clip_media(db, clip)
    delete_project_media(db, project)
    db.delete(project)
    db.commit()


def _clear_previous_run(db: Session, project: Project) -> None:
    """Delete any clips/media left over from a prior run of this project
    before starting a fresh pipeline, so reprocessing never accumulates
    duplicate clips.

    Flush-only, never commits: called from within `start_processing`'s
    row-locked transaction, and an intermediate commit here would end that
    transaction early, releasing the lock before the function finishes.
    """
    clips = db.query(Clip).filter(Clip.project_id == project.id).all()
    if clips:
        logger.info(
            "Clearing %d clip(s) from a previous run before reprocessing project %s",
            len(clips),
            project.id,
        )
        for clip in clips:
            delete_clip_media(db, clip)
            db.delete(clip)
        db.flush()
    usage_service.delete_usage_records_for_project(db, project.id)


def start_processing(db: Session, user_id: int, project_id: int) -> Project:
    """Validate a project is startable, mark it as transcribing, and enqueue
    the Celery pipeline (starting with transcription).

    The quota check runs first (a per-user check, independent of any
    specific project, so it doesn't need the row lock below). The project
    row is then locked (`SELECT ... FOR UPDATE`, a no-op on SQLite but a
    real lock on Postgres) for the remainder of the function, and nothing
    from here until the single commit below may itself call `commit()` --
    doing so would end the transaction early and release the lock before
    two concurrent process requests are actually serialized by it. If the
    broker is unavailable, the project is marked `failed` with a clear
    message rather than left stuck in `transcribing`.
    """
    if not usage_service.check_within_limits(db, user_id):
        raise QuotaExceededError(
            "You have reached your plan's monthly processing limit. "
            "Upgrade your plan or wait for the next billing period to process more videos."
        )

    project = (
        db.query(Project)
        .filter(Project.id == project_id)
        .with_for_update()
        .first()
    )
    if project is None:
        raise NotFoundError("Project")
    if project.user_id != user_id:
        raise ForbiddenError("You do not have access to this project")

    if project.status in _ACTIVE_STATUSES:
        raise ConflictError(f"Project {project_id} is already processing")

    _clear_previous_run(db, project)

    project.status = ProjectStatus.transcribing
    project.error_message = None
    db.commit()
    db.refresh(project)

    # Imported lazily so that a temporarily-missing `app.tasks` module
    # doesn't break every other endpoint in this router at import time.
    from app.tasks import transcribe_project

    try:
        transcribe_project.delay(project_id)
    except Exception as exc:
        logger.exception("Failed to enqueue transcription pipeline for project %s", project_id)
        project.status = ProjectStatus.failed
        project.error_message = "Failed to queue processing. Please try again shortly."
        db.commit()
        raise EnqueueError(
            "Could not start processing right now (background queue unavailable). "
            "Please try again shortly."
        ) from exc

    logger.info("Queued transcription pipeline for project %s", project_id)
    return project


def list_jobs(db: Session, project_id: int) -> list[ProcessingJob]:
    """List processing jobs for a project, in the order they were created."""
    return (
        db.query(ProcessingJob)
        .filter(ProcessingJob.project_id == project_id)
        .order_by(ProcessingJob.id.asc())
        .all()
    )
