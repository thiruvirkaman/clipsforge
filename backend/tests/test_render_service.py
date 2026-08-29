"""Tests for the ffmpeg-based render pipeline in app.services.render_service.

ffmpeg itself is never actually invoked -- `subprocess.run` is mocked so
these tests run without the binary installed and stay fast/deterministic.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.services.asr_service import TranscriptSegment
from app.services.render_service import (
    RenderError,
    _format_srt_timestamp,
    _write_srt,
    render_clip_video,
    thumbnail_path_for,
)


def test_thumbnail_path_for_swaps_extension():
    assert thumbnail_path_for("/media/clip_1.mp4") == "/media/clip_1.jpg"
    assert thumbnail_path_for("/media/clip_1") == "/media/clip_1.jpg"


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "00:00:00,000"),
        (1.5, "00:00:01,500"),
        (61, "00:01:01,000"),
        (3661.25, "01:01:01,250"),
        (-5, "00:00:00,000"),
    ],
)
def test_format_srt_timestamp(seconds, expected):
    assert _format_srt_timestamp(seconds) == expected


def test_write_srt_rebases_timestamps_to_clip_start(tmp_path):
    segments = [
        TranscriptSegment(start=10.0, end=12.0, text="Hello"),
        TranscriptSegment(start=12.0, end=14.0, text="World"),
        TranscriptSegment(start=8.0, end=9.0, text="Before the clip, dropped"),
    ]
    srt_path = str(tmp_path / "out.srt")
    _write_srt(segments, clip_start=10.0, srt_path=srt_path)

    content = (tmp_path / "out.srt").read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:02,000" in content
    assert "Hello" in content
    assert "00:00:02,000 --> 00:00:04,000" in content
    assert "World" in content
    # The segment ending before the clip start (rel_end <= 0) is dropped.
    assert "Before the clip, dropped" not in content


def test_write_srt_skips_blank_text_segments(tmp_path):
    segments = [TranscriptSegment(start=0.0, end=1.0, text="   ")]
    srt_path = str(tmp_path / "out.srt")
    _write_srt(segments, clip_start=0.0, srt_path=srt_path)
    assert (tmp_path / "out.srt").read_text(encoding="utf-8") == ""


def test_render_clip_video_rejects_non_positive_duration(tmp_path):
    with pytest.raises(RenderError, match="Invalid clip window"):
        render_clip_video(
            source_media_path="source.mp4",
            start_time=10.0,
            end_time=10.0,
            output_path=str(tmp_path / "out.mp4"),
            caption_segments=[],
        )


def test_render_clip_video_success_runs_ffmpeg_twice(tmp_path):
    output_path = str(tmp_path / "out.mp4")
    ok_result = MagicMock(returncode=0, stderr="")

    with patch("app.services.render_service.subprocess.run", return_value=ok_result) as mock_run:
        render_clip_video(
            source_media_path="source.mp4",
            start_time=5.0,
            end_time=15.0,
            output_path=output_path,
            caption_segments=[TranscriptSegment(start=5.0, end=8.0, text="hi")],
        )

    assert mock_run.call_count == 2  # trim+crop+captions, then thumbnail
    trim_call, thumb_call = mock_run.call_args_list
    trim_command = trim_call.args[0]
    assert trim_command[0] == "ffmpeg"
    assert output_path in trim_command
    thumb_command = thumb_call.args[0]
    assert thumbnail_path_for(output_path) in thumb_command


def test_render_clip_video_raises_on_ffmpeg_nonzero_exit(tmp_path):
    failing_result = MagicMock(returncode=1, stderr="boom")
    with patch("app.services.render_service.subprocess.run", return_value=failing_result):
        with pytest.raises(RenderError, match="exit code 1"):
            render_clip_video(
                source_media_path="source.mp4",
                start_time=0.0,
                end_time=5.0,
                output_path=str(tmp_path / "out.mp4"),
                caption_segments=[],
            )


def test_render_clip_video_raises_when_ffmpeg_binary_missing(tmp_path):
    with patch(
        "app.services.render_service.subprocess.run", side_effect=FileNotFoundError("no ffmpeg")
    ):
        with pytest.raises(RenderError, match="not installed"):
            render_clip_video(
                source_media_path="source.mp4",
                start_time=0.0,
                end_time=5.0,
                output_path=str(tmp_path / "out.mp4"),
                caption_segments=[],
            )
