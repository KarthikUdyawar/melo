"""
tests/integration/test_playlists_api.py
Integration tests for LIB-2: Playlists endpoints (Postgres-backed).

Vertical slices (TDD order):
1. POST /playlists → 201
2. GET /playlists → list
3. GET /playlists/{id} → detail + 404
4. POST /playlists/{id}/songs/{song_id} → adds song
5. Idempotent add → 200, no dupe
6. DELETE /playlists/{id}/songs/{song_id} → 204
7. DELETE /playlists/{id} → 204 cascade
8. Same song in multiple playlists
9. Position ordering preserved
"""

from __future__ import annotations

import uuid
from datetime import UTC

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.playlist import Playlist, PlaylistSong
from app.models.song import Song, SongStatus


def _make_song(
    db_session: Session, youtube_id: str = "dQw4w9WgXcQ", title: str = "Test Song"
) -> Song:
    song = Song(
        youtube_id=youtube_id,
        status=SongStatus.done,
        speed=1.0,
        title=title,
        file_url="songs/test.mp3",
    )
    db_session.add(song)
    db_session.flush()
    return song


def _make_playlist(db_session: Session, name: str = "Test Playlist") -> Playlist:
    playlist = Playlist(name=name)
    db_session.add(playlist)
    db_session.flush()
    return playlist


class TestCreatePlaylist:
    def test_returns_201(self, client: TestClient, db_session: Session) -> None:
        resp = client.post("/playlists", json={"name": "My Playlist"})
        assert resp.status_code == 201

    def test_response_shape(self, client: TestClient, db_session: Session) -> None:
        resp = client.post("/playlists", json={"name": "My Playlist"})
        body = resp.json()["body"]
        assert body["name"] == "My Playlist"
        assert "id" in body
        assert "created_at" in body
        assert body["song_count"] == 0

    def test_creates_db_row(self, client: TestClient, db_session: Session) -> None:
        client.post("/playlists", json={"name": "DB Check"})
        count = db_session.query(Playlist).filter(Playlist.name == "DB Check").count()
        assert count == 1

    def test_empty_name_422(self, client: TestClient, db_session: Session) -> None:
        resp = client.post("/playlists", json={"name": ""})
        assert resp.status_code == 422

    def test_whitespace_name_422(self, client: TestClient, db_session: Session) -> None:
        resp = client.post("/playlists", json={"name": "   "})
        assert resp.status_code == 422

    def test_missing_name_422(self, client: TestClient, db_session: Session) -> None:
        resp = client.post("/playlists", json={})
        assert resp.status_code == 422


class TestListPlaylists:
    def test_empty_list(self, client: TestClient, db_session: Session) -> None:
        resp = client.get("/playlists")
        assert resp.status_code == 200
        body = resp.json()["body"]
        assert body["count"] == 0
        assert body["records"] == []

    def test_returns_created_playlist(
        self, client: TestClient, db_session: Session
    ) -> None:
        _make_playlist(db_session, "Listed")
        resp = client.get("/playlists")
        records = resp.json()["body"]["records"]
        assert len(records) == 1
        assert records[0]["name"] == "Listed"

    def test_multiple_playlists_ordered_desc(
        self, client: TestClient, db_session: Session
    ) -> None:
        from datetime import datetime

        p1 = Playlist(
            name="First", created_at=datetime(2024, 1, 1, tzinfo=UTC)
        )
        p2 = Playlist(
            name="Second", created_at=datetime(2024, 1, 2, tzinfo=UTC)
        )
        db_session.add_all([p1, p2])
        db_session.flush()
        records = client.get("/playlists").json()["body"]["records"]
        names = [r["name"] for r in records]
        assert names.index("Second") < names.index("First")

    def test_song_count_in_list(self, client: TestClient, db_session: Session) -> None:
        playlist = _make_playlist(db_session)
        song = _make_song(db_session)
        client.post(f"/playlists/{playlist.id}/songs/{song.id}")
        records = client.get("/playlists").json()["body"]["records"]
        assert records[0]["song_count"] == 1


class TestGetPlaylist:
    def test_404_unknown(self, client: TestClient, db_session: Session) -> None:
        resp = client.get(f"/playlists/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_returns_playlist_detail(
        self, client: TestClient, db_session: Session
    ) -> None:
        playlist = _make_playlist(db_session, "Detail Test")
        resp = client.get(f"/playlists/{playlist.id}")
        assert resp.status_code == 200
        body = resp.json()["body"]
        assert body["name"] == "Detail Test"
        assert body["songs"] == []

    def test_includes_songs(self, client: TestClient, db_session: Session) -> None:
        playlist = _make_playlist(db_session)
        song = _make_song(db_session, title="In Playlist")
        client.post(f"/playlists/{playlist.id}/songs/{song.id}")
        body = client.get(f"/playlists/{playlist.id}").json()["body"]
        assert len(body["songs"]) == 1
        assert body["songs"][0]["title"] == "In Playlist"

    def test_songs_have_is_favorite(
        self, client: TestClient, db_session: Session
    ) -> None:
        playlist = _make_playlist(db_session)
        song = _make_song(db_session)
        client.post(f"/playlists/{playlist.id}/songs/{song.id}")
        body = client.get(f"/playlists/{playlist.id}").json()["body"]
        assert "is_favorite" in body["songs"][0]


class TestAddSongToPlaylist:
    def test_returns_201(self, client: TestClient, db_session: Session) -> None:
        playlist = _make_playlist(db_session)
        song = _make_song(db_session)
        resp = client.post(f"/playlists/{playlist.id}/songs/{song.id}")
        assert resp.status_code == 201

    def test_creates_association(self, client: TestClient, db_session: Session) -> None:
        playlist = _make_playlist(db_session)
        song = _make_song(db_session)
        client.post(f"/playlists/{playlist.id}/songs/{song.id}")
        count = (
            db_session.query(PlaylistSong)
            .filter(
                PlaylistSong.playlist_id == playlist.id,
                PlaylistSong.song_id == song.id,
            )
            .count()
        )
        assert count == 1

    def test_idempotent_no_dupe(self, client: TestClient, db_session: Session) -> None:
        playlist = _make_playlist(db_session)
        song = _make_song(db_session)
        client.post(f"/playlists/{playlist.id}/songs/{song.id}")
        resp = client.post(f"/playlists/{playlist.id}/songs/{song.id}")
        assert resp.status_code == 200
        count = (
            db_session.query(PlaylistSong)
            .filter(PlaylistSong.playlist_id == playlist.id)
            .count()
        )
        assert count == 1

    def test_unknown_playlist_404(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = _make_song(db_session)
        resp = client.post(f"/playlists/{uuid.uuid4()}/songs/{song.id}")
        assert resp.status_code == 404

    def test_unknown_song_404(self, client: TestClient, db_session: Session) -> None:
        playlist = _make_playlist(db_session)
        resp = client.post(f"/playlists/{playlist.id}/songs/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_song_count_increments(
        self, client: TestClient, db_session: Session
    ) -> None:
        playlist = _make_playlist(db_session)
        s1 = _make_song(db_session, youtube_id="aaaaaaaaaaa")
        s2 = _make_song(db_session, youtube_id="bbbbbbbbbbb")
        client.post(f"/playlists/{playlist.id}/songs/{s1.id}")
        resp = client.post(f"/playlists/{playlist.id}/songs/{s2.id}")
        assert resp.json()["body"]["song_count"] == 2


class TestPositionOrdering:
    def test_songs_ordered_by_position(
        self, client: TestClient, db_session: Session
    ) -> None:
        playlist = _make_playlist(db_session)
        s1 = _make_song(db_session, youtube_id="aaaaaaaaaaa", title="First")
        s2 = _make_song(db_session, youtube_id="bbbbbbbbbbb", title="Second")
        s3 = _make_song(db_session, youtube_id="ccccccccccc", title="Third")
        client.post(f"/playlists/{playlist.id}/songs/{s1.id}")
        client.post(f"/playlists/{playlist.id}/songs/{s2.id}")
        client.post(f"/playlists/{playlist.id}/songs/{s3.id}")
        songs = client.get(f"/playlists/{playlist.id}").json()["body"]["songs"]
        assert [s["title"] for s in songs] == ["First", "Second", "Third"]

    def test_positions_assigned_sequentially(
        self, client: TestClient, db_session: Session
    ) -> None:
        playlist = _make_playlist(db_session)
        s1 = _make_song(db_session, youtube_id="aaaaaaaaaaa")
        s2 = _make_song(db_session, youtube_id="bbbbbbbbbbb")
        client.post(f"/playlists/{playlist.id}/songs/{s1.id}")
        client.post(f"/playlists/{playlist.id}/songs/{s2.id}")
        entries = (
            db_session.query(PlaylistSong)
            .filter(PlaylistSong.playlist_id == playlist.id)
            .order_by(PlaylistSong.position)
            .all()
        )
        assert entries[0].position == 0
        assert entries[1].position == 1


class TestRemoveSongFromPlaylist:
    def test_returns_204(self, client: TestClient, db_session: Session) -> None:
        playlist = _make_playlist(db_session)
        song = _make_song(db_session)
        client.post(f"/playlists/{playlist.id}/songs/{song.id}")
        resp = client.delete(f"/playlists/{playlist.id}/songs/{song.id}")
        assert resp.status_code == 204

    def test_removes_association(self, client: TestClient, db_session: Session) -> None:
        playlist = _make_playlist(db_session)
        song = _make_song(db_session)
        client.post(f"/playlists/{playlist.id}/songs/{song.id}")
        client.delete(f"/playlists/{playlist.id}/songs/{song.id}")
        count = (
            db_session.query(PlaylistSong)
            .filter(PlaylistSong.playlist_id == playlist.id)
            .count()
        )
        assert count == 0

    def test_not_in_playlist_404(self, client: TestClient, db_session: Session) -> None:
        playlist = _make_playlist(db_session)
        song = _make_song(db_session)
        resp = client.delete(f"/playlists/{playlist.id}/songs/{song.id}")
        assert resp.status_code == 404

    def test_unknown_playlist_404(
        self, client: TestClient, db_session: Session
    ) -> None:
        song = _make_song(db_session)
        resp = client.delete(f"/playlists/{uuid.uuid4()}/songs/{song.id}")
        assert resp.status_code == 404

    def test_unknown_song_404(self, client: TestClient, db_session: Session) -> None:
        playlist = _make_playlist(db_session)
        resp = client.delete(f"/playlists/{playlist.id}/songs/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestDeletePlaylist:
    def test_returns_204(self, client: TestClient, db_session: Session) -> None:
        playlist = _make_playlist(db_session)
        resp = client.delete(f"/playlists/{playlist.id}")
        assert resp.status_code == 204

    def test_removes_from_db(self, client: TestClient, db_session: Session) -> None:
        playlist = _make_playlist(db_session)
        pid = playlist.id
        client.delete(f"/playlists/{playlist.id}")
        assert db_session.query(Playlist).filter(Playlist.id == pid).first() is None

    def test_cascades_song_associations(
        self, client: TestClient, db_session: Session
    ) -> None:
        playlist = _make_playlist(db_session)
        song = _make_song(db_session)
        client.post(f"/playlists/{playlist.id}/songs/{song.id}")
        client.delete(f"/playlists/{playlist.id}")
        count = (
            db_session.query(PlaylistSong)
            .filter(PlaylistSong.playlist_id == playlist.id)
            .count()
        )
        assert count == 0

    def test_unknown_playlist_404(
        self, client: TestClient, db_session: Session
    ) -> None:
        resp = client.delete(f"/playlists/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_after_delete_404(
        self, client: TestClient, db_session: Session
    ) -> None:
        playlist = _make_playlist(db_session)
        client.delete(f"/playlists/{playlist.id}")
        resp = client.get(f"/playlists/{playlist.id}")
        assert resp.status_code == 404


class TestSongInMultiplePlaylists:
    def test_same_song_in_two_playlists(
        self, client: TestClient, db_session: Session
    ) -> None:
        p1 = _make_playlist(db_session, "P1")
        p2 = _make_playlist(db_session, "P2")
        song = _make_song(db_session)
        assert client.post(f"/playlists/{p1.id}/songs/{song.id}").status_code == 201
        assert client.post(f"/playlists/{p2.id}/songs/{song.id}").status_code == 201
        assert client.get(f"/playlists/{p1.id}").json()["body"]["songs"][0][
            "id"
        ] == str(song.id)
        assert client.get(f"/playlists/{p2.id}").json()["body"]["songs"][0][
            "id"
        ] == str(song.id)

    def test_delete_from_one_playlist_leaves_other(
        self, client: TestClient, db_session: Session
    ) -> None:
        p1 = _make_playlist(db_session, "P1")
        p2 = _make_playlist(db_session, "P2")
        song = _make_song(db_session)
        client.post(f"/playlists/{p1.id}/songs/{song.id}")
        client.post(f"/playlists/{p2.id}/songs/{song.id}")
        client.delete(f"/playlists/{p1.id}/songs/{song.id}")
        assert len(client.get(f"/playlists/{p1.id}").json()["body"]["songs"]) == 0
        assert len(client.get(f"/playlists/{p2.id}").json()["body"]["songs"]) == 1
