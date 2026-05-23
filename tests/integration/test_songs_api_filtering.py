"""Integration tests for GET /songs filtering, sorting, and pagination (API-2).

TDD vertical slices:
  1. status filter
  2. favorite filter
  3. search filter (case-insensitive title)
  4. sort_by + order
  5. limit + offset + bookmark (cursor pagination)
"""

# tests/integration/test_songs_api_filtering.py
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.favorite import Favorite
from app.models.song import Song, SongStatus

VALID_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


# ── helpers ───────────────────────────────────────────────────────────────────


def _song(db: Session, **kw: object) -> Song:
    s = Song(
        youtube_id=str(kw.get("youtube_id", "dQw4w9WgXcQ")),
        status=kw.get("status", SongStatus.done),
        file_url=str(kw.get("file_url", "test.mp3")),
        title=kw.get("title", "Test Song"),
        duration=kw.get("duration", 180.0),
        speed=kw.get("speed", 1.0),
        start=kw.get("start"),
        end=kw.get("end"),
        created_at=kw.get("created_at", datetime.now(UTC)),
    )
    db.add(s)
    db.flush()
    return s


def _favorite(db: Session, song: Song) -> Favorite:
    fav = Favorite(song_id=song.id)
    db.add(fav)
    db.flush()
    return fav


# ── Slice 1: status filter ────────────────────────────────────────────────────


class TestStatusFilter:
    def test_filter_done_returns_only_done(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        _song(db_session, status=SongStatus.done, youtube_id="aaa")
        _song(db_session, status=SongStatus.pending, youtube_id="bbb")
        _song(db_session, status=SongStatus.failed, youtube_id="ccc")

        resp = client.get("/songs?status=done")

        assert resp.status_code == 200
        body = resp.json()["body"]
        assert body["count"] == 1
        assert all(r["status"] == "done" for r in body["records"])

    def test_filter_pending(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        _song(db_session, status=SongStatus.pending, youtube_id="p1")
        _song(db_session, status=SongStatus.pending, youtube_id="p2")
        _song(db_session, status=SongStatus.done, youtube_id="d1")

        resp = client.get("/songs?status=pending")

        body = resp.json()["body"]
        assert body["count"] == 2

    def test_invalid_status_returns_422(self, client: TestClient) -> None:
        resp = client.get("/songs?status=unknown")
        assert resp.status_code == 422

    def test_no_status_filter_returns_all(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        _song(db_session, status=SongStatus.done, youtube_id="a1")
        _song(db_session, status=SongStatus.pending, youtube_id="b1")

        resp = client.get("/songs")

        body = resp.json()["body"]
        assert body["count"] >= 2


# ── Slice 2: favorite filter ──────────────────────────────────────────────────


class TestFavoriteFilter:
    def test_favorite_true_returns_only_favorites(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        fav_song = _song(db_session, youtube_id="fav1")
        _song(db_session, youtube_id="notfav")
        _favorite(db_session, fav_song)

        resp = client.get("/songs?favorite=true")

        body = resp.json()["body"]
        assert body["count"] == 1
        assert body["records"][0]["id"] == str(fav_song.id)

    def test_favorite_false_returns_only_non_favorites(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        fav_song = _song(db_session, youtube_id="fav2")
        plain = _song(db_session, youtube_id="plain2")
        _favorite(db_session, fav_song)

        resp = client.get("/songs?favorite=false")

        body = resp.json()["body"]
        ids = [r["id"] for r in body["records"]]
        assert str(plain.id) in ids
        assert str(fav_song.id) not in ids

    def test_favorite_true_records_have_is_favorite_true(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        s = _song(db_session, youtube_id="fav3")
        _favorite(db_session, s)

        resp = client.get("/songs?favorite=true")

        records = resp.json()["body"]["records"]
        assert all(r["is_favorite"] for r in records)

    def test_invalid_favorite_param_returns_422(self, client: TestClient) -> None:
        resp = client.get("/songs?favorite=maybe")
        assert resp.status_code == 422


# ── Slice 3: search filter ────────────────────────────────────────────────────


class TestSearchFilter:
    def test_search_matches_title_case_insensitive(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        _song(db_session, title="Rick Astley", youtube_id="r1")
        _song(db_session, title="Never Gonna Stop", youtube_id="r2")
        _song(db_session, title="Bohemian Rhapsody", youtube_id="r3")

        resp = client.get("/songs?search=rick")

        body = resp.json()["body"]
        assert body["count"] == 1
        assert body["records"][0]["title"] == "Rick Astley"

    def test_search_partial_match(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        _song(db_session, title="Never Gonna Give You Up", youtube_id="ng1")
        _song(db_session, title="Never Gonna Run", youtube_id="ng2")
        _song(db_session, title="Hello World", youtube_id="hw1")

        resp = client.get("/songs?search=never")

        body = resp.json()["body"]
        assert body["count"] == 2

    def test_search_no_match_returns_empty(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        _song(db_session, title="Some Song", youtube_id="ss1")

        resp = client.get("/songs?search=zzznomatch")

        body = resp.json()["body"]
        assert body["count"] == 0
        assert body["records"] == []

    def test_search_with_null_title_not_included(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        _song(db_session, title=None, youtube_id="nt1")
        _song(db_session, title="Real Title", youtube_id="rt1")

        resp = client.get("/songs?search=real")

        body = resp.json()["body"]
        assert body["count"] == 1


# ── Slice 4: sort_by + order ──────────────────────────────────────────────────


class TestSortOrder:
    def test_sort_by_title_asc(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        _song(db_session, title="Zebra", youtube_id="z1")
        _song(db_session, title="Apple", youtube_id="a1")
        _song(db_session, title="Mango", youtube_id="m1")

        resp = client.get("/songs?sort_by=title&order=asc")

        titles = [r["title"] for r in resp.json()["body"]["records"]]
        assert titles == sorted(titles)

    def test_sort_by_title_desc(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        _song(db_session, title="Zebra", youtube_id="z2")
        _song(db_session, title="Apple", youtube_id="a2")

        resp = client.get("/songs?sort_by=title&order=desc")

        titles = [r["title"] for r in resp.json()["body"]["records"]]
        assert titles == sorted(titles, reverse=True)

    def test_sort_by_duration_asc(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        _song(db_session, duration=300.0, youtube_id="d1")
        _song(db_session, duration=100.0, youtube_id="d2")
        _song(db_session, duration=200.0, youtube_id="d3")

        resp = client.get("/songs?sort_by=duration&order=asc")

        durations = [r["duration"] for r in resp.json()["body"]["records"]]
        assert durations == sorted(durations)

    def test_default_sort_is_created_at_desc(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        _song(
            db_session,
            youtube_id="old",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        _song(
            db_session,
            youtube_id="new",
            created_at=datetime(2024, 6, 1, tzinfo=UTC),
        )

        resp = client.get("/songs")

        ids_order = [r["youtube_id"] for r in resp.json()["body"]["records"]]
        assert ids_order[0] == "new"

    def test_invalid_sort_by_returns_422(self, client: TestClient) -> None:
        resp = client.get("/songs?sort_by=invalid_field")
        assert resp.status_code == 422

    def test_invalid_order_returns_422(self, client: TestClient) -> None:
        resp = client.get("/songs?order=sideways")
        assert resp.status_code == 422


# ── Slice 5: limit + offset + bookmark ───────────────────────────────────────


class TestPagination:
    def test_limit_restricts_result_count(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        for i in range(5):
            _song(db_session, youtube_id=f"lim{i}")

        resp = client.get("/songs?limit=3")

        body = resp.json()["body"]
        assert len(body["records"]) == 3

    def test_offset_skips_records(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        songs = [
            _song(
                db_session,
                youtube_id=f"off{i}",
                created_at=datetime(2024, 1, i + 1, tzinfo=UTC),
            )
            for i in range(4)
        ]

        resp_all = client.get("/songs?sort_by=created_at&order=asc&limit=10")
        resp_offset = client.get(
            "/songs?sort_by=created_at&order=asc&limit=10&offset=2"
        )

        all_ids = [r["id"] for r in resp_all.json()["body"]["records"]]
        offset_ids = [r["id"] for r in resp_offset.json()["body"]["records"]]
        assert offset_ids == all_ids[2:]
        _ = songs  # used for seeding

    def test_count_reflects_total_not_page(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        for i in range(5):
            _song(db_session, youtube_id=f"cnt{i}")

        resp = client.get("/songs?limit=2")

        body = resp.json()["body"]
        assert body["count"] >= 5
        assert len(body["records"]) == 2

    def test_bookmark_is_last_record_id(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        for i in range(3):
            _song(db_session, youtube_id=f"bm{i}")

        resp = client.get("/songs?limit=2")

        body = resp.json()["body"]
        records = body["records"]
        assert body["bookmark"] == records[-1]["id"]

    def test_bookmark_null_when_no_records(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/songs?limit=10")
        body = resp.json()["body"]
        assert body["bookmark"] is None

    def test_after_cursor_fetches_next_page(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        songs = [
            _song(
                db_session,
                youtube_id=f"cur{i}",
                created_at=datetime(2024, 1, i + 1, tzinfo=UTC),
            )
            for i in range(4)
        ]

        first_page = client.get("/songs?sort_by=created_at&order=asc&limit=2")
        bookmark = first_page.json()["body"]["bookmark"]

        second_page = client.get(
            f"/songs?sort_by=created_at&order=asc&limit=2&after={bookmark}",
        )

        second_ids = [r["id"] for r in second_page.json()["body"]["records"]]
        assert str(songs[2].id) in second_ids
        assert str(songs[3].id) in second_ids

    def test_limit_above_max_returns_422(self, client: TestClient) -> None:
        resp = client.get("/songs?limit=1001")
        assert resp.status_code == 422

    def test_offset_negative_returns_422(self, client: TestClient) -> None:
        resp = client.get("/songs?offset=-1")
        assert resp.status_code == 422

    def test_combined_filters_and_pagination(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        for i in range(3):
            _song(
                db_session,
                status=SongStatus.done,
                title=f"Done {i}",
                youtube_id=f"cf{i}",
            )
        _song(db_session, status=SongStatus.pending, youtube_id="cfp")

        resp = client.get("/songs?status=done&limit=2&sort_by=title&order=asc")

        body = resp.json()["body"]
        assert body["count"] == 3  # total done songs
        assert len(body["records"]) == 2
        assert all(r["status"] == "done" for r in body["records"])
