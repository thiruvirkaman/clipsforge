"""Celery task package for ClipForge's clip-generation pipeline
(transcription -> highlight detection -> render).

Re-exports the pipeline's entrypoint task (`transcribe_project`) so other
modules (e.g. `app/routers/projects.py`) can do:

    from app.tasks import transcribe_project
    transcribe_project.delay(project_id)
"""
from app.tasks.pipeline import (
    detect_highlights_task,
    render_clip_task,
    transcribe_project,
)

__all__ = ["detect_highlights_task", "render_clip_task", "transcribe_project"]
