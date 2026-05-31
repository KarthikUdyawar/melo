"""Integration tests for GET/POST /songs endpoints.

Uses a real Postgres DB (via pytest-docker) and FastAPI TestClient.
Celery tasks are mocked — no workers needed.
MinIO is mocked for stream tests.

Tests cover:
- POST /songs: 202, invalid URL, invalid speed, dedup path
- GET /songs: empty list, populated list, envelope shape
- GET /songs/{id}: found, not found
- GET /songs/{id}/stream: direct stream, not found, not ready
- DELETE /songs/{id}: soft delete, 404
- API-3: stream_url, effective_duration, upload_date normalization
- GET /health
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.song import Song, SongStatus

# ── helpers ───────────────────────────────────────────────────────────────────

VALID_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def mock_processor():
    with (
        patch("app.api.songs.trim_audio") as m_trim,
        patch("app.api.songs.apply_speed") as m_speed,
        patch("app.api.songs._client") as m_minio,
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.unlink"),
    ):
        mock_res = MagicMock()
        mock_res.stream.return_value = [b"data"]
        m_minio.return_value.get_object.return_value = mock_res
        yield {"trim": m_trim, "speed": m_speed}


def _seed_done_song(db: Session, **kwargs) -> Song:  # type: ignore[no-untyped-def]
    song = Song(
        youtube_id=kwargs.get("youtube_id", "dQw4w9WgXcQ"),
        status=SongStatus.done,
        file_url=kwargs.get("file_url", "dQw4w9WgXcQ.mp3"),
        title=kwargs.get("title", "Never Gonna Give You Up"),
        duration=kwargs.get("duration", 213.0),
        speed=kwargs.get("speed", 1.0),
        start=kwargs.get("start"),
        end=kwargs.get("end"),
        upload_date=kwargs.get("upload_date"),
    )
    db.add(song)
    db.flush()
    return song


def _seed_pending_song(db: Session) -> Song:
    song = Song(youtube_id="dQw4w9WgXcQ", status=SongStatus.pending, speed=1.0)
    db.add(song)
    db.flush()
    return song


# ── POST /songs ───────────────────────────────────────────────────────────────


class TestCreateSong:
    def test_returns_202_accepted(self, client: TestClient) -> None:
        with patch("app.workers.tasks.process_song_task.delay"):
            resp = client.post("/songs", json={"url": VALID_URL})
        assert resp.status_code == 202

    def test_envelope_shape(self, client: TestClient) -> None:
        with patch("app.workers.tasks.process_song_task.delay"):
            resp = client.post("/songs", json={"url": VALID_URL})
        body = resp.json()
        assert "status_code" in body
        assert "message" in body
        assert "body" in body
        assert body["body"]["status"] == "pending"

    def test_returns_song_id(self, client: TestClient) -> None:
        with patch("app.workers.tasks.process_song_task.delay"):
            resp = client.post("/songs", json={"url": VALID_URL})
        body = resp.json()["body"]
        assert uuid.UUID(body["id"])

    def test_invalid_url_returns_422(self, client: TestClient) -> None:
        resp = client.post("/songs", json={"url": "https://vimeo.com/123"})
        assert resp.status_code == 422

    def test_invalid_speed_returns_422(self, client: TestClient) -> None:
        resp = client.post("/songs", json={"url": VALID_URL, "speed": 10.0})
        assert resp.status_code == 422

    def test_speed_below_min_returns_422(self, client: TestClient) -> None:
        resp = client.post("/songs", json={"url": VALID_URL, "speed": 0.1})
        assert resp.status_code == 422

    def test_start_after_end_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/songs", json={"url": VALID_URL, "start": 60.0, "end": 10.0}
        )
        assert resp.status_code == 422

    def test_dispatches_celery_task(self, client: TestClient) -> None:
        with patch("app.workers.tasks.process_song_task.delay") as mock_delay:
            resp = client.post("/songs", json={"url": VALID_URL})
        assert resp.status_code == 202
        mock_delay.assert_called_once()

    def test_with_trim_and_speed(self, client: TestClient) -> None:
        with patch("app.workers.tasks.process_song_task.delay"):
            resp = client.post(
                "/songs",
                json={"url": VALID_URL, "start": 10.0, "end": 60.0, "speed": 1.5},
            )
        assert resp.status_code == 202
        body = resp.json()["body"]
        assert body["start"] == 10.0
        assert body["end"] == 60.0
        assert body["speed"] == 1.5

    def test_missing_url_returns_422(self, client: TestClient) -> None:
        resp = client.post("/songs", json={"speed": 1.0})
        assert resp.status_code == 422

    def test_response_has_stream_url(self, client: TestClient) -> None:
        with patch("app.workers.tasks.process_song_task.delay"):
            resp = client.post("/songs", json={"url": VALID_URL})
        body = resp.json()["body"]
        # pending → stream_url points to /songs/{id} (not /stream)
        assert "stream_url" in body
        assert "/stream" not in body["stream_url"]


# ── GET /songs ────────────────────────────────────────────────────────────────


class TestListSongs:
    def test_empty_list(self, client: TestClient) -> None:
        resp = client.get("/songs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["body"]["records"] == []
        assert body["body"]["count"] == 0

    def test_returns_all_songs(self, client: TestClient, db_session: Session) -> None:
        _seed_done_song(db_session, youtube_id="vid1")
        _seed_done_song(db_session, youtube_id="vid2")
        resp = client.get("/songs")
        assert resp.status_code == 200
        records = resp.json()["body"]["records"]
        assert len(records) >= 2

    def test_envelope_paginated_shape(
        self, client: TestClient, db_session: Session
    ) -> None:
        _seed_done_song(db_session)
        resp = client.get("/songs")
        body = resp.json()
        assert "records" in body["body"]
        assert "count" in body["body"]
        assert isinstance(body["body"]["count"], int)
        assert "bookmark" in body["body"]

    def test_records_contain_expected_fields(
        self, client: TestClient, db_session: Session
    ) -> None:
        _seed_done_song(db_session)
        resp = client.get("/songs")
        record = resp.json()["body"]["records"][0]
        for field in (
            "id",
            "status",
            "youtube_id",
            "created_at",
            "speed",
            "stream_url",
        ):
            assert field in record

    def test_soft_deleted_song_excluded(
        self, client: TestClient, db_session: Session
    ) -> None:
        from datetime import UTC, datetime

        song = _seed_done_song(db_session, youtube_id="deleted1")
        song.deleted_at = datetime.now(UTC)
        db_session.flush()

        resp = client.get("/songs")
        ids = [r["id"] for r in resp.json()["body"]["records"]]
        assert str(song.id) not in ids


# ── GET /songs/{id} ───────────────────────────────────────────────────────────


class TestGetSong:
    def test_found(self, client: TestClient, db_session: Session) -> None:
        song = _seed_done_song(db_session)
        resp = client.get(f"/songs/{song.id}")
        assert resp.status_code == 200
        assert resp.json()["body"]["id"] == str(song.id)

    def test_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get(f"/songs/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_response_fields(self, client: TestClient, db_session: Session) -> None:
        song = _seed_done_song(db_session, title="Test Song", duration=120.0)
        resp = client.get(f"/songs/{song.id}")
        body = resp.json()["body"]
        assert body["title"] == "Test Song"
        assert body["duration"] == 120.0
        assert body["status"] == "done"

    def test_stream_url_done_song(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = _seed_done_song(db_session)
        body = client.get(f"/songs/{song.id}").json()["body"]
        assert body["stream_url"] == f"/songs/{song.id}/stream"

    def test_stream_url_pending_song(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = _seed_pending_song(db_session)
        body = client.get(f"/songs/{song.id}").json()["body"]
        assert body["stream_url"] == f"/songs/{song.id}"
        assert "/stream" not in body["stream_url"]

    def test_effective_duration_with_trim(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = _seed_done_song(db_session, duration=100.0, start=10.0, end=40.0)
        body = client.get(f"/songs/{song.id}").json()["body"]
        assert body["effective_duration"] == 30.0

    def test_effective_duration_no_trim(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = _seed_done_song(db_session, duration=213.0)
        body = client.get(f"/songs/{song.id}").json()["body"]
        assert body["effective_duration"] == 213.0

    def test_upload_date_normalized(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = _seed_done_song(db_session, upload_date="20091025")
        body = client.get(f"/songs/{song.id}").json()["body"]
        assert body["upload_date"] == "2009-10-25"

    def test_soft_deleted_returns_404(
        self, client: TestClient, db_session: Session
    ) -> None:
        from datetime import UTC, datetime

        song = _seed_done_song(db_session)
        song.deleted_at = datetime.now(UTC)
        db_session.flush()

        resp = client.get(f"/songs/{song.id}")
        assert resp.status_code == 404


# ── DELETE /songs/{id} ────────────────────────────────────────────────────────


class TestDeleteSong:
    def test_returns_204(self, client: TestClient, db_session: Session) -> None:
        song = _seed_done_song(db_session)
        with patch("app.api.songs._client"):
            resp = client.delete(f"/songs/{song.id}")
        assert resp.status_code == 204

    def test_sets_deleted_at(self, client: TestClient, db_session: Session) -> None:
        song = _seed_done_song(db_session)
        with patch("app.api.songs._client"):
            client.delete(f"/songs/{song.id}")
        db_session.refresh(song)
        assert song.deleted_at is not None

    def test_deleted_song_not_in_list(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = _seed_done_song(db_session)
        with patch("app.api.songs._client"):
            client.delete(f"/songs/{song.id}")
        ids = [r["id"] for r in client.get("/songs").json()["body"]["records"]]
        assert str(song.id) not in ids

    def test_unknown_song_returns_404(self, client: TestClient) -> None:
        resp = client.delete(f"/songs/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_double_delete_returns_404(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = _seed_done_song(db_session)
        with patch("app.api.songs._client"):
            client.delete(f"/songs/{song.id}")
            resp = client.delete(f"/songs/{song.id}")
        assert resp.status_code == 404

    def test_minio_failure_still_soft_deletes(
        self, client: TestClient, db_session: Session
    ) -> None:
        """MinIO remove failure must not block the soft delete."""
        song = _seed_done_song(db_session)
        with patch("app.api.songs._client") as m:
            m.return_value.remove_object.side_effect = Exception("MinIO down")
            resp = client.delete(f"/songs/{song.id}")
        assert resp.status_code == 204
        db_session.refresh(song)
        assert song.deleted_at is not None


# ── GET /songs/{id}/stream ────────────────────────────────────────────────────


class TestStreamSong:
    def test_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get(f"/songs/{uuid.uuid4()}/stream")
        assert resp.status_code == 404

    def test_pending_song_returns_409(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = _seed_pending_song(db_session)
        resp = client.get(f"/songs/{song.id}/stream")
        assert resp.status_code == 409
        body = resp.json()
        assert "pending" in (body.get("message") or body.get("detail") or "").lower()

    def test_no_file_url_returns_500(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = Song(youtube_id="dQw4w9WgXcQ", status=SongStatus.done, speed=1.0)
        db_session.add(song)
        db_session.flush()
        resp = client.get(f"/songs/{song.id}/stream")
        assert resp.status_code == 500

    def test_direct_stream_no_trim_no_speed(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = _seed_done_song(db_session)
        fake_data = b"\xff\xfb" * 256

        mock_minio = MagicMock()
        presigned_url = "http://minio:9000/songs/test.mp3"
        mock_minio.presigned_get_object.return_value = presigned_url

        # upstream response returned by httpx.Client.stream()
        mock_upstream = MagicMock()
        mock_upstream.status_code = 206
        mock_upstream.headers = {
            "Content-Length": str(len(fake_data)),
            "Content-Range": f"bytes 0-{len(fake_data)-1}/4096",
        }
        mock_upstream.iter_bytes.return_value = [fake_data]

        # context manager returned by stream()
        mock_stream_cm = MagicMock()
        mock_stream_cm.__enter__.return_value = mock_upstream
        mock_stream_cm.__exit__.return_value = None

        # httpx.Client() context manager
        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_cm

        mock_client_cm = MagicMock()
        mock_client_cm.__enter__.return_value = mock_client
        mock_client_cm.__exit__.return_value = None

        range_header = "bytes=0-1023"

        with (
            patch("app.api.songs._client", return_value=mock_minio),
            patch("app.api.songs.trim_audio") as m_trim,
            patch("app.api.songs.apply_speed") as m_speed,
            patch("httpx.Client", return_value=mock_client_cm),
        ):
            resp = client.get(
                f"/songs/{song.id}/stream",
                headers={"Range": range_header},
            )

        assert resp.status_code == 206
        assert (
            resp.headers["content-range"]
            == f"bytes 0-{len(fake_data)-1}/4096"
        )
        assert resp.content == fake_data

        m_trim.assert_not_called()
        m_speed.assert_not_called()

        assert mock_client.stream.call_count == 2

        expected_headers = {"Range": range_header}

        mock_client.stream.assert_any_call(
            "GET",
            presigned_url,
            headers=expected_headers,
            follow_redirects=False,
        )

    def test_stream_processing_song_returns_409(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = Song(youtube_id="dQw4w9WgXcQ", status=SongStatus.processing, speed=1.0)
        db_session.add(song)
        db_session.flush()
        resp = client.get(f"/songs/{song.id}/stream")
        assert resp.status_code == 409

    def test_soft_deleted_song_returns_404(
        self, client: TestClient, db_session: Session
    ) -> None:
        from datetime import UTC, datetime

        song = _seed_done_song(db_session)
        song.deleted_at = datetime.now(UTC)
        db_session.flush()
        resp = client.get(f"/songs/{song.id}/stream")
        assert resp.status_code == 404


# ── GET /health ───────────────────────────────────────────────────────────────


class TestHealth:
    def test_health_returns_200(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_shape(self, client: TestClient) -> None:
        resp = client.get("/health")
        body = resp.json()
        assert body is not None

    def test_health_contains_db_field(self, client: TestClient) -> None:
        resp = client.get("/health")
        body = resp.json()
        # /health is wrapped in envelope_response — status dict is under body.body
        assert "db" in body["body"]


class TestYoutubeExtraction:
    def test_extract_shorts_and_embeds(self, client: TestClient):
        urls = [
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube.com/live/dQw4w9WgXcQ",
        ]
        for url in urls:
            with patch("app.workers.tasks.process_song_task.delay"):
                resp = client.post("/songs", json={"url": url})
                assert resp.status_code == 202, f"Failed for URL: {url}"


class TestStreamProcessing:
    def test_stream_with_trim_and_speed(
        self,
        client: TestClient,
        db_session: Session,
        mock_processor,
    ):
        import os
        from pathlib import Path

        fake_audio = b"processed_audio"
        song = _seed_done_song(db_session, start=10.0, end=20.0, speed=1.5)

        # Use os.makedirs — bypasses the pathlib.Path.mkdir mock in mock_processor
        tmp_dir = "/tmp/melo"
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_speed = Path(f"{tmp_dir}/{song.id}_speed.mp3")
        tmp_speed.write_bytes(fake_audio)

        mock_minio_resp = MagicMock()
        mock_minio_resp.stream.return_value = [b"original"]

        with (
            patch("app.api.songs._client") as m_client,
            patch("pathlib.Path.unlink"),
        ):
            m_client.return_value.get_object.return_value = mock_minio_resp
            resp = client.get(f"/songs/{song.id}/stream")

        assert resp.status_code == 200


class TestSongEdgeCases:
    def test_stream_minio_fetch_error(self, client: TestClient, db_session: Session):
        song = _seed_done_song(db_session)
        with patch("app.api.songs._client") as m_minio:
            m_minio.return_value.presigned_get_object.side_effect = Exception(
                "S3 Connection Refused"
            )
            resp = client.get(f"/songs/{song.id}/stream")
        assert resp.status_code == 502
        body = resp.json()
        error_msg = body.get("detail") or body.get("message") or ""
        assert "S3 Connection Refused" in error_msg


class TestStreamFailures:
    def test_stream_trim_processing_error(self, client, db_session, mock_processor):
        from app.services.processor import ProcessingError

        song = _seed_done_song(db_session, start=0.0, end=10.0)
        mock_processor["trim"].side_effect = ProcessingError("FFmpeg trim failed")
        resp = client.get(f"/songs/{song.id}/stream")
        assert resp.status_code == 502

    def test_stream_speed_processing_error(self, client, db_session, mock_processor):
        from app.services.processor import ProcessingError

        song = _seed_done_song(db_session, speed=2.0)
        mock_processor["speed"].side_effect = ProcessingError("FFmpeg speed failed")
        resp = client.get(f"/songs/{song.id}/stream")
        assert resp.status_code == 502
