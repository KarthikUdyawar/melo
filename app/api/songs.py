# app/api/songs.py
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.responses import envelope_response, paginated_response
from app.core.config import get_settings
from app.core.deps import DbDep
from app.models.song import Song, SongStatus
from app.schemas.song import SongCreate, SongResponse
from app.services.storage import _client

router = APIRouter(prefix="/songs", tags=["songs"])


def _serialize(song: Song) -> dict:
    return SongResponse(
        id=song.id,
        title=song.title,
        youtube_id=song.youtube_id,
        file_url=song.file_url,
        duration=song.duration,
        speed=song.speed,
        status=song.status.value,
        created_at=song.created_at.isoformat(),
    ).model_dump(mode="json")


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_song(payload: SongCreate, db: DbDep) -> JSONResponse:
    """
    Submit a YouTube URL for async download + processing.

    Returns the created song record (status=pending) immediately.
    The Celery worker will update status → processing → done/failed.
    """
    existing = (
        db.query(Song)
        .filter(Song.youtube_id == _extract_youtube_id(payload.url))
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Song with youtube_id '{existing.youtube_id}' \
                already exists (id={existing.id}).",
        )

    youtube_id = _extract_youtube_id(payload.url)
    song = Song(
        youtube_id=youtube_id,
        speed=payload.speed,
        status=SongStatus.pending,
    )
    db.add(song)
    db.commit()
    db.refresh(song)

    from app.workers.tasks import process_song_task

    process_song_task.delay(
        str(song.id),
        payload.url,
        payload.start,
        payload.end,
        payload.speed,
    )

    return envelope_response(
        _serialize(song), "Song submitted.", status.HTTP_202_ACCEPTED
    )


@router.get("")
def list_songs(db: DbDep) -> JSONResponse:
    """List all songs with their current processing status."""
    songs = db.query(Song).order_by(Song.created_at.desc()).all()
    records = [_serialize(s) for s in songs]
    return paginated_response(records, len(records), "Songs retrieved.")


@router.get("/{song_id}")
def get_song(song_id: UUID, db: DbDep) -> JSONResponse:
    """Retrieve a single song by ID."""
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Song {song_id} not found.",
        )
    return envelope_response(_serialize(song), "Song retrieved.")


@router.get("/{song_id}/stream")
def stream_song(song_id: UUID, db: DbDep) -> StreamingResponse:
    # NOTE: StreamingResponse intentionally skips envelope (binary stream).
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")
    if song.status != SongStatus.done:
        raise HTTPException(
            status_code=409, detail=f"Song not ready. Status: {song.status.value}"
        )
    if not song.file_url:
        raise HTTPException(
            status_code=500, detail="Song marked done but has no file_url."
        )

    s = get_settings()
    client = _client()

    try:
        response = client.get_object(s.minio_bucket, song.file_url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    filename = f"{song.title or song_id}.mp3"

    return StreamingResponse(
        response.stream(32 * 1024),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _extract_youtube_id(url: str) -> str:
    """
    Extract the 11-char video ID from any supported YouTube URL format.

    Supported:
      https://www.youtube.com/watch?v=<id>
      https://youtu.be/<id>
      https://youtube.com/shorts/<id>
      https://youtube.com/embed/<id>
    """
    import re

    patterns = [
        r"(?:v=)([\w\-]{11})",
        r"youtu\.be/([\w\-]{11})",
        r"(?:shorts|embed)/([\w\-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    # Fallback: last 11-char segment (already validated by SongCreate)
    return url.split("/")[-1][:11]
