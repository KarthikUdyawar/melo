"""tests/integration/test_favorites_api.py
Integration tests for LIB-1: Favorites endpoints (Postgres-backed).

Tests cover:
- Happy path: POST/DELETE/GET lifecycle
- Idempotency: no duplicate rows on double-POST
- Stateless guarantee: DELETE cleans up, re-GET shows empty
- is_favorite reflected in /songs and /songs/{id}
- Error paths: 404 for unknown song/unfavorited song
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.favorite import Favorite
from app.models.song import Song, SongStatus


def _make_song(db_session: Session, **kwargs) -> Song:
    song = Song(
        youtube_id=kwargs.get("youtube_id", "dQw4w9WgXcQ"),
        status=SongStatus.done,
        speed=1.0,
        title=kwargs.get("title", "Test Song"),
        file_url=kwargs.get("file_url", "songs/test.mp3"),
    )
    db_session.add(song)
    db_session.flush()
    return song


class TestFavoritesLifecycle:
    def test_post_returns_201(self, client: TestClient, db_session: Session) -> None:
        song = _make_song(db_session)
        resp = client.post(f"/favorites/{song.id}")
        assert resp.status_code == 201

    def test_post_creates_db_row(self, client: TestClient, db_session: Session) -> None:
        song = _make_song(db_session)
        client.post(f"/favorites/{song.id}")
        count = db_session.query(Favorite).filter(Favorite.song_id == song.id).count()
        assert count == 1

    def test_post_idempotent_no_dupe(
        self, client: TestClient, db_session: Session,
    ) -> None:
        song = _make_song(db_session)
        client.post(f"/favorites/{song.id}")
        resp = client.post(f"/favorites/{song.id}")
        assert resp.status_code == 200
        count = db_session.query(Favorite).filter(Favorite.song_id == song.id).count()
        assert count == 1

    def test_delete_returns_204(self, client: TestClient, db_session: Session) -> None:
        song = _make_song(db_session)
        client.post(f"/favorites/{song.id}")
        resp = client.delete(f"/favorites/{song.id}")
        assert resp.status_code == 204

    def test_delete_removes_row(self, client: TestClient, db_session: Session) -> None:
        song = _make_song(db_session)
        client.post(f"/favorites/{song.id}")
        client.delete(f"/favorites/{song.id}")
        count = db_session.query(Favorite).filter(Favorite.song_id == song.id).count()
        assert count == 0

    def test_get_returns_favorited_songs(
        self, client: TestClient, db_session: Session,
    ) -> None:
        song = _make_song(db_session, title="Fav Song")
        client.post(f"/favorites/{song.id}")
        resp = client.get("/favorites")
        records = resp.json()["body"]["records"]
        assert len(records) == 1
        assert records[0]["title"] == "Fav Song"
        assert records[0]["is_favorite"] is True

    def test_get_empty_before_any_favorite(
        self, client: TestClient, db_session: Session,
    ) -> None:
        _make_song(db_session)
        resp = client.get("/favorites")
        assert resp.json()["body"]["count"] == 0

    def test_get_empty_after_delete(
        self, client: TestClient, db_session: Session,
    ) -> None:
        song = _make_song(db_session)
        client.post(f"/favorites/{song.id}")
        client.delete(f"/favorites/{song.id}")
        assert client.get("/favorites").json()["body"]["count"] == 0


class TestFavoritesErrors:
    def test_post_unknown_song_404(
        self, client: TestClient, db_session: Session,
    ) -> None:
        resp = client.post(f"/favorites/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_delete_not_favorited_404(
        self, client: TestClient, db_session: Session,
    ) -> None:
        song = _make_song(db_session)
        resp = client.delete(f"/favorites/{song.id}")
        assert resp.status_code == 404

    def test_delete_unknown_song_404(
        self, client: TestClient, db_session: Session,
    ) -> None:
        resp = client.delete(f"/favorites/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestIsFavoriteInSongs:
    def test_songs_list_is_favorite_false(
        self, client: TestClient, db_session: Session,
    ) -> None:
        _make_song(db_session)
        records = client.get("/songs").json()["body"]["records"]
        assert records[0]["is_favorite"] is False

    def test_songs_list_is_favorite_true(
        self, client: TestClient, db_session: Session,
    ) -> None:
        song = _make_song(db_session)
        client.post(f"/favorites/{song.id}")
        records = client.get("/songs").json()["body"]["records"]
        assert records[0]["is_favorite"] is True

    def test_song_detail_is_favorite_toggles(
        self, client: TestClient, db_session: Session,
    ) -> None:
        song = _make_song(db_session)
        assert client.get(f"/songs/{song.id}").json()["body"]["is_favorite"] is False
        client.post(f"/favorites/{song.id}")
        assert client.get(f"/songs/{song.id}").json()["body"]["is_favorite"] is True
        client.delete(f"/favorites/{song.id}")
        assert client.get(f"/songs/{song.id}").json()["body"]["is_favorite"] is False

    def test_multiple_songs_is_favorite_selective(
        self, client: TestClient, db_session: Session,
    ) -> None:
        s1 = _make_song(db_session, youtube_id="aaaaaaaaaaa", title="S1")
        s2 = _make_song(db_session, youtube_id="bbbbbbbbbbb", title="S2")
        client.post(f"/favorites/{s1.id}")
        records = client.get("/songs").json()["body"]["records"]
        by_id = {r["id"]: r for r in records}
        assert by_id[str(s1.id)]["is_favorite"] is True
        assert by_id[str(s2.id)]["is_favorite"] is False
