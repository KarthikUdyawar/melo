"""Playlists API — LIB-2."""

# app/api/playlists.py
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.api._song_utils import serialize_song
from app.api.responses import envelope_response
from app.core.deps import DbDep
from app.core.log_events import LogEvent
from app.core.logging import get_logger
from app.models.favorite import Favorite
from app.models.playlist import Playlist, PlaylistSong
from app.models.song import Song
from app.schemas.playlist import (
    PlaylistCreate,
    PlaylistDetailResponse,
    PlaylistResponse,
)
from app.schemas.song import SongResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/playlists", tags=["playlists"])

_MAX_POSITION_RETRIES = 3


class PlaylistReorder(BaseModel):
    """Request body for PATCH /playlists/{id}/songs/{song_id}."""

    position: int = Field(ge=0)


# ── helpers ───────────────────────────────────────────────────────────────────


def _favorite_ids_for_songs(song_ids: list[UUID], db: DbDep) -> set[UUID]:
    if not song_ids:
        return set()
    return {
        sid
        for (sid,) in db.query(Favorite.song_id)
        .filter(Favorite.song_id.in_(song_ids), Favorite.deleted_at.is_(None))
        .all()
    }


def _serialize_playlist(
    playlist: Playlist, song_count: int | None = None
) -> dict[str, object]:
    count = song_count if song_count is not None else len(playlist.songs)
    return PlaylistResponse(
        id=playlist.id,
        name=playlist.name,
        created_at=playlist.created_at.isoformat(),
        song_count=count,
    ).model_dump(mode="json")


def _serialize_playlist_detail(playlist: Playlist, db: DbDep) -> dict[str, object]:
    song_ids = [s.id for s in playlist.songs]
    fav_ids = _favorite_ids_for_songs(song_ids, db)
    songs = [
        SongResponse.model_validate(
            serialize_song(s, db, is_favorite=(s.id in fav_ids))
        )
        for s in playlist.songs
    ]
    return PlaylistDetailResponse(
        id=playlist.id,
        name=playlist.name,
        created_at=playlist.created_at.isoformat(),
        songs=songs,
    ).model_dump(mode="json")


def _get_playlist_or_404(playlist_id: UUID, db: DbDep) -> Playlist:
    playlist = (
        db.query(Playlist)
        .filter(Playlist.id == playlist_id, Playlist.deleted_at.is_(None))
        .first()
    )
    if not playlist:
        raise HTTPException(
            status_code=404, detail=f"Playlist {playlist_id} not found."
        )
    return playlist


def _get_song_or_404(song_id: UUID, db: DbDep) -> Song:
    song = db.query(Song).filter(Song.id == song_id, Song.deleted_at.is_(None)).first()
    if not song:
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")
    return song


def _lock_playlist_songs(playlist_id: UUID, db: DbDep) -> list[PlaylistSong]:
    """Lock all PlaylistSong rows for playlist_id, serializes concurrent reorders.

    SQLite ignores FOR UPDATE (no row locks) — fine, unit tests don't test
    concurrency there. Postgres blocks a second reorder until first commits.
    """
    return (
        db.query(PlaylistSong)
        .filter(PlaylistSong.playlist_id == playlist_id)
        .order_by(PlaylistSong.position.asc())
        .with_for_update()
        .all()
    )


def _get_membership_or_404(playlist_id: UUID, song_id: UUID, db: DbDep) -> PlaylistSong:
    entry = (
        db.query(PlaylistSong)
        .filter(
            PlaylistSong.playlist_id == playlist_id, PlaylistSong.song_id == song_id
        )
        .first()
    )
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"Song {song_id} is not in playlist {playlist_id}.",
        )
    return entry


def _next_position(playlist_id: UUID, db: DbDep) -> int:
    result = (
        db.query(func.max(PlaylistSong.position))
        .filter(PlaylistSong.playlist_id == playlist_id)
        .scalar()
    )
    return 0 if result is None else result + 1


def _compact_positions(playlist_id: UUID, db: DbDep) -> None:
    """Reassign dense zero-based positions after a removal, preserving order.

    Safe to update in ascending-position order: for sorted rows, the target
    index i is always <= the row's current position, so no in-flight
    collision with the (playlist_id, position) unique constraint occurs.
    """
    rows = (
        db.query(PlaylistSong)
        .filter(PlaylistSong.playlist_id == playlist_id)
        .order_by(PlaylistSong.position.asc())
        .all()
    )
    for i, row in enumerate(rows):
        if row.position != i:
            row.position = i
            db.flush()


def _reposition_song(
    playlist_id: UUID, entry: PlaylistSong, new_position: int, db: DbDep
) -> None:
    """Move `entry` to `new_position`, shifting the songs in between.

    Uses a temp sentinel position (-1) so no two rows ever collide on the
    (playlist_id, position) unique constraint mid-shift.
    """
    old_position = entry.position
    if new_position == old_position:
        return

    entry.position = -1
    db.flush()

    if new_position < old_position:
        shifted = (
            db.query(PlaylistSong)
            .filter(
                PlaylistSong.playlist_id == playlist_id,
                PlaylistSong.position >= new_position,
                PlaylistSong.position < old_position,
            )
            .order_by(PlaylistSong.position.desc())
            .all()
        )
        for row in shifted:
            row.position += 1
            db.flush()
    else:
        shifted = (
            db.query(PlaylistSong)
            .filter(
                PlaylistSong.playlist_id == playlist_id,
                PlaylistSong.position > old_position,
                PlaylistSong.position <= new_position,
            )
            .order_by(PlaylistSong.position.asc())
            .all()
        )
        for row in shifted:
            row.position -= 1
            db.flush()

    entry.position = new_position
    db.commit()


# ── routes ────────────────────────────────────────────────────────────────────


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new playlist",
    responses={422: {"description": "Validation error (empty or too-long name)"}},
)
def create_playlist(payload: PlaylistCreate, db: DbDep) -> JSONResponse:
    """Create a named playlist. Returns the created playlist with song_count=0."""
    from app.core.metrics import playlist_ops_total

    playlist = Playlist(name=payload.name)
    db.add(playlist)
    db.commit()
    db.refresh(playlist)

    playlist_ops_total.labels(action="create").inc()
    logger.info(
        LogEvent.PLAYLIST_CREATED, playlist_id=str(playlist.id), name=playlist.name
    )
    return envelope_response(
        _serialize_playlist(playlist), "Playlist created.", status_code=201
    )


@router.get(
    "",
    summary="List all playlists ordered by creation date",
)
def list_playlists(db: DbDep) -> JSONResponse:
    """List non-deleted playlists, newest first."""
    rows = (
        db.query(Playlist, func.count(Song.id))
        .filter(Playlist.deleted_at.is_(None))
        .outerjoin(PlaylistSong, PlaylistSong.playlist_id == Playlist.id)
        .outerjoin(
            Song,
            (Song.id == PlaylistSong.song_id) & Song.deleted_at.is_(None),
        )
        .group_by(Playlist.id)
        .order_by(Playlist.created_at.desc())
        .all()
    )
    records = [
        PlaylistResponse(
            id=pl.id,
            name=pl.name,
            created_at=pl.created_at.isoformat(),
            song_count=song_count,
        ).model_dump(mode="json")
        for pl, song_count in rows
    ]
    logger.info("playlists_listed", count=len(records))
    return envelope_response(
        {"records": records, "count": len(records), "bookmark": None},
        "Playlists retrieved.",
    )


@router.get(
    "/{playlist_id}",
    summary="Get playlist detail including ordered songs",
    responses={404: {"description": "Playlist not found"}},
)
def get_playlist(playlist_id: UUID, db: DbDep) -> JSONResponse:
    """Return playlist with its songs ordered by position."""
    playlist = _get_playlist_or_404(playlist_id, db)
    logger.info("playlist_retrieved", playlist_id=str(playlist_id))
    return envelope_response(
        _serialize_playlist_detail(playlist, db), "Playlist retrieved."
    )


@router.post(
    "/{playlist_id}/songs/{song_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Add a song to a playlist (idempotent)",
    responses={
        200: {"description": "Song already in playlist"},
        201: {"description": "Song added"},
        404: {"description": "Playlist or song not found"},
        409: {"description": "Could not assign unique position after retries"},
    },
)
def add_song_to_playlist(playlist_id: UUID, song_id: UUID, db: DbDep) -> JSONResponse:
    """Append song to playlist at the next position. Idempotent."""
    from app.core.metrics import playlist_ops_total

    playlist = _get_playlist_or_404(playlist_id, db)
    _get_song_or_404(song_id, db)

    existing = (
        db.query(PlaylistSong)
        .filter(
            PlaylistSong.playlist_id == playlist_id, PlaylistSong.song_id == song_id
        )
        .first()
    )
    if existing:
        logger.info(
            LogEvent.PLAYLIST_SONG_ADDED,
            playlist_id=str(playlist_id),
            song_id=str(song_id),
            already=True,
        )
        return envelope_response(
            _serialize_playlist(playlist), "Song already in playlist.", status_code=200
        )

    for attempt in range(_MAX_POSITION_RETRIES):
        position = _next_position(playlist_id, db)
        entry = PlaylistSong(
            playlist_id=playlist_id, song_id=song_id, position=position
        )
        db.add(entry)
        try:
            db.commit()
            break
        except IntegrityError as exc:
            db.rollback()
            constraint = getattr(
                getattr(exc.orig, "diag", None), "constraint_name", None
            )
            if constraint == "uq_playlist_song":
                logger.info(
                    LogEvent.PLAYLIST_SONG_ADDED,
                    playlist_id=str(playlist_id),
                    song_id=str(song_id),
                    already=True,
                )
                return envelope_response(
                    _serialize_playlist(playlist),
                    "Song already in playlist.",
                    status_code=200,
                )
            if (
                constraint == "uq_playlist_position"
                and attempt < _MAX_POSITION_RETRIES - 1
            ):
                logger.warning(
                    "playlist_position_conflict_retry",
                    playlist_id=str(playlist_id),
                    attempt=attempt + 1,
                )
                continue
            if constraint == "uq_playlist_position":
                logger.error(
                    "playlist_position_retries_exhausted",
                    playlist_id=str(playlist_id),
                    song_id=str(song_id),
                )
                raise HTTPException(
                    status_code=409,
                    detail="Could not assign a unique position; please retry.",
                ) from exc
            raise
    else:
        logger.error(
            "playlist_position_retries_exhausted",
            playlist_id=str(playlist_id),
            song_id=str(song_id),
        )
        raise HTTPException(
            status_code=409, detail="Could not assign a unique position; please retry."
        )

    db.refresh(playlist)
    playlist_ops_total.labels(action="add_song").inc()
    logger.info(
        LogEvent.PLAYLIST_SONG_ADDED,
        playlist_id=str(playlist_id),
        song_id=str(song_id),
        position=position,
    )
    return envelope_response(
        _serialize_playlist(playlist), "Song added to playlist.", status_code=201
    )


@router.patch(
    "/{playlist_id}/songs/{song_id}",
    summary="Reorder a song within a playlist",
    responses={
        404: {"description": "Playlist, song, or membership not found"},
        422: {"description": "position out of range"},
    },
)
def reorder_song_in_playlist(
    playlist_id: UUID, song_id: UUID, payload: PlaylistReorder, db: DbDep
) -> JSONResponse:
    """Move a song to `position`, shifting songs in between."""
    playlist = _get_playlist_or_404(playlist_id, db)
    _get_song_or_404(song_id, db)

    locked_rows = _lock_playlist_songs(playlist_id, db)
    entry = next((r for r in locked_rows if r.song_id == song_id), None)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Song {song_id} is not in playlist {playlist_id}.",
        )
    song_count = len(locked_rows)
    if payload.position >= song_count:
        raise HTTPException(
            status_code=422,
            detail=f"position must be < {song_count} (song_count).",
        )

    _reposition_song(playlist_id, entry, payload.position, db)

    db.refresh(playlist)
    logger.info(
        "playlist_song_reordered",
        playlist_id=str(playlist_id),
        song_id=str(song_id),
        position=payload.position,
    )
    return envelope_response(_serialize_playlist_detail(playlist, db), "Reordered.")


@router.delete(
    "/{playlist_id}/songs/{song_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a song from a playlist",
    responses={404: {"description": "Playlist, song, or membership not found"}},
)
def remove_song_from_playlist(playlist_id: UUID, song_id: UUID, db: DbDep) -> Response:
    """Hard-delete the PlaylistSong join row and compact remaining positions.

    404 if not found. Compaction keeps `position` dense/gap-free so later
    PATCH reorders (which treat `position` as a list index) stay correct.
    """
    from app.core.metrics import playlist_ops_total

    _get_playlist_or_404(playlist_id, db)
    _get_song_or_404(song_id, db)
    entry = _get_membership_or_404(playlist_id, song_id, db)

    db.delete(entry)
    db.flush()
    _compact_positions(playlist_id, db)
    db.commit()
    db.expire_all()

    playlist_ops_total.labels(action="remove_song").inc()
    logger.info(
        LogEvent.PLAYLIST_SONG_REMOVED,
        playlist_id=str(playlist_id),
        song_id=str(song_id),
    )
    return Response(status_code=204)


@router.delete(
    "/{playlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a playlist",
    responses={404: {"description": "Playlist not found"}},
)
def delete_playlist(playlist_id: UUID, db: DbDep) -> Response:
    """Soft-delete a playlist by setting deleted_at. Song associations preserved."""
    from app.core.metrics import playlist_ops_total

    playlist = _get_playlist_or_404(playlist_id, db)
    playlist.deleted_at = datetime.now(UTC)
    db.commit()

    playlist_ops_total.labels(action="delete").inc()
    logger.info(LogEvent.PLAYLIST_DELETED, playlist_id=str(playlist_id))
    return Response(status_code=204)
