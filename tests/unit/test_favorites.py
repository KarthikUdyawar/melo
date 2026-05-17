"""Unit tests for LIB-1: Favorites endpoints.

Tests cover:
- POST /favorites/{song_id}: 201 created, idempotent (200), 404 missing song
- DELETE /favorites/{song_id}: 204 success, 404 not favorited
- GET /favorites: list with song data, empty list
- SongResponse.is_favorite reflects favorite state
"""

from __future__ import annotations

import uuid

from app.models.song import Song, SongStatus


def _make_song(db_session, **kwargs) -> Song:
    song = Song(
        youtube_id=kwargs.get("youtube_id", "dQw4w9WgXcQ"),
        status=kwargs.get("status", SongStatus.done),
        speed=kwargs.get("speed", 1.0),
        title=kwargs.get("title", "Test Song"),
        file_url=kwargs.get("file_url", "songs/test.mp3"),
    )
    db_session.add(song)
    db_session.flush()
    return song


class TestPostFavorite:
    def test_favorite_song_returns_201(self, client, db_session) -> None:
        song = _make_song(db_session)
        resp = client.post(f"/favorites/{song.id}")
        assert resp.status_code == 201

    def test_favorite_response_envelope(self, client, db_session) -> None:
        song = _make_song(db_session)
        resp = client.post(f"/favorites/{song.id}")
        body = resp.json()
        assert body["status_code"] == 201
        assert "body" in body
        assert body["body"]["song_id"] == str(song.id)

    def test_favorite_idempotent_returns_200(self, client, db_session) -> None:
        song = _make_song(db_session)
        client.post(f"/favorites/{song.id}")
        resp = client.post(f"/favorites/{song.id}")
        assert resp.status_code == 200

    def test_favorite_idempotent_no_duplicate(self, client, db_session) -> None:
        from app.models.favorite import Favorite

        song = _make_song(db_session)
        client.post(f"/favorites/{song.id}")
        client.post(f"/favorites/{song.id}")
        count = db_session.query(Favorite).filter(Favorite.song_id == song.id).count()
        assert count == 1

    def test_favorite_missing_song_returns_404(self, client, db_session) -> None:
        resp = client.post(f"/favorites/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_favorite_invalid_uuid_returns_422(self, client, db_session) -> None:
        resp = client.post("/favorites/not-a-uuid")
        assert resp.status_code == 422


class TestDeleteFavorite:
    def test_delete_favorite_returns_204(self, client, db_session) -> None:
        song = _make_song(db_session)
        client.post(f"/favorites/{song.id}")
        resp = client.delete(f"/favorites/{song.id}")
        assert resp.status_code == 204

    def test_delete_removes_row(self, client, db_session) -> None:
        from app.models.favorite import Favorite

        song = _make_song(db_session)
        client.post(f"/favorites/{song.id}")
        client.delete(f"/favorites/{song.id}")
        count = db_session.query(Favorite).filter(Favorite.song_id == song.id).count()
        assert count == 0

    def test_delete_not_favorited_returns_404(self, client, db_session) -> None:
        song = _make_song(db_session)
        resp = client.delete(f"/favorites/{song.id}")
        assert resp.status_code == 404

    def test_delete_missing_song_returns_404(self, client, db_session) -> None:
        resp = client.delete(f"/favorites/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestGetFavorites:
    def test_empty_favorites_returns_200(self, client, db_session) -> None:
        resp = client.get("/favorites")
        assert resp.status_code == 200

    def test_empty_favorites_returns_empty_list(self, client, db_session) -> None:
        resp = client.get("/favorites")
        body = resp.json()
        assert body["body"]["records"] == []
        assert body["body"]["count"] == 0

    def test_get_favorites_includes_song_data(self, client, db_session) -> None:
        song = _make_song(db_session, title="My Fav Song")
        client.post(f"/favorites/{song.id}")
        resp = client.get("/favorites")
        records = resp.json()["body"]["records"]
        assert len(records) == 1
        assert records[0]["title"] == "My Fav Song"
        assert records[0]["is_favorite"] is True

    def test_get_favorites_count_matches(self, client, db_session) -> None:
        s1 = _make_song(db_session, youtube_id="aaaaaaaaaaa")
        s2 = _make_song(db_session, youtube_id="bbbbbbbbbbb")
        client.post(f"/favorites/{s1.id}")
        client.post(f"/favorites/{s2.id}")
        body = client.get("/favorites").json()["body"]
        assert body["count"] == 2

    def test_get_favorites_contains_all_titles(self, client, db_session) -> None:
        # Ordering relies on created_at; SQLite resolves func.now() once per
        # transaction so timestamps are identical — only test set membership here.
        # Ordering correctness is verified in integration tests (Postgres clock).
        s1 = _make_song(db_session, youtube_id="aaaaaaaaaaa", title="First")
        s2 = _make_song(db_session, youtube_id="bbbbbbbbbbb", title="Second")
        client.post(f"/favorites/{s1.id}")
        client.post(f"/favorites/{s2.id}")
        records = client.get("/favorites").json()["body"]["records"]
        titles = {r["title"] for r in records}
        assert titles == {"First", "Second"}


class TestIsFavoriteInSongResponse:
    def test_list_songs_is_favorite_false_by_default(self, client, db_session) -> None:
        _make_song(db_session)
        resp = client.get("/songs")
        records = resp.json()["body"]["records"]
        assert records[0]["is_favorite"] is False

    def test_list_songs_is_favorite_true_after_favoriting(
        self, client, db_session,
    ) -> None:
        song = _make_song(db_session)
        client.post(f"/favorites/{song.id}")
        records = client.get("/songs").json()["body"]["records"]
        assert records[0]["is_favorite"] is True

    def test_get_song_is_favorite_reflects_state(self, client, db_session) -> None:
        song = _make_song(db_session)
        assert client.get(f"/songs/{song.id}").json()["body"]["is_favorite"] is False
        client.post(f"/favorites/{song.id}")
        assert client.get(f"/songs/{song.id}").json()["body"]["is_favorite"] is True
