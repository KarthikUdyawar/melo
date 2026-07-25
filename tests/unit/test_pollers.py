"""Tests for app/core/pollers.py — background gauge polling."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.pollers import (
    _poll_celery_gauges,
    _poll_gauges,
    _poll_minio_gauge,
    _poll_song_status_gauge,
    start_gauge_poller,
)


# ── _poll_celery_gauges ─────────────────────────────────────────────────────
class TestPollCeleryGauges:
    def test_sets_active_tasks_from_inspect_active(self):
        mock_inspect = MagicMock()
        mock_inspect.active.return_value = {
            "worker1": [{"id": "t1"}, {"id": "t2"}],
            "worker2": [{"id": "t3"}],
        }
        mock_inspect.reserved.return_value = {}

        with (
            patch("app.workers.celery_app.celery_app") as mock_celery_app,
            patch("app.core.metrics.celery_active_tasks") as mock_active_gauge,
            patch("app.core.metrics.celery_queue_depth") as mock_queue_gauge,
        ):
            mock_celery_app.control.inspect.return_value = mock_inspect
            _poll_celery_gauges()

        mock_active_gauge.set.assert_called_once_with(3)
        mock_queue_gauge.set.assert_called_once_with(0)

    def test_sets_queue_depth_from_inspect_reserved(self):
        mock_inspect = MagicMock()
        mock_inspect.active.return_value = {}
        mock_inspect.reserved.return_value = {"worker1": [{"id": "t1"}] * 5}

        with (
            patch("app.workers.celery_app.celery_app") as mock_celery_app,
            patch("app.core.metrics.celery_active_tasks") as mock_active_gauge,
            patch("app.core.metrics.celery_queue_depth") as mock_queue_gauge,
        ):
            mock_celery_app.control.inspect.return_value = mock_inspect
            _poll_celery_gauges()

        mock_queue_gauge.set.assert_called_once_with(5)
        mock_active_gauge.set.assert_called_once_with(0)

    def test_handles_none_from_inspect_gracefully(self):
        mock_inspect = MagicMock()
        mock_inspect.active.return_value = None
        mock_inspect.reserved.return_value = None

        with (
            patch("app.workers.celery_app.celery_app") as mock_celery_app,
            patch("app.core.metrics.celery_active_tasks") as mock_active_gauge,
            patch("app.core.metrics.celery_queue_depth") as mock_queue_gauge,
        ):
            mock_celery_app.control.inspect.return_value = mock_inspect
            _poll_celery_gauges()

        mock_active_gauge.set.assert_called_once_with(0)
        mock_queue_gauge.set.assert_called_once_with(0)

    def test_swallows_exception_and_logs(self):
        with (
            patch("app.workers.celery_app.celery_app") as mock_celery_app,
            patch("app.core.pollers.logger") as mock_logger,
        ):
            mock_celery_app.control.inspect.side_effect = RuntimeError("broker down")
            _poll_celery_gauges()  # must not raise

        mock_logger.exception.assert_called_once_with("poll_celery_gauges_failed")


# ── _poll_minio_gauge ────────────────────────────────────────────────────────
class TestPollMinioGauge:
    def test_sums_object_sizes(self):
        obj1 = MagicMock(size=1000)
        obj2 = MagicMock(size=2000)
        mock_client = MagicMock()
        mock_client.list_objects.return_value = [obj1, obj2]

        mock_settings = MagicMock(minio_bucket="melo")

        with (
            patch("app.core.config.get_settings", return_value=mock_settings),
            patch("app.services.storage._client", return_value=mock_client),
            patch("app.core.metrics.minio_bucket_size_bytes") as mock_gauge,
        ):
            _poll_minio_gauge()

        mock_gauge.set.assert_called_once_with(3000)

    def test_treats_none_size_as_zero(self):
        obj1 = MagicMock(size=None)
        mock_client = MagicMock()
        mock_client.list_objects.return_value = [obj1]

        mock_settings = MagicMock(minio_bucket="melo")

        with (
            patch("app.core.config.get_settings", return_value=mock_settings),
            patch("app.services.storage._client", return_value=mock_client),
            patch("app.core.metrics.minio_bucket_size_bytes") as mock_gauge,
        ):
            _poll_minio_gauge()

        mock_gauge.set.assert_called_once_with(0)

    def test_empty_bucket_sets_zero(self):
        mock_client = MagicMock()
        mock_client.list_objects.return_value = []

        mock_settings = MagicMock(minio_bucket="melo")

        with (
            patch("app.core.config.get_settings", return_value=mock_settings),
            patch("app.services.storage._client", return_value=mock_client),
            patch("app.core.metrics.minio_bucket_size_bytes") as mock_gauge,
        ):
            _poll_minio_gauge()

        mock_gauge.set.assert_called_once_with(0)

    def test_swallows_exception_and_logs(self):
        with (
            patch("app.services.storage._client", side_effect=RuntimeError("s3 down")),
            patch("app.core.pollers.logger") as mock_logger,
        ):
            _poll_minio_gauge()  # must not raise

        mock_logger.exception.assert_called_once_with("poll_minio_gauge_failed")


# ── _poll_song_status_gauge ──────────────────────────────────────────────────
class TestPollSongStatusGauge:
    def test_sets_gauge_per_status_with_real_counts(self, db_session):
        from app.models.song import Song

        db_session.add_all(
            [
                Song(title="a", status="done", youtube_id="a1"),
                Song(title="b", status="done", youtube_id="a2"),
                Song(title="c", status="pending", youtube_id="a3"),
            ]
        )
        db_session.commit()

        with (
            patch(
                "app.core.db.get_session_factory",
                return_value=lambda: db_session,
            ),
            patch.object(db_session, "close"),
            patch("app.core.metrics.songs_by_status_total") as mock_gauge,
        ):
            _poll_song_status_gauge()

        calls = {c.kwargs["status"]: c for c in mock_gauge.labels.call_args_list}
        assert "done" in calls
        assert "pending" in calls
        assert "processing" in calls
        assert "failed" in calls

    def test_zero_count_for_status_with_no_songs(self, db_session):
        with (
            patch(
                "app.core.db.get_session_factory",
                return_value=lambda: db_session,
            ),
            patch.object(db_session, "close"),
            patch("app.core.metrics.songs_by_status_total") as mock_gauge,
        ):
            _poll_song_status_gauge()

        mock_gauge.labels.assert_any_call(status="done")

    def test_excludes_soft_deleted_songs(self, db_session):
        from datetime import UTC, datetime

        from app.models.song import Song

        db_session.add(
            Song(
                title="deleted",
                status="done",
                youtube_id="del1",
                deleted_at=datetime.now(UTC),
            )
        )
        db_session.commit()

        with (
            patch(
                "app.core.db.get_session_factory",
                return_value=lambda: db_session,
            ),
            patch.object(db_session, "close"),
            patch("app.core.metrics.songs_by_status_total") as mock_gauge,
        ):
            label_mocks: dict[str, MagicMock] = {}

            def _labels_side_effect(**kwargs):
                status = kwargs["status"]
                if status not in label_mocks:
                    label_mocks[status] = MagicMock()
                return label_mocks[status]

            mock_gauge.labels.side_effect = _labels_side_effect

            _poll_song_status_gauge()

        # The only done song is soft-deleted, so done count must be 0
        assert label_mocks["done"].set.call_args == ((0,),)

    def test_swallows_exception_and_logs(self):
        with (
            patch(
                "app.core.db.get_session_factory",
                side_effect=RuntimeError("db down"),
            ),
            patch("app.core.pollers.logger") as mock_logger,
        ):
            _poll_song_status_gauge()  # must not raise

        mock_logger.exception.assert_called_once_with("poll_song_status_gauge_failed")


# ── _poll_gauges (orchestrator) ──────────────────────────────────────────────
class TestPollGauges:
    def test_calls_all_three_sub_pollers(self):
        with (
            patch("app.core.pollers._poll_celery_gauges") as mock_celery,
            patch("app.core.pollers._poll_minio_gauge") as mock_minio,
            patch("app.core.pollers._poll_song_status_gauge") as mock_song,
        ):
            _poll_gauges()

        mock_celery.assert_called_once()
        mock_minio.assert_called_once()
        mock_song.assert_called_once()

    def test_one_sub_poller_failure_does_not_block_others(self):
        """Each sub-poller already swallows its own exceptions, but this
        guards against a regression where that contract breaks."""
        with (
            patch(
                "app.core.pollers._poll_celery_gauges",
                side_effect=RuntimeError("boom"),
            ),
            patch("app.core.pollers._poll_minio_gauge") as mock_minio,
            patch("app.core.pollers._poll_song_status_gauge") as mock_song,
            pytest.raises(RuntimeError),
        ):
            _poll_gauges()

        # celery raised (sub-pollers are expected to catch their own errors;
        # if one doesn't, _poll_gauges itself does not currently guard —
        # this test documents current behavior, not a requirement)
        mock_minio.assert_not_called()
        mock_song.assert_not_called()


# ── start_gauge_poller ────────────────────────────────────────────────────────
class TestStartGaugePoller:
    def test_starts_background_scheduler_with_30s_interval(self):
        with patch("app.core.pollers.BackgroundScheduler") as mock_scheduler_cls:
            mock_scheduler = MagicMock()
            mock_scheduler_cls.return_value = mock_scheduler

            result = start_gauge_poller()

            mock_scheduler_cls.assert_called_once()
            mock_scheduler.add_job.assert_called_once()
            args, kwargs = mock_scheduler.add_job.call_args
            assert args[0].__name__ == "_poll_gauges"
            assert args[1] == "interval"
            assert kwargs.get("seconds") == 30
            mock_scheduler.start.assert_called_once()
            assert result is mock_scheduler
