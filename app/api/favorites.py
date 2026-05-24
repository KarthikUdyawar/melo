"""Favorites API — LIB-1.

POST   /favorites/{song_id}  → 201 created / 200 already favorited (idempotent)
DELETE /favorites/{song_id}  → 204 removed / 404 not favorited
GET    /favorites             → list of favorited songs
"""

# app/api/favorites.py
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api._song_utils import serialize_song
from app.api.responses import envelope_response
from app.core.deps import DbDep
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
    song = db.query(Song).filter(Song.id == song_id, Song.deleted_at.is_(None)).first()
    if not song:
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")

    if _active_favorite(song_id, db):
        logger.info("favorite_already_exists", song_id=str(song_id))
        return envelope_response(
            {"song_id": str(song_id)}, "Already favorited.", status_code=200
        )

    fav = Favorite(song_id=song_id)
    db.add(fav)
    try:
        db.commit()
        db.refresh(fav)
    except IntegrityError:
        db.rollback()
        logger.info("favorite_already_exists_race", song_id=str(song_id))
        return envelope_response(
            {"song_id": str(song_id)}, "Already favorited.", status_code=200
        )

    logger.info("favorite_created", song_id=str(song_id))
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
    song = db.query(Song).filter(Song.id == song_id, Song.deleted_at.is_(None)).first()
    if not song:
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")

    fav = _active_favorite(song_id, db)
    if not fav:
        raise HTTPException(status_code=404, detail=f"Song {song_id} is not favorited.")

    fav.deleted_at = datetime.now(UTC)
    db.commit()

    logger.info("favorite_removed", song_id=str(song_id))
    return Response(status_code=204)


@router.get(
    "",
    summary="List all favorited songs",
)
def list_favorites(db: DbDep) -> JSONResponse:
    """Return all active favorites ordered by \
        when they were favorited (newest first)."""
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
