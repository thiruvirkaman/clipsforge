"""Tests for clip regeneration validation and media cleanup on deletion."""
from unittest.mock import MagicMock, patch

import pytest

from app.exceptions import ConflictError, ValidationError
from app.models.clip import Clip, ClipStatus
from app.models.project import Project, ProjectStatus, SourceType
from app.services import clip_service


@pytest.fixture()
def project_with_duration(db, test_user) -> Project:
    proj = Project(
        user_id=test_user.id,
        title="Test Project",
        source_type=SourceType.upload,
        source_file_path="source.mp4",
        duration_seconds=120,
        status=ProjectStatus.ready,
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


@pytest.fixture()
def clip(db, project_with_duration, test_user) -> Clip:
    c = Clip(
        project_id=project_with_duration.id,
        user_id=test_user.id,
        title="Clip",
        start_time=10.0,
        end_time=60.0,
        status=ClipStatus.ready,
        video_file_path="clip-video.mp4",
        thumbnail_path="clip-thumb.jpg",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


class TestRegenerationValidation:
    def test_rejects_negative_start_time(self, db, test_user, clip):
        with pytest.raises(ValidationError) as exc_info:
            clip_service.regenerate_clip(db, test_user.id, clip.id, start_time=-5.0)
        assert exc_info.value.status_code == 422

    def test_rejects_end_before_start(self, db, test_user, clip):
        with pytest.raises(ValidationError) as exc_info:
            clip_service.regenerate_clip(
                db, test_user.id, clip.id, start_time=50.0, end_time=40.0
            )
        assert exc_info.value.status_code == 422

    def test_rejects_end_beyond_source_duration(self, db, test_user, clip):
        with pytest.raises(ValidationError) as exc_info:
            clip_service.regenerate_clip(db, test_user.id, clip.id, end_time=500.0)
        assert exc_info.value.status_code == 422

    def test_rejects_unknown_caption_style(self, db, test_user, clip):
        with pytest.raises(ValidationError) as exc_info:
            clip_service.regenerate_clip(db, test_user.id, clip.id, caption_style="comic-sans")
        assert exc_info.value.status_code == 422

    def test_invalid_request_never_enqueues_a_render(self, db, test_user, clip):
        with patch.object(clip_service.render_clip_task, "delay") as mock_delay:
            with pytest.raises(ValidationError):
                clip_service.regenerate_clip(db, test_user.id, clip.id, end_time=-1.0)
            mock_delay.assert_not_called()

    def test_rejects_regeneration_of_an_already_queued_clip(self, db, test_user, clip):
        clip.status = ClipStatus.queued
        db.commit()

        with pytest.raises(ConflictError):
            clip_service.regenerate_clip(db, test_user.id, clip.id, start_time=5.0, end_time=55.0)

    def test_valid_request_updates_and_enqueues(self, db, test_user, clip):
        with patch.object(clip_service.render_clip_task, "delay") as mock_delay:
            updated = clip_service.regenerate_clip(
                db, test_user.id, clip.id, start_time=5.0, end_time=55.0, caption_style="bold"
            )
        assert updated.start_time == 5.0
        assert updated.end_time == 55.0
        assert updated.caption_style == "bold"
        assert updated.status == ClipStatus.queued
        mock_delay.assert_called_once_with(clip.id)


class TestMediaCleanup:
    def test_delete_clip_removes_media_files(self, db, test_user, clip):
        storage = MagicMock()
        with patch("app.services.media_cleanup.get_media_storage", return_value=storage):
            clip_service.delete_clip(db, test_user.id, clip.id)

        storage.delete.assert_any_call("clip-video.mp4")
        storage.delete.assert_any_call("clip-thumb.jpg")
        assert db.query(Clip).filter(Clip.id == clip.id).first() is None

    def test_delete_project_removes_clip_and_source_media(
        self, db, test_user, project_with_duration, clip
    ):
        from app.services import project_service

        storage = MagicMock()
        with patch("app.services.media_cleanup.get_media_storage", return_value=storage):
            project_service.delete_project(db, test_user.id, project_with_duration.id)

        deleted_paths = {call.args[0] for call in storage.delete.call_args_list}
        assert "clip-video.mp4" in deleted_paths
        assert "clip-thumb.jpg" in deleted_paths
        assert "source.mp4" in deleted_paths
        assert db.query(Project).filter(Project.id == project_with_duration.id).first() is None

    def test_delete_clip_skips_file_still_referenced_by_another_clip(
        self, db, test_user, project_with_duration, clip
    ):
        sibling = Clip(
            project_id=project_with_duration.id,
            user_id=test_user.id,
            title="Sibling",
            start_time=70.0,
            end_time=110.0,
            status=ClipStatus.ready,
            video_file_path="clip-video.mp4",  # same stored path as `clip`
        )
        db.add(sibling)
        db.commit()

        storage = MagicMock()
        with patch("app.services.media_cleanup.get_media_storage", return_value=storage):
            clip_service.delete_clip(db, test_user.id, clip.id)

        # The shared video file must not be deleted while `sibling` still
        # references it (thumbnail, unique to `clip`, is still deleted).
        deleted_paths = {call.args[0] for call in storage.delete.call_args_list}
        assert "clip-video.mp4" not in deleted_paths
        assert "clip-thumb.jpg" in deleted_paths
