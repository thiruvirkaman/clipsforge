"""ClipForge's async clip-generation pipeline: transcription -> highlight
detection -> render, wired together as three chained Celery tasks.

Each task opens its own DB session directly (Celery tasks don't have
FastAPI's `Depends`), and every task catches all exceptions so a failure
always ends with clear `ProcessingJob`/`Project`/`Clip` state in the
database rather than a silently-dead task.
"""
import logging
import os
import shutil
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models.clip import Clip, ClipStatus
from app.models.processing_job import JobStatus, JobType, ProcessingJob
from app.models.project import Project, ProjectStatus, SourceType
from app.services import usage_service
from app.services.asr_service import TranscriptSegment, get_transcription_service
from app.services.highlight_service import (
    DEFAULT_TOP_N,
    HighlightCandidate,
    get_highlight_service,
)
from app.services.render_service import DEFAULT_CAPTION_STYLE, render_clip_video, thumbnail_path_for
from app.services.youtube_service import download_youtube_video
from app.storage import get_media_storage

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.transcribe_project")
def transcribe_project(project_id: int) -> None:
    """Step 1: (download if needed and) transcribe a project's source media,
    persist the timestamped transcript, then chain to highlight detection."""
    db: Session = SessionLocal()
    job: ProcessingJob | None = None
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            logger.error("transcribe_project: project %s not found", project_id)
            return

        job = ProcessingJob(
            project_id=project_id,
            job_type=JobType.transcription,
            status=JobStatus.running,
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        project.status = ProjectStatus.transcribing
        db.commit()
        db.refresh(job)

        # Checked after job creation (not before) so a missing key still
        # leaves a ProcessingJob row explaining the failure, not just the
        # Project's own error_message.
        if not settings.ASR_SERVICE_API_KEY:
            raise RuntimeError(
                "ASR_SERVICE_API_KEY is not configured; the worker cannot transcribe "
                "any video until an ASR provider is set."
            )

        if not project.source_file_path:
            if project.source_type == SourceType.url and project.source_url:
                _ingest_youtube_source(db, project)
            else:
                raise RuntimeError(
                    "Project has no source_file_path and no supported source_url to download"
                )

        assert project.source_file_path is not None  # guaranteed by the check/download above
        media_storage = get_media_storage()
        media_path = media_storage.get_path(project.source_file_path)

        service = get_transcription_service()
        result = service.transcribe(media_path)

        if not result.segments:
            raise RuntimeError(
                "Transcription produced no usable transcript segments (silent, "
                "empty, or unrecognized audio)"
            )

        segments_payload = [
            {"start": seg.start, "end": seg.end, "text": seg.text} for seg in result.segments
        ]

        # Persisted so the render step can slice out sentence/segment-level
        # captions for each clip's own window, rather than one caption
        # spanning the whole clip.
        project.transcript_segments = segments_payload

        job.status = JobStatus.completed
        job.completed_at = datetime.now(timezone.utc)
        project.status = ProjectStatus.analyzing
        db.commit()

        detect_highlights_task.delay(project_id, segments_payload)

    except Exception as exc:
        logger.exception("transcribe_project failed for project %s", project_id)
        db.rollback()
        _fail_job(db, job, str(exc))
        _fail_project(db, project_id, str(exc))
    finally:
        db.close()


def _ingest_youtube_source(db: Session, project: Project) -> None:
    """Download `project.source_url` (already validated as a supported
    YouTube URL at project-creation time) into media storage, and set
    `source_file_path`/`duration_seconds` on `project`.

    Raises `ValidationError` (propagated from `download_youtube_video`) for
    anything that should surface as a clean pipeline failure: unsupported
    URL shape, playlist, live stream, or private/unavailable/removed video.
    """
    assert project.source_url is not None  # only called when source_type == url with a URL set
    downloaded = download_youtube_video(project.source_url)
    tmp_dir = os.path.dirname(downloaded.file_path)
    try:
        stored_path = get_media_storage().save_file(downloaded.file_path, downloaded.filename)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    project.source_file_path = stored_path
    project.duration_seconds = downloaded.duration_seconds
    if not project.title or not project.title.strip():
        project.title = downloaded.title
    db.commit()
    logger.info(
        "Ingested YouTube source for project %s: %s (%ds)",
        project.id,
        downloaded.title,
        downloaded.duration_seconds,
    )


@celery_app.task(name="app.tasks.detect_highlights_task")
def detect_highlights_task(project_id: int, segments: list[dict]) -> None:
    """Step 2: rank candidate moments and keep only the top N (selective, not
    full coverage) as `Clip` rows, then enqueue a render task per clip.

    If detection returns zero candidates, the project is marked `failed`
    immediately rather than being left in `analyzing` forever with no clips
    and nothing left to drive it forward.
    """
    db: Session = SessionLocal()
    job: ProcessingJob | None = None
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            logger.error("detect_highlights_task: project %s not found", project_id)
            return

        job = ProcessingJob(
            project_id=project_id,
            job_type=JobType.highlight_detection,
            status=JobStatus.running,
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        transcript_segments = [
            TranscriptSegment(start=float(s["start"]), end=float(s["end"]), text=str(s["text"]))
            for s in segments
        ]

        service = get_highlight_service()
        candidates: list[HighlightCandidate] = service.detect_highlights(
            transcript_segments, top_n=DEFAULT_TOP_N
        )

        if not candidates:
            message = "No highlight-worthy moments were found in this video."
            job.status = JobStatus.failed
            job.error_message = message
            job.completed_at = datetime.now(timezone.utc)
            project.status = ProjectStatus.failed
            project.error_message = message
            db.commit()
            logger.info("detect_highlights_task: no candidates for project %s", project_id)
            return

        created_clip_ids: list[int] = []
        for candidate in candidates:
            clip = Clip(
                project_id=project_id,
                user_id=project.user_id,
                title=candidate.title,
                start_time=candidate.start_time,
                end_time=candidate.end_time,
                transcript_snippet=candidate.transcript_snippet,
                relevance_score=candidate.relevance_score,
                caption_style=DEFAULT_CAPTION_STYLE,
                status=ClipStatus.queued,
            )
            db.add(clip)
            db.flush()
            created_clip_ids.append(clip.id)

        job.status = JobStatus.completed
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "detect_highlights_task: created %d clip(s) for project %s",
            len(created_clip_ids),
            project_id,
        )
        for clip_id in created_clip_ids:
            render_clip_task.delay(clip_id)

    except Exception as exc:
        logger.exception("detect_highlights_task failed for project %s", project_id)
        db.rollback()
        _fail_job(db, job, str(exc))
        _fail_project(db, project_id, str(exc))
    finally:
        db.close()


def _build_caption_segments(project: Project, clip: Clip) -> list[TranscriptSegment]:
    """Slice the project's persisted transcript to this clip's [start, end]
    window, so captions are synchronized sentence-by-sentence rather than a
    single caption spanning the whole clip.

    Falls back to one synthetic segment covering the whole clip if the
    project has no persisted transcript (e.g. a clip created before
    transcript persistence existed, or a hand-built test fixture).
    """
    raw_segments = project.transcript_segments or []
    sliced = [
        TranscriptSegment(start=float(s["start"]), end=float(s["end"]), text=str(s["text"]))
        for s in raw_segments
        if float(s["end"]) > clip.start_time and float(s["start"]) < clip.end_time
    ]
    if sliced:
        return sliced
    return [
        TranscriptSegment(
            start=clip.start_time, end=clip.end_time, text=clip.transcript_snippet or ""
        )
    ]


@celery_app.task(name="app.tasks.render_clip_task")
def render_clip_task(clip_id: int) -> None:
    """Step 3: render a single clip via ffmpeg with synchronized per-segment
    captions. After each clip finishes (success or failure), checks whether
    the parent project can now be finalized."""
    db: Session = SessionLocal()
    job: ProcessingJob | None = None
    project_id: int | None = None
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if clip is None:
            logger.error("render_clip_task: clip %s not found", clip_id)
            return
        project_id = clip.project_id

        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            logger.error("render_clip_task: project %s not found for clip %s", project_id, clip_id)
            clip.status = ClipStatus.failed
            db.commit()
            return

        job = ProcessingJob(
            project_id=project_id,
            job_type=JobType.render,
            status=JobStatus.running,
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        clip.status = ClipStatus.rendering
        db.commit()
        db.refresh(job)

        if not project.source_file_path:
            raise RuntimeError("Project has no source_file_path to render from")

        media_storage = get_media_storage()
        source_path = media_storage.get_path(project.source_file_path)

        output_filename = f"clip_{clip.id}.mp4"
        output_path = os.path.join(settings.MEDIA_STORAGE_PATH, output_filename)

        caption_segments = _build_caption_segments(project, clip)

        render_clip_video(
            source_media_path=source_path,
            start_time=clip.start_time,
            end_time=clip.end_time,
            output_path=output_path,
            caption_segments=caption_segments,
            caption_style=clip.caption_style or DEFAULT_CAPTION_STYLE,
        )

        clip.video_file_path = output_filename
        clip.thumbnail_path = os.path.basename(thumbnail_path_for(output_path))
        clip.status = ClipStatus.ready
        job.status = JobStatus.completed
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        logger.exception("render_clip_task failed for clip %s", clip_id)
        db.rollback()
        _fail_job(db, job, str(exc))
        # Note: Clip has no error_message column -- failure detail lives on
        # the associated ProcessingJob.error_message instead.
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if clip is not None:
            clip.status = ClipStatus.failed
            db.commit()
    finally:
        if project_id is not None:
            _maybe_finalize_project(db, project_id)
        db.close()


def _fail_job(db: Session, job: ProcessingJob | None, error_message: str) -> None:
    """Mark a job failed, re-fetching it fresh in case the session was
    rolled back after the job was already committed with an id."""
    if job is None or job.id is None:
        return
    fresh = db.query(ProcessingJob).filter(ProcessingJob.id == job.id).first()
    if fresh is not None:
        fresh.status = JobStatus.failed
        fresh.error_message = error_message
        fresh.completed_at = datetime.now(timezone.utc)
        db.commit()


def _fail_project(db: Session, project_id: int, error_message: str) -> None:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is not None:
        project.status = ProjectStatus.failed
        project.error_message = error_message
        db.commit()


def _maybe_finalize_project(db: Session, project_id: int) -> None:
    """After a clip render finishes (success or failure), check whether
    every sibling clip for the project is done (ready or failed).

    A project only becomes `ready` once rendering has fully settled AND at
    least one clip actually rendered successfully; if every clip failed, the
    project is marked `failed` instead of a misleading `ready` with nothing
    watchable in it. Usage is recorded exactly once per successful run.
    """
    try:
        clips = db.query(Clip).filter(Clip.project_id == project_id).all()
        if not clips:
            return

        still_active = any(c.status in (ClipStatus.queued, ClipStatus.rendering) for c in clips)
        if still_active:
            return

        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None or project.status == ProjectStatus.failed:
            return

        ready_clips = [c for c in clips if c.status == ClipStatus.ready]
        if ready_clips:
            project.status = ProjectStatus.ready
            db.commit()
            _record_usage_once(db, project, ready_clips)
        else:
            project.status = ProjectStatus.failed
            project.error_message = "All clip renders failed."
            db.commit()
    except Exception:
        logger.exception("Failed to finalize project %s status after clip render", project_id)
        db.rollback()


def _record_usage_once(db: Session, project: Project, ready_clips: list[Clip]) -> None:
    """Record usage for this run, guarded so a race between multiple render
    tasks finishing near-simultaneously (each triggering a finalize check)
    or a task retry can never record the same run's usage twice."""
    if usage_service.has_usage_record(db, project.id):
        return
    minutes_processed = (project.duration_seconds or 0) / 60.0
    usage_service.record_usage(
        db,
        user_id=project.user_id,
        project_id=project.id,
        minutes_processed=minutes_processed,
        clips_generated=len(ready_clips),
    )
