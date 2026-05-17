"""Favorites API — LIB-1.

POST   /favorites/{song_id}  → 201 created / 200 already favorited (idempotent)
DELETE /favorites/{song_id}  → 204 removed / 404 not favorited
GET    /favorites             → paginated list of favorited songs
"""

# app/api/favorites.py
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.responses import envelope_response, paginated_response
from app.core.deps import DbDep
from app.core.logging import get_logger
from app.models.favorite import Favorite
from app.models.song import Song

logger = get_logger(__name__)

router = APIRouter(prefix="/favorites", tags=["favorites"])


def _serialize_song(song: Song, *, is_favorite: bool = True) -> dict[str, object]:
    """Serialize a Song model into a SongResponse dict.

    Args:
        song: The Song ORM model instance to serialize.
        is_favorite: Whether to mark the song as favorited in the response.
            Defaults to True.

    Returns:
        dict representation of the song following SongResponse schema.
    """
    from app.schemas.song import SongResponse

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
    ).model_dump(mode="json")


@router.post("/{song_id}", status_code=status.HTTP_201_CREATED)
def add_favorite(song_id: UUID, db: DbDep) -> JSONResponse:
    """Favorite a song.

    The operation is idempotent: calling it again on an already favorited
    song returns 200 instead of 201.

    Uniqueness is enforced at the database level via a unique constraint.

    Args:
        song_id: UUID of the song to favorite.
        db: Database dependency.

    Returns:
        JSONResponse with envelope containing the song_id and appropriate message.

    Raises:
        HTTPException: 404 if the song does not exist.
    """
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")

    existing = db.query(Favorite).filter(Favorite.song_id == song_id).first()
    if existing:
        logger.info("favorite_already_exists", song_id=str(song_id))
        return envelope_response(
            {"song_id": str(song_id)},
            "Already favorited.",
            status_code=200,
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
            {"song_id": str(song_id)},
            "Already favorited.",
            status_code=200,
        )

    logger.info("favorite_created", song_id=str(song_id))
    return envelope_response(
        {"song_id": str(song_id)},
        "Song favorited.",
        status_code=201,
    )


@router.delete("/{song_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(song_id: UUID, db: DbDep) -> Response:
    """Remove a song from the user's favorites.

    Args:
        song_id: UUID of the song to remove from favorites.
        db: Database dependency.

    Returns:
        Empty Response with status 204 on success.

    Raises:
        HTTPException: 404 if the song doesn't exist or is not favorited.
    """
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")

    fav = db.query(Favorite).filter(Favorite.song_id == song_id).first()
    if not fav:
        raise HTTPException(status_code=404, detail=f"Song {song_id} is not favorited.")

    db.delete(fav)
    db.commit()

    logger.info("favorite_removed", song_id=str(song_id))
    return Response(status_code=204)


@router.get("")
def list_favorites(db: DbDep) -> JSONResponse:
    """List all songs favorited by the user.

    Results are ordered by when they were favorited (newest first).
    Each song includes full metadata and `is_favorite=True`.

    Args:
        db: Database dependency.

    Returns:
        Paginated JSON response containing the list of favorited songs.
    """
    rows = (
        db.query(Song)
        .join(Favorite, Favorite.song_id == Song.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )

    records = [_serialize_song(s, is_favorite=True) for s in rows]
    logger.info("favorites_listed", count=len(records))
    return paginated_response(records, len(records), "Favorites retrieved.")
