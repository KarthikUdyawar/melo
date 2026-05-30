"""Integration tests for POST /songs/preview (META-2).

Uses a real Postgres DB (via pytest-docker) and FastAPI TestClient.
yt-dlp is always mocked — no network calls.

Tests cover:
- Happy path: envelope shape, all fields, youtube_id extraction
- URL format variants (shorts, embed, live, youtu.be)
- Validation: non-YouTube domain, missing url field
- Error path: DownloadError → 502 with envelope body: null
- Stateless guarantee: zero Song rows after any preview call
- Idempotency: two preview calls → still zero rows
- Missing body → 422 envelope
- Extra fields in request body are ignored
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.song import Song
from app.services.downloader import DownloadError

VALID_ID = "dQw4w9WgXcQ"
VALID_URL = f"https://www.youtube.com/watch?v={VALID_ID}"

FULL_META = {
    "title": "Never Gonna Give You Up",
    "duration": 213.0,
    "thumbnail_url": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
    "channel": "RickAstleyVEVO",
    "upload_date": "20091025",
}

SPARSE_META: dict[str, object] = {
    "title": "Sparse Video",
    "duration": 42.0,
    "thumbnail_url": None,
    "channel": None,
    "upload_date": None,
}


# ── Happy path ────────────────────────────────────────────────────────────────


class TestPreviewHappyPath:
    def test_status_200(self, client: TestClient) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=FULL_META):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        assert resp.status_code == 200

    def test_envelope_top_level_keys(self, client: TestClient) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=FULL_META):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        body = resp.json()
        assert set(body.keys()) >= {"status_code", "message", "body"}
        assert body["status_code"] == 200
        assert body["body"] is not None

    def test_all_metadata_fields_present(self, client: TestClient) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=FULL_META):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        data = resp.json()["body"]
        assert data["youtube_id"] == VALID_ID
        assert data["title"] == FULL_META["title"]
        assert data["duration"] == FULL_META["duration"]
        assert data["thumbnail_url"] == FULL_META["thumbnail_url"]
        assert data["channel"] == FULL_META["channel"]
        assert data["upload_date"] == "2009-10-25"

    def test_youtube_id_extracted_correctly(self, client: TestClient) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=FULL_META):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        assert resp.json()["body"]["youtube_id"] == VALID_ID

    def test_sparse_meta_nulls_returned(self, client: TestClient) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=SPARSE_META):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        data = resp.json()["body"]
        assert data["thumbnail_url"] is None
        assert data["channel"] is None
        assert data["upload_date"] is None
        assert data["title"] == "Sparse Video"

    def test_message_content(self, client: TestClient) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=FULL_META):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        assert "fetched" in resp.json()["message"].lower()


# ── URL format variants ───────────────────────────────────────────────────────


class TestPreviewUrlFormats:
    @pytest.mark.parametrize(
        "url, expected_id",
        [
            (f"https://youtu.be/{VALID_ID}", VALID_ID),
            (f"https://www.youtube.com/shorts/{VALID_ID}", VALID_ID),
            (f"https://www.youtube.com/embed/{VALID_ID}", VALID_ID),
            (f"https://www.youtube.com/live/{VALID_ID}", VALID_ID),
            (f"https://www.youtube.com/watch?v={VALID_ID}&list=PLxxx", VALID_ID),
            (f"https://youtube.com/watch?v={VALID_ID}", VALID_ID),
        ],
    )
    def test_url_format_accepted(
        self, client: TestClient, url: str, expected_id: str,
    ) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=FULL_META):
            resp = client.post("/songs/preview", json={"url": url})
        assert resp.status_code == 200
        assert resp.json()["body"]["youtube_id"] == expected_id


# ── Validation errors ─────────────────────────────────────────────────────────


class TestPreviewValidation:
    def test_non_youtube_url_returns_422(self, client: TestClient) -> None:
        resp = client.post("/songs/preview", json={"url": "https://vimeo.com/123456"})
        assert resp.status_code == 422

    def test_empty_url_returns_422(self, client: TestClient) -> None:
        resp = client.post("/songs/preview", json={"url": ""})
        assert resp.status_code == 422

    def test_missing_url_field_returns_422(self, client: TestClient) -> None:
        resp = client.post("/songs/preview", json={})
        assert resp.status_code == 422

    def test_missing_body_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/songs/preview",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_plain_text_url_returns_422(self, client: TestClient) -> None:
        resp = client.post("/songs/preview", json={"url": "not-a-url"})
        assert resp.status_code == 422

    def test_youtube_homepage_returns_422(self, client: TestClient) -> None:
        resp = client.post("/songs/preview", json={"url": "https://www.youtube.com/"})
        assert resp.status_code == 422

    def test_extra_fields_ignored(self, client: TestClient) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=FULL_META):
            resp = client.post(
                "/songs/preview",
                json={"url": VALID_URL, "start": 10, "speed": 2.0, "bogus": "x"},
            )
        assert resp.status_code == 200

    def test_422_response_has_envelope_shape(self, client: TestClient) -> None:
        resp = client.post("/songs/preview", json={"url": "https://vimeo.com/123"})
        body = resp.json()
        # Global exception handler wraps validation errors in envelope
        assert "status_code" in body
        assert body["body"] is None


# ── Error paths ───────────────────────────────────────────────────────────────


class TestPreviewErrors:
    def test_download_error_returns_502(self, client: TestClient) -> None:
        with patch(
            "app.services.downloader.probe_metadata",
            side_effect=DownloadError("video unavailable"),
        ):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        assert resp.status_code == 502

    def test_502_envelope_body_contains_error(self, client: TestClient) -> None:
        with patch(
            "app.services.downloader.probe_metadata",
            side_effect=DownloadError("age restricted"),
        ):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        body = resp.json()
        assert "age restricted" in body["message"]

    def test_502_envelope_body_is_null(self, client: TestClient) -> None:
        with patch(
            "app.services.downloader.probe_metadata",
            side_effect=DownloadError("private video"),
        ):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        assert resp.json()["body"] is None

    def test_unexpected_error_returns_500(self, client: TestClient) -> None:
        with patch(
            "app.services.downloader.probe_metadata",
            side_effect=RuntimeError("unexpected boom"),
        ):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        assert resp.status_code == 500


# ── Stateless guarantee ───────────────────────────────────────────────────────


class TestPreviewStateless:
    def test_no_song_row_created_on_success(
        self, client: TestClient, db_session: Session,
    ) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=FULL_META):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        assert resp.status_code == 200
        assert db_session.query(Song).count() == 0

    def test_no_song_row_created_on_502(
        self, client: TestClient, db_session: Session,
    ) -> None:
        with patch(
            "app.services.downloader.probe_metadata",
            side_effect=DownloadError("unavailable"),
        ):
            client.post("/songs/preview", json={"url": VALID_URL})
        assert db_session.query(Song).count() == 0

    def test_idempotent_multiple_calls(
        self, client: TestClient, db_session: Session,
    ) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=FULL_META):
            client.post("/songs/preview", json={"url": VALID_URL})
            client.post("/songs/preview", json={"url": VALID_URL})
            client.post("/songs/preview", json={"url": VALID_URL})
        assert db_session.query(Song).count() == 0

    def test_preview_does_not_affect_existing_songs(
        self, client: TestClient, db_session: Session,
    ) -> None:
        """Preview must not disturb pre-existing Song rows."""
        existing = Song(
            youtube_id=VALID_ID,
            status="done",  # type: ignore[arg-type]
            speed=1.0,
            file_url="songs/existing.mp3",
        )
        db_session.add(existing)
        db_session.flush()

        with patch("app.services.downloader.probe_metadata", return_value=FULL_META):
            resp = client.post("/songs/preview", json={"url": VALID_URL})

        assert resp.status_code == 200
        # Still exactly 1 row — our pre-existing one
        assert db_session.query(Song).count() == 1
        assert db_session.query(Song).one().id == existing.id
        assert db_session.query(Song).one().youtube_id == VALID_ID
