# PRD — Melo

> *Your personal self-hosted audio library.*

**Owner:** Karthik | **Repo:** `melo` | **Timeline:** 4 weeks (solo) | **Stack:** FastAPI · yt-dlp · FFmpeg · MinIO · PostgreSQL · Redis + Celery · Docker · uv · Vanilla HTML/JS/CSS · nginx

---

## Problem

No simple self-hosted tool lets you download, trim, and manage YouTube audio in a personal library with playlist and favorites support — with a usable UI.

---

## Goal

Build a personal audio manager: paste a YouTube URL → get a trimmed, playable audio file stored in MinIO, organized into playlists and favorites — all accessible via a clean, minimal browser UI.

---

## Users

Solo user (self-hosted). No multi-tenancy in MVP.

---

## Scope

### ✅ In

| Feature        | Details                                                                       |
| -------------- | ----------------------------------------------------------------------------- |
| Audio download | `yt-dlp`, best audio format                                                   |
| Processing     | FFmpeg trim (start/end) + speed (0.5–4.0×)                                    |
| Storage        | MinIO, path: `{song_id}.mp3`                                                  |
| Metadata       | PostgreSQL: songs, favorites, playlists                                       |
| Streaming      | API-proxied MinIO stream with on-the-fly FFmpeg                               |
| Async jobs     | Celery + Redis (download + process pipeline)                                  |
| API            | FastAPI REST                                                                  |
| UI             | Vanilla HTML/JS/CSS SPA: library, favorites, playlists, persistent player bar |

### ❌ Out (v1)

Lyrics, waveforms, AI recommendations, multi-user auth, mobile UI, drag-to-reorder playlists, JS framework/bundler.

---

## API Surface

```text
POST   /songs/preview      # fetch YouTube metadata, no DB write
POST   /songs              # submit URL + trim/speed params → job_id
GET    /songs              # list all — filter, sort, cursor-paginate
GET    /songs/{id}         # single song + status
GET    /songs/{id}/stream  # stream mp3 (trim + speed applied on-the-fly)
DELETE /songs/{id}         # soft delete + MinIO remove

POST   /favorites/{song_id}
DELETE /favorites/{song_id}
GET    /favorites

POST   /playlists
GET    /playlists
GET    /playlists/{id}
DELETE /playlists/{id}
POST   /playlists/{id}/songs/{song_id}
DELETE /playlists/{id}/songs/{song_id}

GET    /health
```

---

## Data Model

```text
songs(id, title, youtube_id, file_url, duration, speed, start, end,
      thumbnail_url, channel, upload_date, status, created_at, deleted_at)
favorites(id, song_id, created_at, deleted_at)
playlists(id, name, created_at, deleted_at)
playlist_songs(playlist_id, song_id, position)
```

---

## Async Job Flow

```text
POST /songs → push Celery task
  └── download (yt-dlp) → process (FFmpeg) → upload (MinIO) → update DB status
```

---

## UI Flow

```text
Sidebar nav → Library / Favorites / Playlists
Library → [Add Song] → preview modal → submit → poll status → play
Player bar → persistent, loads song on click, streams /songs/{id}/stream
Hash routing → #/ · #/favorites · #/playlists · #/playlists/:id
```

---

## Folder Structure

```text
melo/
  app/                    # FastAPI backend
    api/
    services/
    models/
    workers/
    core/
  ui/                     # Vanilla HTML/JS/CSS frontend
    index.html            # app shell + Google Fonts
    style.css             # design tokens + all styles
    api.js                # fetch wrappers (envelope unwrap)
    player.js             # audio element + player state
    components.js         # renderSongCard, renderStatusPill, renderModal, etc.
    app.js                # hash router + page logic
    nginx.conf
    Dockerfile
  tests/
  docker-compose.yml      # includes ui service
  pyproject.toml
  .pre-commit-config.yaml
  .coderabbit.yaml
```

---

## Milestones

| Week | Deliverable                                                                                                |
| ---- | ---------------------------------------------------------------------------------------------------------- |
| 1    | Docker infra (FastAPI + Postgres + MinIO + Redis) · DB models · `/songs` POST                              |
| 2    | Celery pipeline (download → FFmpeg → MinIO upload) · `/songs` GET + stream                                 |
| 3    | Favorites + playlists · filtering/sorting/pagination · pre-commit · tests (94.77% cov)                     |
| 4    | Vanilla JS UI · Library + Favorites + Playlists pages · persistent player bar · docker-compose integration |

---

## Quality Constraints

- **Linting:** ruff + mypy via pre-commit (backend); no frontend build tooling
- **Code review:** CodeRabbit on every PR
- **Packaging:** `uv` only (backend); no package manager for frontend
- **Deployment:** single `docker compose up` — no manual steps
- **Tests:** backend ≥ 80% coverage; no frontend unit tests (no framework)
- **Clean Code:** single-responsibility JS modules, intention-revealing names, no logic in render functions

---

## Risks

| Risk                | Mitigation                                                           |
| ------------------- | -------------------------------------------------------------------- |
| YouTube ToS         | Personal/local use only; no redistribution                           |
| yt-dlp breakage     | Pin version; wrap in try/except with fallback error status           |
| Long jobs blocking  | All heavy work behind Celery; API returns `job_id` immediately       |
| CORS in development | nginx proxies `/api` → `api:8000`; dev uses Live Server or similar   |
| Polling load        | Poll only when song status is `pending`/`processing`; stop on `done` |
| No bundler          | ES modules via `<script type="module">`; no tree-shaking needed      |
