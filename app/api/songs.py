"""Song-related API endpoints."""

# app/api/songs.py
from collections.abc import Generator
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.sql.elements import ColumnElement

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


def _is_favorited(song_id: UUID, db: DbDep) -> bool:
    return db.query(Favorite).filter(Favorite.song_id == song_id).first() is not None


def _serialize(
    song: Song,
    db: DbDep,
    *,
    is_favorite: bool | None = None,
) -> dict[str, object]:
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
        filename: Original filename to embed in the header.

    Returns:
        Content-Disposition string with ASCII fallback and UTF-8 encoded name.
    """
    ascii_fallback = filename.encode("latin-1", "ignore").decode()
    utf8_encoded = quote(filename)
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{utf8_encoded}"


def _sort_column(sort_by: SortBy, order: SortOrder) -> ColumnElement[Any]:
    """Map sort params to a SQLAlchemy order_by clause."""
    col = {
        SortBy.created_at: Song.created_at,
        SortBy.song_title: Song.title,
        SortBy.duration: Song.duration,
    }[sort_by]
    return col.asc() if order == SortOrder.asc else col.desc()


# ── endpoints ─────────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_song(payload: SongCreate, db: DbDep) -> JSONResponse:
    """Submit a YouTube URL for async download and processing."""
    logger.info("create_song_request", url=payload.url, speed=payload.speed)

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

    logger.info("song_created", song_id=str(song.id), youtube_id=youtube_id)

    from app.workers.tasks import process_song_task

    try:
        process_song_task.delay(str(song.id), payload.url)
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
    """Preview YouTube metadata without persisting."""
    from app.services.downloader import DownloadError, probe_metadata

    logger.info("preview_request", url=payload.url)

    try:
        youtube_id = extract_youtube_id(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        meta = probe_metadata(payload.url)
    except DownloadError as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch metadata: {exc}"
        ) from exc

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


@router.get("")
def list_songs(
    db: DbDep,
    status_filter: Annotated[SongStatus | None, Query(alias="status")] = None,
    favorite: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    sort_by: Annotated[SortBy, Query()] = SortBy.created_at,
    order: Annotated[SortOrder, Query()] = SortOrder.desc,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    after: Annotated[UUID | None, Query()] = None,
) -> JSONResponse:
    """List songs with filtering, sorting, and cursor pagination.

    Cursor (`after`) takes precedence over `offset` for pagination.
    `count` reflects total matching records, not the current page size.
    `bookmark` is the last record's ID (UUID v7), or null when empty.
    """
    logger.debug("list_songs_request", status=status_filter, search=search)

    q = db.query(Song)

    # ── filters ───────────────────────────────────────────────────────────────
    if status_filter is not None:
        q = q.filter(Song.status == status_filter)

    if favorite is True:
        q = q.join(Favorite, Favorite.song_id == Song.id)
    elif favorite is False:
        q = q.outerjoin(Favorite, Favorite.song_id == Song.id).filter(
            Favorite.id.is_(None),
        )

    if search is not None:
        q = q.filter(Song.title.ilike(f"%{search}%"))

    # ── total count (before pagination) ───────────────────────────────────────
    total = q.count()

    # ── sort ──────────────────────────────────────────────────────────────────
    q = q.order_by(_sort_column(sort_by, order))

    # ── cursor pagination ─────────────────────────────────────────────────────
    if after is not None:
        anchor = db.query(Song).filter(Song.id == after).first()
        if anchor is not None:
            anchor_val = _cursor_value(anchor, sort_by)
            cursor_col = _cursor_column(sort_by)
            if order == SortOrder.asc:
                q = q.filter(cursor_col > anchor_val)
            else:
                q = q.filter(cursor_col < anchor_val)
    else:
        q = q.offset(offset)

    songs = q.limit(limit).all()

    # ── serialize with prefetched favorites (N+1 guard) ───────────────────────
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
    bookmark = records[-1]["id"] if records else None

    return paginated_response(records, total, "Songs retrieved.", bookmark=bookmark)


@router.get("/{song_id}")
def get_song(song_id: UUID, db: DbDep) -> JSONResponse:
    """Retrieve a single song by ID."""
    song = db.query(Song).filter(Song.id == song_id).first()

    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Song {song_id} not found."
        )

    return envelope_response(_serialize(song, db), "Song retrieved.")


@router.get("/{song_id}/stream")
def stream_song(song_id: UUID, db: DbDep) -> StreamingResponse:
    """Stream audio with optional on-the-fly trim and speed."""
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
    filename = f"{song.title or song_id}.mp3"

    has_trim = song.start is not None or song.end is not None
    has_speed = song.speed is not None and song.speed != 1.0

    if not has_trim and not has_speed:
        try:
            response = client.get_object(s.minio_bucket, song.file_url)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return StreamingResponse(
            response.stream(32 * 1024),
            media_type="audio/mpeg",
            headers={"Content-Disposition": build_content_disposition(filename)},
        )

    original_path = _TMP_DIR / f"{song_id}_original.mp3"
    trimmed_path = _TMP_DIR / f"{song_id}_trimmed.mp3"
    speed_path = _TMP_DIR / f"{song_id}_speed.mp3"
    created_paths: list[Path] = []

    try:
        _TMP_DIR.mkdir(parents=True, exist_ok=True)

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
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        post_trim_path = original_path
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
                raise HTTPException(
                    status_code=502, detail=f"Trim failed: {exc}"
                ) from exc

        final_path = post_trim_path
        if has_speed:
            try:
                apply_speed(
                    input_path=post_trim_path, output_path=speed_path, speed=song.speed
                )
                created_paths.append(speed_path)
                final_path = speed_path
            except ProcessingError as exc:
                raise HTTPException(
                    status_code=502, detail=f"Speed processing failed: {exc}"
                ) from exc

        paths_to_cleanup = list(created_paths)

        def _iter_and_cleanup() -> Generator[bytes, None, None]:
            try:
                with final_path.open("rb") as f:
                    while chunk := f.read(32 * 1024):
                        yield chunk
            finally:
                for p in paths_to_cleanup:
                    p.unlink(missing_ok=True)

        return StreamingResponse(
            _iter_and_cleanup(),
            media_type="audio/mpeg",
            headers={"Content-Disposition": build_content_disposition(filename)},
        )

    except HTTPException:
        for p in created_paths:
            p.unlink(missing_ok=True)
        raise


# ── cursor helpers ────────────────────────────────────────────────────────────


def _cursor_column(sort_by: SortBy) -> ColumnElement[Any]:
    """Return the SQLAlchemy column for cursor comparison."""
    return {  # type: ignore[return-value]
        SortBy.created_at: Song.created_at,
        SortBy.song_title: Song.title,
        SortBy.duration: Song.duration,
    }[sort_by]


def _cursor_value(song: Song, sort_by: SortBy) -> object:
    """Extract the cursor field value from a Song instance."""
    return {
        SortBy.created_at: song.created_at,
        SortBy.song_title: song.title,
        SortBy.duration: song.duration,
    }[sort_by]
