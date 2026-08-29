"""YouTube video ingestion for ClipForge's URL-based projects.

Deliberately narrow: only recognized youtube.com/youtu.be video URLs are
accepted (never an arbitrary-site downloader). `noplaylist` is always forced
so a playlist-attached URL still only ever downloads the single referenced
video, and playlist/live/unavailable/private URLs are translated into a
clean `ValidationError` rather than propagating a raw yt-dlp exception.
"""
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import yt_dlp

from app.config import settings
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)

_ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}

#: A real YouTube video id is always exactly 11 URL-safe base64-ish
#: characters. Requiring this shape (rather than just "path is non-empty")
#: is what actually rejects non-video URLs like channel/@handle links.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

#: Path prefixes that are never a single video, however non-empty the path
#: looks (channel pages, playlists, user/community pages).
_NON_VIDEO_PATH_PREFIXES = ("/@", "/channel/", "/c/", "/user/", "/playlist")

#: MVP sanity bound -- reject implausibly long source videos rather than
#: letting a multi-hour download/transcription run unbounded.
MAX_SOURCE_DURATION_SECONDS = 3 * 60 * 60  # 3 hours


@dataclass
class DownloadedVideo:
    file_path: str
    filename: str
    duration_seconds: int
    title: str


def _extract_video_id_segment(path: str, prefix: str) -> str:
    return path[len(prefix):].split("/")[0]


def is_supported_youtube_url(url: str) -> bool:
    """Return whether `url` looks like a single-video youtube.com/youtu.be URL.

    Requires a syntactically valid 11-character video id in the expected
    position (watch `v=`, `/shorts/<id>`, `/embed/<id>`, `/v/<id>`, or a
    youtu.be short link) -- not just "the path is non-empty", which would
    also accept channel/@handle/playlist/user URLs that were never a single
    video to begin with.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        return False

    path = parsed.path
    if any(path.startswith(prefix) for prefix in _NON_VIDEO_PATH_PREFIXES):
        return False

    if host == "youtu.be":
        return bool(_VIDEO_ID_RE.match(path.strip("/")))

    if path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        return bool(_VIDEO_ID_RE.match(video_id))
    for prefix in ("/shorts/", "/embed/", "/v/"):
        if path.startswith(prefix):
            return bool(_VIDEO_ID_RE.match(_extract_video_id_segment(path, prefix)))

    return False


def download_youtube_video(url: str) -> DownloadedVideo:
    """Download `url` (a supported YouTube video URL) into a fresh temp
    directory and return its local path, duration, and title.

    Raises `ValidationError` for anything that should surface as a clean,
    user-facing failure: unsupported URL shape, playlist, live stream,
    private/unavailable/removed video, or any other yt-dlp download error.
    """
    if not is_supported_youtube_url(url):
        raise ValidationError(
            "Only single-video YouTube URLs (youtube.com or youtu.be) are supported."
        )

    tmp_dir = tempfile.mkdtemp(prefix="clipforge_yt_")
    try:
        return _download_into(url, tmp_dir)
    except Exception:
        # Any failure below (validation, yt-dlp error, etc.) must not leak
        # this temp directory -- the success path leaves it for the caller
        # to clean up after moving the file out (see project_service /
        # pipeline's `_ingest_youtube_source`), but a failure path here
        # would otherwise never reach that cleanup at all.
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def _download_into(url: str, tmp_dir: str) -> DownloadedVideo:
    output_template = os.path.join(tmp_dir, "%(id)s.%(ext)s")
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "retries": 2,
    }
    # Some hosting providers' IP ranges trigger YouTube's anti-bot challenge
    # ("Sign in to confirm you're not a bot"), which no amount of player
    # client spoofing resolves -- only an authenticated session (via
    # cookies) does. Optional: most environments don't need this at all.
    if settings.YOUTUBE_COOKIES_PATH:
        ydl_opts["cookiefile"] = settings.YOUTUBE_COOKIES_PATH

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info and info.get("_type") not in (None, "video"):
                # Extractor resolved to something other than a single video
                # (e.g. a playlist entry list) despite noplaylist.
                raise ValidationError("This URL does not point to a single video.")
            downloaded_path = ydl.prepare_filename(info) if info else None
    except yt_dlp.utils.DownloadError as exc:
        logger.info("YouTube download failed for %s: %s", url, exc)
        raise ValidationError(
            "This YouTube video could not be downloaded -- it may be private, "
            "unavailable, region-restricted, or removed."
        ) from exc

    if info is None:
        raise ValidationError("Could not read metadata for this YouTube video.")
    if info.get("entries"):
        raise ValidationError("Playlist URLs are not supported; provide a single video URL.")
    if info.get("is_live") or info.get("live_status") == "is_live":
        raise ValidationError("Live streams are not supported.")

    duration = info.get("duration")
    if not duration or duration <= 0:
        raise ValidationError("Could not determine this video's duration.")
    if duration > MAX_SOURCE_DURATION_SECONDS:
        raise ValidationError(
            f"Video exceeds the maximum supported duration of "
            f"{MAX_SOURCE_DURATION_SECONDS // 60} minutes."
        )

    if not downloaded_path or not os.path.exists(downloaded_path):
        # merge_output_format can change the final extension; fall back to
        # scanning the temp dir for what actually landed there.
        candidates = os.listdir(tmp_dir) if os.path.isdir(tmp_dir) else []
        if len(candidates) == 1:
            downloaded_path = os.path.join(tmp_dir, candidates[0])
        else:
            raise ValidationError("Downloaded file could not be located after download.")

    logger.info("Downloaded YouTube video %s to %s", url, downloaded_path)
    return DownloadedVideo(
        file_path=downloaded_path,
        filename=os.path.basename(downloaded_path),
        duration_seconds=int(duration),
        title=str(info.get("title") or "YouTube video"),
    )
