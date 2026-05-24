"""Unit tests for app/services/downloader.py

yt-dlp is fully mocked — no network calls.
Tests cover:
- probe_metadata: success, yt-dlp error, unexpected error, empty info
- download_audio: success, yt-dlp error, missing output file
- _build_youtube_id extraction (via song create indirectly)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from app.services.downloader import DownloadError, download_audio, probe_metadata

FAKE_INFO = {
    "title": "Never Gonna Give You Up",
    "duration": 213.0,
    "thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/default.jpg",
    "channel": "RickAstleyVEVO",
    "upload_date": "20091025",
}

TEST_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


# ── probe_metadata ────────────────────────────────────────────────────────────


class TestProbeMetadata:
    def test_success(self) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = FAKE_INFO

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            meta = probe_metadata(TEST_URL)

        assert meta.get("title") == "Never Gonna Give You Up"
        assert meta.get("duration") == 213.0
        assert meta.get("channel") == "RickAstleyVEVO"
        assert meta.get("upload_date") == "20091025"
        assert "thumbnail_url" in meta

    def test_maps_thumbnail_key(self) -> None:
        info = {**FAKE_INFO, "thumbnail": "https://example.com/thumb.jpg"}
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = info

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            meta = probe_metadata(TEST_URL)

        assert meta.get("thumbnail_url") == "https://example.com/thumb.jpg"

    def test_falls_back_to_uploader_when_no_channel(self) -> None:
        info = {**FAKE_INFO, "channel": None, "uploader": "Rick Astley"}
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = info

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            meta = probe_metadata(TEST_URL)

        assert meta.get("channel") == "Rick Astley"

    def test_raises_download_error_on_yt_dlp_error(self) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = YtDlpDownloadError("video unavailable")

        with (
            patch("yt_dlp.YoutubeDL", return_value=mock_ydl),
            pytest.raises(DownloadError, match="yt-dlp probe failed"),
        ):
            probe_metadata(TEST_URL)

    def test_raises_download_error_on_unexpected_exception(self) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = RuntimeError("network error")

        with (
            patch("yt_dlp.YoutubeDL", return_value=mock_ydl),
            pytest.raises(DownloadError, match="Unexpected error probing"),
        ):
            probe_metadata(TEST_URL)

    def test_raises_when_info_is_none(self) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = None

        with (
            patch("yt_dlp.YoutubeDL", return_value=mock_ydl),
            pytest.raises(DownloadError, match="no info"),
        ):
            probe_metadata(TEST_URL)

    def test_optional_fields_can_be_none(self) -> None:
        sparse_info = {"title": "Test", "duration": 60.0}
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = sparse_info

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            meta = probe_metadata(TEST_URL)

        assert meta.get("title") == "Test"
        assert meta.get("thumbnail_url") is None
        assert meta.get("channel") is None


# ── download_audio ────────────────────────────────────────────────────────────


class TestDownloadAudio:
    def test_success(self, tmp_path: Path) -> None:
        song_id = "abc-123"
        expected_path = tmp_path / f"{song_id}.mp3"
        expected_path.write_bytes(b"\xff\xfb" * 512)

        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {**FAKE_INFO}

        with (
            patch("yt_dlp.YoutubeDL", return_value=mock_ydl),
            patch("app.services.downloader._DOWNLOAD_DIR", tmp_path),
        ):
            path, duration = download_audio(url=TEST_URL, song_id=song_id)

        assert path == expected_path
        assert duration == 213.0

    def test_duration_none_when_info_missing(self, tmp_path: Path) -> None:
        song_id = "no-duration"
        (tmp_path / f"{song_id}.mp3").write_bytes(b"\xff\xfb" * 512)

        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = None

        with (
            patch("yt_dlp.YoutubeDL", return_value=mock_ydl),
            patch("app.services.downloader._DOWNLOAD_DIR", tmp_path),
        ):
            path, duration = download_audio(url=TEST_URL, song_id=song_id)

        assert duration is None

    def test_raises_on_yt_dlp_error(self, tmp_path: Path) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = YtDlpDownloadError("age restricted")

        with (
            patch("yt_dlp.YoutubeDL", return_value=mock_ydl),
            patch("app.services.downloader._DOWNLOAD_DIR", tmp_path),
            pytest.raises(DownloadError, match="yt-dlp failed"),
        ):
            download_audio(url=TEST_URL, song_id="fail-song")

    def test_raises_on_unexpected_error(self, tmp_path: Path) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = OSError("disk full")

        with (
            patch("yt_dlp.YoutubeDL", return_value=mock_ydl),
            patch("app.services.downloader._DOWNLOAD_DIR", tmp_path),
            pytest.raises(DownloadError, match="Unexpected error"),
        ):
            download_audio(url=TEST_URL, song_id="fail-song")

    def test_raises_when_output_missing(self, tmp_path: Path) -> None:
        """yt-dlp succeeds but output file never appears."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = FAKE_INFO

        with (
            patch("yt_dlp.YoutubeDL", return_value=mock_ydl),
            patch("app.services.downloader._DOWNLOAD_DIR", tmp_path),
            pytest.raises(DownloadError, match="Expected output file not found"),
        ):
            download_audio(url=TEST_URL, song_id="missing-output")
