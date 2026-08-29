"""Highlight-detection service abstraction for ClipForge.

Product rules encoded here:
  * SELECTIVE, NOT FULL COVERAGE: `detect_highlights` ranks candidate moments
    and returns only the top `top_n` (default ~8) -- most of the source
    transcript is never turned into a clip.
  * SOFT ~60s TARGET: start_time/end_time are snapped to the nearest
    sentence/topic boundary in the transcript text (semantic only -- no
    audio silence/pause detection), so real clip durations land roughly in
    the 40-90s range rather than being clamped to exactly 60s.
"""
import json
import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import settings
from app.services.asr_service import TranscriptSegment

logger = logging.getLogger(__name__)

#: Default number of highlights to keep per project when not otherwise specified.
DEFAULT_TOP_N = 8

#: Soft target clip length; real clips land ~40-90s once snapped to sentence
#: boundaries (see `_snap_to_sentence_boundary`).
TARGET_CLIP_SECONDS = 60.0
MIN_CLIP_SECONDS = 40.0
MAX_CLIP_SECONDS = 90.0

#: Below this, a candidate window is too degenerate to be a real clip and is
#: dropped outright rather than normalized (used when validating untrusted
#: LLM-provided timestamps -- see `_validate_and_normalize_candidates`).
MIN_VALID_CANDIDATE_SECONDS = 5.0


@dataclass
class HighlightCandidate:
    """A single ranked highlight moment, ready to become a `Clip` row."""

    start_time: float
    end_time: float
    title: str
    transcript_snippet: str
    relevance_score: float


class HighlightDetectionService(Protocol):
    """Pluggable interface for ranking and selecting highlight moments."""

    def detect_highlights(
        self, segments: list[TranscriptSegment], top_n: int = DEFAULT_TOP_N
    ) -> list[HighlightCandidate]:
        """Return at most `top_n` `HighlightCandidate`s, ranked by relevance."""
        ...


def _is_sentence_end(segment: TranscriptSegment) -> bool:
    """A segment "ends a sentence" if its text ends with sentence-terminating
    punctuation. This is a purely textual/semantic check -- no audio silence
    or pause detection is used, per product rules."""
    stripped = segment.text.strip()
    return stripped.endswith((".", "!", "?")) if stripped else False


def _snap_to_sentence_boundary(
    segments: list[TranscriptSegment],
    target_start: float,
    target_seconds: float = TARGET_CLIP_SECONDS,
) -> tuple[float, float]:
    """Given a rough target window `[target_start, target_start + target_seconds]`,
    walk the segment boundaries in `segments` to find the nearest sentence
    start/end so the returned window snaps to real transcript sentence
    boundaries. Pure Python -- no LLM call -- so it is directly testable and
    usable as a fallback highlight detector without a live API key.

    Returns (start, end). If `segments` is empty, returns the unmodified
    target window.
    """
    if not segments:
        return target_start, target_start + target_seconds

    ordered = sorted(segments, key=lambda s: s.start)

    # A segment "starts a sentence" if the preceding segment ended one.
    # (The very first segment is a trivial, always-true "boundary" that
    # doesn't reflect any real sentence detection -- deliberately excluded
    # here so that a transcript with NO real sentence-ending punctuation
    # anywhere doesn't silently collapse to a one-element candidate list,
    # which would snap every scan window to that same single start
    # regardless of target_start.)
    real_boundary_starts = [
        seg.start for i, seg in enumerate(ordered) if i > 0 and _is_sentence_end(ordered[i - 1])
    ]
    if real_boundary_starts:
        start_candidates = [ordered[0].start, *real_boundary_starts]
    else:
        # No real sentence boundaries anywhere in the transcript -- fall
        # back to every segment start so different target_start values
        # still produce different windows.
        start_candidates = [seg.start for seg in ordered]
    start = min(start_candidates, key=lambda t: abs(t - target_start))

    target_end = start + target_seconds
    min_end = start + MIN_CLIP_SECONDS
    max_end = start + MAX_CLIP_SECONDS

    end_candidates = [seg.end for seg in ordered if _is_sentence_end(seg) and seg.end > start]
    if not end_candidates:
        end_candidates = [seg.end for seg in ordered if seg.end > start]
    if not end_candidates:
        return start, start + target_seconds

    # Prefer a sentence-end within the acceptable 40-90s range, closest to
    # the 60s target; fall back to the closest sentence-end overall.
    in_range = [t for t in end_candidates if min_end <= t <= max_end]
    pool = in_range if in_range else end_candidates
    end = min(pool, key=lambda t: abs(t - target_end))

    if end <= start:
        end = start + target_seconds

    return start, end


class HeuristicHighlightDetectionService:
    """Pure-Python fallback highlight detector used when no LLM API key is
    configured (`LLM_SERVICE_API_KEY` is empty), so tests and local dev work
    without a real key.

    Scores candidate windows with a simple lexical heuristic (no ML/LLM
    call) and snaps their boundaries to sentence breaks via
    `_snap_to_sentence_boundary`.
    """

    #: Spacing (seconds) between successive candidate window starts when
    #: scanning the transcript for windows to score.
    _SCAN_STEP_SECONDS = 45.0

    def detect_highlights(
        self, segments: list[TranscriptSegment], top_n: int = DEFAULT_TOP_N
    ) -> list[HighlightCandidate]:
        if not segments:
            return []

        ordered = sorted(segments, key=lambda s: s.start)
        total_start = ordered[0].start
        total_end = ordered[-1].end

        raw_candidates: list[HighlightCandidate] = []
        target_start = total_start
        while target_start < total_end:
            start, end = _snap_to_sentence_boundary(
                ordered, target_start, target_seconds=TARGET_CLIP_SECONDS
            )
            end = min(end, total_end)
            if end > start:
                snippet_segments = [s for s in ordered if s.start < end and s.end > start]
                if snippet_segments:
                    raw_candidates.append(self._build_candidate(snippet_segments, start, end))
            target_start += self._SCAN_STEP_SECONDS

        # De-duplicate windows that snapped to the same start, keeping the
        # highest-scoring one for each.
        best_by_start: dict[float, HighlightCandidate] = {}
        for candidate in raw_candidates:
            existing = best_by_start.get(candidate.start_time)
            if existing is None or candidate.relevance_score > existing.relevance_score:
                best_by_start[candidate.start_time] = candidate

        ranked = sorted(best_by_start.values(), key=lambda c: c.relevance_score, reverse=True)
        top = ranked[:top_n]
        return sorted(top, key=lambda c: c.start_time)

    def _build_candidate(
        self, snippet_segments: list[TranscriptSegment], start: float, end: float
    ) -> HighlightCandidate:
        snippet = " ".join(s.text.strip() for s in snippet_segments if s.text.strip()).strip()
        score = self._score_snippet(snippet)
        title = snippet[:60].rsplit(" ", 1)[0] if len(snippet) > 60 else snippet
        return HighlightCandidate(
            start_time=start,
            end_time=end,
            title=title or "Untitled highlight",
            transcript_snippet=snippet,
            relevance_score=score,
        )

    @staticmethod
    def _score_snippet(snippet: str) -> float:
        """Cheap, deterministic engagement proxy: rewards exclamation/question
        marks and overall content length. Not ML-based -- purely a fallback
        so the pipeline works end-to-end without a live LLM call."""
        if not snippet:
            return 0.0
        exclamations = snippet.count("!")
        questions = snippet.count("?")
        word_count = len(snippet.split())
        return round(word_count * 0.1 + exclamations * 2.0 + questions * 1.5, 4)


def _validate_and_normalize_candidates(
    candidates: list[HighlightCandidate],
    segments: list[TranscriptSegment],
    top_n: int,
) -> list[HighlightCandidate]:
    """Validate LLM-provided candidates and rebuild their timing
    deterministically before they can become `Clip` rows.

    In practice, LLMs are unreliable at following an exact duration
    instruction in a prompt: they routinely pick short (2-10s) "hook"
    moments instead of the ~60s/40-90s window this product requires, even
    when told to target one explicitly. Rather than reject those (which
    would silently discard most or all of a model's real judgment about
    *which* moments matter -- exactly what happened before this fix, where
    a real run's 8 well-formed but short candidates were all dropped), only
    `start_time` is trusted as an anchor ("this moment is worth a clip");
    the actual window is then built with the same deterministic
    `_snap_to_sentence_boundary` sentence-boundary snapping the heuristic
    detector uses, which always produces a window in the product's target
    range (when the transcript has enough content). `end_time` from the
    model is never used for timing. This:
      * drops non-finite/non-numeric start/end values,
      * clamps the anchor to the actual transcript's [first segment start,
        last segment end] bounds,
      * snaps a fresh, properly-sized window around that anchor,
      * drops anything left with end <= start or shorter than
        `MIN_VALID_CANDIDATE_SECONDS` (a maximally sparse transcript could
        still fail to produce a usable window),
      * clamps windows longer than `MAX_CLIP_SECONDS` down to that ceiling,
      * rebuilds `transcript_snippet` from the segments actually covered by
        the final window (the model's original short snippet no longer
        matches a window it didn't choose the bounds of), keeping the
        model's `title` and `relevance_score` (judgment calls, not timing),
      * de-duplicates near-identical start times (keeping the higher-scored
        one), and
      * caps the result at `top_n`, ranked by relevance_score.
    """
    if not segments or not candidates:
        return []

    ordered = sorted(segments, key=lambda s: s.start)
    transcript_start = ordered[0].start
    transcript_end = ordered[-1].end
    logger.info(
        "Validating %d LLM candidates against transcript bounds [%.2f, %.2f]",
        len(candidates),
        transcript_start,
        transcript_end,
    )

    normalized: list[HighlightCandidate] = []
    for candidate in candidates:
        raw_start, raw_end = candidate.start_time, candidate.end_time
        score = candidate.relevance_score

        if not isinstance(raw_start, (int, float)) or not isinstance(raw_end, (int, float)):
            logger.info("Dropping candidate: non-numeric start/end (%r, %r)", raw_start, raw_end)
            continue
        if raw_start != raw_start or raw_end != raw_end:  # NaN
            logger.info("Dropping candidate: NaN start/end (%r, %r)", raw_start, raw_end)
            continue
        if raw_start in (float("inf"), float("-inf")) or raw_end in (
            float("inf"),
            float("-inf"),
        ):
            logger.info("Dropping candidate: infinite start/end (%r, %r)", raw_start, raw_end)
            continue
        if not isinstance(score, (int, float)) or score != score:
            score = 0.0

        anchor = min(max(float(raw_start), transcript_start), transcript_end)
        start, end = _snap_to_sentence_boundary(ordered, anchor, target_seconds=TARGET_CLIP_SECONDS)
        end = min(end, transcript_end)
        if end <= start:
            logger.info("Dropping candidate: anchor=%.2f snapped=[%.2f, %.2f]", anchor, start, end)
            continue

        duration = end - start
        if duration < MIN_VALID_CANDIDATE_SECONDS:
            logger.info(
                "Dropping candidate: anchor=%.2f snapped duration %.2fs < minimum %.2fs",
                anchor,
                duration,
                MIN_VALID_CANDIDATE_SECONDS,
            )
            continue
        if duration > MAX_CLIP_SECONDS:
            end = start + MAX_CLIP_SECONDS

        snippet_segments = [s for s in ordered if s.start < end and s.end > start]
        snippet = " ".join(s.text.strip() for s in snippet_segments if s.text.strip()).strip()

        title = (candidate.title or "").strip()[:200] or "Untitled highlight"
        normalized.append(
            HighlightCandidate(
                start_time=start,
                end_time=end,
                title=title,
                transcript_snippet=snippet or (candidate.transcript_snippet or "").strip()[:2000],
                relevance_score=float(score),
            )
        )

    best_by_start: dict[int, HighlightCandidate] = {}
    for candidate in normalized:
        key = round(candidate.start_time)
        existing = best_by_start.get(key)
        if existing is None or candidate.relevance_score > existing.relevance_score:
            best_by_start[key] = candidate

    ranked = sorted(best_by_start.values(), key=lambda c: c.relevance_score, reverse=True)
    top = ranked[:top_n]
    return sorted(top, key=lambda c: c.start_time)


class LLMHighlightDetectionService:
    """Calls an LLM chat-completion API to rank and select highlight moments.

    Best-effort, pluggable stub (mirrors `WhisperAPITranscriptionService`):
    targets a generic OpenAI-compatible chat completions endpoint. Swap in a
    real provider client later behind the same `HighlightDetectionService`
    interface. Falls back to `HeuristicHighlightDetectionService` if no API
    key is configured or the call fails.
    """

    DEFAULT_API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str | None = None, api_url: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.LLM_SERVICE_API_KEY
        self.api_url = api_url or self.DEFAULT_API_URL
        self._fallback = HeuristicHighlightDetectionService()

    def detect_highlights(
        self, segments: list[TranscriptSegment], top_n: int = DEFAULT_TOP_N
    ) -> list[HighlightCandidate]:
        if not segments:
            return []

        if not self.api_key:
            logger.info(
                "LLM_SERVICE_API_KEY not configured; using heuristic fallback highlight detector"
            )
            return self._fallback.detect_highlights(segments, top_n=top_n)

        prompt = self._build_prompt(segments, top_n)
        logger.info("Requesting up to %d highlight candidates from LLM service", top_n)
        try:
            response = httpx.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            candidates = [
                HighlightCandidate(
                    start_time=float(item["start_time"]),
                    end_time=float(item["end_time"]),
                    title=str(item["title"]),
                    transcript_snippet=str(item.get("transcript_snippet", "")),
                    relevance_score=float(item.get("relevance_score", 0.0)),
                )
                for item in parsed.get("highlights", [])
            ]
            validated = _validate_and_normalize_candidates(candidates, segments, top_n)
            logger.info(
                "LLM returned %d raw candidates, %d after validation/normalization",
                len(candidates),
                len(validated),
            )
            return validated
        except Exception:
            logger.exception("LLM highlight detection failed; falling back to heuristic detector")
            return self._fallback.detect_highlights(segments, top_n=top_n)

    @staticmethod
    def _build_prompt(segments: list[TranscriptSegment], top_n: int) -> str:
        transcript_lines = "\n".join(
            f"[{seg.start:.2f}-{seg.end:.2f}] {seg.text}" for seg in segments
        )
        return (
            "You are selecting the most engaging moments from a long-form video "
            "transcript to turn into short vertical clips.\n\n"
            f"Rank candidate moments by engagement/relevance and return ONLY the "
            f"top {top_n} moments -- do not attempt full coverage of the transcript; "
            "most of it should be left unused.\n\n"
            "For each selected moment, choose start_time and end_time at the "
            "NEAREST SENTENCE BOUNDARY in the transcript segments below (semantic "
            "text boundaries only, not audio silence). Target a clip length of "
            "about 60 seconds, but it is acceptable and expected for clips to "
            "range roughly between 40 and 90 seconds depending on where sentences "
            "naturally begin and end -- never truncate mid-sentence and never "
            "hard-clamp to exactly 60 seconds.\n\n"
            "Return strict JSON of the form:\n"
            '{"highlights": [{"start_time": <float seconds>, "end_time": <float '
            'seconds>, "title": <short string>, "transcript_snippet": <string>, '
            '"relevance_score": <float 0-1>}]}\n\n'
            "Transcript segments (timestamps in seconds):\n"
            f"{transcript_lines}"
        )


def get_highlight_service() -> HighlightDetectionService:
    """Return the configured HighlightDetectionService implementation.

    Falls back to the pure-Python heuristic detector (no network call) when
    `LLM_SERVICE_API_KEY` is not configured, so tests and local dev work
    without a real key.
    """
    if not settings.LLM_SERVICE_API_KEY:
        return HeuristicHighlightDetectionService()
    return LLMHighlightDetectionService()
