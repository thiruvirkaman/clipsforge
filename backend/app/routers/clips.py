"""API routes for clip listing, retrieval, deletion, and regeneration.

Routes live under both `/projects/{project_id}/clips` and `/clips/{id}`, so
no shared router prefix is used -- paths are declared explicitly.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.clip import Clip
from app.models.user import User
from app.schemas.clip import ClipResponse
from app.services import clip_service

router = APIRouter(tags=["clips"])


class ClipRegenerateRequest(BaseModel):
    """Optional overrides applied before re-enqueuing a clip's render."""

    start_time: float | None = None
    end_time: float | None = None
    caption_style: str | None = None


@router.get("/projects/{project_id}/clips", response_model=list[ClipResponse])
async def list_project_clips(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Clip]:
    """List all clips generated for a project."""
    return clip_service.list_clips(db, current_user.id, project_id)


@router.get("/clips/{id}", response_model=ClipResponse)
async def get_clip(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ClipResponse:
    """Fetch a single clip's details."""
    return clip_service.get_clip(db, current_user.id, id)


@router.post("/clips/{id}/regenerate", response_model=ClipResponse)
async def regenerate_clip(
    id: int,
    payload: ClipRegenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ClipResponse:
    """Re-render a clip, optionally adjusting its window or caption style."""
    return clip_service.regenerate_clip(
        db,
        current_user.id,
        id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        caption_style=payload.caption_style,
    )


@router.delete("/clips/{id}", status_code=204)
async def delete_clip(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a clip."""
    clip_service.delete_clip(db, current_user.id, id)
