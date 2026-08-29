"""ffmpeg-based clip rendering for ClipForge.

Trims a clip window from the source media, crops/pads it to 9:16, burns in
captions (via a generated .srt + ffmpeg's `subtitles` filter), and generates
a thumbnail. Shells out to the `ffmpeg` binary via `subprocess` -- this is a
best-effort wrapper (no hardware acceleration tuning, retries, etc.), not a
production-hardened media pipeline.
"""
import logging
import os
import subprocess
import tempfile

from app.services.asr_service import TranscriptSegment

logger = logging.getLogger(__name__)

#: Target 9:16 vertical output resolution.
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920

#: Supported caption styles -> ffmpeg `subtitles` filter `force_style` value.
#: The keys here are the single source of truth for which `caption_style`
#: values are accepted anywhere in the app (see `clip_service.regenerate_clip`).
CAPTION_STYLES: dict[str, str] = {
    "default": "FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
    "BorderStyle=1,Outline=2",
    "bold": "FontSize=26,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
    "BorderStyle=1,Outline=3",
    "minimal": "FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
    "BorderStyle=0,Outline=1",
}
DEFAULT_CAPTION_STYLE = "default"


class RenderError(RuntimeError):
    """Raised when an ffmpeg render step exits with a non-zero status."""


def thumbnail_path_for(output_path: str) -> str:
    """Return the thumbnail path derived from a rendered clip's output path
    (same base name, `.jpg` extension)."""
    base, _ = os.path.splitext(output_path)
    return f"{base}.jpg"


def _format_srt_timestamp(seconds: float) -> str:
    seconds = max(seconds, 0.0)
    total_ms = round(seconds * 1000)
    hours, rem_ms = divmod(total_ms, 3_600_000)
    minutes, rem_ms = divmod(rem_ms, 60_000)
    secs, ms = divmod(rem_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _write_srt(caption_segments: list[TranscriptSegment], clip_start: float, srt_path: str) -> None:
    """Write an SRT file for `caption_segments`, with timestamps rebased to
    be relative to `clip_start` (the trimmed clip's own timeline, since the
    output video starts at t=0)."""
    lines: list[str] = []
    index = 1
    for seg in caption_segments:
        rel_start = seg.start - clip_start
        rel_end = seg.end - clip_start
        if rel_end <= 0:
            continue
        rel_start = max(rel_start, 0.0)
        text = seg.text.strip()
        if not text:
            continue
        lines.append(str(index))
        lines.append(f"{_format_srt_timestamp(rel_start)} --> {_format_srt_timestamp(rel_end)}")
        lines.append(text)
        lines.append("")
        index += 1

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _run_ffmpeg(command: list[str], step_name: str) -> None:
    logger.info("Running ffmpeg (%s): %s", step_name, " ".join(command))
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        logger.error("ffmpeg binary not found while running step '%s'", step_name)
        raise RenderError(f"ffmpeg is not installed or not on PATH ({exc})") from exc

    if result.returncode != 0:
        logger.error(
            "ffmpeg step '%s' failed (exit %d): %s",
            step_name,
            result.returncode,
            result.stderr,
        )
        raise RenderError(
            f"ffmpeg step '{step_name}' failed with exit code {result.returncode}: {result.stderr}"
        )
    logger.info("ffmpeg step '%s' completed successfully", step_name)


def render_clip_video(
    source_media_path: str,
    start_time: float,
    end_time: float,
    output_path: str,
    caption_segments: list[TranscriptSegment],
    caption_style: str = DEFAULT_CAPTION_STYLE,
) -> None:
    """Trim `[start_time, end_time]` from `source_media_path`, crop/pad to
    9:16, burn in per-segment captions from `caption_segments` (each with its
    own timing, so captions stay in sync sentence-by-sentence rather than one
    caption spanning the whole clip), and write the result to `output_path`.
    Also generates a thumbnail JPEG at `thumbnail_path_for(output_path)`.

    Raises `RenderError` if any ffmpeg step exits non-zero, or if
    `caption_style` is not a key in `CAPTION_STYLES`.
    """
    duration = end_time - start_time
    if duration <= 0:
        raise RenderError(f"Invalid clip window: start_time={start_time} end_time={end_time}")

    force_style = CAPTION_STYLES.get(caption_style)
    if force_style is None:
        raise RenderError(
            f"Unknown caption_style {caption_style!r}; must be one of {sorted(CAPTION_STYLES)}"
        )

    output_dir = os.path.dirname(output_path) or "."
    os.makedirs(output_dir, exist_ok=True)

    srt_fd, srt_path = tempfile.mkstemp(suffix=".srt")
    os.close(srt_fd)
    try:
        _write_srt(caption_segments, clip_start=start_time, srt_path=srt_path)

        # ffmpeg's subtitles filter treats ':' and '\' specially in its
        # argument syntax, so escape the path (matters especially on Windows).
        escaped_srt_path = srt_path.replace("\\", "/").replace(":", "\\:")
        video_filter = (
            f"crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',"
            f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
            f"subtitles='{escaped_srt_path}':force_style='{force_style}'"
        )

        command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_time),
            "-i",
            source_media_path,
            "-t",
            str(duration),
            "-vf",
            video_filter,
            "-c:v",
            "libx264",
            # No preset previously meant libx264's default "medium" -- the
            # slowest setting still called "safe" by ffmpeg's own docs, and
            # tuned for archival compression rather than short social clips
            # that get re-compressed by every platform's own upload pipeline
            # anyway. "veryfast" cuts encode time substantially for a
            # quality difference that isn't visible at this output size.
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            output_path,
        ]
        _run_ffmpeg(command, step_name="trim+crop+captions")
    finally:
        if os.path.exists(srt_path):
            os.remove(srt_path)

    _generate_thumbnail(output_path, duration)


def _generate_thumbnail(output_path: str, clip_duration: float) -> None:
    thumbnail_path = thumbnail_path_for(output_path)
    midpoint = max(clip_duration / 2.0, 0.0)
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(midpoint),
        "-i",
        output_path,
        "-frames:v",
        "1",
        thumbnail_path,
    ]
    _run_ffmpeg(command, step_name="thumbnail")
