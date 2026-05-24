"""Playlists API — LIB-2.

POST   /playlists                        → 201 created
GET    /playlists                        → list
GET    /playlists/{id}                   → detail with songs
POST   /playlists/{id}/songs/{song_id}  → add song (idempotent)
DELETE /playlists/{id}/songs/{song_id}  → remove song
DELETE /playlists/{id}                  → soft-delete playlist
"""

# app/api/playlists.py
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.api._song_utils import serialize_song
from app.api.responses import envelope_response
from app.core.deps import DbDep
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


def _next_position(playlist_id: UUID, db: DbDep) -> int:
    result = (
        db.query(func.max(PlaylistSong.position))
        .filter(PlaylistSong.playlist_id == playlist_id)
        .scalar()
    )
    return 0 if result is None else result + 1


# ── routes ────────────────────────────────────────────────────────────────────


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new playlist",
    responses={422: {"description": "Validation error (empty or too-long name)"}},
)
def create_playlist(payload: PlaylistCreate, db: DbDep) -> JSONResponse:
    """Create a named playlist. Returns the created playlist with song_count=0."""
    playlist = Playlist(name=payload.name)
    db.add(playlist)
    db.commit()
    db.refresh(playlist)

    logger.info("playlist_created", playlist_id=str(playlist.id), name=playlist.name)
    return envelope_response(
        _serialize_playlist(playlist), "Playlist created.", status_code=201
    )


@router.get(
    "",
    summary="List all playlists ordered by creation date",
)
def list_playlists(db: DbDep) -> JSONResponse:
    """List non-deleted playlists, newest first.

    song_count reflects only non-deleted songs — soft-deleted songs are excluded
    even when their PlaylistSong join rows remain.
    """
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
    """Append song to playlist at the next position.

    Idempotent — returns 200 if already present.
    """
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
            "playlist_song_already_exists",
            playlist_id=str(playlist_id),
            song_id=str(song_id),
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
                    "playlist_song_race_condition",
                    playlist_id=str(playlist_id),
                    song_id=str(song_id),
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
    logger.info(
        "playlist_song_added",
        playlist_id=str(playlist_id),
        song_id=str(song_id),
        position=position,
    )
    return envelope_response(
        _serialize_playlist(playlist), "Song added to playlist.", status_code=201
    )


@router.delete(
    "/{playlist_id}/songs/{song_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a song from a playlist",
    responses={404: {"description": "Playlist, song, or membership not found"}},
)
def remove_song_from_playlist(playlist_id: UUID, song_id: UUID, db: DbDep) -> Response:
    """Hard-delete the PlaylistSong join row. 404 if not found."""
    _get_playlist_or_404(playlist_id, db)
    _get_song_or_404(song_id, db)

    entry = (
        db.query(PlaylistSong)
        .filter(
            PlaylistSong.playlist_id == playlist_id, PlaylistSong.song_id == song_id
        )
        .first()
    )
    if not entry:
        raise HTTPException(
            status_code=404, detail=f"Song {song_id} is not in playlist {playlist_id}."
        )

    db.delete(entry)
    db.commit()
    db.expire_all()

    logger.info(
        "playlist_song_removed", playlist_id=str(playlist_id), song_id=str(song_id)
    )
    return Response(status_code=204)


@router.delete(
    "/{playlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a playlist",
    responses={404: {"description": "Playlist not found"}},
)
def delete_playlist(playlist_id: UUID, db: DbDep) -> Response:
    """Soft-delete a playlist by setting deleted_at.

    Song associations are preserved in DB.
    """
    playlist = _get_playlist_or_404(playlist_id, db)
    playlist.deleted_at = datetime.now(UTC)
    db.commit()

    logger.info("playlist_deleted", playlist_id=str(playlist_id))
    return Response(status_code=204)
