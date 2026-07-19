# Melo — Storage (MinIO)

> Verified against `app/services/storage.py`, `app/api/songs.py`, `infra/docker-compose.monitoring.yml`, `docker-compose.yml`.

---

## Bucket Layout

| Bucket                                                                   | Contents                                                               | Written by                                  |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------- | ------------------------------------------- |
| `songs` (configurable via `MINIO_BUCKET`, default `songs`)               | One object per `Song.file_url`, keyed `{song_id}.mp3`                  | `app/workers/tasks.py` → `upload_file()`    |
| `melo-log-backups` (`LOG_BACKUP_BUCKET` env, default `melo-log-backups`) | Gzipped rotated log files, keyed `<service>/<YYYY>/<MM>/<filename>.gz` | `app/core/log_manager.py` (Sprint 5, OBS-1) |

`ensure_bucket_exists()` is idempotent and is called once per worker process on the `worker_ready` Celery signal (`app/workers/celery_app.py`) — not checked on every task.

---

## Upload Path

`upload_file(local_path, object_key)`:
- `fput_object(bucket_name, object_name, file_path, content_type="audio/mpeg")`
- Wrapped in OTEL span `minio.upload`, observes `minio_upload_duration_seconds`
- Raises `StorageError` if the local file doesn't exist or the MinIO call fails (`S3Error` or any other exception, both logged then re-raised)

---

## Why the Stream Endpoint Proxies Instead of Redirecting

`get_presigned_url()` in `storage.py` *can* rewrite a presigned URL's scheme/host to a public value (`minio_public_url` setting) — but the actual `GET /songs/{id}/stream` route (`app/api/songs.py`) does **not** call this function or redirect the browser to it. Instead, for the no-trim/no-speed case, it:

1. Calls `client.presigned_get_object(...)` directly to get an internally-valid presigned URL (`minio:9000` inside the Docker network).
2. Opens an `httpx.Client` and streams a `GET` to that presigned URL itself, forwarding the incoming `Range` header.
3. Streams the upstream response bytes straight back to the browser via `StreamingResponse`, copying `Content-Length`/`Content-Range`/`ETag`/`Last-Modified` headers, and returning `206` when a `Content-Range` header is present.

**Reason:** MinIO presigned URLs are signed (SigV4) against the hostname they were generated for. If the API redirected the browser to a presigned URL built for the internal Docker hostname (`minio:9000`), the browser couldn't reach it; rewriting the hostname after signing breaks the HMAC signature. Proxying the bytes server-side avoids both problems and keeps the browser talking only to the API/nginx — no CORS, no exposed internal hostname.

For trim/speed cases, the API instead does a full `get_object` fetch to a local temp file, runs FFmpeg, and serves the result via `FileResponse` (Starlette handles Range natively for local files) — see `PIPELINE.md`'s stream case matrix for the full breakdown.

---

## Temp File Handling

- `_TMP_DIR = Path("/tmp/melo")`, shared by the download step (`downloader.py`), the trim/speed steps (`processor.py`), and the stream endpoint's temp-file path (`songs.py`).
- In `docker-compose.yml`, both `api` and `worker` mount `/tmp/melo` as **tmpfs** (`tmpfs: - /tmp/melo:mode=1777`) rather than a bind mount or named volume — this sidesteps the WSL2 bind-mount permission/corruption issues that affected earlier iterations of this path (see `DECISIONS.md`).
- The stream endpoint cleans up all intermediate files (`_original`, `_trimmed`, `_speed`) via a `BackgroundTask` after the response completes, or immediately in an `except HTTPException` block if something fails before streaming starts.

---

## Persistent Log Volume vs. Temp Volume

Two different volume strategies coexist and shouldn't be confused:

| Volume           | Type                                                                                                                                     | Purpose                                                                                                                                         |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `/tmp/melo`      | `tmpfs`                                                                                                                                  | Ephemeral download/processing scratch space, per-container, cleared on restart                                                                  |
| `melo_melo_logs` | Named volume (`name: melo_melo_logs` in `docker-compose.yml`, referenced as `external: true` from `infra/docker-compose.monitoring.yml`) | Persistent, shared between `api`, `worker`, and `promtail` at `/var/log/melo/` so Promtail can scrape JSONL log files written by either process |

The named-volume requirement for `melo_melo_logs` (rather than a bind mount) was a hard-won fix — Loki received zero logs until api/worker switched to the named volume matching Promtail's `external: true` reference.
