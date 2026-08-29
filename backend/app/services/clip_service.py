"""Business logic for clip listing, retrieval, deletion, and regeneration."""
import logging

from sqlalchemy.orm import Session

from app.exceptions import (
    ConflictError,
    EnqueueError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.models.clip import Clip, ClipStatus
from app.models.project import Project
from app.services.media_cleanup import delete_clip_media
from app.services.render_service import CAPTION_STYLES
from app.tasks import render_clip_task

logger = logging.getLogger(__name__)

# MVP sanity bound on a single clip's length, independent of the source
# project's duration (which may be unknown for not-yet-processed sources).
_MAX_CLIP_DURATION_SECONDS = 15 * 60


def list_clips(db: Session, user_id: int, project_id: int) -> list[Clip]:
    """List all clips for a project, verifying the project belongs to `user_id`."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise NotFoundError("Project")
    if project.user_id != user_id:
        raise ForbiddenError("You do not have access to this project")

    return (
        db.query(Clip)
        .filter(Clip.project_id == project_id)
        .order_by(Clip.start_time.asc())
        .all()
    )


def get_clip(db: Session, user_id: int, clip_id: int) -> Clip:
    """Fetch a single clip, verifying ownership."""
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if clip is None:
        raise NotFoundError("Clip")
    if clip.user_id != user_id:
        raise ForbiddenError("You do not have access to this clip")
    return clip


def delete_clip(db: Session, user_id: int, clip_id: int) -> None:
    """Delete a clip owned by `user_id`, including its rendered media."""
    clip = get_clip(db, user_id, clip_id)
    delete_clip_media(db, clip)
    db.delete(clip)
    db.commit()
    logger.info("Deleted clip %s", clip_id)


def _validate_regeneration_window(
    clip: Clip, start_time: float | None, end_time: float | None
) -> tuple[float, float]:
    """Resolve and validate the effective start/end for a regenerate request.

    Raises `ValidationError` for a negative start, end <= start, a window
    beyond the source project's known duration, or an implausibly long clip.
    """
    effective_start = clip.start_time if start_time is None else start_time
    effective_end = clip.end_time if end_time is None else end_time

    if effective_start < 0:
        raise ValidationError("start_time must not be negative")
    if effective_end <= effective_start:
        raise ValidationError("end_time must be greater than start_time")

    duration = effective_end - effective_start
    if duration > _MAX_CLIP_DURATION_SECONDS:
        raise ValidationError(
            f"Clip duration must not exceed {_MAX_CLIP_DURATION_SECONDS} seconds"
        )

    project_duration = clip.project.duration_seconds if clip.project else None
    if project_duration is not None and effective_end > project_duration:
        raise ValidationError(
            f"end_time ({effective_end}s) is beyond the source video's duration "
            f"({project_duration}s)"
        )

    return effective_start, effective_end


def regenerate_clip(
    db: Session,
    user_id: int,
    clip_id: int,
    start_time: float | None = None,
    end_time: float | None = None,
    caption_style: str | None = None,
) -> Clip:
    """Update a clip's editable fields (if provided), reset it to `queued`,
    and re-enqueue a render job for it.

    Validates the requested window and caption style before making any
    change or enqueuing anything -- an invalid request never reaches Celery.
    The clip row is locked (`SELECT ... FOR UPDATE`, a no-op on SQLite but a
    real lock on Postgres) so two concurrent regenerate requests can't both
    pass the "not already active" check and both enqueue a render against
    the same output file. If the broker is unavailable, the clip is marked
    `failed` with a clear message rather than left stuck in `queued` forever.
    """
    clip = db.query(Clip).filter(Clip.id == clip_id).with_for_update().first()
    if clip is None:
        raise NotFoundError("Clip")
    if clip.user_id != user_id:
        raise ForbiddenError("You do not have access to this clip")

    if clip.status in (ClipStatus.queued, ClipStatus.rendering):
        raise ConflictError(f"Clip {clip_id} is already queued or rendering")

    effective_start, effective_end = _validate_regeneration_window(clip, start_time, end_time)

    if caption_style is not None and caption_style not in CAPTION_STYLES:
        raise ValidationError(
            f"Unknown caption_style {caption_style!r}; must be one of {sorted(CAPTION_STYLES)}"
        )

    clip.start_time = effective_start
    clip.end_time = effective_end
    if caption_style is not None:
        clip.caption_style = caption_style

    clip.status = ClipStatus.queued
    db.commit()
    db.refresh(clip)

    try:
        render_clip_task.delay(clip.id)
    except Exception as exc:
        logger.exception("Failed to enqueue render for clip %s", clip_id)
        clip.status = ClipStatus.failed
        db.commit()
        raise EnqueueError(
            "Could not queue this clip for rendering right now. Please try again shortly."
        ) from exc

    logger.info("Re-enqueued render for clip %s", clip_id)
    return clip
