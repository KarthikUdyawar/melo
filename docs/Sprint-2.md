# Melo — Sprint 2: Processing, Metadata & API Polish

**Duration:** Week 2 (Days 8–14)
**Goal:** Songs are trimmed via FFmpeg on stream; YouTube metadata is probed once on ingest and served from DB; every endpoint returns a consistent response envelope.
**Branch strategy:** `develop` base → feature branches → PR → CodeRabbit review → merge

---

## Sprint Goal

> *A user can submit the same YouTube URL with different trim points without re-downloading; FFmpeg trims on stream; all API responses share a consistent envelope shape; structured JSON logs trace every request.*

---

## Backlog

---

### 📦 API-1 — Response Envelope
**Branch:** `feature/api-envelope`

- [ ] `app/schemas/envelope.py` — `Envelope` generic schema:
  ```python
  class Envelope(BaseModel, Generic[T]):
      status_code: int
      message: str
      body: T | None
  ```
- [ ] `app/api/responses.py` — `envelope_response(data, message, status_code)` helper that returns `JSONResponse` with envelope shape
- [ ] `app/api/responses.py` — `paginated_response(records, count, message, status_code)` helper:
  ```json
  {
    "status_code": 200,
    "message": "...",
    "body": { "records": [...], "count": 3 }
  }
  ```
- [ ] `app/core/exception_handlers.py` — global `HTTPException` handler → envelope with `body: null`
- [ ] `app/core/exception_handlers.py` — global `RequestValidationError` handler → 422 envelope with field errors in `message`
- [ ] `app/core/exception_handlers.py` — global unhandled `Exception` handler → 500 envelope
- [ ] Register all handlers in `main.py` via `app.add_exception_handler(...)`
- [ ] Skip envelope for: `GET /songs/{id}/stream`, `/docs`, `/redoc`, `/openapi.json`, `/health`
- [ ] Update all existing routers (`songs.py`) to use `envelope_response` / `paginated_response`
- [ ] Verify: error responses from 404, 409, 422, 500 all return envelope with `body: null`

---

### 📝 LOG-1 — Structured JSON Logging + Request Middleware
**Branch:** `feature/logging`

- [ ] `app/core/logging.py` — configure `structlog` (or `python-json-logger`) at app startup:
  - JSON format in staging/production, pretty console format in development
  - Fields on every log line: `timestamp`, `level`, `logger`, `message`, `env`
- [ ] `app/core/middleware.py` — `RequestLoggingMiddleware` (Starlette `BaseHTTPMiddleware`):
  - On request: log `method`, `path`, `query_params`, `client_ip`
  - On response: log `status_code`, `duration_ms`
  - Skip logging body for `/health`
- [ ] Register middleware in `main.py`
- [ ] Replace all `logging.getLogger(__name__)` calls across `downloader.py`, `storage.py`, `tasks.py`, `songs.py` with structured logger
- [ ] Uvicorn access logs disabled (duplicate of middleware); uvicorn error logs kept
- [ ] Worker logs (Celery) also emit JSON: `task_name`, `song_id`, `status`, `duration_ms`
- [ ] Verify: `make logs-api` shows one JSON line per request with all fields

---

### 🎬 META-1 — YouTube Metadata Probe on Ingest
**Branch:** `feature/metadata`

- [ ] `app/models/song.py` — add fields: `thumbnail_url: str | None`, `channel: str | None`, `upload_date: str | None`
- [ ] `app/services/downloader.py` — `probe_metadata(url) -> dict` using `yt_dlp.YoutubeDL.extract_info(download=False)`:
  - Returns: `title`, `duration`, `thumbnail`, `channel`, `upload_date`
  - Raises `DownloadError` on failure
- [ ] `app/workers/tasks.py` — call `probe_metadata` as first step in `process_song_task`:
  - Populate `song.title`, `song.duration`, `song.thumbnail_url` immediately after probe (before download)
  - Status stays `processing` during download
- [ ] **Dedup with different trim:** `POST /songs` with existing `youtube_id` but different `start`/`end`:
  - Do NOT 409 — create new `Song` DB record pointing to same MinIO object
  - Reuse `file_url` from existing done song with same `youtube_id`
  - Copy `title`, `duration`, `thumbnail_url` from existing record — no re-probe, no re-download
  - Enqueue no Celery task — record goes straight to `done`
- [ ] `app/schemas/song.py` — add `thumbnail_url`, `channel`, `upload_date` to `SongResponse`
- [ ] `GET /songs/{id}` — returns metadata fields alongside existing fields
- [ ] `GET /songs` — includes metadata fields in list response

---

### ✂️ FFMPEG-1 — Trim on Stream
**Branch:** `feature/ffmpeg-trim`

- [ ] `app/services/processor.py` — `trim_audio(input_path, output_path, start, end) -> Path`:
  - Uses `subprocess` + `ffmpeg` with `-ss {start} -to {end} -c copy` for fast stream copy
  - Falls back to `-c:a libmp3lame` re-encode if stream copy fails (codec mismatch)
  - Raises `ProcessingError` on non-zero ffmpeg exit
  - Cleans up `output_path` on failure
- [ ] `app/models/song.py` — `start: float | None`, `end: float | None` fields (already in `SongCreate`, now persisted to DB)
- [ ] `app/workers/tasks.py` — persist `start` and `end` onto `Song` record after creation
- [ ] `GET /songs/{id}/stream` — trim-on-stream logic:
  - If `song.start` or `song.end` is set: fetch from MinIO → write to `/tmp/melo/{id}_original.mp3` → `trim_audio(...)` → stream trimmed file → cleanup both files
  - If no trim params: stream original directly from MinIO (existing behaviour)
- [ ] `ProcessingError` → 502 response with envelope
- [ ] Verify: song submitted with `start=30, end=90` streams only the 60s segment

---

## Definition of Done

- [ ] All feature branches merged to `develop` via PR
- [ ] `POST /songs` with existing `youtube_id` + new trim params → new DB record, no re-download, status `done` immediately
- [ ] `GET /songs/{id}/stream` with trim params → correct trimmed audio segment
- [ ] All endpoints (except stream + docs) return envelope shape
- [ ] `make logs-api` shows structured JSON per request
- [ ] `SPRINT_2.md` checked off and moved to `melo/docs/sprints/`

---

## Out of Scope (→ Sprint 3)

- Speed processing (`atempo` FFmpeg filter)
- Favorites + playlists endpoints
- Correlation IDs (`X-Request-ID` header passthrough)
- Frontend / Streamlit UI

---

## Decision Log

| Decision                                              | Reason                                                                                                                                    |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Dedup reuses existing MinIO object                    | Same audio source, different trim — no point re-downloading. New DB row allows different `start`/`end` per record while sharing one file. |
| FFmpeg trim on stream, not on ingest                  | Avoids storing N trimmed variants per song. One source file in MinIO; trim applied ephemerally per stream request.                        |
| `probe_metadata(download=False)` before download      | Populates `title`, `thumbnail_url`, `duration` immediately so `GET /songs/{id}` returns useful data even while status is `processing`.    |
| Global exception handler wraps all errors in envelope | Single place to control error shape; routers never build error responses manually.                                                        |
| Skip envelope on `StreamingResponse` endpoints        | Binary stream cannot be wrapped in JSON. Documented exception — not a design inconsistency.                                               |
| Structured JSON logs, pretty in dev                   | JSON parseable by log aggregators in staging/prod; human-readable in dev without config change.                                           |
| Uvicorn access logs disabled                          | Middleware already logs method + path + status + duration — duplicate lines add noise.                                                    |