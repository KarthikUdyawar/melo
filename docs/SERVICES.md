# Melo — Services

> What each service/module does. For request flow and task lifecycle, see `PIPELINE.md`.

---

## API (`app/`)

FastAPI + Uvicorn, run with `--reload` in dev (see `docker-compose.yml`'s `api` command). Routers: `songs.py`, `favorites.py`, `playlists.py`, plus system routes (`/health`, `/metrics`) registered directly in `main.py`.

- `create_app()` in `main.py` wires exception handlers, `TraceIdMiddleware`, `RequestLoggingMiddleware`, and the three routers.
- `lifespan()` (in `main.py`) runs on startup/shutdown: `init_db()`, `configure_tracing("melo.api")`, `configure_pyroscope("melo.api")`, starts `LogManager` (rotation/backup) and a gauge-polling scheduler (`start_gauge_poller`, `app/core/pollers.py`), and tears them down on shutdown.
- `_setup_metrics(app)` attaches `prometheus_fastapi_instrumentator`, excluding `/metrics` and `/health` from its own instrumentation, and exposes `GET /metrics`.
- `docs_url`/`redoc_url` are disabled when `settings.is_production` is true.

## Worker (`app/workers/`)

Celery app (`celery_app.py`) with Redis as both broker and result backend, `include=["app.workers.tasks"]`, `task_acks_late=True`, `worker_prefetch_multiplier=1`.

- `on_worker_init` (the `worker_init` signal): re-runs `configure_tracing`, `configure_logging`, and `configure_pyroscope` for the child process after fork — necessary because logging/tracing guards (`_CONFIGURED`) are reset so each forked worker gets its own file handles and trace provider.
- `on_worker_ready` (the `worker_ready` signal): starts a `LogManager` for the worker service and calls `ensure_bucket_exists()` so the MinIO bucket is guaranteed to exist before the first task runs.
- `_BaseTask` (in `tasks.py`) gives every task a lazily-created, shared SQLAlchemy session per worker process (`self.db`), closed in `after_return`.
- The only task defined is `process_song_task` (`name="app.workers.tasks.process_song"`, `max_retries=3`, `default_retry_delay=10`). See `PIPELINE.md` for its full logic.

## UI (`ui/`)

Vanilla JS SPA served by nginx. See `DESIGN.md` for visual spec and `USER-FLOW.md` for interaction flows. File responsibilities:

- `api.js` — `apiFetch()` + typed wrappers for all endpoints, envelope unwrap
- `player.js` — single module-scope `<audio>` element, play/pause/scrubber sync
- `components.js` — pure render functions: `renderSongCard`, `renderStatusPill`, `renderPlaylistCard`, `renderToast` (there is **no** `renderModal()` — modal markup is built inline in `app.js`)
- `app.js` — hash router, page renderers, 2s poll loop, all event delegation, modal builders

nginx (`ui/nginx.conf`) serves static files and proxies `/api/*` to `api:8000` with `proxy_buffering off` (required for audio streaming).

## Admin Dashboard (`admin/`)

Separate Streamlit app, not part of the main UI's design system. Session-password gated (`ADMIN_PASSWORD` env, checked in `admin/auth.py` via `hmac.compare_digest`). Pages: Overview, Songs, Logs, Metrics, Alerts, DB Health — each queries a different backend directly (Melo API, Prometheus, Loki, Grafana Alerting API) rather than going through Melo's own API for observability data. See `PRD.md`/`Sprint-5.md` for the full page breakdown.

---

## Downloader (`app/services/downloader.py`)

Wraps `yt-dlp`.

- `extract_youtube_id(url)` — parses any supported YouTube URL (validates domain against an allow-list, extracts the `v=` query param, `/shorts|embed|live|v/` path segments, or a trailing 11-char path segment) and raises `ValueError` if nothing valid is found.
- `probe_metadata(url) -> SongMeta` — `extract_info(download=False)`, returns `title`, `duration`, `thumbnail_url`, `channel`, `upload_date`. Uses a pinned format selector (`140/251/250/249/139/18`) and `extractor_args: {skip: [hls, dash]}` to avoid yt-dlp's JS-runtime signature solving. `noplaylist: True` so a `?v=X&list=Y` URL always resolves to the single video.
- `download_audio(url, song_id) -> (Path, duration)` — downloads with the same pinned format + `FFmpegExtractAudio` postprocessor to `.mp3` at 192kbps, wrapped in an OTEL span (`download_audio`) with `song.id`/`youtube.id` attributes, and observes `download_duration_seconds`.
- Both functions raise `DownloadError` on failure; a `_YtDlpLogger` adapter bridges yt-dlp's internal logger calls into structlog.

## Processor (`app/services/processor.py`)

Wraps FFmpeg via `subprocess.run` (120s timeout on every call).

- `trim_audio(input_path, output_path, start, end)` — tries `-c copy` (stream copy, instant) first; on non-zero exit or empty output, falls back to `-c:a libmp3lame -q:a 2` re-encode. Wrapped in span `ffmpeg.trim`, observes `ffmpeg_duration_seconds{op="trim"}`.
- `apply_speed(input_path, output_path, speed)` — no-op copy (`shutil.copy2`) when `speed == 1.0`; otherwise builds a chained `atempo` filter string via `_build_atempo_filters` (FFmpeg caps a single `atempo` stage to `[0.5, 2.0]`, so e.g. `speed=4.0` becomes `atempo=2.0,atempo=2.0`). Wrapped in span `ffmpeg.speed`, observes `ffmpeg_duration_seconds{op="speed"}`.
- Both raise `ProcessingError` on failure and clean up partial output files before raising.

## Storage (`app/services/storage.py`)

Wraps the MinIO Python client.

- `_client()` — builds a `Minio` client from settings (`minio_endpoint`, `minio_access_key`, `minio_secret_key`, `minio_secure`).
- `ensure_bucket_exists()` — idempotent create; called on worker startup.
- `upload_file(local_path, object_key)` — `fput_object` with `content_type="audio/mpeg"`, wrapped in span `minio.upload`, observes `minio_upload_duration_seconds`. Raises `StorageError` on failure or if the local file is missing.
- `get_presigned_url(object_key, expires_seconds=3600)` — generates a presigned GET URL, wrapped in span `minio.stream`; if `minio_public_url` is configured, rewrites the URL's scheme/netloc to the public value. **Note:** this rewriting helper exists in `storage.py`, but the actual stream endpoint (`GET /songs/{id}/stream`, in `app/api/songs.py`) calls `client.presigned_get_object` directly and proxies the bytes itself via `httpx` rather than redirecting the browser — see `STORAGE.md` and `PIPELINE.md` for why.
