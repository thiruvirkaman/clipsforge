"""Business logic for the export & publish module: platform connections and
publishing clips.

MVP SCOPE: connecting a platform account and actually publishing a clip are
both **disabled** (raise `FeatureNotImplementedError`) rather than wired to
stub implementations that fabricate a fake success URL -- real platform API
integrations (TikTok Content Posting API, Instagram Graph API, YouTube Data
API) are explicitly out of scope for this pass, and this module must never
claim to have published something it didn't. Listing/deleting connections
still works (harmlessly returns real, empty data) since nothing can ever be
connected. The `PlatformPublisher` protocol and per-platform classes below
are kept as the intended integration seam for a future pass -- swap
`get_publisher`'s callers back to using them once real OAuth credentials and
publishing API access exist.
"""
import logging
from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.exceptions import FeatureNotImplementedError, NotFoundError
from app.models.clip import Clip
from app.models.publish_connection import Platform, PublishConnection
from app.models.scheduled_post import ScheduledPost

logger = logging.getLogger(__name__)


class PlatformPublisher(Protocol):
    """Interface every platform integration must implement."""

    def publish(self, clip: Clip, connection: PublishConnection) -> str:
        """Publish `clip` using the credentials in `connection`, returning the published URL."""
        ...


class TikTokPublisher:
    """Stub TikTok publisher. # TODO: real platform API integration"""

    def publish(self, clip: Clip, connection: PublishConnection) -> str:
        # TODO: real platform API integration (TikTok Content Posting API)
        logger.info(
            "Stub-publishing clip id=%s to TikTok for connection id=%s",
            clip.id,
            connection.id,
        )
        return f"https://tiktok.com/@{connection.account_handle or 'user'}/video/{clip.id}"


class InstagramPublisher:
    """Stub Instagram publisher. # TODO: real platform API integration"""

    def publish(self, clip: Clip, connection: PublishConnection) -> str:
        # TODO: real platform API integration (Instagram Graph API)
        logger.info(
            "Stub-publishing clip id=%s to Instagram for connection id=%s",
            clip.id,
            connection.id,
        )
        return f"https://instagram.com/reel/stub-{clip.id}"


class YouTubeShortsPublisher:
    """Stub YouTube Shorts publisher. # TODO: real platform API integration"""

    def publish(self, clip: Clip, connection: PublishConnection) -> str:
        # TODO: real platform API integration (YouTube Data API v3)
        logger.info(
            "Stub-publishing clip id=%s to YouTube Shorts for connection id=%s",
            clip.id,
            connection.id,
        )
        return f"https://youtube.com/shorts/stub-{clip.id}"


_PUBLISHERS: dict[str, PlatformPublisher] = {
    Platform.tiktok.value: TikTokPublisher(),
    Platform.instagram.value: InstagramPublisher(),
    Platform.youtube_shorts.value: YouTubeShortsPublisher(),
}

_VALID_PLATFORMS = {p.value for p in Platform}


def get_publisher(platform: str) -> PlatformPublisher:
    """Return the `PlatformPublisher` implementation for `platform`.

    Not currently called by any route (see `publish_clip`) -- kept as the
    integration seam a future pass wires back in once real platform API
    access exists.

    Raises:
        NotFoundError: If `platform` is not a recognized platform.
    """
    publisher = _PUBLISHERS.get(platform)
    if publisher is None:
        raise NotFoundError("Platform")
    return publisher


def start_oauth_connect(platform: str) -> str:
    """Disabled for this MVP pass: connecting a platform account is not a
    real, working feature (no OAuth app credentials exist yet), so this
    never returns a URL that would make a user think they successfully
    connected something.

    Raises:
        NotFoundError: If `platform` is not a recognized platform at all.
        FeatureNotImplementedError: Always, for any recognized platform.
    """
    if platform not in _VALID_PLATFORMS:
        raise NotFoundError("Platform")
    raise FeatureNotImplementedError(
        f"Connecting a {platform} account is not available yet."
    )


def list_connections(db: Session, user_id: int) -> list[PublishConnection]:
    """List all platform connections for a user."""
    return (
        db.query(PublishConnection)
        .filter(PublishConnection.user_id == user_id)
        .all()
    )


def delete_connection(db: Session, user_id: int, connection_id: int) -> None:
    """Remove a user's platform connection.

    Raises:
        NotFoundError: If no such connection exists for this user.
    """
    connection = (
        db.query(PublishConnection)
        .filter(
            PublishConnection.id == connection_id,
            PublishConnection.user_id == user_id,
        )
        .first()
    )
    if connection is None:
        raise NotFoundError("PublishConnection")

    db.delete(connection)
    db.commit()


def publish_clip(
    db: Session,
    user_id: int,
    clip_id: int,
    platform: str,
    scheduled_at: datetime | None = None,
) -> ScheduledPost:
    """Disabled for this MVP pass, for both immediate and scheduled
    publishing: no `ScheduledPost` row is ever created, so nothing in the UI
    or API can be mistaken for a real, working publish.

    # TODO: once real platform API integrations exist, restore clip/
    # connection lookup, create a ScheduledPost, and either invoke
    # `get_publisher(platform).publish(...)` immediately or (for a future
    # Celery-beat-driven scheduler) leave it `scheduled`.

    Raises:
        NotFoundError: If `platform` is not a recognized platform.
        FeatureNotImplementedError: Always, for any recognized platform.
    """
    if platform not in _VALID_PLATFORMS:
        raise NotFoundError("Platform")
    raise FeatureNotImplementedError(f"Publishing to {platform} is not available yet.")


def list_posts(db: Session, user_id: int) -> list[ScheduledPost]:
    """List all scheduled/published posts for a user."""
    return db.query(ScheduledPost).filter(ScheduledPost.user_id == user_id).all()
