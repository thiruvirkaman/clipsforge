"""Tests for the ClipForge project endpoints: create (upload/YouTube URL),
list/get/delete, process (enqueue safety, quota, reprocess cleanup), and jobs.

Uses the shared conftest fixtures (`client`, `db`, `test_user`, `other_user`,
`auth_headers`), bound to the real `app.main.app` (all routers wired). The
real `ffprobe` binary and Celery broker are never required: uploads mock
`project_service.probe_media`, and `.delay()` calls are monkeypatched.
"""
from unittest.mock import MagicMock

import pytest

from app.models.clip import Clip, ClipStatus
from app.models.processing_job import JobStatus, JobType, ProcessingJob
from app.models.project import Project, ProjectStatus, SourceType
from app.models.usage_record import UsageRecord
from app.services import project_service
from app.services.media_probe import MediaProbeError, MediaProbeResult


@pytest.fixture()
def mock_probe(monkeypatch):
    """Skip real ffprobe validation; return a fixed 42s duration."""
    fake = MagicMock(return_value=MediaProbeResult(duration_seconds=42.0, has_video_stream=True))
    monkeypatch.setattr(project_service, "probe_media", fake)
    return fake


@pytest.fixture()
def mock_transcribe_delay(monkeypatch):
    """`start_processing` imports `app.tasks.transcribe_project` lazily
    inside the function body, so patch the real task's `.delay` directly."""
    fake = MagicMock()
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module.transcribe_project, "delay", fake)
    return fake


def _upload(client, auth_headers, title="My Video", filename="clip.mp4"):
    return client.post(
        "/api/v1/projects",
        data={"title": title, "source_type": "upload"},
        files={"file": (filename, b"fake-video-bytes", "video/mp4")},
        headers=auth_headers,
    )


# --- create: upload -------------------------------------------------------


def test_create_project_upload(client, auth_headers, mock_probe):
    response = _upload(client, auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "My Video"
    assert body["source_type"] == "upload"
    assert body["source_file_path"] is not None
    assert body["duration_seconds"] == 42
    assert body["status"] == "pending"


def test_create_project_upload_missing_file(client, auth_headers):
    response = client.post(
        "/api/v1/projects",
        data={"title": "No File", "source_type": "upload"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_project_upload_rejects_disallowed_extension(client, auth_headers):
    response = client.post(
        "/api/v1/projects",
        data={"title": "Bad ext", "source_type": "upload"},
        files={"file": ("not-a-video.exe", b"whatever", "application/octet-stream")},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_project_upload_rejects_non_video_content(client, auth_headers, monkeypatch):
    """A .mp4-named file that isn't actually playable media is rejected via ffprobe."""
    monkeypatch.setattr(
        project_service,
        "probe_media",
        MagicMock(side_effect=MediaProbeError("no video stream")),
    )
    response = _upload(client, auth_headers)
    assert response.status_code == 422
    assert "not a valid video" in response.json()["message"]


def test_create_project_upload_rejects_oversized_file(client, auth_headers, monkeypatch):
    monkeypatch.setattr(project_service, "MAX_UPLOAD_SIZE_BYTES", 5)
    response = _upload(client, auth_headers)
    assert response.status_code == 422
    assert "exceeds the maximum" in response.json()["message"]


# --- create: URL (YouTube) ------------------------------------------------


def test_create_project_youtube_url(client, auth_headers):
    response = client.post(
        "/api/v1/projects",
        data={
            "title": "From YouTube",
            "source_type": "url",
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "url"
    assert body["source_file_path"] is None


def test_create_project_youtu_be_url(client, auth_headers):
    response = client.post(
        "/api/v1/projects",
        data={
            "title": "Short link",
            "source_type": "url",
            "source_url": "https://youtu.be/dQw4w9WgXcQ",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://example.com/video.mp4",
        "https://vimeo.com/12345",
        "https://www.youtube.com/playlist?list=PLxyz",
        "not-a-url-at-all",
    ],
)
def test_create_project_rejects_unsupported_urls(client, auth_headers, bad_url):
    response = client.post(
        "/api/v1/projects",
        data={"title": "Bad", "source_type": "url", "source_url": bad_url},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_project_url_missing_source_url(client, auth_headers):
    response = client.post(
        "/api/v1/projects", data={"title": "Bad", "source_type": "url"}, headers=auth_headers
    )
    assert response.status_code == 422


# --- list / get ------------------------------------------------------------


def test_list_projects(client, auth_headers):
    client.post(
        "/api/v1/projects",
        data={"title": "P1", "source_type": "url", "source_url": "https://youtu.be/aaaaaaaaaaa"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/projects",
        data={"title": "P2", "source_type": "url", "source_url": "https://youtu.be/bbbbbbbbbbb"},
        headers=auth_headers,
    )
    response = client.get("/api/v1/projects", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_project(client, auth_headers):
    create = client.post(
        "/api/v1/projects",
        data={"title": "Solo", "source_type": "url", "source_url": "https://youtu.be/ccccccccccc"},
        headers=auth_headers,
    )
    project_id = create.json()["id"]

    response = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == project_id


def test_get_project_not_found(client, auth_headers):
    response = client.get("/api/v1/projects/999999", headers=auth_headers)
    assert response.status_code == 404


def test_get_project_not_owned(client, db, other_user, auth_headers):
    other_project = Project(
        user_id=other_user.id,
        title="Not yours",
        source_type=SourceType.url,
        source_url="https://youtu.be/ddddddddddd",
        status=ProjectStatus.pending,
    )
    db.add(other_project)
    db.commit()
    db.refresh(other_project)

    response = client.get(f"/api/v1/projects/{other_project.id}", headers=auth_headers)
    assert response.status_code == 403


# --- delete ------------------------------------------------------------


def test_delete_project(client, auth_headers):
    create = client.post(
        "/api/v1/projects",
        data={"title": "ToDelete", "source_type": "url", "source_url": "https://youtu.be/eeeeeeeeeee"},
        headers=auth_headers,
    )
    project_id = create.json()["id"]

    response = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert response.status_code == 204

    follow_up = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert follow_up.status_code == 404


# --- process / jobs ---------------------------------------------------------


def test_process_project_queues_task(client, auth_headers, mock_transcribe_delay):
    create = client.post(
        "/api/v1/projects",
        data={"title": "ToProcess", "source_type": "url", "source_url": "https://youtu.be/fffffffffff"},
        headers=auth_headers,
    )
    project_id = create.json()["id"]

    response = client.post(f"/api/v1/projects/{project_id}/process", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "transcribing"
    mock_transcribe_delay.assert_called_once_with(project_id)


def test_process_project_already_processing_conflicts(client, auth_headers, mock_transcribe_delay):
    create = client.post(
        "/api/v1/projects",
        data={"title": "Busy", "source_type": "url", "source_url": "https://youtu.be/ggggggggggg"},
        headers=auth_headers,
    )
    project_id = create.json()["id"]
    client.post(f"/api/v1/projects/{project_id}/process", headers=auth_headers)

    response = client.post(f"/api/v1/projects/{project_id}/process", headers=auth_headers)
    assert response.status_code == 409


def test_process_project_rejects_when_over_quota(
    client, db, auth_headers, test_user, mock_transcribe_delay
):
    create = client.post(
        "/api/v1/projects",
        data={"title": "Quota", "source_type": "url", "source_url": "https://youtu.be/hhhhhhhhhhh"},
        headers=auth_headers,
    )
    project_id = create.json()["id"]

    # Push the user well over the free-tier monthly minutes limit.
    db.add(
        UsageRecord(
            user_id=test_user.id, project_id=None, minutes_processed=10_000.0, clips_generated=0
        )
    )
    db.commit()

    response = client.post(f"/api/v1/projects/{project_id}/process", headers=auth_headers)
    assert response.status_code == 402
    mock_transcribe_delay.assert_not_called()


def test_process_project_enqueue_failure_marks_project_failed(client, db, auth_headers):
    create = client.post(
        "/api/v1/projects",
        data={"title": "Broker down", "source_type": "url", "source_url": "https://youtu.be/iiiiiiiiiii"},
        headers=auth_headers,
    )
    project_id = create.json()["id"]

    import app.tasks as tasks_module

    def _boom(_project_id):
        raise ConnectionError("redis unavailable")

    original = tasks_module.transcribe_project.delay
    tasks_module.transcribe_project.delay = _boom
    try:
        response = client.post(f"/api/v1/projects/{project_id}/process", headers=auth_headers)
    finally:
        tasks_module.transcribe_project.delay = original

    assert response.status_code == 503

    project = db.query(Project).filter(Project.id == project_id).first()
    assert project.status == ProjectStatus.failed
    assert project.error_message


def test_reprocessing_clears_previous_clips_and_usage(
    client, db, test_user, auth_headers, mock_transcribe_delay
):
    create = client.post(
        "/api/v1/projects",
        data={"title": "Redo", "source_type": "url", "source_url": "https://youtu.be/jjjjjjjjjjj"},
        headers=auth_headers,
    )
    project_id = create.json()["id"]

    # Simulate leftovers from a prior completed run.
    old_clip = Clip(
        project_id=project_id,
        user_id=test_user.id,
        title="Stale clip",
        start_time=0.0,
        end_time=50.0,
        status=ClipStatus.ready,
    )
    db.add(old_clip)
    db.add(
        UsageRecord(
            user_id=test_user.id, project_id=project_id, minutes_processed=1.0, clips_generated=1
        )
    )
    db.commit()

    response = client.post(f"/api/v1/projects/{project_id}/process", headers=auth_headers)
    assert response.status_code == 200

    assert db.query(Clip).filter(Clip.project_id == project_id).count() == 0
    assert db.query(UsageRecord).filter(UsageRecord.project_id == project_id).count() == 0


def test_list_jobs(client, db, auth_headers, mock_transcribe_delay):
    create = client.post(
        "/api/v1/projects",
        data={"title": "WithJobs", "source_type": "url", "source_url": "https://youtu.be/kkkkkkkkkkk"},
        headers=auth_headers,
    )
    project_id = create.json()["id"]

    job = ProcessingJob(
        project_id=project_id, job_type=JobType.transcription, status=JobStatus.queued
    )
    db.add(job)
    db.commit()

    response = client.get(f"/api/v1/projects/{project_id}/jobs", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["job_type"] == "transcription"
