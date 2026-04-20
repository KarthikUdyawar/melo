# PRD — Melo

> *Your personal self-hosted audio library.*

**Owner:** Karthik | **Repo:** `melo` | **Timeline:** 4 weeks (solo) | **Stack:** FastAPI · yt-dlp · FFmpeg · MinIO · PostgreSQL · Redis + Celery · Docker · uv

---

## Problem

No simple self-hosted tool lets you download, trim, and manage YouTube audio in a personal library with playlist and favorites support.

---

## Goal

Build a personal audio manager: paste a YouTube URL → get a trimmed, playable audio file stored in MinIO, organized into playlists and favorites.

---

## Users

Solo user (self-hosted). No multi-tenancy in MVP.

---

## Scope

### ✅ In

| Feature        | Details                                      |
| -------------- | -------------------------------------------- |
| Audio download | `yt-dlp`, best audio format                  |
| Processing     | FFmpeg trim (start/end) + speed (0.5–2.0×)   |
| Storage        | MinIO, path: `{user_id}/{song_id}.mp3`       |
| Metadata       | PostgreSQL: songs, favorites, playlists      |
| Streaming      | Pre-signed MinIO URLs                        |
| Async jobs     | Celery + Redis (download + process pipeline) |
| API            | FastAPI REST                                 |

### ❌ Out (v1)

Lyrics, waveforms, AI recommendations, multi-user auth, mobile UI.

---

## API Surface

```
POST   /songs              # submit URL + trim/speed params → job_id
GET    /songs              # list all
GET    /songs/{id}/stream  # returns pre-signed URL
DELETE /songs/{id}

POST   /favorites/{song_id}
GET    /favorites

POST   /playlists
POST   /playlists/{id}/songs/{song_id}
GET    /playlists
```

---

## Data Model

```
songs(id, title, youtube_id, file_url, duration, speed, status, created_at)
favorites(id, song_id, created_at)
playlists(id, name, created_at)
playlist_songs(playlist_id, song_id, position)
```

---

## Async Job Flow

```
POST /songs → push Celery task
  └── download (yt-dlp) → process (FFmpeg) → upload (MinIO) → update DB status
```

---

## Folder Structure

```
melo/
  app/
    api/          # FastAPI routers
    services/     # downloader.py, processor.py, storage.py
    models/       # SQLAlchemy models
    workers/      # Celery tasks
    core/         # config, db, deps
  docker-compose.yml
  pyproject.toml  # uv managed
  .pre-commit-config.yaml
  .coderabbit.yaml
```

---

## Milestones

| Week | Deliverable                                                                   |
| ---- | ----------------------------------------------------------------------------- |
| 1    | Docker infra (FastAPI + Postgres + MinIO + Redis) · DB models · `/songs` POST |
| 2    | Celery pipeline (download → FFmpeg → MinIO upload) · `/songs` GET + stream    |
| 3    | Favorites + playlists endpoints · pre-commit hooks (ruff, mypy, black)        |
| 4    | Error handling · job status polling · README · CodeRabbit config · cleanup    |

---

## Quality Constraints

- **Linting:** ruff + black + mypy via pre-commit
- **Code review:** CodeRabbit on every PR
- **Packaging:** `uv` only, no pip/poetry
- **Deployment:** single `docker compose up` — no manual steps
- **FFmpeg:** chain `atempo` filters if speed < 0.5 or > 2.0
- **Dedup:** skip re-download if `youtube_id` already exists in DB

---

## Risks

| Risk               | Mitigation                                                     |
| ------------------ | -------------------------------------------------------------- |
| YouTube ToS        | Personal/local use only; no redistribution                     |
| yt-dlp breakage    | Pin version; wrap in try/except with fallback error status     |
| Long jobs blocking | All heavy work behind Celery; API returns `job_id` immediately |