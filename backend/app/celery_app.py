"""Celery application instance for ClipForge's async pipeline
(transcription, highlight detection, rendering).

Task modules are wired via `include=["app.tasks"]`; Phase 2's Clip
Generation agent is responsible for creating `app/tasks/` with the
actual task implementations.
"""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "clipforge",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
