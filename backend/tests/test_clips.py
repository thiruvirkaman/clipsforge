"""Tests for the clips router: list / get / delete / regenerate.

`render_clip_task.delay` is monkeypatched so these tests don't require a
real Celery worker or broker.
"""
from app.models.clip import Clip, ClipStatus
from app.models.project import Project, ProjectStatus, SourceType


def _make_project(db, user, status: ProjectStatus = ProjectStatus.ready) -> Project:
    project = Project(
        user_id=user.id,
        title="Test Project",
        source_type=SourceType.upload,
        source_file_path="source.mp4",
        status=status,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _make_clip(db, project: Project, user, **overrides) -> Clip:
    defaults = dict(
        project_id=project.id,
        user_id=user.id,
        title="Highlight 1",
        start_time=10.0,
        end_time=70.0,
        transcript_snippet="Something interesting happens here.",
        relevance_score=0.9,
        status=ClipStatus.ready,
    )
    defaults.update(overrides)
    clip = Clip(**defaults)
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


def test_list_clips_for_project(client, db, test_user, auth_headers):
    project = _make_project(db, test_user)
    _make_clip(db, project, test_user, title="Clip A", start_time=0.0, end_time=60.0)
    _make_clip(db, project, test_user, title="Clip B", start_time=100.0, end_time=160.0)

    response = client.get(f"/api/v1/projects/{project.id}/clips", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {c["title"] for c in body} == {"Clip A", "Clip B"}


def test_list_clips_requires_auth(client, db, test_user):
    project = _make_project(db, test_user)

    response = client.get(f"/api/v1/projects/{project.id}/clips")

    assert response.status_code == 401


def test_list_clips_forbidden_for_other_users_project(client, db, other_user, auth_headers):
    project = _make_project(db, other_user)

    response = client.get(f"/api/v1/projects/{project.id}/clips", headers=auth_headers)

    assert response.status_code == 403


def test_list_clips_project_not_found(client, auth_headers):
    response = client.get("/api/v1/projects/999999/clips", headers=auth_headers)

    assert response.status_code == 404


def test_get_clip(client, db, test_user, auth_headers):
    project = _make_project(db, test_user)
    clip = _make_clip(db, project, test_user)

    response = client.get(f"/api/v1/clips/{clip.id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == clip.id
    assert body["status"] == ClipStatus.ready.value


def test_get_clip_forbidden_for_other_users_clip(client, db, other_user, auth_headers):
    project = _make_project(db, other_user)
    clip = _make_clip(db, project, other_user)

    response = client.get(f"/api/v1/clips/{clip.id}", headers=auth_headers)

    assert response.status_code == 403


def test_get_clip_not_found(client, auth_headers):
    response = client.get("/api/v1/clips/999999", headers=auth_headers)

    assert response.status_code == 404


def test_delete_clip(client, db, test_user, auth_headers):
    project = _make_project(db, test_user)
    clip = _make_clip(db, project, test_user)

    response = client.delete(f"/api/v1/clips/{clip.id}", headers=auth_headers)

    assert response.status_code == 204
    assert db.query(Clip).filter(Clip.id == clip.id).first() is None


def test_delete_clip_forbidden_for_other_users_clip(client, db, other_user, auth_headers):
    project = _make_project(db, other_user)
    clip = _make_clip(db, project, other_user)

    response = client.delete(f"/api/v1/clips/{clip.id}", headers=auth_headers)

    assert response.status_code == 403
    assert db.query(Clip).filter(Clip.id == clip.id).first() is not None


def test_regenerate_clip_updates_fields_resets_status_and_reenqueues_render(
    client, db, test_user, auth_headers, monkeypatch
):
    project = _make_project(db, test_user)
    clip = _make_clip(
        db, project, test_user, status=ClipStatus.ready, start_time=5.0, end_time=65.0
    )

    delay_calls: list[int] = []
    monkeypatch.setattr(
        "app.services.clip_service.render_clip_task.delay",
        lambda clip_id: delay_calls.append(clip_id),
    )

    response = client.post(
        f"/api/v1/clips/{clip.id}/regenerate",
        json={"start_time": 12.0, "end_time": 80.0, "caption_style": "bold"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == ClipStatus.queued.value
    assert body["start_time"] == 12.0
    assert body["end_time"] == 80.0
    assert body["caption_style"] == "bold"
    assert delay_calls == [clip.id]


def test_regenerate_clip_without_overrides_keeps_existing_window(
    client, db, test_user, auth_headers, monkeypatch
):
    project = _make_project(db, test_user)
    clip = _make_clip(
        db, project, test_user, status=ClipStatus.failed, start_time=5.0, end_time=65.0
    )

    monkeypatch.setattr("app.services.clip_service.render_clip_task.delay", lambda clip_id: None)

    response = client.post(f"/api/v1/clips/{clip.id}/regenerate", json={}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == ClipStatus.queued.value
    assert body["start_time"] == 5.0
    assert body["end_time"] == 65.0


def test_regenerate_clip_not_found(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.services.clip_service.render_clip_task.delay", lambda clip_id: None)

    response = client.post("/api/v1/clips/999999/regenerate", json={}, headers=auth_headers)

    assert response.status_code == 404
