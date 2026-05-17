"""tests/unit/test_playlist_schemas.py — Unit tests for playlist schemas."""

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.playlist import PlaylistCreate, PlaylistResponse, PlaylistSongAdd


class TestPlaylistCreate:
    def test_valid_name(self) -> None:
        p = PlaylistCreate(name="My Playlist")
        assert p.name == "My Playlist"

    def test_strips_whitespace(self) -> None:
        p = PlaylistCreate(name="  Chill Vibes  ")
        assert p.name == "Chill Vibes"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError, match="must not be empty"):
            PlaylistCreate(name="")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValidationError, match="must not be empty"):
            PlaylistCreate(name="   ")

    def test_name_too_long_raises(self) -> None:
        with pytest.raises(ValidationError, match="255 characters"):
            PlaylistCreate(name="x" * 256)

    def test_name_max_length_ok(self) -> None:
        p = PlaylistCreate(name="x" * 255)
        assert len(p.name) == 255


class TestPlaylistSongAdd:
    def test_no_position_defaults_none(self) -> None:
        p = PlaylistSongAdd()
        assert p.position is None

    def test_valid_position(self) -> None:
        p = PlaylistSongAdd(position=3)
        assert p.position == 3

    def test_zero_position_ok(self) -> None:
        p = PlaylistSongAdd(position=0)
        assert p.position == 0

    def test_negative_position_raises(self) -> None:
        with pytest.raises(ValidationError, match=">= 0"):
            PlaylistSongAdd(position=-1)


class TestPlaylistResponse:
    def test_serializes_correctly(self) -> None:
        pid = uuid.uuid4()
        r = PlaylistResponse(
            id=pid,
            name="Workout",
            created_at="2024-01-01T00:00:00",
            song_count=5,
        )
        data = r.model_dump(mode="json")
        assert data["id"] == str(pid)
        assert data["name"] == "Workout"
        assert data["song_count"] == 5

    def test_song_count_defaults_zero(self) -> None:
        r = PlaylistResponse(
            id=uuid.uuid4(),
            name="Empty",
            created_at="2024-01-01T00:00:00",
        )
        assert r.song_count == 0
