"""Endpoints for connecting publishing platforms and viewing scheduled posts."""
import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.publish import PublishConnectionResponse, ScheduledPostResponse
from app.services import publish_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/publish", tags=["publish"])


@router.post("/connections/{platform}")
async def connect_platform(
    platform: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Start the OAuth connect flow for a platform, returning an authorization URL."""
    authorize_url = publish_service.start_oauth_connect(platform)
    return {"authorize_url": authorize_url}


@router.get("/connections", response_model=list[PublishConnectionResponse])
async def list_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """List all platform connections for the current user."""
    return publish_service.list_connections(db, current_user.id)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove a platform connection for the current user."""
    publish_service.delete_connection(db, current_user.id, connection_id)


@router.get("/posts", response_model=list[ScheduledPostResponse])
async def list_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """List all scheduled/published posts for the current user."""
    return publish_service.list_posts(db, current_user.id)
