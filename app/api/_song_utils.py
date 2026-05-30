"""Shared song serialization helpers.

Centralizes _is_favorited + _serialize so songs.py, favorites.py, and
playlists.py all produce identical SongResponse dicts without duplication.
"""

# app/api/_song_utils.py
from uuid import UUID

from app.core.deps import DbDep
from app.models.favorite import Favorite
from app.models.song import Song, SongStatus
from app.schemas.song import SongResponse


def _is_favorited(song_id: UUID, db: DbDep) -> bool:
    """Return True if an active (non-deleted) Favorite row exists for song_id."""
    return (
        db.query(Favorite)
        .filter(Favorite.song_id == song_id, Favorite.deleted_at.is_(None))
        .first()
        is not None
    )


def _stream_url(song: Song) -> str:
    """Derive the appropriate stream URL based on song status and soft-delete state."""
    if song.status == SongStatus.done and song.deleted_at is None:
        return f"/songs/{song.id}/stream"
    return f"/songs/{song.id}"


def serialize_song(
    song: Song,
    db: DbDep,
    *,
    is_favorite: bool | None = None,
) -> dict[str, object]:
    """Serialize a Song ORM instance into a SongResponse dict.

    Args:
        song: The Song ORM instance.
        db: Active DB session (used for is_favorite lookup when not provided).
        is_favorite: Pre-fetched favorite flag. When None, performs a single
            DB query. Pass explicitly to avoid N+1 in list endpoints.

    Returns:
        JSON-serializable dict following SongResponse schema.
    """
    if is_favorite is None:
        is_favorite = _is_favorited(song.id, db)

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
        stream_url=_stream_url(song),
    ).model_dump(mode="json")
