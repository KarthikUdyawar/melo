"""
Unit tests for app/schemas/song.py

Tests cover:
- SongCreate URL validation (valid and invalid formats)
- SongCreate speed validation (bounds + edge cases)
- SongCreate trim range validation (start/end logic)
- SongResponse construction from dict
"""

import pytest
from pydantic import ValidationError

from app.schemas.song import SongCreate, SongResponse

# ── URL validation ────────────────────────────────────────────────────────────

VALID_URLS = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    "https://www.youtube.com/embed/dQw4w9WgXcQ",
    # With playlist param — validator extracts video ID
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxxx",
    # Leading/trailing whitespace — validator strips it
    "  https://www.youtube.com/watch?v=dQw4w9WgXcQ  ",
]

INVALID_URLS = [
    "https://vimeo.com/123456789",
    "https://example.com/watch?v=dQw4w9WgXcQ",
    "not-a-url",
    "",
    "https://youtube.com/",  # no video ID
    "https://www.youtube.com/watch",  # no v param
]


@pytest.mark.parametrize("url", VALID_URLS)
def test_song_create_valid_url(url: str) -> None:
    song = SongCreate(url=url)
    assert song.url.startswith("http")  # stripped


@pytest.mark.parametrize("url", INVALID_URLS)
def test_song_create_invalid_url(url: str) -> None:
    with pytest.raises(ValidationError, match="url"):
        SongCreate(url=url)


# ── Speed validation ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("speed", [0.5, 1.0, 2.0, 4.0])
def test_song_create_speed_boundary_valid(speed: float) -> None:
    song = SongCreate(url="https://youtu.be/dQw4w9WgXcQ", speed=speed)
    assert song.speed == speed


@pytest.mark.parametrize("speed", [0.49, 4.01, 0.0, -1.0, 5.0, 100.0])
def test_song_create_speed_out_of_range(speed: float) -> None:
    with pytest.raises(ValidationError, match="speed"):
        SongCreate(url="https://youtu.be/dQw4w9WgXcQ", speed=speed)


def test_song_create_speed_default() -> None:
    song = SongCreate(url="https://youtu.be/dQw4w9WgXcQ")
    assert song.speed == 1.0


# ── Trim range validation ─────────────────────────────────────────────────────


def test_song_create_trim_valid() -> None:
    song = SongCreate(url="https://youtu.be/dQw4w9WgXcQ", start=10.0, end=60.0)
    assert song.start == 10.0
    assert song.end == 60.0


def test_song_create_trim_start_only() -> None:
    song = SongCreate(url="https://youtu.be/dQw4w9WgXcQ", start=5.0)
    assert song.start == 5.0
    assert song.end is None


def test_song_create_trim_end_only() -> None:
    song = SongCreate(url="https://youtu.be/dQw4w9WgXcQ", end=30.0)
    assert song.end == 30.0
    assert song.start is None


def test_song_create_start_negative() -> None:
    with pytest.raises(ValidationError, match="start"):
        SongCreate(url="https://youtu.be/dQw4w9WgXcQ", start=-1.0)


def test_song_create_end_zero() -> None:
    with pytest.raises(ValidationError, match="end"):
        SongCreate(url="https://youtu.be/dQw4w9WgXcQ", end=0.0)


def test_song_create_end_negative() -> None:
    with pytest.raises(ValidationError, match="end"):
        SongCreate(url="https://youtu.be/dQw4w9WgXcQ", end=-5.0)


def test_song_create_start_equals_end() -> None:
    with pytest.raises(ValidationError, match="start must be less than end"):
        SongCreate(url="https://youtu.be/dQw4w9WgXcQ", start=30.0, end=30.0)


def test_song_create_start_greater_than_end() -> None:
    with pytest.raises(ValidationError, match="start must be less than end"):
        SongCreate(url="https://youtu.be/dQw4w9WgXcQ", start=60.0, end=30.0)


def test_song_create_no_trim() -> None:
    song = SongCreate(url="https://youtu.be/dQw4w9WgXcQ")
    assert song.start is None
    assert song.end is None


# ── SongResponse ──────────────────────────────────────────────────────────────


def test_song_response_minimal() -> None:
    import uuid

    song_id = uuid.uuid4()
    resp = SongResponse(
        id=song_id,
        status="pending",
        created_at="2024-01-01T00:00:00+00:00",
    )
    assert resp.id == song_id
    assert resp.status == "pending"
    assert resp.speed == 1.0
    assert resp.title is None


def test_song_response_full() -> None:
    import uuid

    resp = SongResponse(
        id=uuid.uuid4(),
        title="Rick Astley - Never Gonna Give You Up",
        youtube_id="dQw4w9WgXcQ",
        file_url="songs/abc-123.mp3",
        duration=213.0,
        start=10.0,
        end=60.0,
        speed=1.5,
        status="done",
        thumbnail_url="https://img.youtube.com/vi/dQw4w9WgXcQ/default.jpg",
        channel="RickAstleyVEVO",
        upload_date="20091025",
        created_at="2024-01-01T00:00:00+00:00",
    )
    assert resp.speed == 1.5
    assert resp.duration == 213.0
    assert resp.upload_date == "20091025"
