"""Song-related API endpoints."""

# app/api/songs.py
from collections.abc import Iterator
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import literal, tuple_
from sqlalchemy.sql.elements import ColumnElement

from app.api._song_utils import serialize_song
from app.api.responses import envelope_response
from app.core.config import get_settings
from app.core.deps import DbDep
from app.core.log_events import LogEvent
from app.core.logging import get_logger
from app.models.favorite import Favorite
from app.models.song import Song, SongStatus
from app.schemas.song import (
    PreviewRequest,
    SongCreate,
    SongPreviewResponse,
)
from app.services.downloader import extract_youtube_id
from app.services.processor import ProcessingError, apply_speed, trim_audio
from app.services.storage import _client

logger = get_logger(__name__)

router = APIRouter(prefix="/songs", tags=["songs"])

_TMP_DIR = Path("/tmp/melo")  # nosec B108

_PRESIGNED_EXPIRY = 3600  # seconds


# ── query param enums ─────────────────────────────────────────────────────────


class SortBy(StrEnum):
    """Allowed sort fields for GET /songs."""

    created_at = "created_at"
    song_title = "title"
    duration = "duration"


class SortOrder(StrEnum):
    """Sort direction for GET /songs."""

    asc = "asc"
    desc = "desc"


# ── helpers ───────────────────────────────────────────────────────────────────


def build_content_disposition(filename: str) -> str:
    """Build RFC 5987 compliant Content-Disposition header with UTF-8 support."""
    cleaned = (
        filename.replace("\\", "_")
        .replace('"', "'")
        .replace("\r", "")
        .replace("\n", "")
    )
    ascii_fallback = cleaned.encode("latin-1", "ignore").decode() or "download.mp3"
    utf8_encoded = quote(cleaned)
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{utf8_encoded}"


def _sort_column(sort_by: SortBy, order: SortOrder) -> ColumnElement[Any]:
    col = {
        SortBy.created_at: Song.created_at,
        SortBy.song_title: Song.title,
        SortBy.duration: Song.duration,
    }[sort_by]
    return col.asc().nulls_last() if order == SortOrder.asc else col.desc().nulls_last()


def _cursor_column(sort_by: SortBy) -> ColumnElement[Any]:
    return {  # type: ignore[return-value]
        SortBy.created_at: Song.created_at,
        SortBy.song_title: Song.title,
        SortBy.duration: Song.duration,
    }[sort_by]


def _cursor_value(song: Song, sort_by: SortBy) -> object:
    return {
        SortBy.created_at: song.created_at,
        SortBy.song_title: song.title,
        SortBy.duration: song.duration,
    }[sort_by]


def _rewrite_minio_url(url: str) -> str:
    """Rewrite internal MinIO hostname to public URL if configured."""
    s = get_settings()
    if not s.minio_public_url:
        return url
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url)
    public = urlparse(s.minio_public_url)
    return urlunparse(parsed._replace(scheme=public.scheme, netloc=public.netloc))


def _inject_trace_context_into_task(
    task: Any,
    song_id: str,
    url: str,
) -> None:
    """Enqueue task with OTEL traceparent header injected."""
    try:
        from opentelemetry.propagate import inject

        headers: dict[str, str] = {}
        inject(headers)

        task.apply_async(
            args=(song_id, url),
            headers=headers,
        )
    except Exception:  # noqa: BLE001
        task.delay(song_id, url)


# ── endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/preview",
    summary="Preview YouTube metadata without persisting",
    responses={
        422: {"description": "Invalid YouTube URL"},
        502: {"description": "yt-dlp fetch failed"},
    },
)
def preview_song(payload: PreviewRequest) -> JSONResponse:
    """Fetch YouTube metadata (title, duration, thumbnail) without any DB write."""
    from app.services.downloader import DownloadError, probe_metadata

    try:
        youtube_id = extract_youtube_id(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        meta = probe_metadata(payload.url)
    except DownloadError as exc:
        logger.error(LogEvent.PREVIEW_FAILED, url=payload.url, error=str(exc))
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch metadata: {exc}"
        ) from exc

    logger.info(LogEvent.PREVIEW_FETCHED, url=payload.url, youtube_id=youtube_id)

    preview = SongPreviewResponse(
        youtube_id=youtube_id,
        title=meta.get("title"),
        duration=meta.get("duration"),
        thumbnail_url=meta.get("thumbnail_url"),
        channel=meta.get("channel"),
        upload_date=meta.get("upload_date"),
    )
    return envelope_response(
        preview.model_dump(mode="json"), "Metadata fetched successfully."
    )

@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a YouTube URL for async download and processing",
    responses={422: {"description": "Validation error"}},
)
def create_song(payload: SongCreate, db: DbDep) -> JSONResponse:
    """Submit a YouTube URL — returns 202 immediately, processing happens async."""
    from app.core.metrics import songs_submitted_total

    try:
        youtube_id = extract_youtube_id(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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

    songs_submitted_total.inc()

    logger.info(
        LogEvent.SONG_SUBMITTED,
        song_id=str(song.id),
        youtube_id=youtube_id,
        speed=payload.speed,
    )

    from app.workers.tasks import process_song_task

    try:
        # Inject OTEL trace context into Celery task headers
        _inject_trace_context_into_task(process_song_task, str(song.id), payload.url)
    except Exception as exc:
        logger.error(
            LogEvent.TASK_FAILED,
            song_id=str(song.id),
            error=str(exc),
        )
        try:
            song.status = SongStatus.failed
            db.commit()
        except Exception as db_exc:
            logger.error(
                LogEvent.TASK_FAILED,
                song_id=str(song.id),
                error=str(db_exc),
            )
        raise

    return envelope_response(
        serialize_song(song, db), "Song submitted.", status.HTTP_202_ACCEPTED
    )


@router.get(
    "",
    summary="List songs with filtering, sorting, and cursor pagination",
)
def list_songs(
    db: DbDep,
    status_filter: Annotated[
        SongStatus | None,
        Query(alias="status", description="Filter by processing status."),
    ] = None,
    favorite: Annotated[
        bool | None,
        Query(description="Filter to favorited (true) or unfavorited (false) songs."),
    ] = None,
    search: Annotated[
        str | None,
        Query(
            min_length=1, max_length=200, description="Case-insensitive title search."
        ),
    ] = None,
    sort_by: Annotated[
        SortBy,
        Query(description="Field to sort by. Defaults to created_at."),
    ] = SortBy.created_at,
    order: Annotated[
        SortOrder,
        Query(description="Sort direction. Defaults to desc."),
    ] = SortOrder.desc,
    limit: Annotated[
        int, Query(ge=1, le=1000, description="Max records per page.")
    ] = 50,
    offset: Annotated[
        int, Query(ge=0, description="Offset (ignored when after is set).")
    ] = 0,
    after: Annotated[
        UUID | None,
        Query(description="Cursor — UUID v7 of the last seen record. \
                Enables stable pagination."),
    ] = None,
) -> JSONResponse:
    """List songs. `count` is total matching records. \
        `bookmark` is last record's ID for next page."""
    logger.debug("list_songs_request", status=status_filter, search=search)

    q = db.query(Song).filter(Song.deleted_at.is_(None))

    if status_filter is not None:
        q = q.filter(Song.status == status_filter)

    if favorite is True:
        q = q.join(Favorite, Favorite.song_id == Song.id).filter(
            Favorite.deleted_at.is_(None)
        )
    elif favorite is False:
        q = q.outerjoin(
            Favorite,
            (Favorite.song_id == Song.id) & Favorite.deleted_at.is_(None),
        ).filter(Favorite.id.is_(None))

    if search is not None:
        q = q.filter(Song.title.ilike(f"%{search}%"))

    total = q.count()

    id_tiebreaker = Song.id.asc() if order == SortOrder.asc else Song.id.desc()
    q = q.order_by(_sort_column(sort_by, order), id_tiebreaker)

    if after is not None:
        anchor = db.query(Song).filter(Song.id == after).first()
        if anchor is not None:
            anchor_val = _cursor_value(anchor, sort_by)
            cursor_col = _cursor_column(sort_by)

            if anchor_val is None:
                if order == SortOrder.asc:
                    q = q.filter(cursor_col.is_(None), Song.id > anchor.id)
                else:
                    q = q.filter(cursor_col.is_(None), Song.id < anchor.id)
            else:
                if order == SortOrder.asc:
                    q = q.filter(
                        cursor_col.is_(None)
                        | (cursor_col > anchor_val)
                        | (
                            tuple_(cursor_col, Song.id)
                            > tuple_(literal(anchor_val), literal(anchor.id))
                        ),
                    )
                else:
                    q = q.filter(
                        cursor_col.is_(None)
                        | (cursor_col < anchor_val)
                        | (
                            tuple_(cursor_col, Song.id)
                            < tuple_(literal(anchor_val), literal(anchor.id))
                        ),
                    )
    else:
        q = q.offset(offset)

    songs = q.limit(limit).all()

    song_ids = [s.id for s in songs]
    favorite_ids: set[UUID] = set()
    if song_ids:
        favorite_ids = {
            sid
            for (sid,) in db.query(Favorite.song_id)
            .filter(Favorite.song_id.in_(song_ids), Favorite.deleted_at.is_(None))
            .all()
        }

    records = [serialize_song(s, db, is_favorite=(s.id in favorite_ids)) for s in songs]
    bookmark = records[-1]["id"] if records else None

    return envelope_response(
        {"records": records, "count": total, "bookmark": bookmark},
        "Songs retrieved.",
    )


@router.get(
    "/{song_id}",
    summary="Get song detail and current status",
    responses={404: {"description": "Song not found"}},
)
def get_song(song_id: UUID, db: DbDep) -> JSONResponse:
    """Retrieve a single song by ID."""
    song = db.query(Song).filter(Song.id == song_id, Song.deleted_at.is_(None)).first()
    if not song:
        logger.warning(LogEvent.SONG_NOT_FOUND, song_id=str(song_id))
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")
    return envelope_response(serialize_song(song, db), "Song retrieved.")


@router.delete(
    "/{song_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a song and remove its file from MinIO",
    responses={404: {"description": "Song not found or already deleted"}},
)
def delete_song(song_id: UUID, db: DbDep) -> Response:
    """Soft-delete a song. Sets deleted_at timestamp and removes the MinIO object."""
    song = db.query(Song).filter(Song.id == song_id, Song.deleted_at.is_(None)).first()
    if not song:
        logger.warning(LogEvent.SONG_NOT_FOUND, song_id=str(song_id))
        raise HTTPException(status_code=404, detail=f"Song {song_id} not found.")

    if song.file_url:
        try:
            s = get_settings()
            client = _client()
            client.remove_object(s.minio_bucket, song.file_url)
        except Exception as exc:
            logger.warning(
                LogEvent.MINIO_STREAM_FAILED, song_id=str(song_id), error=str(exc)
            )

    song.deleted_at = datetime.now(UTC)
    db.commit()

    logger.info(LogEvent.SONG_DELETED, song_id=str(song_id))
    return Response(status_code=204)


@router.get(
    "/{song_id}/stream",
    summary="Stream song audio with optional on-the-fly trim and speed",
    responses={
        302: {"description": "Redirect to presigned MinIO URL (no processing needed)"},
        200: {"description": "Audio file (trim/speed applied)"},
        404: {"description": "Song not found"},
        409: {"description": "Song not ready (status is not done)"},
        500: {"description": "Song has no file_url"},
        502: {"description": "MinIO or FFmpeg error"},
    },
    openapi_extra={
        "responses": {
            "200": {
                "description": "Audio stream",
                "content": {"audio/mpeg": {}},
            }
        }
    },
)
def stream_song(song_id: UUID, db: DbDep, request: Request) -> Response:
    """Stream mp3.

    - No trim/speed → presigned MinIO redirect (browser gets range support natively).
    - Trim/speed → process to tmp file → FileResponse (Starlette handles ranges).
    """
    import time

    from app.core.metrics import stream_duration_seconds

    song = db.query(Song).filter(Song.id == song_id, Song.deleted_at.is_(None)).first()
    if not song:
        logger.warning(LogEvent.SONG_NOT_FOUND, song_id=str(song_id))
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
    filename = f"{song.title or song_id}.mp3"

    has_trim = song.start is not None or song.end is not None
    has_speed = song.speed is not None and song.speed != 1.0

    logger.info(
        LogEvent.SONG_STREAM_STARTED,
        song_id=str(song_id),
        has_trim=has_trim,
        has_speed=has_speed,
    )

    stream_start = time.monotonic()

    # ── Case 1: no processing — proxy MinIO directly, forwarding Range header ─
    if not has_trim and not has_speed:
        from contextlib import ExitStack
        from datetime import timedelta

        import httpx
        from fastapi.responses import StreamingResponse

        try:
            presigned = client.presigned_get_object(
                s.minio_bucket,
                song.file_url,
                expires=timedelta(seconds=_PRESIGNED_EXPIRY),
            )
        except Exception as exc:
            logger.error(
                LogEvent.SONG_STREAM_FAILED, song_id=str(song_id), error=str(exc)
            )
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        headers: dict[str, str] = {}
        if range_header := request.headers.get("range"):
            headers["Range"] = range_header

        timeout = httpx.Timeout(connect=5.0, read=None, write=30.0, pool=30.0)

        stack = ExitStack()
        success = False
        try:
            http_client = stack.enter_context(httpx.Client(timeout=timeout))

            upstream = stack.enter_context(
                http_client.stream(
                    "GET",
                    presigned,
                    headers=headers,
                    follow_redirects=False,
                )
            )

            if upstream.status_code not in (200, 206):
                logger.error(
                    LogEvent.SONG_STREAM_FAILED,
                    song_id=str(song_id),
                    upstream_status=upstream.status_code,
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Storage service returned HTTP {upstream.status_code}",
                )

            response_headers = {
                "Content-Type": "audio/mpeg",
                "Accept-Ranges": "bytes",
                "Content-Disposition": build_content_disposition(filename),
            }

            for h in ("Content-Length", "Content-Range", "ETag", "Last-Modified"):
                if h in upstream.headers:
                    response_headers[h] = upstream.headers[h]

            success = True

        except httpx.HTTPError as exc:
            logger.error(
                LogEvent.SONG_STREAM_FAILED, song_id=str(song_id), error=str(exc)
            )
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch audio from storage: {exc}",
            ) from exc
        finally:
            if not success:
                stack.close()

        def stream_and_close() -> Iterator[bytes]:
            try:
                yield from upstream.iter_bytes()
            finally:
                stack.close()
                stream_duration_seconds.observe(time.monotonic() - stream_start)

        return StreamingResponse(
            stream_and_close(),
            status_code=206 if "Content-Range" in response_headers else 200,
            media_type="audio/mpeg",
            headers=response_headers,
        )

    # ── Case 2: trim/speed — write to tmp file, serve with FileResponse ───────
    _TMP_DIR.mkdir(parents=True, exist_ok=True)

    original_path = _TMP_DIR / f"{song_id}_original.mp3"
    trimmed_path = _TMP_DIR / f"{song_id}_trimmed.mp3"
    speed_path = _TMP_DIR / f"{song_id}_speed.mp3"
    created_paths: list[Path] = []

    try:
        try:
            minio_response = client.get_object(s.minio_bucket, song.file_url)
            created_paths.append(original_path)
            try:
                with original_path.open("wb") as f:
                    for chunk in minio_response.stream(32 * 1024):
                        f.write(chunk)
            finally:
                minio_response.close()
                minio_response.release_conn()
        except Exception as exc:
            logger.error(
                LogEvent.MINIO_STREAM_FAILED, song_id=str(song_id), error=str(exc)
            )
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        post_trim_path = original_path
        if has_trim:
            try:
                created_paths.append(trimmed_path)
                trim_audio(
                    input_path=original_path,
                    output_path=trimmed_path,
                    start=song.start,
                    end=song.end,
                )
                post_trim_path = trimmed_path
            except (ProcessingError, Exception) as exc:
                logger.error(
                    LogEvent.SONG_STREAM_FAILED, song_id=str(song_id), error=str(exc)
                )
                raise HTTPException(
                    status_code=502, detail=f"Trim failed: {exc}"
                ) from exc

        final_path = post_trim_path
        if has_speed:
            try:
                created_paths.append(speed_path)
                apply_speed(
                    input_path=post_trim_path,
                    output_path=speed_path,
                    speed=song.speed,
                )
                final_path = speed_path
            except (ProcessingError, Exception) as exc:
                logger.error(
                    LogEvent.SONG_STREAM_FAILED, song_id=str(song_id), error=str(exc)
                )
                raise HTTPException(
                    status_code=502, detail=f"Speed processing failed: {exc}"
                ) from exc

        from starlette.background import BackgroundTask

        paths_to_cleanup = [p for p in created_paths if p != final_path]

        def _cleanup() -> None:
            for p in [*paths_to_cleanup, final_path]:
                p.unlink(missing_ok=True)
            stream_duration_seconds.observe(time.monotonic() - stream_start)

        return FileResponse(
            path=final_path,
            media_type="audio/mpeg",
            filename=filename,
            background=BackgroundTask(_cleanup),
        )

    except Exception:
        for p in created_paths:
            p.unlink(missing_ok=True)
        raise
