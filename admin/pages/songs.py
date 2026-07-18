"""Songs page — status breakdown table and re-queue failed songs."""

# admin/pages/songs.py

from __future__ import annotations

from typing import Any

import requests
import streamlit as st

MELO_API = "http://api:8000"


def _fetch_songs(status: str | None = None) -> list[dict[str, Any]]:
    """Return all songs, optionally filtered by status."""
    params: dict[str, Any] = {"limit": 200}
    if status:
        params["status"] = status

    songs: list[dict[str, Any]] = []
    bookmark: str | None = None

    while True:
        if bookmark:
            params["after"] = bookmark

        try:
            response = requests.get(
                f"{MELO_API}/songs",
                params=params,
                timeout=10,
            )
            response.raise_for_status()

            body = response.json().get("body", {})
            records = body.get("records", [])
            if isinstance(records, list):
                songs.extend(records)

            bookmark = body.get("bookmark")
            if not bookmark:
                break
        except Exception:  # noqa: BLE001
            break

    return songs


def _requeue_song(song: dict[str, Any]) -> bool:
    """Re-submit a song via POST /songs. Return True on success."""
    payload: dict[str, Any] = {
        "url": f"https://www.youtube.com/watch?v={song['youtube_id']}"
    }

    for field in ("start", "end", "speed"):
        if song.get(field) is not None:
            payload[field] = song[field]

    try:
        response = requests.post(
            f"{MELO_API}/songs",
            json=payload,
            timeout=10,
        )
        return response.status_code == 202  # noqa: PLR2004
    except Exception:  # noqa: BLE001
        return False


st.header("Songs")

status_filter = st.selectbox(
    "Filter by status",
    ["all", "pending", "processing", "done", "failed"],
)

songs = _fetch_songs(None if status_filter == "all" else status_filter)

# ── Status breakdown ──────────────────────────────────────────────────────────

counts: dict[str, int] = {}
for song in songs:
    status = str(song["status"])
    counts[status] = counts.get(status, 0) + 1

bcols = st.columns(4)
for col, status in zip(
    bcols,
    ["pending", "processing", "done", "failed"],
    strict=True,
):
    col.metric(status.capitalize(), counts.get(status, 0))

st.divider()

# ── Song table ────────────────────────────────────────────────────────────────

if not songs:
    st.info("No songs found.")
else:
    for song in songs:
        cols = st.columns([3, 1, 1, 1])

        cols[0].write(song.get("title") or song.get("youtube_id") or song["id"])
        cols[1].write(song["status"])
        cols[2].write(song.get("channel") or "—")

        if song["status"] == "failed":
            if cols[3].button("Re-queue", key=f"requeue_{song['id']}"):
                if _requeue_song(song):
                    st.success(f"Re-queued: {song['id']}")
                else:
                    st.error("Re-queue failed.")
        else:
            cols[3].write("")
