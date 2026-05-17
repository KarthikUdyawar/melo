"""Unit tests for META-2: POST /songs/preview

Tests cover:
- extract_youtube_id: all URL formats, invalid cases
- POST /songs/preview: success, DownloadError → 502, invalid URL → 422
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.downloader import DownloadError, extract_youtube_id

VALID_ID = "dQw4w9WgXcQ"


# ── extract_youtube_id ────────────────────────────────────────────────────────


class TestExtractYoutubeId:
    @pytest.mark.parametrize(
        "url",
        [
            f"https://www.youtube.com/watch?v={VALID_ID}",
            f"https://youtube.com/watch?v={VALID_ID}",
            f"https://youtu.be/{VALID_ID}",
            f"https://www.youtube.com/shorts/{VALID_ID}",
            f"https://www.youtube.com/embed/{VALID_ID}",
            f"https://www.youtube.com/live/{VALID_ID}",
            f"https://www.youtube.com/watch?v={VALID_ID}&list=PLxxx",
            f"http://www.youtube.com/watch?v={VALID_ID}",
        ],
    )
    def test_extracts_known_formats(self, url: str) -> None:
        assert extract_youtube_id(url) == VALID_ID

    def test_raises_on_non_youtube_domain(self) -> None:
        with pytest.raises(ValueError, match="Invalid YouTube domain"):
            extract_youtube_id("https://vimeo.com/123456")

    def test_raises_on_no_video_id(self) -> None:
        with pytest.raises(ValueError):
            extract_youtube_id("https://www.youtube.com/")

    def test_raises_on_watch_no_v_param(self) -> None:
        with pytest.raises(ValueError):
            extract_youtube_id("https://www.youtube.com/watch?list=PLxxx")


# ── POST /songs/preview (integration via TestClient) ─────────────────────────

FAKE_META = {
    "title": "Never Gonna Give You Up",
    "duration": 213.0,
    "thumbnail_url": "https://img.youtube.com/vi/dQw4w9WgXcQ/default.jpg",
    "channel": "RickAstleyVEVO",
    "upload_date": "20091025",
}

VALID_URL = f"https://www.youtube.com/watch?v={VALID_ID}"


class TestPreviewEndpoint:
    def test_success_returns_200(self, client) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=FAKE_META):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        assert resp.status_code == 200

    def test_envelope_shape(self, client) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=FAKE_META):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        body = resp.json()
        assert body["status_code"] == 200
        assert "Metadata fetched" in body["message"]
        assert "body" in body

    def test_response_fields(self, client) -> None:
        with patch("app.services.downloader.probe_metadata", return_value=FAKE_META):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        data = resp.json()["body"]
        assert data["youtube_id"] == VALID_ID
        assert data["title"] == "Never Gonna Give You Up"
        assert data["duration"] == 213.0
        assert data["channel"] == "RickAstleyVEVO"
        assert data["upload_date"] == "20091025"
        assert "thumbnail_url" in data

    def test_invalid_url_returns_422(self, client) -> None:
        resp = client.post("/songs/preview", json={"url": "https://vimeo.com/123"})
        assert resp.status_code == 422

    def test_download_error_returns_502(self, client) -> None:
        with patch(
            "app.services.downloader.probe_metadata",
            side_effect=DownloadError("video unavailable"),
        ):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        assert resp.status_code == 502
        assert "video unavailable" in resp.json()["message"]

    def test_no_db_write(self, client, db_session) -> None:
        """Preview must not create Song records."""
        from app.models.song import Song

        with patch("app.services.downloader.probe_metadata", return_value=FAKE_META):
            client.post("/songs/preview", json={"url": VALID_URL})

        count = db_session.query(Song).count()
        assert count == 0

    def test_sparse_metadata_ok(self, client) -> None:
        """Probe returning minimal fields must not crash."""
        sparse = {"title": "Test", "duration": 60.0}
        with patch("app.services.downloader.probe_metadata", return_value=sparse):
            resp = client.post("/songs/preview", json={"url": VALID_URL})
        assert resp.status_code == 200
        data = resp.json()["body"]
        assert data["thumbnail_url"] is None
        assert data["channel"] is None
