# Melo — Pipeline

> Request & async job flow, task state machine, dedup logic, and the stream-time processing matrix.

---

## Request & Async Job Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant N as nginx
    participant A as FastAPI
    participant R as Redis
    participant W as Celery Worker
    participant YT as YouTube
    participant M as MinIO
    participant DB as PostgreSQL

    Note over B,A: Preview (stateless — no DB write)
    B->>N: POST /api/songs/preview {url}
    N->>A: proxy
    A->>YT: yt-dlp probe_metadata (no download)
    A-->>B: 200 {youtube_id, title, duration, channel, thumbnail_url}

    Note over B,DB: Submit Song
    B->>N: POST /api/songs {url, start, end, speed}
    N->>A: proxy
    A->>DB: INSERT song (status=pending)
    A->>A: inject OTEL traceparent into task headers
    A->>R: enqueue process_song_task (with trace headers)
    A-->>B: 202 {id, status=pending}

    Note over R,DB: Async Processing
    R->>W: dequeue task
    W->>W: reconstruct OTEL context from headers
    W->>DB: UPDATE status=processing
    W->>YT: probe_metadata (title, duration, thumbnail, channel, upload_date)
    W->>DB: UPDATE metadata fields (status stays processing)
    alt existing done song with same youtube_id
        W->>DB: copy file_url + metadata from existing record, status=done
    else no existing match
        W->>YT: yt-dlp download_audio → /tmp/melo/<id>.mp3
        W->>M: upload songs/<id>.mp3
        W->>DB: UPDATE file_url, duration, status=done
    end

    Note over B,A: Poll until done
    B->>N: GET /api/songs/{id}
    N->>A: proxy
    A-->>B: { status: "done", stream_url: "/api/songs/id/stream" }

    Note over B,A: Streaming (no trim/speed case)
    B->>N: GET /api/songs/{id}/stream
    N->>A: proxy (buffering off)
    A->>DB: SELECT song WHERE id=…
    A->>M: presigned_get_object(...)
    A->>M: httpx.stream GET presigned URL, forwarding Range header
    Note over A: API proxies bytes itself — never redirects the browser to MinIO
    A-->>B: StreamingResponse (200 or 206, audio/mpeg)
```

---

## Task State Machine

```mermaid
stateDiagram-v2
    [*] --> pending : POST /songs

    pending --> processing : worker picks up task

    processing --> done : dedup match found (existing done song, same youtube_id)
    processing --> done : download + upload success
    processing --> failed : DownloadError / StorageError (no retry)
    processing --> processing : retry (self.retry(), max 3×, unknown exceptions only)
    processing --> failed : MaxRetriesExceededError

    done --> [*]
    failed --> [*]
```

Notes (from `app/workers/tasks.py`):
- `DownloadError`/`StorageError` mark the song `failed` immediately — **no retry** for these.
- Any other exception triggers `self.retry(exc=exc)` (Celery-native retry, `default_retry_delay=10`, `max_retries=3`); once retries are exhausted, `MaxRetriesExceededError` is caught and the song is marked `failed`.
- `_mark_failed()` is best-effort: if the DB commit itself fails while marking a song failed, the exception is swallowed and logged (`mark_failed_error`) rather than propagated, so a broken DB connection during error handling doesn't crash the task twice.
- The downloaded temp file (`local_path`) is always cleaned up in a `finally` block regardless of outcome.
- `songs_completed_total{status="done"|"failed"}` is incremented on every terminal transition (including the dedup path).

---

## Dedup Logic

When a song is submitted with a `youtube_id` that already has a **`done`** record (different `start`/`end`/`speed` — the API always inserts a new row, never rejects with 409), the worker:

1. Still probes metadata fresh for the new record (so `title`/`duration`/etc. are populated even in the dedup path).
2. Looks up an existing `Song` with the same `youtube_id`, `status == done`, and a different `id`.
3. If found: copies `file_url`, `duration`, `title`, `thumbnail_url`, `channel`, `upload_date` from the existing record onto the new one, sets `status = done`, and returns immediately — **no download, no MinIO upload.**
4. If not found: proceeds to `download_audio` → `upload_file` as normal.

This means multiple `Song` rows can point at the same MinIO object (`file_url`), each with its own trim/speed applied at stream time.

---

## Stream Pipeline (Case Matrix)

Trim and speed are applied on-the-fly at stream time — no variants stored in MinIO. Source: `GET /songs/{id}/stream` in `app/api/songs.py`.

```mermaid
flowchart TD
    Start([GET /songs/id/stream]) --> HasTrim{has_trim?}
    HasTrim -- No --> HasSpeed1{has_speed?}
    HasSpeed1 -- No --> DirectProxy["presigned_get_object + httpx.stream\nforwards Range header\n200 or 206"]
    HasSpeed1 -- Yes --> FetchA[Fetch full object to /tmp/melo]
    HasTrim -- Yes --> FetchB[Fetch full object to /tmp/melo]
    FetchB --> TrimStep[FFmpeg: trim_audio]
    TrimStep --> HasSpeed2{has_speed?}
    HasSpeed2 -- No --> FileResp1[FileResponse — 200 only]
    HasSpeed2 -- Yes --> SpeedStep2[FFmpeg: apply_speed]
    FetchA --> SpeedStep1[FFmpeg: apply_speed]
    SpeedStep1 --> FileResp2[FileResponse — 200 only]
    SpeedStep2 --> FileResp3[FileResponse — 200 only]
    DirectProxy --> Stream4[StreamingResponse — 200 or 206]
```

| `start/end` set? | `speed != 1.0`? | Behaviour                                                     | Status codes  |
| ---------------- | --------------- | ------------------------------------------------------------- | ------------- |
| ❌                | ❌               | Presigned MinIO fetch, proxied via `httpx`, `Range` forwarded | `200` / `206` |
| ✅                | ❌               | Fetch → `trim_audio` → `FileResponse`                         | `200` only    |
| ❌                | ✅               | Fetch → `apply_speed` → `FileResponse`                        | `200` only    |
| ✅                | ✅               | Fetch → `trim_audio` → `apply_speed` → `FileResponse`         | `200` only    |

- Range/partial-content (`206`) is **only** available on the no-trim/no-speed path, since that's the only case not re-encoded through FFmpeg to a local file first.
- `FileResponse` cases use a `BackgroundTask` to delete all intermediate temp files (original/trimmed/speed-adjusted) after the response finishes, and observe `stream_duration_seconds` in that same cleanup callback.
- The proxy path (`DirectProxy`) generates a presigned URL via `client.presigned_get_object` directly and streams bytes itself with `httpx` — it does **not** redirect the browser to MinIO. See `STORAGE.md` for why.
- `atempo` chaining: FFmpeg caps a single `atempo` stage at `[0.5, 2.0]`, so `speed=4.0` → `atempo=2.0,atempo=2.0` and `speed=0.25` → `atempo=0.5,atempo=0.5`. Trim always runs before speed (reduces data before re-encoding).

---

## Distributed Tracing Through the Pipeline

- `POST /songs` injects the current OTEL `traceparent` into the Celery task's headers (`_inject_trace_context_into_task` in `songs.py`, via `opentelemetry.propagate.inject`), falling back to a plain `.delay()` call if injection fails for any reason.
- `process_song_task` reconstructs that context on the worker side (`_trace_context` contextmanager in `tasks.py`, via `opentelemetry.propagate.extract`) and opens a child span `celery.process_song` inside it — so the HTTP request span and the async task span appear in the same trace in Tempo.
- `X-Trace-Id` is injected into every API response by `TraceIdMiddleware` (`app/core/tracing.py`), and the same trace ID is attached to every structlog record for log↔trace correlation in Grafana.
