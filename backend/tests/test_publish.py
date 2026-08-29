"""Tests for the export & publish module.

Publishing itself is MVP-disabled (see app/services/publish_service.py) --
connecting a platform account and publishing/scheduling a clip both return
501 rather than a fabricated success, so nothing here can be mistaken for a
real working integration. Connection listing/deletion and clip download
still work normally.
"""
from datetime import datetime, timezone

import pytest

from app.models.clip import Clip, ClipStatus
from app.models.publish_connection import Platform, PublishConnection
from app.services.crypto_service import encrypt_token


@pytest.fixture
def ready_clip(db, test_user):
    """A clip in `ready` status with a video file path set."""
    clip = Clip(
        project_id=1,
        user_id=test_user.id,
        title="Test Clip",
        start_time=0.0,
        end_time=30.0,
        status=ClipStatus.ready,
        video_file_path="does-not-exist-on-disk.mp4",
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


@pytest.fixture
def queued_clip(db, test_user):
    """A clip that has not finished rendering yet."""
    clip = Clip(
        project_id=1,
        user_id=test_user.id,
        title="Not Ready Clip",
        start_time=0.0,
        end_time=30.0,
        status=ClipStatus.queued,
        video_file_path=None,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


@pytest.fixture
def tiktok_connection(db, test_user):
    """A connected TikTok account for the test user."""
    connection = PublishConnection(
        user_id=test_user.id,
        platform=Platform.tiktok,
        access_token=encrypt_token("fake-access-token"),
        refresh_token=encrypt_token("fake-refresh-token"),
        account_handle="testhandle",
        connected_at=datetime.now(timezone.utc),
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


class TestConnections:
    def test_connect_is_not_implemented(self, client, auth_headers):
        """Connecting a platform account is MVP-disabled -- 501, not a fake authorize URL."""
        response = client.post("/api/v1/publish/connections/tiktok", headers=auth_headers)
        assert response.status_code == 501
        assert response.json()["code"] == "NOT_IMPLEMENTED"

    def test_connect_unknown_platform_404s(self, client, auth_headers):
        response = client.post("/api/v1/publish/connections/not-a-platform", headers=auth_headers)
        assert response.status_code == 404

    def test_list_connections(self, client, auth_headers, tiktok_connection):
        response = client.get("/api/v1/publish/connections", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["platform"] == "tiktok"
        assert body[0]["account_handle"] == "testhandle"
        # Tokens must never be exposed via the API.
        assert "access_token" not in body[0]
        assert "refresh_token" not in body[0]

    def test_delete_connection(self, client, auth_headers, tiktok_connection):
        response = client.delete(
            f"/api/v1/publish/connections/{tiktok_connection.id}", headers=auth_headers
        )
        assert response.status_code == 204

        remaining = client.get("/api/v1/publish/connections", headers=auth_headers).json()
        assert remaining == []

    def test_delete_missing_connection_404s(self, client, auth_headers):
        response = client.delete("/api/v1/publish/connections/999999", headers=auth_headers)
        assert response.status_code == 404


class TestPublish:
    def test_publish_is_not_implemented(self, client, auth_headers, ready_clip):
        """Publishing (immediate) never creates a ScheduledPost or fake success."""
        response = client.post(
            f"/api/v1/clips/{ready_clip.id}/publish",
            json={"platform": "tiktok"},
            headers=auth_headers,
        )
        assert response.status_code == 501
        assert response.json()["code"] == "NOT_IMPLEMENTED"

    def test_publish_scheduled_is_also_not_implemented(self, client, auth_headers, ready_clip):
        """Scheduling is disabled too -- nothing would ever process a scheduled post."""
        response = client.post(
            f"/api/v1/clips/{ready_clip.id}/publish",
            json={"platform": "tiktok", "scheduled_at": "2030-01-01T00:00:00Z"},
            headers=auth_headers,
        )
        assert response.status_code == 501

    def test_publish_unknown_platform_404s(self, client, auth_headers, ready_clip):
        response = client.post(
            f"/api/v1/clips/{ready_clip.id}/publish",
            json={"platform": "not-a-platform"},
            headers=auth_headers,
        )
        assert response.status_code == 422  # rejected by the Literal-typed schema


class TestDownload:
    def test_download_404s_when_clip_not_ready(self, client, auth_headers, queued_clip):
        response = client.get(f"/api/v1/clips/{queued_clip.id}/download", headers=auth_headers)
        assert response.status_code == 404

    def test_download_404s_when_file_missing_on_disk(self, client, auth_headers, ready_clip):
        # ready_clip has status=ready but points at a nonexistent file path.
        response = client.get(f"/api/v1/clips/{ready_clip.id}/download", headers=auth_headers)
        assert response.status_code == 404

    def test_download_requires_ownership(self, client, other_user_auth_headers, ready_clip):
        response = client.get(
            f"/api/v1/clips/{ready_clip.id}/download", headers=other_user_auth_headers
        )
        assert response.status_code == 404  # scoped by user_id at the query level


class TestThumbnail:
    def test_thumbnail_404s_when_missing(self, client, auth_headers, ready_clip):
        response = client.get(f"/api/v1/clips/{ready_clip.id}/thumbnail", headers=auth_headers)
        assert response.status_code == 404

    def test_thumbnail_requires_ownership(self, client, other_user_auth_headers, ready_clip):
        response = client.get(
            f"/api/v1/clips/{ready_clip.id}/thumbnail", headers=other_user_auth_headers
        )
        assert response.status_code == 404
