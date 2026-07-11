"""Favorites API — LIB-1."""

# app/api/favorites.py
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.api._song_utils import serialize_song
from app.api.responses import envelope_response
from app.core.deps import DbDep
from app.core.log_events import LogEvent
from app.core.logging import get_logger
from app.models.favorite import Favorite
from app.models.song import Song

logger = get_logger(__name__)

router = APIRouter(prefix="/favorites", tags=["favorites"])


def _active_favorite(song_id: UUID, db: DbDep) -> Favorite | None:
    """Return the active (non-deleted) Favorite row for a song, or None."""
    return (
        db.query(Favorite)
        .filter(Favorite.song_id == song_id, Favorite.deleted_at.is_(None))
        .first()
    )


@router.post(
    "/{song_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Favorite a song (idempotent)",
    responses={
        200: {"description": "Already favorited"},
        201: {"description": "Favorited"},
        404: {"description": "Song not found"},
    },
)
def add_favorite(song_id: UUID, db: DbDep) -> JSONResponse:
    """Mark a song as favorite. Returns 201 on create, 200 if already favorited."""
    from app.core.metrics import favorites_toggled_total

    song = db.query(Song).filter(Song.id == song_id, Song.deleted_at.is_(None)).first()
    if not song:
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")

    # Check for any row — active or soft-deleted — to avoid unique constraint violation.
    existing = (
        db.query(Favorite).filter(Favorite.song_id == song_id).first()
    )

    if existing:
        if existing.deleted_at is None:
            # Already active — idempotent 200.
            logger.info(LogEvent.FAVORITE_ADDED, song_id=str(song_id), already=True)
            return envelope_response(
                {"song_id": str(song_id)}, "Already favorited.", status_code=200
            )
        # Soft-deleted row exists — reactivate it.
        existing.deleted_at = None
        db.commit()
        favorites_toggled_total.labels(action="add").inc()
        logger.info(LogEvent.FAVORITE_ADDED, song_id=str(song_id))
        return envelope_response(
            {"song_id": str(song_id)}, "Song favorited.", status_code=201
        )

    fav = Favorite(song_id=song_id)
    db.add(fav)
    db.commit()
    db.refresh(fav)

    favorites_toggled_total.labels(action="add").inc()
    logger.info(LogEvent.FAVORITE_ADDED, song_id=str(song_id))
    return envelope_response(
        {"song_id": str(song_id)}, "Song favorited.", status_code=201
    )


@router.delete(
    "/{song_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a song from favorites",
    responses={
        204: {"description": "Unfavorited"},
        404: {"description": "Song not found or not favorited"},
    },
)
def remove_favorite(song_id: UUID, db: DbDep) -> Response:
    """Soft-delete the favorite row. Returns 404 if song or favorite not found."""
    from app.core.metrics import favorites_toggled_total

    song = db.query(Song).filter(Song.id == song_id, Song.deleted_at.is_(None)).first()
    if not song:
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")

    fav = _active_favorite(song_id, db)
    if not fav:
        raise HTTPException(status_code=404, detail=f"Song {song_id} is not favorited.")

    fav.deleted_at = datetime.now(UTC)
    db.commit()

    favorites_toggled_total.labels(action="remove").inc()
    logger.info(LogEvent.FAVORITE_REMOVED, song_id=str(song_id))
    return Response(status_code=204)


@router.get(
    "",
    summary="List all favorited songs",
)
def list_favorites(db: DbDep) -> JSONResponse:
    """Return all active favorite songs.

    Order the results by the time they were favorited, with the newest
    favorites returned first.
    """
    rows = (
        db.query(Song)
        .join(Favorite, Favorite.song_id == Song.id)
        .filter(Favorite.deleted_at.is_(None), Song.deleted_at.is_(None))
        .order_by(Favorite.created_at.desc())
        .all()
    )

    records = [serialize_song(s, db, is_favorite=True) for s in rows]
    logger.info("favorites_listed", count=len(records))
    return envelope_response(
        {"records": records, "count": len(records), "bookmark": None},
        "Favorites retrieved.",
    )
