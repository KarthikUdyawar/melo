"""Integration tests for Song model + DB layer.

Uses a real Postgres container (via pytest-docker).
Each test runs in a rolled-back transaction.

Tests cover:
- Song creation with defaults
- Status transitions
- Dedup query (find existing done record by youtube_id)
- Multiple songs with same youtube_id (different trim)
- Ordering / filtering queries
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.song import Song, SongStatus


def _make_song(
    youtube_id: str = "dQw4w9WgXcQ",
    status: SongStatus = SongStatus.pending,
    speed: float = 1.0,
    start: float | None = None,
    end: float | None = None,
    file_url: str | None = None,
) -> Song:
    return Song(
        youtube_id=youtube_id,
        status=status,
        speed=speed,
        start=start,
        end=end,
        file_url=file_url,
    )


class TestSongModel:
    def test_create_song_defaults(self, db_session: Session) -> None:
        song = _make_song()
        db_session.add(song)
        db_session.flush()

        assert song.id is not None
        assert isinstance(song.id, uuid.UUID)
        assert song.status == SongStatus.pending
        assert song.speed == 1.0
        assert song.title is None
        assert song.file_url is None
        assert song.created_at is not None

    def test_status_transition(self, db_session: Session) -> None:
        song = _make_song()
        db_session.add(song)
        db_session.flush()

        song.status = SongStatus.processing
        db_session.flush()
        assert song.status == SongStatus.processing

        song.status = SongStatus.done
        song.file_url = "songs/test.mp3"
        db_session.flush()
        assert song.status == SongStatus.done

    def test_all_status_values(self, db_session: Session) -> None:
        for status in SongStatus:
            song = _make_song(youtube_id=f"test_{status.value}")
            song.status = status
            db_session.add(song)
        db_session.flush()

        results = db_session.query(Song).all()
        statuses = {s.status for s in results}
        assert SongStatus.pending in statuses
        assert SongStatus.done in statuses

    def test_metadata_fields(self, db_session: Session) -> None:
        song = _make_song()
        song.title = "Never Gonna Give You Up"
        song.duration = 213.0
        song.thumbnail_url = "https://example.com/thumb.jpg"
        song.channel = "RickAstleyVEVO"
        song.upload_date = "20091025"
        db_session.add(song)
        db_session.flush()

        fetched = db_session.query(Song).filter(Song.id == song.id).first()
        assert fetched is not None
        assert fetched.title == "Never Gonna Give You Up"
        assert fetched.duration == 213.0
        assert fetched.channel == "RickAstleyVEVO"

    def test_trim_fields(self, db_session: Session) -> None:
        song = _make_song(start=10.0, end=60.0)
        db_session.add(song)
        db_session.flush()

        fetched = db_session.query(Song).filter(Song.id == song.id).first()
        assert fetched is not None
        assert fetched.start == 10.0
        assert fetched.end == 60.0

    def test_speed_stored(self, db_session: Session) -> None:
        song = _make_song(speed=2.0)
        db_session.add(song)
        db_session.flush()

        fetched = db_session.query(Song).filter(Song.id == song.id).first()
        assert fetched is not None
        assert fetched.speed == 2.0


class TestDedupQuery:
    """Tests for the dedup pattern used in tasks.py."""

    def test_finds_existing_done_record(self, db_session: Session) -> None:
        done_song = _make_song(status=SongStatus.done, file_url="songs/orig.mp3")
        db_session.add(done_song)
        db_session.flush()

        new_song = _make_song(start=10.0, end=60.0)  # same youtube_id, different trim
        db_session.add(new_song)
        db_session.flush()

        existing = (
            db_session.query(Song)
            .filter(
                Song.youtube_id == new_song.youtube_id,
                Song.status == SongStatus.done,
                Song.id != new_song.id,
            )
            .first()
        )

        assert existing is not None
        assert existing.id == done_song.id
        assert existing.file_url == "songs/orig.mp3"

    def test_no_dedup_hit_when_none_done(self, db_session: Session) -> None:
        processing_song = _make_song(status=SongStatus.processing)
        db_session.add(processing_song)
        new_song = _make_song(start=5.0)
        db_session.add(new_song)
        db_session.flush()

        existing = (
            db_session.query(Song)
            .filter(
                Song.youtube_id == new_song.youtube_id,
                Song.status == SongStatus.done,
                Song.id != new_song.id,
            )
            .first()
        )

        assert existing is None

    def test_dedup_does_not_return_self(self, db_session: Session) -> None:
        song = _make_song(status=SongStatus.done, file_url="songs/x.mp3")
        db_session.add(song)
        db_session.flush()

        existing = (
            db_session.query(Song)
            .filter(
                Song.youtube_id == song.youtube_id,
                Song.status == SongStatus.done,
                Song.id != song.id,  # exclude self
            )
            .first()
        )

        assert existing is None

    def test_multiple_done_records_same_youtube_id(self, db_session: Session) -> None:
        """Multiple done rows for same video (different trims) — dedup returns one."""
        for i in range(3):
            s = _make_song(
                status=SongStatus.done,
                file_url=f"songs/variant_{i}.mp3",
                start=float(i * 10),
                end=float(i * 10 + 30),
            )
            db_session.add(s)
        db_session.flush()

        new_song = _make_song(start=100.0, end=200.0)
        db_session.add(new_song)
        db_session.flush()

        existing = (
            db_session.query(Song)
            .filter(
                Song.youtube_id == new_song.youtube_id,
                Song.status == SongStatus.done,
                Song.id != new_song.id,
            )
            .first()
        )

        assert existing is not None

    def test_dedup_ignores_soft_deleted_done_record(self, db_session: Session) -> None:
        deleted_done = _make_song(status=SongStatus.done, file_url="songs/deleted.mp3")
        deleted_done.deleted_at = datetime.now(UTC)
        db_session.add(deleted_done)
        new_song = _make_song(start=12.0, end=45.0)
        db_session.add(new_song)
        db_session.flush()

        existing = (
            db_session.query(Song)
            .filter(
                Song.youtube_id == new_song.youtube_id,
                Song.status == SongStatus.done,
                Song.deleted_at.is_(None),
                Song.id != new_song.id,
            )
            .first()
        )
        assert existing is None


class TestSongQueries:
    def test_list_all_ordered_by_created_at_desc(self, db_session: Session) -> None:
        for i in range(5):
            db_session.add(_make_song(youtube_id=f"vid_{i:04d}"))
        db_session.flush()

        songs = db_session.query(Song).order_by(Song.created_at.desc()).all()
        assert len(songs) >= 5

    def test_filter_by_status(self, db_session: Session) -> None:
        db_session.add(
            _make_song(status=SongStatus.done, youtube_id="done1", file_url="x.mp3"),
        )
        db_session.add(
            _make_song(status=SongStatus.done, youtube_id="done2", file_url="y.mp3"),
        )
        db_session.add(_make_song(status=SongStatus.pending, youtube_id="pend1"))
        db_session.flush()

        done = db_session.query(Song).filter(Song.status == SongStatus.done).all()
        assert all(s.status == SongStatus.done for s in done)
        assert len([s for s in done if s.youtube_id in ("done1", "done2")]) == 2

    def test_lookup_by_id(self, db_session: Session) -> None:
        song = _make_song()
        db_session.add(song)
        db_session.flush()

        fetched = db_session.query(Song).filter(Song.id == song.id).first()
        assert fetched is not None
        assert fetched.id == song.id

    def test_returns_none_for_missing_id(self, db_session: Session) -> None:
        missing = db_session.query(Song).filter(Song.id == uuid.uuid4()).first()
        assert missing is None
