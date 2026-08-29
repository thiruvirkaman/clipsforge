"""Unit tests for the pure-Python highlight-detection fallback.

These directly exercise ClipForge's product rules:
  * "selective, not full coverage" -- `detect_highlights` never returns more
    than `top_n` candidates, however long the transcript.
  * "~60s soft target" -- `_snap_to_sentence_boundary` snaps windows to real
    sentence boundaries in the transcript text rather than clamping to an
    exact duration.
"""
from unittest.mock import MagicMock, patch

from app.services.asr_service import TranscriptSegment
from app.services.highlight_service import (
    MAX_CLIP_SECONDS,
    MIN_VALID_CANDIDATE_SECONDS,
    HeuristicHighlightDetectionService,
    HighlightCandidate,
    LLMHighlightDetectionService,
    _snap_to_sentence_boundary,
    _validate_and_normalize_candidates,
)


def _segment(start: float, end: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(start=start, end=end, text=text)


def _build_segments(count: int = 75, segment_seconds: float = 8.0) -> list[TranscriptSegment]:
    """Synthetic transcript: `count` sentences, each its own segment, every
    segment ending with sentence-terminating punctuation (a period, plus an
    exclamation on every 7th one for scoring variety)."""
    segments = []
    t = 0.0
    for i in range(count):
        text = f"This is sentence number {i}."
        if i % 7 == 0:
            text += " Amazing!"
        segments.append(_segment(t, t + segment_seconds, text))
        t += segment_seconds
    return segments


def test_snap_to_sentence_boundary_lands_near_target_and_on_boundary():
    segments = _build_segments()
    boundary_starts = {s.start for s in segments}
    boundary_ends = {s.end for s in segments}

    start, end = _snap_to_sentence_boundary(segments, target_start=100.0, target_seconds=60.0)

    assert start in boundary_starts
    assert end in boundary_ends
    assert end > start
    duration = end - start
    assert 30.0 <= duration <= 100.0  # generous bound around the 40-90s soft range
    assert abs(start - 100.0) <= 16.0  # snapped near the requested start


def test_snap_to_sentence_boundary_prefers_end_within_40_to_90s_range():
    segments = _build_segments()

    start, end = _snap_to_sentence_boundary(segments, target_start=0.0, target_seconds=60.0)

    duration = end - start
    assert 40.0 <= duration <= 90.0


def test_snap_to_sentence_boundary_empty_segments_returns_target_window():
    start, end = _snap_to_sentence_boundary([], target_start=50.0, target_seconds=60.0)

    assert start == 50.0
    assert end == 110.0


def test_detect_highlights_never_exceeds_top_n():
    # 10 minutes of synthetic transcript -- far more candidate windows than
    # any of the requested top_n values below.
    segments = _build_segments()
    service = HeuristicHighlightDetectionService()

    for top_n in (3, 5, 8):
        candidates = service.detect_highlights(segments, top_n=top_n)
        assert len(candidates) <= top_n


def test_detect_highlights_selects_a_strict_subset_not_full_coverage():
    segments = _build_segments()
    total_duration = segments[-1].end - segments[0].start
    service = HeuristicHighlightDetectionService()

    candidates = service.detect_highlights(segments, top_n=5)

    covered = sum(c.end_time - c.start_time for c in candidates)
    assert covered < total_duration  # most of the transcript is left unused


def test_detect_highlights_returns_sorted_by_start_time():
    segments = _build_segments()
    service = HeuristicHighlightDetectionService()

    candidates = service.detect_highlights(segments, top_n=5)

    starts = [c.start_time for c in candidates]
    assert starts == sorted(starts)


def test_detect_highlights_without_terminal_punctuation_does_not_collapse_to_one_clip():
    """Regression test: an independent review found that a transcript with
    NO sentence-terminating punctuation anywhere made every scan window
    snap to the same start=0 (the `i == 0` fallback was always non-empty),
    collapsing 75 segments of real content down to a single clip."""
    segments = [
        _segment(float(i * 8), float(i * 8 + 8), f"sentence number {i} with no punctuation")
        for i in range(75)
    ]
    service = HeuristicHighlightDetectionService()

    candidates = service.detect_highlights(segments, top_n=8)

    assert len(candidates) > 1
    starts = {round(c.start_time) for c in candidates}
    assert len(starts) > 1  # not all collapsed to the same window


def test_detect_highlights_empty_segments_returns_empty():
    service = HeuristicHighlightDetectionService()

    assert service.detect_highlights([], top_n=5) == []


# --- LLM output validation/normalization ------------------------------------
#
# The LLM path receives timestamps from an external model response, which
# (unlike the heuristic path) cannot be trusted to respect ordering,
# transcript bounds, or the 40-90s target range.


def test_validate_candidates_clamps_out_of_bounds_window():
    segments = [
        TranscriptSegment(start=0.0, end=5.0, text="a."),
        TranscriptSegment(start=5.0, end=100.0, text="b."),
    ]
    candidates = [
        HighlightCandidate(
            start_time=-50.0, end_time=500.0, title="t", transcript_snippet="s",
            relevance_score=0.9,
        )
    ]

    result = _validate_and_normalize_candidates(candidates, segments, top_n=8)

    assert len(result) == 1
    assert result[0].start_time == 0.0  # clamped to transcript start
    assert result[0].end_time <= result[0].start_time + MAX_CLIP_SECONDS  # clamped, not rejected


def test_validate_candidates_ignores_llm_end_time_and_snaps_a_fresh_window():
    """A nonsensical raw end_time (before start_time) doesn't matter -- only
    start_time is used, as an anchor for deterministic snapping."""
    segments = [TranscriptSegment(start=0.0, end=100.0, text="a.")]
    candidates = [
        HighlightCandidate(
            start_time=50.0, end_time=10.0, title="t", transcript_snippet="s",
            relevance_score=0.9,
        )
    ]

    result = _validate_and_normalize_candidates(candidates, segments, top_n=8)

    assert len(result) == 1
    assert result[0].end_time > result[0].start_time


def test_validate_candidates_expands_short_llm_window_via_snapping():
    """Regression test: a real run had the LLM return well-formed but short
    (2-5s) "hook" windows for every candidate, and the old
    reject-if-too-short logic dropped all of them, failing the whole
    project. Short raw LLM windows must be expanded to a real clip via
    sentence-boundary snapping, not discarded."""
    segments = _build_segments()  # 75 sentences, ~600s of real content
    candidates = [
        HighlightCandidate(
            start_time=100.0, end_time=102.5, title="t", transcript_snippet="s",
            relevance_score=0.9,
        )
    ]

    result = _validate_and_normalize_candidates(candidates, segments, top_n=8)

    assert len(result) == 1
    duration = result[0].end_time - result[0].start_time
    assert duration >= MIN_VALID_CANDIDATE_SECONDS
    assert duration > (102.5 - 100.0)  # meaningfully expanded, not left tiny


def test_validate_candidates_drops_non_finite_values():
    segments = [TranscriptSegment(start=0.0, end=100.0, text="a.")]
    candidates = [
        HighlightCandidate(
            start_time=float("nan"), end_time=50.0, title="t", transcript_snippet="s",
            relevance_score=0.9,
        ),
        HighlightCandidate(
            start_time=0.0, end_time=float("inf"), title="t2", transcript_snippet="s",
            relevance_score=0.9,
        ),
    ]

    assert _validate_and_normalize_candidates(candidates, segments, top_n=8) == []


def test_validate_candidates_caps_at_top_n_by_score():
    segments = _build_segments()  # 75 sentences spread across ~600s
    candidates = [
        HighlightCandidate(
            start_time=float(i * 60),
            end_time=float(i * 60 + 3),  # short raw window -- gets expanded via snapping
            title=f"t{i}",
            transcript_snippet="s",
            relevance_score=float(i),
        )
        for i in range(10)
    ]

    result = _validate_and_normalize_candidates(candidates, segments, top_n=3)

    assert len(result) == 3
    # Kept the 3 highest-scored (7, 8, 9), returned sorted by start_time.
    assert [c.title for c in result] == ["t7", "t8", "t9"]


def test_llm_service_falls_back_to_heuristic_when_provider_returns_malformed_json():
    segments = _build_segments()
    service = LLMHighlightDetectionService(api_key="fake-key")

    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "choices": [{"message": {"content": "not valid json{{{"}}]
    }

    with patch("app.services.highlight_service.httpx.post", return_value=fake_response):
        candidates = service.detect_highlights(segments, top_n=5)

    # Falls back to the heuristic detector rather than raising or returning
    # unvalidated garbage.
    assert 0 < len(candidates) <= 5


def test_llm_service_validates_provider_timestamps_before_returning():
    segments = [TranscriptSegment(start=0.0, end=120.0, text="Hello there. Goodbye now.")]
    service = LLMHighlightDetectionService(api_key="fake-key")

    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"highlights": [{"start_time": -10, "end_time": 99999, '
                        '"title": "x", "transcript_snippet": "y", "relevance_score": 0.8}]}'
                    )
                }
            }
        ]
    }

    with patch("app.services.highlight_service.httpx.post", return_value=fake_response):
        candidates = service.detect_highlights(segments, top_n=5)

    assert len(candidates) == 1
    assert candidates[0].start_time == 0.0
    assert candidates[0].end_time <= 120.0
    assert candidates[0].end_time - candidates[0].start_time <= MAX_CLIP_SECONDS
