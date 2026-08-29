"""Endpoints for exporting clips: downloading the rendered file and publishing it."""
import logging
import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.exceptions import NotFoundError
from app.models.clip import Clip, ClipStatus
from app.models.user import User
from app.schemas.publish import PublishRequest, ScheduledPostResponse
from app.services import publish_service
from app.storage import get_media_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clips", tags=["clips-export"])


def _get_ready_clip(db: Session, user_id: int, clip_id: int) -> Clip:
    clip = db.query(Clip).filter(Clip.id == clip_id, Clip.user_id == user_id).first()
    if clip is None or clip.status != ClipStatus.ready or not clip.video_file_path:
        raise NotFoundError("Clip")
    return clip


@router.get("/{clip_id}/download")
async def download_clip(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Stream a ready clip's rendered video file for download.

    Authenticated and ownership-checked (via `_get_ready_clip`) -- this is
    the only way to reach a clip's video file. There is no public/static
    media mount.
    """
    clip = _get_ready_clip(db, current_user.id, clip_id)

    assert clip.video_file_path is not None  # guaranteed by _get_ready_clip
    storage = get_media_storage()
    absolute_path = storage.get_path(clip.video_file_path)
    if not os.path.isfile(absolute_path):
        raise NotFoundError("Clip file")

    filename = f"{clip.title or 'clip'}.mp4"
    return FileResponse(absolute_path, media_type="video/mp4", filename=filename)


@router.get("/{clip_id}/thumbnail")
async def download_clip_thumbnail(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Stream a ready clip's thumbnail image.

    Authenticated and ownership-checked, same as `download_clip` -- the
    frontend fetches this (and the video) via the API client (which attaches
    the bearer token) and renders it as a blob URL, since `<img>`/`<video>`
    tags cannot send an Authorization header directly.
    """
    clip = _get_ready_clip(db, current_user.id, clip_id)
    if not clip.thumbnail_path:
        raise NotFoundError("Clip thumbnail")

    storage = get_media_storage()
    absolute_path = storage.get_path(clip.thumbnail_path)
    if not os.path.isfile(absolute_path):
        raise NotFoundError("Clip thumbnail file")

    return FileResponse(absolute_path, media_type="image/jpeg")


@router.post("/{clip_id}/publish", response_model=ScheduledPostResponse)
async def publish_clip(
    clip_id: int,
    payload: PublishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Publish (or schedule) a clip to a connected platform."""
    return publish_service.publish_clip(
        db,
        user_id=current_user.id,
        clip_id=clip_id,
        platform=payload.platform,
        scheduled_at=payload.scheduled_at,
    )
