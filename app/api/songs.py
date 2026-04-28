# app/api/songs.py
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.responses import envelope_response, paginated_response
from app.core.config import get_settings
from app.core.deps import DbDep
from app.core.logging import get_logger
from app.models.song import Song, SongStatus
from app.schemas.song import SongCreate, SongResponse
from app.services.storage import _client

logger = get_logger(__name__)

router = APIRouter(prefix="/songs", tags=["songs"])

YOUTUBE_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}

YOUTUBE_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{11}$")

_TMP_DIR = Path("/tmp/melo")


def _serialize(song: Song) -> dict:
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
    ).model_dump(mode="json")


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_song(payload: SongCreate, db: DbDep) -> JSONResponse:
    """
    Submit a YouTube URL for async download + processing.

    - First submission: creates record, enqueues Celery task.
    - Same youtube_id + different trim: creates new record, task handles dedup
      (reuses existing MinIO object, no re-download).
    """
    logger.info("create_song_request", url=payload.url, speed=payload.speed)

    youtube_id = _extract_youtube_id(payload.url)
    logger.debug("youtube_id_extracted", youtube_id=youtube_id)

    song = Song(
        youtube_id=youtube_id,
        start=payload.start,
        end=payload.end,
        speed=payload.speed,
        status=SongStatus.pending,
    )

    db.add(song)
    db.commit()
    db.refresh(song)

    logger.info(
        "song_created",
        song_id=str(song.id),
        youtube_id=youtube_id,
        status=song.status.value,
    )

    from app.workers.tasks import process_song_task

    try:
        process_song_task.delay(
            str(song.id),
            payload.url,
            payload.start,
            payload.end,
            payload.speed,
        )
        logger.info("song_processing_dispatched", song_id=str(song.id))
    except Exception as exc:
        logger.error("celery_dispatch_failed", song_id=str(song.id), error=str(exc))
        raise

    return envelope_response(
        _serialize(song), "Song submitted.", status.HTTP_202_ACCEPTED
    )


@router.get("")
def list_songs(db: DbDep) -> JSONResponse:
    """List all songs with their current processing status."""
    logger.debug("list_songs_request")
    songs = db.query(Song).order_by(Song.created_at.desc()).all()
    logger.info("songs_retrieved", count=len(songs))
    records = [_serialize(s) for s in songs]
    return paginated_response(records, len(records), "Songs retrieved.")


@router.get("/{song_id}")
def get_song(song_id: UUID, db: DbDep) -> JSONResponse:
    """Retrieve a single song by ID."""
    logger.debug("get_song_request", song_id=str(song_id))
    song = db.query(Song).filter(Song.id == song_id).first()

    if not song:
        logger.warning("song_not_found", song_id=str(song_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Song {song_id} not found.",
        )

    logger.info("song_retrieved", song_id=str(song_id))
    return envelope_response(_serialize(song), "Song retrieved.")


@router.get("/{song_id}/stream")
def stream_song(song_id: UUID, db: DbDep) -> StreamingResponse:
    """
    Stream the audio for a done song.

    Trim-on-stream logic
    --------------------
    - No trim params (start=None, end=None): stream raw MinIO object directly.
    - Trim params set: fetch to /tmp/melo, run FFmpeg trim, stream result, cleanup.

    NOTE: StreamingResponse intentionally skips envelope (binary stream).
    """
    logger.debug("stream_request", song_id=str(song_id))

    song = db.query(Song).filter(Song.id == song_id).first()

    if not song:
        logger.warning("stream_song_not_found", song_id=str(song_id))
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")

    if song.status != SongStatus.done:
        logger.warning(
            "stream_not_ready", song_id=str(song_id), status=song.status.value
        )
        raise HTTPException(
            status_code=409, detail=f"Song not ready. Status: {song.status.value}"
        )

    if not song.file_url:
        logger.error("missing_file_url", song_id=str(song_id))
        raise HTTPException(
            status_code=500, detail="Song marked done but has no file_url."
        )

    s = get_settings()
    client = _client()
    filename = f"{song.title or song_id}.mp3"

    # ── No trim: stream directly from MinIO ──────────────────────────────────
    if song.start is None and song.end is None:
        try:
            logger.debug(
                "stream_direct",
                song_id=str(song_id),
                bucket=s.minio_bucket,
                file_url=song.file_url,
            )
            response = client.get_object(s.minio_bucket, song.file_url)
        except Exception as exc:
            logger.error("stream_fetch_error", song_id=str(song_id), error=str(exc))
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        logger.info(
            "stream_started", song_id=str(song_id), filename=filename, mode="direct"
        )
        return StreamingResponse(
            response.stream(32 * 1024),
            media_type="audio/mpeg",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ── Trim: fetch → FFmpeg → stream → cleanup ──────────────────────────────
    from app.services.processor import ProcessingError, trim_audio

    original_path = _TMP_DIR / f"{song_id}_original.mp3"
    trimmed_path = _TMP_DIR / f"{song_id}_trimmed.mp3"

    try:
        # 1. Fetch from MinIO to local tmp
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        logger.debug(
            "stream_fetch_for_trim",
            song_id=str(song_id),
            start=song.start,
            end=song.end,
        )
        try:
            minio_response = client.get_object(s.minio_bucket, song.file_url)
            with original_path.open("wb") as f:
                for chunk in minio_response.stream(32 * 1024):
                    f.write(chunk)
        except Exception as exc:
            logger.error("stream_fetch_error", song_id=str(song_id), error=str(exc))
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        # 2. Trim
        try:
            trim_audio(
                input_path=original_path,
                output_path=trimmed_path,
                start=song.start,
                end=song.end,
            )
        except ProcessingError as exc:
            logger.error("trim_error", song_id=str(song_id), error=str(exc))
            raise HTTPException(status_code=502, detail=f"Trim failed: {exc}") from exc

        # 3. Stream trimmed file, cleanup in generator finally block
        logger.info(
            "stream_started",
            song_id=str(song_id),
            filename=filename,
            mode="trimmed",
            start=song.start,
            end=song.end,
        )

        def _iter_and_cleanup():
            try:
                with trimmed_path.open("rb") as f:
                    while chunk := f.read(32 * 1024):
                        yield chunk
            finally:
                original_path.unlink(missing_ok=True)
                trimmed_path.unlink(missing_ok=True)
                logger.debug("stream_trim_cleanup", song_id=str(song_id))

        return StreamingResponse(
            _iter_and_cleanup(),
            media_type="audio/mpeg",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        # Cleanup on error before streaming starts
        original_path.unlink(missing_ok=True)
        trimmed_path.unlink(missing_ok=True)
        raise


def _extract_youtube_id(url: str) -> str:
    """
    Extract YouTube video ID from any URL format.
    Works with playlists but only returns video_id.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if domain not in YOUTUBE_DOMAINS:
        raise ValueError(f"Invalid YouTube domain: {domain}")

    # --- 1. Query param (?v=...) → MOST IMPORTANT (covers playlists)
    query = parse_qs(parsed.query)
    video_ids = query.get("v")
    if video_ids:
        vid = video_ids[0]
        if YOUTUBE_ID_REGEX.match(vid):
            return vid

    # --- 2. Short URL (youtu.be/<id>)
    if domain == "youtu.be":
        vid = parsed.path.lstrip("/").split("/")[0]
        if YOUTUBE_ID_REGEX.match(vid):
            return vid

    # --- 3. Path-based formats (/shorts/, /embed/, /live/)
    match = re.search(r"/(shorts|embed|live)/([\w\-]{11})", parsed.path)
    if match:
        return match.group(2)

    raise ValueError("Could not extract valid YouTube video ID")
