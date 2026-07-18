"""Unit tests for OBS-2: metric observations in service layer.

Behavior tested:
  5. download_duration_seconds has at least one observation after download_audio()
"""

# tests/unit/test_metrics_unit.py
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_download_duration_seconds_observed_after_download() -> None:
    """download_audio() records an observation in the histogram."""
    from app.core.metrics import download_duration_seconds

    # snapshot count before
    before = download_duration_seconds._sum.get()  # type: ignore[attr-defined]

    fake_info = {
        "title": "Test",
        "duration": 213.0,
        "thumbnail": "http://example.com/thumb.jpg",
        "channel": "TestChannel",
        "upload_date": "2024-01-01",
    }

    with (
        patch("app.services.downloader.yt_dlp.YoutubeDL") as mock_ydl_cls,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.mkdir"),
    ):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = fake_info
        mock_ydl_cls.return_value = mock_ydl

        from app.services.downloader import download_audio

        download_audio("https://youtube.com/watch?v=dQw4w9WgXcQ", "test-song-id")

    after = download_duration_seconds._sum.get()  # type: ignore[attr-defined]
    assert after > before, "download_duration_seconds should have been observed"
