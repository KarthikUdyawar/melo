# 🎵 Melo — Architecture

> Personal self-hosted audio library. Paste a YouTube URL → trimmed, speed-adjusted, playable mp3 stored in MinIO.

---

## Stack

| Layer      | Tech                  |
| ---------- | --------------------- |
| API        | FastAPI + Uvicorn     |
| Queue      | Celery + Redis        |
| Download   | yt-dlp                |
| Processing | FFmpeg                |
| Storage    | MinIO (S3-compatible) |
| Database   | PostgreSQL 16         |
| Packaging  | uv                    |
| Runtime    | Docker Compose        |

---

## High-Level System Overview

```mermaid
graph TD
    Client["🖥️ Client (curl / browser)"]

    subgraph Docker Compose
        API["⚡ FastAPI\n:8000"]
        Worker["⚙️ Celery Worker"]
        PG[("🐘 PostgreSQL\n:5432")]
        Redis[("🔴 Redis\n:6379")]
        MinIO[("🪣 MinIO\n:9000")]
        Adminer["🔍 Adminer\n:8080"]
        MinIOConsole["🪣 MinIO Console\n:9001"]
    end

    YT["▶️ YouTube"]

    Client -->|HTTP REST| API
    API --> PG
    API --> Redis
    API --> MinIO
    Worker --> PG
    Worker --> Redis
    Worker --> MinIO
    Worker -->|yt-dlp download| YT
    Adminer --> PG
```

---

## Request & Async Job Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI
    participant R as Redis
    participant W as Celery Worker
    participant YT as YouTube
    participant M as MinIO
    participant DB as PostgreSQL

    Note over C,A: Preview (stateless — no DB write)
    C->>A: POST /songs/preview {url}
    A->>YT: yt-dlp probe_metadata (no download)
    A-->>C: 200 {youtube_id, title, duration, channel, thumbnail_url}

    Note over C,DB: Submit Song
    C->>A: POST /songs {url, start, end, speed}
    A->>DB: INSERT song (status=pending)
    A->>R: enqueue process_song_task
    A-->>C: 202 {id, status=pending}

    Note over R,DB: Async Processing
    R->>W: dequeue task
    W->>DB: UPDATE status=processing
    W->>YT: yt-dlp download → /tmp/melo/<id>.mp3
    W->>M: upload songs/<id>.mp3
    W->>DB: UPDATE file_url, duration, status=done

    Note over C,A: Streaming
    C->>A: GET /songs/{id}/stream
    A->>DB: SELECT song WHERE id=…
    A->>M: get_object(songs/<id>.mp3)
    Note over A: trim + speed applied on-the-fly via FFmpeg
    A-->>C: StreamingResponse (audio/mpeg)
```

---

## Task State Machine

```mermaid
stateDiagram-v2
    [*] --> pending : POST /songs

    pending --> processing : worker picks up task

    processing --> done : download + upload success
    processing --> failed : DownloadError / StorageError
    processing --> processing : retry (max 3×, unknown errors only)
    processing --> failed : MaxRetriesExceeded

    done --> [*]
    failed --> [*]
```

---

## Stream Pipeline (Case Matrix)

Trim and speed are applied on-the-fly at stream time — no variants stored in MinIO.

```mermaid
flowchart TD
    Start([GET /songs/id/stream]) --> FetchObj[Fetch object from MinIO]
    FetchObj --> HasTrim{has_trim?}
    HasTrim -- No --> HasSpeed1{has_speed?}
    HasTrim -- Yes --> TrimStep[FFmpeg: trim via stream-copy]
    TrimStep --> HasSpeed2{has_speed?}
    HasSpeed1 -- No --> DirectProxy[Direct MinIO proxy\nfastest path]
    HasSpeed1 -- Yes --> SpeedStep1[FFmpeg: atempo filter]
    HasSpeed2 -- No --> Stream1[StreamingResponse]
    HasSpeed2 -- Yes --> SpeedStep2[FFmpeg: atempo filter]
    SpeedStep1 --> Stream2[StreamingResponse]
    SpeedStep2 --> Stream3[StreamingResponse]
    DirectProxy --> Stream4[StreamingResponse]
```

| has_trim | has_speed | Behaviour                     |
| -------- | --------- | ----------------------------- |
| ❌        | ❌         | Direct MinIO proxy (fastest)  |
| ✅        | ❌         | Fetch → trim → stream         |
| ❌        | ✅         | Fetch → speed → stream        |
| ✅        | ✅         | Fetch → trim → speed → stream |

**`atempo` chaining** — FFmpeg caps a single `atempo` stage at `[0.5, 2.0]`:

```text
speed=4.0  → atempo=2.0,atempo=2.0
speed=0.25 → atempo=0.5,atempo=0.5
```

---

## Data Model

```mermaid
erDiagram
    songs {
        uuid     id           PK
        string   title
        string   youtube_id   UK
        string   file_url
        float    duration
        float    speed
        string   status
        int      start
        int      end
        string   thumbnail_url
        string   channel
        string   upload_date
        datetime created_at
        datetime deleted_at
    }

    favorites {
        uuid     id           PK
        uuid     song_id      FK
        datetime created_at
        datetime deleted_at
    }

    playlists {
        uuid     id           PK
        string   name
        datetime created_at
        datetime deleted_at
    }

    playlist_songs {
        uuid     playlist_id  FK
        uuid     song_id      FK
        int      position
    }

    songs ||--o{ favorites       : "favorited via"
    songs ||--o{ playlist_songs  : "appears in"
    playlists ||--o{ playlist_songs : "contains"
```

Notes:
- All PKs are **UUID v7** (via `uuid6` package) — string-sortable = chronological = natural cursor key.
- `favorites.song_id` has a `unique=True` constraint (one row per song).
- `playlist_songs.position` auto-increments on add; same song can appear in multiple playlists.
- `deleted_at` on `songs`, `favorites`, `playlists` — soft delete. `playlist_songs` is hard-deleted (join table, no audit need).
- Indexes on `songs.youtube_id`, `songs.status`, `songs.created_at`, `songs.title` (btree) for dedup and filtering.

---

## API Surface

```mermaid
graph LR
    subgraph Songs
        S1["POST /songs/preview"]
        S2["POST /songs"]
        S3["GET /songs"]
        S4["GET /songs/{id}"]
        S5["DELETE /songs/{id}"]
        S6["GET /songs/{id}/stream"]
    end

    subgraph Favorites
        F1["POST /favorites/{song_id}"]
        F2["DELETE /favorites/{song_id}"]
        F3["GET /favorites"]
    end

    subgraph Playlists
        P1["POST /playlists"]
        P2["GET /playlists"]
        P3["GET /playlists/{id}"]
        P4["DELETE /playlists/{id}"]
        P5["POST /playlists/{id}/songs/{song_id}"]
        P6["DELETE /playlists/{id}/songs/{song_id}"]
    end

    subgraph System
        H["GET /health"]
    end
```

All responses follow the **envelope format**:

```json
{
  "status_code": 200,
  "message": "…",
  "body": { … }
}
```

Paginated list responses include:

```json
{
  "records": [ … ],
  "count": 42,
  "bookmark": "<last-uuid>"
}
```

`bookmark` enables **cursor-based pagination** via `?after=<uuid>` on `GET /songs`.

---

## Folder Structure

```text
melo/
├── app/
│   ├── api/
│   │   ├── songs.py        # /songs + /songs/preview + /songs/{id}/stream
│   │   ├── favorites.py    # /favorites
│   │   ├── playlists.py    # /playlists
│   │   ├── _song_utils.py  # shared serialize_song + _is_favorited
│   │   └── responses.py    # envelope_response, paginated_response
│   ├── core/
│   │   ├── config.py       # APP_ENV-driven settings
│   │   ├── db.py           # SQLAlchemy engine + session
│   │   ├── deps.py         # FastAPI dependency injection
│   │   ├── logging.py      # structlog setup
│   │   ├── middleware.py   # request logging
│   │   └── exception_handlers.py
│   ├── models/
│   │   ├── song.py         # Song SQLAlchemy model
│   │   ├── favorite.py     # Favorite model
│   │   └── playlist.py     # Playlist + PlaylistSong models
│   ├── schemas/
│   │   ├── song.py         # SongCreate, SongResponse, SongPreviewResponse, …
│   │   ├── playlist.py     # PlaylistCreate, PlaylistResponse, …
│   │   └── envelope.py     # Envelope[T], PaginatedResponse[T]
│   ├── services/
│   │   ├── downloader.py   # yt-dlp: probe_metadata, download_audio
│   │   ├── processor.py    # FFmpeg: trim_audio, apply_speed
│   │   └── storage.py      # MinIO: upload_file, get_presigned_url
│   └── workers/
│       ├── celery_app.py   # Celery app + Redis broker config
│       └── tasks.py        # process_song_task (download → process → upload)
├── tests/
│   ├── unit/               # Mocked, SQLite — no Docker needed
│   └── integration/        # Postgres via pytest-docker
├── docs/
│   └── sprints/
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
└── example.env
```

---

## Service Ports

| Service       | URL                        |
| ------------- | -------------------------- |
| API           | http://localhost:8000      |
| API Docs      | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001      |
| Adminer (DB)  | http://localhost:8080      |
| PostgreSQL    | localhost:5432             |
| Redis         | localhost:6379             |

---

## Key Design Decisions

| Decision                                         | Reason                                                              |
| ------------------------------------------------ | ------------------------------------------------------------------- |
| UUID v7 for all PKs                              | String-sortable = chronological = natural cursor key for pagination |
| Cursor pagination on `GET /songs`                | Stable under concurrent inserts; no offset drift                    |
| Speed applied at stream time                     | Avoid storing per-speed variants in MinIO                           |
| Chain `atempo` filters                           | FFmpeg `atempo` capped at `[0.5, 2.0]` per stage                    |
| Trim before speed                                | Correct order — reduces data before re-encoding                     |
| Preview endpoint is stateless                    | No DB writes; simpler system; worker re-probes as source of truth   |
| API proxies MinIO stream                         | Presigned URLs signed to internal hostname break on host rewrite    |
| Favorites idempotent (check-then-insert)         | Solo user; clean UX; avoids upsert complexity                       |
| `is_favorite` queried per song                   | N+1 acceptable at MVP scale                                         |
| Playlist ordering via `position`                 | Predictable playback; auto-increments on add                        |
| `db.expire_all()` after playlist mutations       | Clears stale SQLAlchemy identity map state post-commit              |
| Soft delete on `songs`, `favorites`, `playlists` | Safer than hard delete; preserves audit trail; `deleted_at` column  |
| `playlist_songs` hard delete                     | Join table — no user-facing audit need; position logic unaffected   |
| `_song_utils.py` shared serializer               | Eliminates duplicate `_serialize_song`; avoids circular import      |
| `stream_url` status-driven, never null           | Client polls `GET /songs/{id}` until done, then hits stream         |
| Health check probes Redis + MinIO                | Silent infra failure previously undetectable via `/health`          |
| `docs_url=None` in production                    | Swagger not needed in prod; reduces attack surface                  |
| No Alembic                                       | Solo project; `create_all()` on startup is sufficient               |
| `APP_ENV`-driven env files                       | Clean separation: dev (localhost) / staging (Docker) / prod         |
| `tasks.py` excluded from coverage                | Celery internals require live worker; covered by `make smoke`       |
| Unit test isolation via `_truncate_all()`        | Savepoint rollback unreliable when endpoints call `db.commit()`     |
