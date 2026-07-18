"""Integration tests for OBS-2: Prometheus metrics.

Behaviors tested (one per TDD slice):
  1. GET /metrics returns 200 and body contains songs_submitted_total
  2. songs_submitted_total increments on POST /songs
  3. favorites_toggled_total increments with correct label on add/remove
  4. playlist_ops_total increments on create and delete
"""

# tests/integration/test_metrics_api.py
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

# ── helpers ───────────────────────────────────────────────────────────────────


def _parse_metric(body: str, name: str) -> float:
    """Return the scalar value for a metric name from a /metrics text body."""
    for line in body.splitlines():
        if line.startswith(name) and not line.startswith("#"):
            parts = line.split()
            if len(parts) >= 2:
                return float(parts[-1])
    raise KeyError(f"Metric {name!r} not found in /metrics output")


def _parse_labeled_metric(body: str, name: str, labels: dict[str, str]) -> float:
    """Return the value for a metric with specific label key=value pairs."""
    for line in body.splitlines():
        if (
        line.startswith(name)
        and not line.startswith("#")
        and all(f'{k}="{v}"' in line for k, v in labels.items())
    ):
            parts = line.split()
            return float(parts[-1])
    raise KeyError(f"Metric {name!r} with labels {labels} not found")


def _make_song(client: TestClient) -> dict:
    """POST /songs with a mocked task and return the response body."""
    with (
        patch("app.api.songs.extract_youtube_id", return_value="dQw4w9WgXcQ"),
        patch("app.workers.tasks.process_song_task") as mock_task,
    ):
        mock_task.delay.return_value = None
        resp = client.post(
            "/songs", json={"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"}
        )
    return resp


def _make_song_in_db(client: TestClient, db_session) -> str:
    """Create a done song directly in the DB and return its ID."""
    from datetime import UTC, datetime

    from app.models.song import Song, SongStatus

    song = Song(
        youtube_id="dQw4w9WgXcQ",
        title="Test Song",
        status=SongStatus.done,
        speed=1.0,
        created_at=datetime.now(UTC),
    )
    db_session.add(song)
    db_session.commit()
    db_session.refresh(song)
    return str(song.id)


# ── slice 1: GET /metrics endpoint ───────────────────────────────────────────


def test_metrics_endpoint_returns_200(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200


def test_metrics_endpoint_contains_songs_submitted_total(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert "songs_submitted_total" in resp.text


# ── slice 2: songs_submitted_total increments ─────────────────────────────────


def test_songs_submitted_total_increments_on_post(client: TestClient) -> None:
    before_resp = client.get("/metrics")
    before = _parse_metric(before_resp.text, "songs_submitted_total")

    _make_song(client)

    after_resp = client.get("/metrics")
    after = _parse_metric(after_resp.text, "songs_submitted_total")

    assert after == before + 1.0


# ── slice 3: favorites_toggled_total increments ───────────────────────────────


def test_favorites_toggled_total_add_increments(client: TestClient, db_session) -> None:
    song_id = _make_song_in_db(client, db_session)

    before_resp = client.get("/metrics")
    try:
        before = _parse_labeled_metric(
            before_resp.text, "favorites_toggled_total", {"action": "add"}
        )
    except KeyError:
        before = 0.0

    client.post(f"/favorites/{song_id}")

    after_resp = client.get("/metrics")
    after = _parse_labeled_metric(
        after_resp.text, "favorites_toggled_total", {"action": "add"}
    )
    assert after == before + 1.0


def test_favorites_toggled_total_remove_increments(
    client: TestClient, db_session
) -> None:
    song_id = _make_song_in_db(client, db_session)
    client.post(f"/favorites/{song_id}")

    before_resp = client.get("/metrics")
    try:
        before = _parse_labeled_metric(
            before_resp.text, "favorites_toggled_total", {"action": "remove"}
        )
    except KeyError:
        before = 0.0

    client.delete(f"/favorites/{song_id}")

    after_resp = client.get("/metrics")
    after = _parse_labeled_metric(
        after_resp.text, "favorites_toggled_total", {"action": "remove"}
    )
    assert after == before + 1.0


# ── slice 4: playlist_ops_total increments ────────────────────────────────────


def test_playlist_ops_total_create_increments(client: TestClient) -> None:
    before_resp = client.get("/metrics")
    try:
        before = _parse_labeled_metric(
            before_resp.text, "playlist_ops_total", {"action": "create"}
        )
    except KeyError:
        before = 0.0

    client.post("/playlists", json={"name": "Test Playlist"})

    after_resp = client.get("/metrics")
    after = _parse_labeled_metric(
        after_resp.text, "playlist_ops_total", {"action": "create"}
    )
    assert after == before + 1.0


def test_playlist_ops_total_delete_increments(client: TestClient) -> None:
    create_resp = client.post("/playlists", json={"name": "To Delete"})
    playlist_id = create_resp.json()["body"]["id"]

    before_resp = client.get("/metrics")
    try:
        before = _parse_labeled_metric(
            before_resp.text, "playlist_ops_total", {"action": "delete"}
        )
    except KeyError:
        before = 0.0

    client.delete(f"/playlists/{playlist_id}")

    after_resp = client.get("/metrics")
    after = _parse_labeled_metric(
        after_resp.text, "playlist_ops_total", {"action": "delete"}
    )
    assert after == before + 1.0
