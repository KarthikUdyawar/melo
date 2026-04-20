# Melo — Sprint 1: Infrastructure & Ingest

**Duration:** Week 1 (Days 1–7)
**Goal:** `docker compose up` runs the full Melo stack; a YouTube URL can be submitted and lands in MinIO with DB metadata.
**Branch strategy:** `develop` base → feature branches → PR → CodeRabbit review → merge

---

## Sprint Goal

> *A user can POST a YouTube URL, the job runs async via Celery, audio is downloaded + stored in MinIO, and the song record is queryable via GET /songs.*

---

## Backlog

### 🏗️ INFRA-1 — Docker Compose stack
**Branch:** `feature/infra-docker`

- [x] `docker-compose.yml` with services: `api`, `worker`, `postgres`, `minio`, `redis`
- [x] `Dockerfile` for `api` and `worker` (shared base image, uv install)
- [x] Health checks on all services
- [x] `example.env` with all required vars (`DATABASE_URL`, `MINIO_*`, `REDIS_URL`, `CELERY_BROKER`)
- [x] Volumes for postgres data and minio data
- [x] `Makefile` targets: `up`, `down`, `logs`, `test`

---

### ⚙️ INFRA-2 — Project scaffold & tooling
**Branch:** `feature/infra-scaffold`

- [x] `pyproject.toml` with uv — `name = "melo"`, deps: `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `celery`, `redis`, `minio`, `yt-dlp`, `pydantic-settings`
- [x] `app/core/config.py` — pydantic `Settings` with `APP_ENV`-driven env file loading (`get_settings()` + `reset_settings()`)
- [x] `app/core/db.py` — SQLAlchemy lazy engine + session factory + `init_db()` + `reset_db()` + `ping_db()`
- [x] `app/core/deps.py` — `get_db` dependency + `DbDep` annotated alias
- [x] `.env.development` — local machine config (localhost endpoints)
- [x] `.env.staging` — Docker Compose config (service-name hostnames)
- [x] `.env.production` — production template (CHANGE_ME placeholders, `MINIO_SECURE=true`)
- [x] `example.env` — copy-paste reference for all vars

---

### 🗄️ DB-1 — Database models & schema
**Branch:** `feature/db-models`

- [x] `app/models/song.py` — `Song` model: `id`, `title`, `youtube_id`, `file_url`, `duration`, `speed`, `status` (enum: pending/processing/done/failed), `created_at`
- [x] `app/models/favorite.py` — `Favorite` model (cascade FK → songs, unique per song)
- [x] `app/models/playlist.py` — `Playlist` + `PlaylistSong` models (position ordering)
- [x] `app/models/__init__.py` — re-exports all models so `init_db()` sees them
- [x] `init_db()` in `db.py` — `Base.metadata.create_all()` called at app startup (no Alembic)
- [x] `reset_db()` in `db.py` — drop + recreate for tests
- [x] Verified: `init_db()` creates all 4 tables cleanly against SQLite and Postgres

---

### 🎵 SONGS-1 — POST /songs endpoint
**Branch:** `feature/songs-ingest`

- [x] `app/schemas/song.py` — `SongCreate` (url, start, end, speed), `SongResponse`
- [x] `app/api/songs.py` — `POST /songs` router: validate input → create DB record (status=pending) → enqueue Celery task → return `{id, status}`
- [x] `app/api/songs.py` — `GET /songs` — list all songs with status
- [x] `GET /songs/{id}` — single song detail
- [x] Input validation: URL must be a valid YouTube URL (regex or yt-dlp probe), speed between 0.5–4.0

---

### ⚡ WORKER-1 — Celery + download pipeline
**Branch:** `feature/worker-pipeline`

- [x] `app/workers/celery_app.py` — Celery instance, Redis broker + backend; `worker_ready` signal ensures MinIO bucket exists before first task
- [x] `app/services/downloader.py` — `download_audio(url, song_id) -> (Path, duration)` using yt-dlp; explicit format selector (`140/251/250/249/139/18`) bypasses JS runtime requirement
- [x] `app/services/storage.py` — `upload_file(path, key) -> key`, `get_presigned_url(key, expires)`, `ensure_bucket_exists()`
- [x] `app/workers/tasks.py` — `process_song_task(song_id, url, start, end, speed)`:
  - [x] Set status → `processing`
  - [x] Download audio via yt-dlp
  - [x] Upload to MinIO at `{song_id}.mp3` (bucket: `songs`)
  - [x] Update DB: `file_url`, `duration`, status → `done`
  - [x] On `DownloadError`/`StorageError`: status → `failed`, no retry
  - [x] On unknown exception: retry up to 3×, then status → `failed`
- [x] MinIO bucket auto-created on worker startup via `worker_ready` signal
- [x] Smoke tested: `POST /songs` → Celery job → `songs/<id>.mp3` confirmed in MinIO, status `done` in DB

---

### 🔊 SONGS-2 — GET /songs/{id}/stream
**Branch:** `feature/songs-stream`

- [x] `GET /songs/{id}/stream` — streams mp3 directly via FastAPI `StreamingResponse`
- [x] Guard: return 404 if song not found
- [x] Guard: return 409 if song status is not `done`
- [x] Guard: return 500 if song has no `file_url`
- [x] Guard: return 502 if MinIO fetch fails
- [x] Response: `audio/mpeg` + `Content-Disposition: attachment` header for download
---

## Definition of Done

- [x] All feature branches merged to `develop` via PR
- [x] `docker compose up` starts clean with zero manual steps
- [x] `POST /songs` → Celery job → MinIO file confirmed via manual smoke test
- [ ] `SPRINT_1.md` checked off and moved to `melo/docs/sprints/`

---

## Out of Scope (→ Sprint 2)

- FFmpeg trim + speed processing
- Favorites + playlists endpoints
- Frontend / Streamlit UI

---

## Decision Log

| Decision                            | Reason                                                                                                                                                   |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dropped Alembic                     | Solo project; `Base.metadata.create_all()` on startup is simpler and sufficient without schema drift risk                                                |
| `APP_ENV`-driven env files          | Clean separation: `.env.development` (localhost), `.env.staging` (Docker service names), `.env.production` (real infra)                                  |
| `reset_settings()` + `reset_db()`   | Lets tests swap envs and DB state without process restart; no global state leaks between test cases                                                      |
| `expire_on_commit=False` on session | Avoids lazy-load errors after commit in async contexts                                                                                                   |
| Pinned yt-dlp format selector       | `bestaudio/best` requires JS runtime (EJS) for YouTube signature solving; explicit format IDs (`140/251/…`) use plain `https` and work without Node/Deno |
| `worker_ready` signal for MinIO     | Ensures bucket exists once per worker process at startup rather than checking on every task                                                              |
| `_BaseTask` with shared DB session  | One SQLAlchemy session per worker process via `get_session_factory()()`, closed in `after_return` — avoids per-task connection overhead                  |
| Proxy stream via FastAPI instead of presigned URL | MinIO presigned URLs are signed against internal Docker hostname (`minio:9000`); rewriting host post-signing breaks HMAC signature. API fetches from MinIO internally and proxies bytes to client — no signature mismatch, no CORS issue. |
