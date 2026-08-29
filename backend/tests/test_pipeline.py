"""Tests for the Celery pipeline tasks in app.tasks.pipeline.

Runs each task function synchronously (never `.delay()`) against the same
in-memory SQLite database as the `db` fixture, by monkeypatching
`app.tasks.pipeline.SessionLocal` to the test session factory -- Celery
tasks open their own sessions via `SessionLocal` directly (no FastAPI
`Depends`), so this is required to observe/seed their DB state in tests.
"""
from unittest.mock import patch

import pytest
from conftest import TestingSessionLocal

from app.config import settings
from app.models.clip import Clip, ClipStatus
from app.models.processing_job import JobStatus, JobType, ProcessingJob
from app.models.project import Project, ProjectStatus
from app.models.usage_record import UsageRecord
from app.services.asr_service import TranscriptResult, TranscriptSegment
from app.services.highlight_service import HighlightCandidate
from app.services.render_service import RenderError
from app.tasks import pipeline


@pytest.fixture(autouse=True)
def _patch_session_local(monkeypatch):
    """Point the pipeline's SessionLocal at the test DB for every test here,
    and ensure ASR is "configured" by default so transcription tests don't
    all have to opt into it individually."""
    monkeypatch.setattr(pipeline, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(settings, "ASR_SERVICE_BASE_URL", "https://fake-asr.test")
    monkeypatch.setattr(settings, "ASR_SERVICE_API_KEY", "fake-asr-key")


@pytest.fixture()
def project(db, test_user) -> Project:
    proj = Project(
        user_id=test_user.id,
        title="Test Project",
        source_type="upload",
        source_file_path="source.mp4",
        status=ProjectStatus.pending,
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


def test_transcribe_project_success_chains_to_highlights(db, project):
    fake_result = TranscriptResult(
        full_text="Hello world. This is a test.",
        segments=[
            TranscriptSegment(start=0.0, end=2.0, text="Hello world."),
            TranscriptSegment(start=2.0, end=4.0, text="This is a test."),
        ],
    )
    with (
        patch("app.tasks.pipeline.get_transcription_service") as mock_get_service,
        patch.object(pipeline.detect_highlights_task, "delay") as mock_delay,
    ):
        mock_get_service.return_value.transcribe.return_value = fake_result
        pipeline.transcribe_project(project.id)

    db.refresh(project)
    assert project.status == ProjectStatus.analyzing
    assert project.transcript_segments == [
        {"start": 0.0, "end": 2.0, "text": "Hello world."},
        {"start": 2.0, "end": 4.0, "text": "This is a test."},
    ]

    job = db.query(ProcessingJob).filter(ProcessingJob.project_id == project.id).first()
    assert job is not None
    assert job.job_type == JobType.transcription
    assert job.status == JobStatus.completed

    mock_delay.assert_called_once()
    called_project_id, called_segments = mock_delay.call_args[0]
    assert called_project_id == project.id
    assert called_segments == project.transcript_segments


def test_transcribe_project_missing_source_marks_failed(db, test_user):
    proj = Project(
        user_id=test_user.id,
        title="No source",
        source_type="upload",
        status=ProjectStatus.pending,
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)

    pipeline.transcribe_project(proj.id)

    db.refresh(proj)
    assert proj.status == ProjectStatus.failed
    assert proj.error_message

    job = db.query(ProcessingJob).filter(ProcessingJob.project_id == proj.id).first()
    assert job is not None
    assert job.status == JobStatus.failed


def test_transcribe_project_unknown_project_is_a_noop(db):
    # Should not raise even though no project with this id exists.
    pipeline.transcribe_project(999999)


def test_transcribe_project_fails_clearly_when_asr_not_configured(db, project, monkeypatch):
    # ASR_SERVICE_BASE_URL now has a real default (OpenAI's endpoint), so
    # the API key is what actually gates "is ASR configured".
    monkeypatch.setattr(settings, "ASR_SERVICE_API_KEY", "")

    pipeline.transcribe_project(project.id)

    db.refresh(project)
    assert project.status == ProjectStatus.failed
    assert "ASR_SERVICE_API_KEY" in project.error_message


def test_transcribe_project_empty_transcript_marks_failed(db, project):
    empty_result = TranscriptResult(full_text="", segments=[])
    with patch("app.tasks.pipeline.get_transcription_service") as mock_get_service:
        mock_get_service.return_value.transcribe.return_value = empty_result
        pipeline.transcribe_project(project.id)

    db.refresh(project)
    assert project.status == ProjectStatus.failed
    assert project.error_message


def test_transcribe_project_downloads_youtube_source_first(db, test_user, tmp_path):
    proj = Project(
        user_id=test_user.id,
        title="",
        source_type="url",
        source_url="https://youtu.be/abcdefghijk",
        status=ProjectStatus.pending,
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)

    fake_video = tmp_path / "abcdefghijk.mp4"
    fake_video.write_bytes(b"fake video bytes")

    from app.services.youtube_service import DownloadedVideo

    fake_result = TranscriptResult(
        full_text="hi", segments=[TranscriptSegment(start=0.0, end=1.0, text="Hi.")]
    )
    with (
        patch(
            "app.tasks.pipeline.download_youtube_video",
            return_value=DownloadedVideo(
                file_path=str(fake_video),
                filename="abcdefghijk.mp4",
                duration_seconds=120,
                title="A YouTube Video",
            ),
        ),
        patch("app.tasks.pipeline.get_transcription_service") as mock_get_service,
        patch.object(pipeline.detect_highlights_task, "delay"),
    ):
        mock_get_service.return_value.transcribe.return_value = fake_result
        pipeline.transcribe_project(proj.id)

    db.refresh(proj)
    assert proj.source_file_path is not None
    assert proj.duration_seconds == 120
    assert proj.title == "A YouTube Video"
    assert proj.status == ProjectStatus.analyzing


def test_detect_highlights_task_creates_only_top_n_clips_and_enqueues_render(db, project):
    candidates = [
        HighlightCandidate(
            start_time=float(i * 60),
            end_time=float(i * 60 + 55),
            title=f"Moment {i}",
            transcript_snippet=f"snippet {i}",
            relevance_score=1.0 - i * 0.1,
        )
        for i in range(3)
    ]
    segments = [{"start": 0.0, "end": 200.0, "text": "some transcript text"}]

    with (
        patch("app.tasks.pipeline.get_highlight_service") as mock_get_service,
        patch.object(pipeline.render_clip_task, "delay") as mock_delay,
    ):
        mock_get_service.return_value.detect_highlights.return_value = candidates
        pipeline.detect_highlights_task(project.id, segments)

    clips = db.query(Clip).filter(Clip.project_id == project.id).all()
    assert len(clips) == 3
    assert {c.status for c in clips} == {ClipStatus.queued}
    assert mock_delay.call_count == 3

    job = (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.project_id == project.id,
            ProcessingJob.job_type == JobType.highlight_detection,
        )
        .first()
    )
    assert job is not None
    assert job.status == JobStatus.completed


def test_detect_highlights_task_zero_candidates_marks_project_failed(db, project):
    """No highlight-worthy moments -> failed immediately, never stuck in `analyzing`."""
    segments = [{"start": 0.0, "end": 5.0, "text": "."}]

    with patch("app.tasks.pipeline.get_highlight_service") as mock_get_service:
        mock_get_service.return_value.detect_highlights.return_value = []
        pipeline.detect_highlights_task(project.id, segments)

    db.refresh(project)
    assert project.status == ProjectStatus.failed
    assert project.error_message
    assert db.query(Clip).filter(Clip.project_id == project.id).count() == 0

    job = (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.project_id == project.id,
            ProcessingJob.job_type == JobType.highlight_detection,
        )
        .first()
    )
    assert job.status == JobStatus.failed


def test_detect_highlights_task_unknown_project_is_a_noop(db):
    pipeline.detect_highlights_task(999999, [])


@pytest.fixture()
def queued_clip(db, project) -> Clip:
    clip = Clip(
        project_id=project.id,
        user_id=project.user_id,
        title="Clip 1",
        start_time=0.0,
        end_time=55.0,
        transcript_snippet="hello",
        relevance_score=0.9,
        status=ClipStatus.queued,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


def test_render_clip_task_success_marks_ready_and_finalizes_project(db, project, queued_clip):
    with (
        patch("app.tasks.pipeline.render_clip_video") as mock_render,
        patch("app.tasks.pipeline.thumbnail_path_for", return_value="/media/clip_1.jpg"),
    ):
        mock_render.return_value = None
        pipeline.render_clip_task(queued_clip.id)

    db.refresh(queued_clip)
    assert queued_clip.status == ClipStatus.ready
    assert queued_clip.video_file_path == f"clip_{queued_clip.id}.mp4"
    assert queued_clip.thumbnail_path == "clip_1.jpg"

    db.refresh(project)
    assert project.status == ProjectStatus.ready

    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.project_id == project.id, ProcessingJob.job_type == JobType.render)
        .first()
    )
    assert job.status == JobStatus.completed

    # Usage recorded exactly once for this run.
    records = db.query(UsageRecord).filter(UsageRecord.project_id == project.id).all()
    assert len(records) == 1
    assert records[0].clips_generated == 1


def test_render_clip_task_all_failed_marks_project_failed_not_ready(db, project, queued_clip):
    """All clips failing must NOT leave the project `ready` with nothing watchable in it."""
    with patch("app.tasks.pipeline.render_clip_video", side_effect=RenderError("ffmpeg exploded")):
        pipeline.render_clip_task(queued_clip.id)

    db.refresh(queued_clip)
    assert queued_clip.status == ClipStatus.failed

    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.project_id == project.id, ProcessingJob.job_type == JobType.render)
        .first()
    )
    assert job.status == JobStatus.failed
    assert "ffmpeg exploded" in job.error_message

    db.refresh(project)
    assert project.status == ProjectStatus.failed
    assert db.query(UsageRecord).filter(UsageRecord.project_id == project.id).count() == 0


def test_render_clip_task_one_success_one_failure_marks_project_ready(db, project):
    """At least one successful render is enough for the project to be `ready`."""
    ok_clip = Clip(
        project_id=project.id,
        user_id=project.user_id,
        title="OK",
        start_time=0.0,
        end_time=50.0,
        status=ClipStatus.queued,
    )
    bad_clip = Clip(
        project_id=project.id,
        user_id=project.user_id,
        title="Bad",
        start_time=60.0,
        end_time=110.0,
        status=ClipStatus.queued,
    )
    db.add_all([ok_clip, bad_clip])
    db.commit()
    db.refresh(ok_clip)
    db.refresh(bad_clip)

    with (
        patch("app.tasks.pipeline.render_clip_video") as mock_render,
        patch("app.tasks.pipeline.thumbnail_path_for", return_value="/media/x.jpg"),
    ):
        mock_render.return_value = None
        pipeline.render_clip_task(ok_clip.id)

    with patch("app.tasks.pipeline.render_clip_video", side_effect=RenderError("boom")):
        pipeline.render_clip_task(bad_clip.id)

    db.refresh(project)
    assert project.status == ProjectStatus.ready

    # Usage is still recorded exactly once even though finalize ran twice.
    records = db.query(UsageRecord).filter(UsageRecord.project_id == project.id).all()
    assert len(records) == 1
    assert records[0].clips_generated == 1


def test_render_clip_task_unknown_clip_is_a_noop(db):
    pipeline.render_clip_task(999999)


def test_maybe_finalize_project_waits_for_all_siblings(db, project):
    clip_a = Clip(
        project_id=project.id,
        user_id=project.user_id,
        title="A",
        start_time=0.0,
        end_time=10.0,
        status=ClipStatus.ready,
    )
    clip_b = Clip(
        project_id=project.id,
        user_id=project.user_id,
        title="B",
        start_time=10.0,
        end_time=20.0,
        status=ClipStatus.rendering,
    )
    db.add_all([clip_a, clip_b])
    db.commit()

    pipeline._maybe_finalize_project(db, project.id)
    db.refresh(project)
    assert project.status != ProjectStatus.ready

    clip_b.status = ClipStatus.ready
    db.commit()

    pipeline._maybe_finalize_project(db, project.id)
    db.refresh(project)
    assert project.status == ProjectStatus.ready


def test_build_caption_segments_slices_transcript_to_clip_window(db, project):
    """Captions come from the real per-sentence transcript slice, not one
    caption spanning the whole clip."""
    project.transcript_segments = [
        {"start": 0.0, "end": 5.0, "text": "Before the clip."},
        {"start": 10.0, "end": 15.0, "text": "Inside the clip, part one."},
        {"start": 15.0, "end": 20.0, "text": "Inside the clip, part two."},
        {"start": 40.0, "end": 45.0, "text": "After the clip."},
    ]
    db.commit()

    clip = Clip(
        project_id=project.id,
        user_id=project.user_id,
        title="Clip",
        start_time=10.0,
        end_time=20.0,
        status=ClipStatus.queued,
    )

    segments = pipeline._build_caption_segments(project, clip)

    assert len(segments) == 2
    assert [s.text for s in segments] == [
        "Inside the clip, part one.",
        "Inside the clip, part two.",
    ]


def test_build_caption_segments_falls_back_when_no_transcript(db, project):
    clip = Clip(
        project_id=project.id,
        user_id=project.user_id,
        title="Clip",
        start_time=10.0,
        end_time=20.0,
        transcript_snippet="Fallback text.",
        status=ClipStatus.queued,
    )

    segments = pipeline._build_caption_segments(project, clip)

    assert len(segments) == 1
    assert segments[0].text == "Fallback text."
    assert segments[0].start == 10.0
    assert segments[0].end == 20.0
