# 🎵 Melo

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

## Architecture

```mermaid
graph TD
    Client -->|POST /songs| API
    API -->|create record status=pending| PG[(PostgreSQL)]
    API -->|enqueue task| Redis[(Redis)]
    Redis -->|consume| Worker
    Worker -->|yt-dlp download| YT[YouTube]
    Worker -->|upload mp3| MinIO[(MinIO)]
    Worker -->|update status=done| PG
    Client -->|GET /songs/id/stream| API
    API -->|fetch + trim + speed| MinIO
    API -->|StreamingResponse| Client
```

---

## Async Job Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant R as Redis
    participant W as Worker
    participant M as MinIO
    participant D as DB

    C->>A: POST /songs {url, start, end, speed}
    A->>D: INSERT song status=pending
    A->>R: enqueue process_song_task
    A-->>C: 202 {id, status=pending}

    R->>W: dequeue task
    W->>D: UPDATE status=processing
    W->>W: probe_metadata (yt-dlp, no download)
    W->>W: yt-dlp download → /tmp/melo/<id>.mp3
    W->>M: upload songs/<id>.mp3
    W->>D: UPDATE file_url, duration, status=done

    C->>A: GET /songs/{id}/stream?
    A->>D: SELECT song WHERE id=...
    A->>M: get_object(songs/<id>.mp3)
    note over A: trim and/or speed applied on-the-fly
    A-->>C: StreamingResponse audio/mpeg
```

---

## Stream Case Matrix

| has_trim | has_speed | Behaviour                     |
| -------- | --------- | ----------------------------- |
| ❌        | ❌         | Direct MinIO proxy (fastest)  |
| ✅        | ❌         | Fetch → trim → stream         |
| ❌        | ✅         | Fetch → speed → stream        |
| ✅        | ✅         | Fetch → trim → speed → stream |

Speed uses FFmpeg `atempo` filter, chained for values outside `[0.5, 2.0]`:

```text
speed=4.0  → atempo=2.0,atempo=2.0
speed=0.25 → atempo=0.5,atempo=0.5
```

---

## Task State Machine

```mermaid
stateDiagram-v2
    [*] --> pending: POST /songs
    pending --> processing: worker picks up task
    processing --> done: download + upload success
    processing --> failed: DownloadError / StorageError
    processing --> processing: retry (max 3×, unknown errors only)
    processing --> failed: MaxRetriesExceeded
    done --> [*]
    failed --> [*]
```

---

## Services

```mermaid
graph LR
    subgraph Docker Compose
        API[api :8000]
        Worker[worker]
        PG[postgres :5432]
        Redis[redis :6379]
        MinIO[minio :9000]
        Adminer[adminer :8080]
        MinIOConsole[minio-console :9001]
    end

    API --> PG
    API --> Redis
    API --> MinIO
    Worker --> PG
    Worker --> Redis
    Worker --> MinIO
    Adminer --> PG
```

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/KarthikUdyawar/melo && cd melo

# 2. Configure
cp example.env .env.staging   # already set for Docker Compose

# 3. Run
make up

# 4. Submit a song (with optional trim + speed)
curl -X POST http://localhost:8000/songs \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "start": 10, "end": 60, "speed": 1.5}'

# 5. Check status
curl http://localhost:8000/songs/<id>

# 6. Stream when done
curl -OJ http://localhost:8000/songs/<id>/stream

# 7. Run smoke test
make smoke
```

---

## Make Targets

| Target                    | Description                           |
| ------------------------- | ------------------------------------- |
| `make up`                 | Build + start all services detached   |
| `make down`               | Stop all services                     |
| `make down-v`             | Stop + delete all volumes             |
| `make logs`               | Tail all logs                         |
| `make logs-api`           | Tail API logs only                    |
| `make logs-worker`        | Tail worker logs only                 |
| `make ps`                 | Show service status                   |
| `make shell-api`          | Bash into api container               |
| `make shell-worker`       | Bash into worker container            |
| `make health`             | Hit /health endpoint                  |
| `make songs`              | List all songs                        |
| `make test-smoke`              | End-to-end smoke test (curl + jq)     |
| `make test`               | Run full test suite + coverage report |
| `make test-unit`          | Unit tests only (no Docker needed)    |
| `make test-integration`   | Integration tests (requires Docker)   |
| `make test-cov`           | Tests + HTML coverage report          |
| `make pre-commit`         | Run all pre-commit hooks on all files |
| `make pre-commit-install` | Install pre-commit hooks (run once)   |

---

## API

| Method | Path                 | Description                       |
| ------ | -------------------- | --------------------------------- |
| `POST` | `/songs`             | Submit YouTube URL → async job    |
| `GET`  | `/songs`             | List all songs                    |
| `GET`  | `/songs/{id}`        | Get song detail + status          |
| `GET`  | `/songs/{id}/stream` | Stream mp3 (trim + speed applied) |
| `GET`  | `/health`            | Health check                      |

Interactive docs: **http://localhost:8000/docs**

---

## Folder Structure

```
melo/
├── app/
│   ├── api/          # FastAPI routers
│   ├── core/         # config, db, deps
│   ├── models/       # SQLAlchemy models
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # downloader, processor, storage
│   └── workers/      # Celery app + tasks
├── tests/
│   ├── conftest.py
│   ├── docker-compose.test.yml
│   ├── smoke_test.sh
│   ├── unit/
│   └── integration/
├── docs/
│   ├── PRD.md
│   └── sprints/
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
├── .pre-commit-config.yaml
├── .coderabbit.yaml
└── example.env
```

---

## Ports

| Service       | URL                        |
| ------------- | -------------------------- |
| API           | http://localhost:8000      |
| API Docs      | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001      |
| Adminer (DB)  | http://localhost:8080      |
| PostgreSQL    | localhost:5432             |
| Redis         | localhost:6379             |

---

## Testing

```bash
# Unit tests only — no Docker needed, fast
make test-unit

# Full suite — spins up Postgres via pytest-docker
make test

# HTML coverage report → htmlcov/index.html
make test-cov
```

Coverage target: **80%** (currently 85.74%).

Test layout:

| Module                                | Type        | Coverage |
| ------------------------------------- | ----------- | -------- |
| `tests/unit/test_schemas.py`          | Unit        | 100%     |
| `tests/unit/test_processor.py`        | Unit        | 100%     |
| `tests/unit/test_storage.py`          | Unit        | 97%      |
| `tests/unit/test_downloader.py`       | Unit        | 94%      |
| `tests/integration/test_db.py`        | Integration | —        |
| `tests/integration/test_songs_api.py` | Integration | —        |

---

## Decision Log

| Decision                                | Reason                                                                                       |
| --------------------------------------- | -------------------------------------------------------------------------------------------- |
| No Alembic                              | Solo project; `create_all()` on startup sufficient                                           |
| `APP_ENV`-driven env files              | Clean separation: dev (localhost) / staging (Docker) / prod                                  |
| Pinned yt-dlp format selector           | `bestaudio` needs JS runtime; explicit IDs (`140/251/…`) use plain HTTPS                     |
| `worker_ready` signal for MinIO bucket  | Create once per process, not per task                                                        |
| Proxy stream via FastAPI                | Presigned URLs signed to internal hostname break on host rewrite; API proxies bytes directly |
| `expire_on_commit=False`                | Avoids lazy-load errors post-commit in Celery context                                        |
| Speed applied at stream time            | Avoid storing per-speed variants in MinIO                                                    |
| Chain `atempo` filters                  | FFmpeg atempo limited to 0.5–2.0 per stage                                                   |
| Trim before speed                       | Correct processing order — trim reduces data before re-encoding                              |
| `created_paths` list in stream endpoint | Guarantees cleanup of all temp files regardless of which pipeline steps ran                  |
| Root `conftest.py` for env setup        | `pytest_configure` runs before collection — only reliable hook for early env vars            |
| Savepoint pattern in `db_session`       | Per-test rollback without truncation; compatible with SQLAlchemy nested transactions         |
| `tasks.py` excluded from coverage       | Celery internals require live worker; covered by `make smoke` instead                        |
| `# nosec B108/B603/B607` in processor   | `/tmp/melo` intentional; subprocess args are internal constants only, never user input       |

---

## Out of Scope (v1)

- Favorites + playlists endpoints → Sprint 3 (in progress)
- Metadata preview endpoint → Sprint 3 (in progress)
- Frontend UI → Sprint 4
- Multi-user auth, lyrics, waveforms → never (personal tool)
