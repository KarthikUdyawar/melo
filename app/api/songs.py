"""Song-related API endpoints.

This module provides FastAPI routes for managing songs with the following
functionality:
- Submitting YouTube URLs for async download and processing
- Previewing YouTube metadata without persisting data
- Listing all songs with favorite status
- Retrieving individual song details
- Streaming processed audio (with optional trim and speed adjustment)

All endpoints are prefixed with `/songs`.
"""

# app/api/songs.py
from collections.abc import Generator
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.responses import envelope_response, paginated_response
from app.core.config import get_settings
from app.core.deps import DbDep
from app.core.logging import get_logger
from app.models.favorite import Favorite
from app.models.song import Song, SongStatus
from app.schemas.song import (
    PreviewRequest,
    SongCreate,
    SongPreviewResponse,
    SongResponse,
)
from app.services.downloader import extract_youtube_id
from app.services.processor import ProcessingError, apply_speed, trim_audio
from app.services.storage import _client

logger = get_logger(__name__)

router = APIRouter(prefix="/songs", tags=["songs"])


_TMP_DIR = Path("/tmp/melo")  # nosec B108


def _is_favorited(song_id: UUID, db: DbDep) -> bool:
    """Check if a song is favorited by the current user.

    Args:
        song_id: UUID of the song to check.
        db: Database dependency.

    Returns:
        True if the song is in the user's favorites, False otherwise.
    """
    return db.query(Favorite).filter(Favorite.song_id == song_id).first() is not None


def _serialize(
    song: Song,
    db: DbDep,
    *,
    is_favorite: bool | None = None,
) -> dict[str, object]:
    """Serialize a Song model into a SongResponse dictionary.

    Args:
        song: The Song ORM instance to serialize.
        db: Database dependency (used only if is_favorite is None).
        is_favorite: Pre-computed favorite status to avoid N+1 queries.
            If None, it will be queried individually.

    Returns:
        Dictionary representation of the song following the SongResponse schema.
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
    ).model_dump(mode="json")


def build_content_disposition(filename: str) -> str:
    """Build RFC 5987 compliant Content-Disposition header with UTF-8 support.

    Args:
        filename: Original filename to be used in the download header.

    Returns:
        Content-Disposition string that supports both ASCII fallback and UTF-8
        characters (e.g. non-English song titles).
    """
    ascii_fallback = filename.encode("latin-1", "ignore").decode()
    utf8_encoded = quote(filename)

    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{utf8_encoded}"


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_song(payload: SongCreate, db: DbDep) -> JSONResponse:
    """Submit a YouTube URL for asynchronous download and processing.

    First submission creates a new record and enqueues a Celery task.
    Duplicate submissions with different trim/speed settings create new
    records (deduplication of download is handled by the worker).

    Args:
        payload: Song creation payload containing YouTube URL and optional
            trim/speed parameters.
        db: Database dependency.

    Returns:
        Envelope response with the created song and status 202 Accepted.

    Raises:
        HTTPException: 422 if the YouTube URL is invalid.
    """
    logger.info("create_song_request", url=payload.url, speed=payload.speed)

    try:
        youtube_id = extract_youtube_id(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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
        )
        logger.info("song_processing_dispatched", song_id=str(song.id))
    except Exception as exc:
        logger.error("celery_dispatch_failed", song_id=str(song.id), error=str(exc))
        raise

    return envelope_response(
        _serialize(song, db),
        "Song submitted.",
        status.HTTP_202_ACCEPTED,
    )


@router.post("/preview")
def preview_song(payload: PreviewRequest) -> JSONResponse:
    """Preview YouTube song metadata without creating any database record.

    Pure metadata probe using yt-dlp. Used to show the user details before
    submitting the actual song.

    Args:
        payload: Preview request containing the YouTube URL.

    Returns:
        Envelope response with song preview metadata.

    Raises:
        HTTPException: 422 for invalid URL, 502 if metadata fetching fails.
    """
    from app.services.downloader import (
        DownloadError,
        extract_youtube_id,
        probe_metadata,
    )

    logger.info("preview_request", url=payload.url)

    try:
        youtube_id = extract_youtube_id(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        meta = probe_metadata(payload.url)
    except DownloadError as exc:
        logger.error("preview_probe_failed", url=payload.url, error=str(exc))
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch metadata: {exc}",
        ) from exc

    preview = SongPreviewResponse(
        youtube_id=youtube_id,
        title=meta.get("title"),
        duration=meta.get("duration"),
        thumbnail_url=meta.get("thumbnail_url"),
        channel=meta.get("channel"),
        upload_date=meta.get("upload_date"),
    )

    logger.info(
        "preview_complete",
        youtube_id=youtube_id,
        title=preview.title,
        duration=preview.duration,
    )

    return envelope_response(
        preview.model_dump(mode="json"),
        "Metadata fetched successfully.",
    )


@router.get("")
def list_songs(db: DbDep) -> JSONResponse:
    """List all songs ordered by creation date (newest first).

    Optimised to fetch all favorite statuses in a single query to avoid N+1.

    Args:
        db: Database dependency.

    Returns:
        Paginated envelope response containing all songs with their favorite
        status.
    """
    logger.debug("list_songs_request")
    songs = db.query(Song).order_by(Song.created_at.desc()).all()

    # Prefetch all favorites in one query → eliminates N+1
    song_ids = [s.id for s in songs]
    favorite_ids: set[UUID] = set()
    if song_ids:
        favorite_ids = {
            sid
            for (sid,) in db.query(Favorite.song_id)
            .filter(Favorite.song_id.in_(song_ids))
            .all()
        }

    records = [_serialize(s, db, is_favorite=(s.id in favorite_ids)) for s in songs]
    return paginated_response(records, len(records), "Songs retrieved.")


@router.get("/{song_id}")
def get_song(song_id: UUID, db: DbDep) -> JSONResponse:
    """Retrieve detailed information about a single song.

    Args:
        song_id: UUID of the song to retrieve.
        db: Database dependency.

    Returns:
        Envelope response with the song data.

    Raises:
        HTTPException: 404 if the song is not found.
    """
    logger.debug("get_song_request", song_id=str(song_id))
    song = db.query(Song).filter(Song.id == song_id).first()

    if not song:
        logger.warning("song_not_found", song_id=str(song_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Song {song_id} not found.",
        )

    logger.info("song_retrieved", song_id=str(song_id))
    return envelope_response(_serialize(song, db), "Song retrieved.")


@router.get("/{song_id}/stream")
def stream_song(song_id: UUID, db: DbDep) -> StreamingResponse:
    """Stream a processed song with optional on-the-fly trimming and speed adjustment.

    Supports four streaming modes:
    - Direct MinIO proxy (no trim, no speed) — fastest
    - Trim only
    - Speed only
    - Trim + Speed

    NOTE: This endpoint returns a raw StreamingResponse (no envelope) because
    it streams binary audio data.

    Args:
        song_id: UUID of the song to stream.
        db: Database dependency.

    Returns:
        StreamingResponse with audio/mpeg content.

    Raises:
        HTTPException: 404 if song not found, 409 if not ready, \
            502 on processing errors.
    """
    logger.debug("stream_request", song_id=str(song_id))

    song = db.query(Song).filter(Song.id == song_id).first()

    if not song:
        logger.warning("stream_song_not_found", song_id=str(song_id))
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")

    if song.status != SongStatus.done:
        logger.warning(
            "stream_not_ready",
            song_id=str(song_id),
            status=song.status.value,
        )
        raise HTTPException(
            status_code=409,
            detail=f"Song not ready. Status: {song.status.value}",
        )

    if not song.file_url:
        logger.error("missing_file_url", song_id=str(song_id))
        raise HTTPException(
            status_code=500,
            detail="Song marked done but has no file_url.",
        )

    s = get_settings()
    client = _client()
    filename = f"{song.title or song_id}.mp3"

    has_trim = song.start is not None or song.end is not None
    has_speed = song.speed is not None and song.speed != 1.0

    # ── Case 1: No trim, no speed — direct MinIO proxy ───────────────────────
    if not has_trim and not has_speed:
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
            "stream_started",
            song_id=str(song_id),
            filename=filename,
            mode="direct",
        )
        return StreamingResponse(
            response.stream(32 * 1024),
            media_type="audio/mpeg",
            headers={"Content-Disposition": build_content_disposition(filename)},
        )

    # ── Cases 2–4: fetch → [trim] → [speed] → stream → cleanup ──────────────
    original_path = _TMP_DIR / f"{song_id}_original.mp3"
    trimmed_path = _TMP_DIR / f"{song_id}_trimmed.mp3"
    speed_path = _TMP_DIR / f"{song_id}_speed.mp3"

    # Track which paths actually get created for guaranteed cleanup
    created_paths: list[Path] = []

    try:
        _TMP_DIR.mkdir(parents=True, exist_ok=True)

        # 1. Fetch from MinIO ─────────────────────────────────────────────────
        logger.debug(
            "stream_fetch",
            song_id=str(song_id),
            has_trim=has_trim,
            has_speed=has_speed,
        )
        try:
            minio_response = client.get_object(s.minio_bucket, song.file_url)

            try:
                with original_path.open("wb") as f:
                    for chunk in minio_response.stream(32 * 1024):
                        f.write(chunk)
            finally:
                minio_response.close()
                minio_response.release_conn()

            created_paths.append(original_path)
        except Exception as exc:
            logger.error("stream_fetch_error", song_id=str(song_id), error=str(exc))
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        # 2. Trim (if needed) ─────────────────────────────────────────────────
        post_trim_path = original_path  # default: pass original through
        if has_trim:
            try:
                trim_audio(
                    input_path=original_path,
                    output_path=trimmed_path,
                    start=song.start,
                    end=song.end,
                )
                created_paths.append(trimmed_path)
                post_trim_path = trimmed_path
            except ProcessingError as exc:
                logger.error("trim_error", song_id=str(song_id), error=str(exc))
                raise HTTPException(
                    status_code=502,
                    detail=f"Trim failed: {exc}",
                ) from exc

        # 3. Speed (if needed) ────────────────────────────────────────────────
        final_path = post_trim_path  # default: pass trim result through
        if has_speed:
            try:
                apply_speed(
                    input_path=post_trim_path,
                    output_path=speed_path,
                    speed=song.speed,
                )
                created_paths.append(speed_path)
                final_path = speed_path
            except ProcessingError as exc:
                logger.error("speed_error", song_id=str(song_id), error=str(exc))
                raise HTTPException(
                    status_code=502,
                    detail=f"Speed processing failed: {exc}",
                ) from exc

        # 4. Stream + cleanup in generator ────────────────────────────────────
        mode = (
            "trim+speed" if has_trim and has_speed else "trim" if has_trim else "speed"
        )

        logger.info(
            "stream_started",
            song_id=str(song_id),
            filename=filename,
            mode=mode,
            start=song.start,
            end=song.end,
            speed=song.speed,
        )

        # Capture for closure (list is mutable, safe across generator boundary)
        paths_to_cleanup = list(created_paths)

        def _iter_and_cleanup() -> Generator[bytes, None, None]:
            try:
                with final_path.open("rb") as f:
                    while chunk := f.read(32 * 1024):
                        yield chunk
            finally:
                for p in paths_to_cleanup:
                    p.unlink(missing_ok=True)
                logger.debug("stream_cleanup", song_id=str(song_id), mode=mode)

        return StreamingResponse(
            _iter_and_cleanup(),
            media_type="audio/mpeg",
            headers={"Content-Disposition": build_content_disposition(filename)},
        )

    except HTTPException:
        # Pre-stream error: cleanup synchronously before raising
        for p in created_paths:
            p.unlink(missing_ok=True)
        raise
