"""Shared helpers for deleting a project's/clip's on-disk media files.

Every `video_file_path`/`thumbnail_path`/`source_file_path` in this schema is
a freshly generated UUID filename created for exactly one record (see
`LocalMediaStorage.save_stream`/`save_file`), so in practice nothing is ever
shared between rows -- but callers here still verify no *other* row
references the same stored path before deleting it, as cheap defense in
depth against ever deleting a file another record still needs.
"""
import logging
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.storage import get_media_storage

if TYPE_CHECKING:
    from app.models.clip import Clip
    from app.models.project import Project

logger = logging.getLogger(__name__)


def delete_clip_media(db: Session, clip: "Clip") -> None:
    """Delete a clip's rendered video and thumbnail from storage, unless
    another clip row still references the same stored path."""
    from app.models.clip import Clip as ClipModel

    storage = get_media_storage()
    for attr in ("video_file_path", "thumbnail_path"):
        stored_path = getattr(clip, attr)
        if not stored_path:
            continue
        still_referenced = (
            db.query(ClipModel)
            .filter(ClipModel.id != clip.id, getattr(ClipModel, attr) == stored_path)
            .first()
            is not None
        )
        if still_referenced:
            logger.warning(
                "Skipping delete of %s=%s for clip %s: still referenced by another clip",
                attr,
                stored_path,
                clip.id,
            )
            continue
        storage.delete(stored_path)


def delete_project_media(db: Session, project: "Project") -> None:
    """Delete a project's source file (and, via cascade, its clips' files --
    callers should delete clip media first if clips are still attached)."""
    from app.models.project import Project as ProjectModel

    if not project.source_file_path:
        return
    storage = get_media_storage()
    still_referenced = (
        db.query(ProjectModel)
        .filter(
            ProjectModel.id != project.id,
            ProjectModel.source_file_path == project.source_file_path,
        )
        .first()
        is not None
    )
    if still_referenced:
        logger.warning(
            "Skipping delete of source_file_path=%s for project %s: still referenced",
            project.source_file_path,
            project.id,
        )
        return
    storage.delete(project.source_file_path)
