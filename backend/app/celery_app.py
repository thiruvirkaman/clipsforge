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
    # Without these, a worker restart (deploy, crash, OOM) silently drops
    # whatever task it was running or had already prefetched -- the default
    # is to ack a task the moment it's received, not once it finishes. Late
    # acks mean an interrupted task gets redelivered to another worker
    # instead of vanishing; prefetch=1 stops a worker hoarding several
    # long-running render tasks while sibling clips sit idle. Every task in
    # this app (transcribe/highlight/render) re-derives its state from the
    # DB and writes to a deterministic output path, so a redelivered retry
    # is safe to just re-run from scratch.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
