"""Playlists API — LIB-2.

POST   /playlists                        → 201 created
GET    /playlists                        → paginated list
GET    /playlists/{id}                   → detail with songs
POST   /playlists/{id}/songs/{song_id}  → add song (idempotent)
DELETE /playlists/{id}/songs/{song_id}  → remove song
DELETE /playlists/{id}                  → delete playlist
"""

# app/api/playlists.py
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.api.responses import envelope_response, paginated_response
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


# ── Serializers ───────────────────────────────────────────────────────────────


def _favorite_ids_for_songs(song_ids: list[UUID], db: DbDep) -> set[UUID]:
    if not song_ids:
        return set()
    return {
        sid
        for (sid,) in db.query(Favorite.song_id)
        .filter(Favorite.song_id.in_(song_ids))
        .all()
    }


def _serialize_song(song: Song, *, is_favorite: bool) -> SongResponse:
    return SongResponse(
        id=song.id,
        title=song.title,
        youtube_id=song.youtube_id,
        file_url=song.file_url,
        duration=song.duration,
        start=song.start,
        end=song.end,
        speed=song.speed,
        status=song.status.value,
        thumbnail_url=song.thumbnail_url,
        channel=song.channel,
        upload_date=song.upload_date,
        created_at=song.created_at.isoformat(),
        is_favorite=is_favorite,
    )


def _serialize_playlist(playlist: Playlist) -> dict[str, object]:
    return PlaylistResponse(
        id=playlist.id,
        name=playlist.name,
        created_at=playlist.created_at.isoformat(),
        song_count=len(playlist.songs),
    ).model_dump(mode="json")


def _serialize_playlist_detail(playlist: Playlist, db: DbDep) -> dict[str, object]:
    song_ids = [s.id for s in playlist.songs]
    fav_ids = _favorite_ids_for_songs(song_ids, db)
    songs = [_serialize_song(s, is_favorite=(s.id in fav_ids)) for s in playlist.songs]
    return PlaylistDetailResponse(
        id=playlist.id,
        name=playlist.name,
        created_at=playlist.created_at.isoformat(),
        songs=songs,
    ).model_dump(mode="json")


def _get_playlist_or_404(playlist_id: UUID, db: DbDep) -> Playlist:
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(
            status_code=404, detail=f"Playlist {playlist_id} not found."
        )
    return playlist


def _get_song_or_404(song_id: UUID, db: DbDep) -> Song:
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")
    return song


def _next_position(playlist_id: UUID, db: DbDep) -> int:
    """Return max(position) + 1 for a playlist, or 0 if empty."""
    result = (
        db.query(func.max(PlaylistSong.position))
        .filter(PlaylistSong.playlist_id == playlist_id)
        .scalar()
    )
    return 0 if result is None else result + 1


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
def create_playlist(payload: PlaylistCreate, db: DbDep) -> JSONResponse:
    """Create a new playlist.

    Args:
        payload: Playlist creation data (name).
        db: Database dependency.

    Returns:
        JSONResponse with the created playlist.
    """
    playlist = Playlist(name=payload.name)
    db.add(playlist)
    db.commit()
    db.refresh(playlist)

    logger.info("playlist_created", playlist_id=str(playlist.id), name=playlist.name)
    return envelope_response(
        _serialize_playlist(playlist), "Playlist created.", status_code=201
    )


@router.get("")
def list_playlists(db: DbDep) -> JSONResponse:
    """List all playlists ordered by creation date descending."""
    rows = (
        db.query(Playlist, func.count(PlaylistSong.song_id))
        .outerjoin(PlaylistSong, PlaylistSong.playlist_id == Playlist.id)
        .group_by(Playlist.id)
        .order_by(Playlist.created_at.desc())
        .all()
    )
    records = [
        PlaylistResponse(
            id=playlist.id,
            name=playlist.name,
            created_at=playlist.created_at.isoformat(),
            song_count=song_count,
        ).model_dump(mode="json")
        for playlist, song_count in rows
    ]
    logger.info("playlists_listed", count=len(records))
    return paginated_response(records, len(records), "Playlists retrieved.")


@router.get("/{playlist_id}")
def get_playlist(playlist_id: UUID, db: DbDep) -> JSONResponse:
    """Get playlist detail including ordered songs."""
    playlist = _get_playlist_or_404(playlist_id, db)
    logger.info("playlist_retrieved", playlist_id=str(playlist_id))
    return envelope_response(
        _serialize_playlist_detail(playlist, db), "Playlist retrieved."
    )


@router.post("/{playlist_id}/songs/{song_id}", status_code=status.HTTP_201_CREATED)
def add_song_to_playlist(playlist_id: UUID, song_id: UUID, db: DbDep) -> JSONResponse:
    """Add a song to a playlist.

    Idempotent — calling with the same song returns 200 OK.

    Position is assigned as max(position) + 1. If a concurrent request claims
    the same position (race), we retry up to _MAX_POSITION_RETRIES times before
    raising. The DB-level UniqueConstraint on (playlist_id, position) is the
    authoritative guard; the retry loop keeps the conflict window small.
    """
    playlist = _get_playlist_or_404(playlist_id, db)
    _get_song_or_404(song_id, db)

    existing = (
        db.query(PlaylistSong)
        .filter(
            PlaylistSong.playlist_id == playlist_id,
            PlaylistSong.song_id == song_id,
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
            _serialize_playlist(playlist),
            "Song already in playlist.",
            status_code=200,
        )

    for attempt in range(_MAX_POSITION_RETRIES):
        position = _next_position(playlist_id, db)
        entry = PlaylistSong(
            playlist_id=playlist_id, song_id=song_id, position=position
        )
        db.add(entry)
        try:
            db.commit()
            break  # success
        except IntegrityError as exc:
            db.rollback()
            constraint = getattr(
                getattr(exc.orig, "diag", None), "constraint_name", None
            )
            if constraint == "uq_playlist_song":
                # Duplicate (playlist_id, song_id) — lost race with identical request.
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
                # Duplicate (playlist_id, position) — concurrent add claimed this slot.
                logger.warning(
                    "playlist_position_conflict_retry",
                    playlist_id=str(playlist_id),
                    attempt=attempt + 1,
                )
                continue
            raise  # unknown constraint or retries exhausted → 500
    else:
        # All retries exhausted on position conflict.
        logger.error(
            "playlist_position_retries_exhausted",
            playlist_id=str(playlist_id),
            song_id=str(song_id),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not assign a unique position; please retry.",
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


@router.delete("/{playlist_id}/songs/{song_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_song_from_playlist(playlist_id: UUID, song_id: UUID, db: DbDep) -> Response:
    """Remove a song from a playlist. 404 if playlist, song, or membership not found."""
    _get_playlist_or_404(playlist_id, db)
    _get_song_or_404(song_id, db)

    entry = (
        db.query(PlaylistSong)
        .filter(
            PlaylistSong.playlist_id == playlist_id,
            PlaylistSong.song_id == song_id,
        )
        .first()
    )
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"Song {song_id} is not in playlist {playlist_id}.",
        )

    db.delete(entry)
    db.commit()
    db.expire_all()

    logger.info(
        "playlist_song_removed",
        playlist_id=str(playlist_id),
        song_id=str(song_id),
    )
    return Response(status_code=204)


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(playlist_id: UUID, db: DbDep) -> Response:
    """Delete a playlist and all its song associations (cascade)."""
    playlist = _get_playlist_or_404(playlist_id, db)
    db.delete(playlist)
    db.commit()

    logger.info("playlist_deleted", playlist_id=str(playlist_id))
    return Response(status_code=204)
