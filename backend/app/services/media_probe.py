"""ffprobe-based media validation for ClipForge.

Used to confirm an uploaded file is actually a playable video (not just an
allowed extension) and to read its real duration, rather than trusting the
client-supplied filename/extension alone.
"""
import json
import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class MediaProbeError(RuntimeError):
    """Raised when a file cannot be probed or contains no usable video stream."""


@dataclass
class MediaProbeResult:
    duration_seconds: float
    has_video_stream: bool


def probe_media(path: str) -> MediaProbeResult:
    """Run ffprobe against `path` and return its duration and whether it has
    a video stream. Raises `MediaProbeError` if ffprobe fails, times out, or
    the file has no video stream (e.g. it's an audio file, corrupt, or not
    actually media despite its extension)."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=60
        )
    except FileNotFoundError as exc:
        raise MediaProbeError(f"ffprobe is not installed or not on PATH ({exc})") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaProbeError("ffprobe timed out while inspecting the file") from exc

    if result.returncode != 0:
        raise MediaProbeError(f"ffprobe could not read this file: {result.stderr.strip()}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProbeError("ffprobe returned unparseable output") from exc

    streams = data.get("streams", [])
    has_video_stream = any(s.get("codec_type") == "video" for s in streams)
    if not has_video_stream:
        raise MediaProbeError("File has no video stream")

    duration_raw = data.get("format", {}).get("duration")
    try:
        duration_seconds = float(duration_raw)
    except (TypeError, ValueError) as exc:
        raise MediaProbeError("Could not determine media duration") from exc

    if duration_seconds <= 0:
        raise MediaProbeError("Media duration must be positive")

    return MediaProbeResult(duration_seconds=duration_seconds, has_video_stream=True)
