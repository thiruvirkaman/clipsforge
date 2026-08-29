"""Media storage abstraction for ClipForge.

Provides a small interface (`MediaStorage`) that other modules (uploads,
YouTube downloads, ffmpeg renders, etc.) use to persist, resolve, and delete
files, decoupled from the underlying backend. Only a local-filesystem
implementation is provided for now; cloud backends can be added later
behind the same interface, selected via `settings.MEDIA_STORAGE_BACKEND`.
"""
import logging
import os
import shutil
import uuid
from abc import ABC, abstractmethod
from typing import BinaryIO

from app.config import settings

logger = logging.getLogger(__name__)


class UploadTooLargeError(RuntimeError):
    """Raised by `save_stream` when the source exceeds `max_bytes`."""


class MediaStorage(ABC):
    """Abstract interface for storing, resolving, and deleting media files."""

    @abstractmethod
    def save_stream(self, file_obj: BinaryIO, filename: str, max_bytes: int) -> str:
        """Copy `file_obj` in bounded chunks and return a stored path/key.

        Raises `UploadTooLargeError` (without buffering the whole source in
        memory) if more than `max_bytes` are read.
        """
        raise NotImplementedError

    @abstractmethod
    def save_file(self, local_path: str, filename: str) -> str:
        """Move an existing local file (e.g. a yt-dlp download) into storage
        and return a stored path/key identifying it."""
        raise NotImplementedError

    @abstractmethod
    def get_path(self, stored_path: str) -> str:
        """Resolve a stored path/key to an absolute filesystem path (or URL)."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, stored_path: str) -> None:
        """Delete a previously stored file. Never raises if it's already gone."""
        raise NotImplementedError


class LocalMediaStorage(MediaStorage):
    """Stores media files on the local filesystem under MEDIA_STORAGE_PATH."""

    def __init__(self, base_path: str | None = None) -> None:
        self.base_path = os.path.abspath(base_path or settings.MEDIA_STORAGE_PATH)
        os.makedirs(self.base_path, exist_ok=True)

    def _new_stored_name(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1]
        return f"{uuid.uuid4().hex}{ext}"

    def save_stream(self, file_obj: BinaryIO, filename: str, max_bytes: int) -> str:
        stored_name = self._new_stored_name(filename)
        full_path = os.path.join(self.base_path, stored_name)

        chunk_size = 1024 * 1024  # 1 MiB
        total_written = 0
        try:
            with open(full_path, "wb") as out:
                while True:
                    chunk = file_obj.read(chunk_size)
                    if not chunk:
                        break
                    total_written += len(chunk)
                    if total_written > max_bytes:
                        raise UploadTooLargeError(
                            f"Upload exceeds the maximum allowed size of {max_bytes} bytes"
                        )
                    out.write(chunk)
        except UploadTooLargeError:
            self._safe_remove(full_path)
            raise
        except Exception:
            self._safe_remove(full_path)
            raise

        logger.info("Streamed %d bytes to %s", total_written, full_path)
        return stored_name

    def save_file(self, local_path: str, filename: str) -> str:
        stored_name = self._new_stored_name(filename)
        full_path = os.path.join(self.base_path, stored_name)
        shutil.move(local_path, full_path)
        logger.info("Moved %s to %s", local_path, full_path)
        return stored_name

    def get_path(self, stored_path: str) -> str:
        """Return the absolute filesystem path for a previously stored file.

        `stored_path` is always a bare filename we generated ourselves
        (never derived from user input), but this still resolves and
        verifies the result stays within `base_path` as defense in depth
        against path traversal.
        """
        candidate = os.path.abspath(os.path.join(self.base_path, stored_path))
        if os.path.commonpath([candidate, self.base_path]) != self.base_path:
            raise ValueError(f"Refusing to resolve path outside media storage: {stored_path!r}")
        return candidate

    def delete(self, stored_path: str) -> None:
        if not stored_path:
            return
        try:
            full_path = self.get_path(stored_path)
        except ValueError:
            logger.warning("Refusing to delete suspicious stored path: %s", stored_path)
            return
        self._safe_remove(full_path)

    @staticmethod
    def _safe_remove(path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError:
            logger.exception("Failed to remove media file %s", path)


def get_media_storage() -> MediaStorage:
    """Return the configured MediaStorage implementation."""
    if settings.MEDIA_STORAGE_BACKEND == "local":
        return LocalMediaStorage()
    raise NotImplementedError(
        f"Media storage backend '{settings.MEDIA_STORAGE_BACKEND}' is not implemented yet"
    )
