"""Tests for WhisperAPITranscriptionService's audio extraction and chunking.

OpenAI's Whisper API rejects any request over 25MB (413), so a real video
must never be sent whole -- audio is always extracted first, and split into
multiple requests if still too large. ffmpeg/ffprobe subprocess calls and
the ASR HTTP call are mocked throughout; no real binaries or network calls.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.services.asr_service import WhisperAPITranscriptionService


def _fake_ffmpeg_creates_output(command, **kwargs):
    """Mimic ffmpeg by writing a (fake) file at its output path argument."""
    output_path = command[-1]
    with open(output_path, "wb") as f:
        f.write(b"fake-audio-bytes")
    return MagicMock(returncode=0, stderr="")


def _fake_whisper_response(text: str, segments: list[dict]) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"text": text, "segments": segments}
    return response


@pytest.fixture()
def service() -> WhisperAPITranscriptionService:
    return WhisperAPITranscriptionService(
        base_url="https://api.openai.com", api_key="fake-key", model="whisper-1"
    )


def test_transcribe_requires_api_key():
    service = WhisperAPITranscriptionService(api_key="")
    with pytest.raises(RuntimeError, match="ASR_SERVICE_API_KEY"):
        service.transcribe("video.mp4")


def test_transcribe_small_audio_sends_a_single_request(service, tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake video bytes")

    whisper_response = _fake_whisper_response(
        "Hello world.",
        [{"start": 0.0, "end": 1.5, "text": "Hello world."}],
    )

    with (
        patch(
            "app.services.asr_service.subprocess.run",
            side_effect=_fake_ffmpeg_creates_output,
        ) as mock_run,
        patch("app.services.asr_service.httpx.post", return_value=whisper_response) as mock_post,
    ):
        result = service.transcribe(str(source))

    assert mock_run.call_count == 1  # only the audio-extraction step
    assert mock_post.call_count == 1
    assert result.full_text == "Hello world."
    assert len(result.segments) == 1
    assert result.segments[0].start == 0.0
    assert result.segments[0].end == 1.5

    # Extracted audio is mono/16kHz/mp3, not the raw video.
    extract_command = mock_run.call_args_list[0].args[0]
    assert "-vn" in extract_command
    assert "-ac" in extract_command


def test_transcribe_large_audio_splits_into_multiple_requests_with_offsets(service, tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake video bytes")

    call_log = {"post_count": 0}

    def fake_post(url, **kwargs):
        call_log["post_count"] += 1
        if call_log["post_count"] == 1:
            return _fake_whisper_response(
                "First half.", [{"start": 0.0, "end": 2.0, "text": "First half."}]
            )
        return _fake_whisper_response(
            "Second half.", [{"start": 0.0, "end": 2.0, "text": "Second half."}]
        )

    # Force the "audio too large, must chunk" branch regardless of the tiny
    # fake file the mocked ffmpeg call actually writes.
    with (
        patch(
            "app.services.asr_service.subprocess.run",
            side_effect=_fake_ffmpeg_creates_output,
        ) as mock_run,
        patch("app.services.asr_service.os.path.getsize", return_value=50 * 1024 * 1024),
        patch.object(
            WhisperAPITranscriptionService, "_probe_audio_duration", return_value=200.0
        ),
        patch("app.services.asr_service.httpx.post", side_effect=fake_post) as mock_post,
    ):
        result = service.transcribe(str(source))

    # 50MB / 20MB target => 3 chunks.
    assert mock_post.call_count == 3
    # 1 extraction + 3 chunk-split ffmpeg invocations.
    assert mock_run.call_count == 4

    # Each chunk's segments are offset by that chunk's start time, not all
    # starting back at 0 -- this is what keeps captions in sync after
    # merging chunk transcripts back together.
    starts = sorted(seg.start for seg in result.segments)
    assert starts[0] == pytest.approx(0.0)
    assert starts[1] > starts[0]
    assert starts[2] > starts[1]
    assert "First half." in result.full_text


def test_extract_audio_raises_clear_error_on_ffmpeg_failure(service, tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake video bytes")

    failing_result = MagicMock(returncode=1, stderr="ffmpeg: invalid data")
    with patch("app.services.asr_service.subprocess.run", return_value=failing_result):
        with pytest.raises(RuntimeError, match="Failed to extract audio"):
            service.transcribe(str(source))


def test_chunk_split_failure_raises_clear_error(service, tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake video bytes")

    call_count = {"n": 0}

    def run_side_effect(command, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # extraction succeeds
            return _fake_ffmpeg_creates_output(command, **kwargs)
        # chunk split fails
        return MagicMock(returncode=1, stderr="ffmpeg: split failed")

    with (
        patch("app.services.asr_service.subprocess.run", side_effect=run_side_effect),
        patch("app.services.asr_service.os.path.getsize", return_value=50 * 1024 * 1024),
        patch.object(
            WhisperAPITranscriptionService, "_probe_audio_duration", return_value=200.0
        ),
    ):
        with pytest.raises(RuntimeError, match="Failed to split audio chunk"):
            service.transcribe(str(source))
