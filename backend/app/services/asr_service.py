"""ASR (speech-to-text) service abstraction for ClipForge's transcription step.

Defines a small, pluggable `TranscriptionService` interface so the concrete
provider (Whisper API, a self-hosted model, etc.) can be swapped without
touching the pipeline code that consumes it.
"""
import logging
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# OpenAI's Whisper API rejects any request body over 25 MB with a 413. Chunk
# well under that (real-world encoding sizes aren't perfectly predictable).
_CHUNK_TARGET_BYTES = 20 * 1024 * 1024

# Whisper resamples everything to 16kHz mono internally anyway, so
# extracting audio-only at a modest bitrate loses no useful signal for
# speech while shrinking the upload dramatically vs. sending the whole
# video -- often enough on its own to dodge the limit without chunking at
# all. A 3-hour source (see youtube_service.MAX_SOURCE_DURATION_SECONDS) at
# this bitrate is ~40MB of audio, i.e. 2-3 chunks.
_AUDIO_SAMPLE_RATE_HZ = 16000
_AUDIO_BITRATE_KBPS = 32


@dataclass
class TranscriptSegment:
    """A single timestamped segment of a transcript.

    Timestamps (in seconds, relative to the source media) are required
    because highlight detection snaps clip start/end times to sentence
    boundaries derived from segment timing.
    """

    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    """Full transcription output for a piece of media."""

    full_text: str
    segments: list[TranscriptSegment] = field(default_factory=list)


class TranscriptionService(Protocol):
    """Pluggable interface for speech-to-text providers."""

    def transcribe(self, media_path: str) -> TranscriptResult:
        """Transcribe the media file at `media_path` and return the result."""
        ...


class WhisperAPITranscriptionService:
    """Calls OpenAI's real Whisper transcription API (or an OpenAI-compatible
    provider at a different `base_url`) to transcribe media.

    Always extracts audio-only first (smaller upload, and required to check
    against Whisper's 25MB per-request limit), then splits into multiple
    chunks -- each transcribed separately and merged with corrected
    timestamps -- if the extracted audio is still too large for one request.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = base_url if base_url is not None else settings.ASR_SERVICE_BASE_URL
        self.api_key = api_key if api_key is not None else settings.ASR_SERVICE_API_KEY
        self.model = model if model is not None else settings.ASR_MODEL

    def transcribe(self, media_path: str) -> TranscriptResult:
        # `base_url` has a real default (OpenAI's actual endpoint), so an
        # API key is the real signal of "is ASR configured" -- mirrors how
        # `get_highlight_service` gates on LLM_SERVICE_API_KEY, not a URL.
        if not self.api_key:
            raise RuntimeError("ASR_SERVICE_API_KEY is not configured")

        with tempfile.TemporaryDirectory(prefix="clipforge_asr_") as tmp_dir:
            audio_path = os.path.join(tmp_dir, "audio.mp3")
            self._extract_audio(media_path, audio_path)
            audio_size = os.path.getsize(audio_path)

            if audio_size <= _CHUNK_TARGET_BYTES:
                logger.info(
                    "Transcribing extracted audio via ASR API: %s (%.1f MB)",
                    media_path,
                    audio_size / (1024 * 1024),
                )
                result = self._transcribe_file(audio_path, offset=0.0)
            else:
                logger.info(
                    "Extracted audio for %s is %.1f MB, over the per-request limit; chunking",
                    media_path,
                    audio_size / (1024 * 1024),
                )
                result = self._transcribe_in_chunks(audio_path, audio_size, tmp_dir)

        logger.info(
            "Transcription complete for %s: %d segments", media_path, len(result.segments)
        )
        return result

    def _extract_audio(self, media_path: str, audio_path: str) -> None:
        """Extract a mono, low-bitrate audio track from `media_path`."""
        command = [
            "ffmpeg",
            "-y",
            "-i",
            media_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(_AUDIO_SAMPLE_RATE_HZ),
            "-c:a",
            "libmp3lame",
            "-b:a",
            f"{_AUDIO_BITRATE_KBPS}k",
            audio_path,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=3600)
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to extract audio for transcription: {result.stderr[-2000:]}"
            )

    def _probe_audio_duration(self, path: str) -> float:
        """Duration-only probe (no video-stream requirement, unlike
        `media_probe.probe_media`, since this runs against an audio-only
        extracted file)."""
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            path,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(f"Could not determine extracted audio duration: {result.stderr}")
        return float(result.stdout.strip())

    def _transcribe_in_chunks(
        self, audio_path: str, audio_size: int, tmp_dir: str
    ) -> TranscriptResult:
        total_duration = self._probe_audio_duration(audio_path)
        num_chunks = max(1, math.ceil(audio_size / _CHUNK_TARGET_BYTES))
        chunk_duration = total_duration / num_chunks

        all_segments: list[TranscriptSegment] = []
        full_text_parts: list[str] = []
        for i in range(num_chunks):
            start = i * chunk_duration
            length = min(chunk_duration, total_duration - start)
            if length <= 0:
                continue

            chunk_path = os.path.join(tmp_dir, f"chunk_{i:03d}.mp3")
            command = [
                "ffmpeg",
                "-y",
                "-ss",
                str(start),
                "-t",
                str(length),
                "-i",
                audio_path,
                "-c",
                "copy",
                chunk_path,
            ]
            result = subprocess.run(
                command, capture_output=True, text=True, check=False, timeout=600
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to split audio chunk {i}: {result.stderr[-2000:]}")

            chunk_result = self._transcribe_file(chunk_path, offset=start)
            all_segments.extend(chunk_result.segments)
            full_text_parts.append(chunk_result.full_text)

        return TranscriptResult(full_text=" ".join(full_text_parts), segments=all_segments)

    def _transcribe_file(self, file_path: str, offset: float) -> TranscriptResult:
        """POST one (already within the size limit) audio file to the ASR
        API and return its transcript, with segment timestamps shifted by
        `offset` seconds (its position within the original source)."""
        with open(file_path, "rb") as audio_file:
            response = httpx.post(
                f"{self.base_url.rstrip('/')}/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (os.path.basename(file_path), audio_file, "audio/mpeg")},
                data={
                    "model": self.model,
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": "segment",
                },
                # Generous: a real provider transcribing a large chunk may
                # genuinely take a while, and this runs inside a Celery task
                # with no hard task time limit -- this only guards against a
                # truly hung connection, not normal processing time.
                timeout=3600.0,
            )
        response.raise_for_status()
        data = response.json()

        segments = [
            TranscriptSegment(
                start=float(seg["start"]) + offset,
                end=float(seg["end"]) + offset,
                text=str(seg["text"]),
            )
            for seg in data.get("segments", [])
        ]
        full_text = data.get("text") or " ".join(seg.text for seg in segments)
        return TranscriptResult(full_text=full_text, segments=segments)


def get_transcription_service() -> TranscriptionService:
    """Return the configured TranscriptionService implementation."""
    return WhisperAPITranscriptionService()
