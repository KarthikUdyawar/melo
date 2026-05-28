# Changelog

All notable changes to Melo are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Planned (Sprint 4)
- Frontend UI
- `make seed` sample data
- `GET /favorites` cursor pagination
- HTTP 206 range streaming

---

## [0.3.0] — Sprint 3 — 2026-05-29

### Added
- `POST /songs/preview` — stateless YouTube metadata fetch (no DB write)
- `GET /songs` filtering: `status`, `favorite`, `search`, `sort_by`, `order`
- `GET /songs` cursor-based pagination via `?after=<uuid>` + `bookmark` in response
- `POST /favorites/{song_id}`, `DELETE /favorites/{song_id}`, `GET /favorites`
- `POST /playlists`, `GET /playlists`, `GET /playlists/{id}`, `DELETE /playlists/{id}`
- `POST /playlists/{id}/songs/{song_id}`, `DELETE /playlists/{id}/songs/{song_id}`
- `DELETE /songs/{id}` — soft delete + MinIO object removal
- Speed processing via FFmpeg `atempo` filter (chained for values outside `[0.5, 2.0]`)
- `effective_duration` computed field on `SongResponse` (reflects trim)
- `stream_url` field on `SongResponse` — status-driven, never null
- `upload_date` normalised from yt-dlp `"YYYYMMDD"` → ISO `"YYYY-MM-DD"`
- `is_favorite` field on all song responses
- Soft delete (`deleted_at`) on `songs`, `favorites`, `playlists`
- UUID v7 PKs via `uuid6` package (string-sortable = natural cursor key)
- `_song_utils.py` shared serializer (eliminates 3 copies of `_serialize_song`)
- Health check now probes Redis + MinIO alongside PostgreSQL
- Swagger/OpenAPI: `summary`, `responses`, `Field(description=...)` on all routes
- `docs_url=None` / `redoc_url=None` in production
- Pre-commit hook suite: ruff, black, mypy --strict, bandit, gitleaks
- pytest suite: 200+ tests, 94.77% coverage (unit + integration)
- Smoke test: 24-section end-to-end bash script
- `.github/`: CI workflow, issue templates, PR template
- `CONTRIBUTING.md`, `LICENSE`, `SECURITY.md`, `CHANGELOG.md`
- Makefile targets: `lint`, `fmt`, `reset-db`, `seed`, `clean-tmp`, `backup`, `backup-db`, `backup-minio`, `restore-db`, `restore-minio`
- `.dockerignore` — excludes tests, dev tooling, env files, backups from image

### Fixed
- Route ordering bug: `/songs/preview` must precede `/{song_id}`
- `_is_favorited` now filters `Favorite.deleted_at.is_(None)` — soft-deleted favorites no longer show as active
- Dockerfile: removed Node.js (unused — format selector is plain HTTPS); added `uv.lock --frozen` for reproducible builds
- `clean-tmp` Makefile target: exec inside worker container (volume is not on host)

### Changed
- All model PKs migrated to UUID v7
- `paginated_response` gains `bookmark` field
- Unit test isolation switched from savepoint rollback to `_truncate_all()` (savepoint unreliable when endpoints call `db.commit()`)

---

## [0.2.0] — Sprint 2 — 2026-05-01

### Added
- Celery worker: `process_song_task` (download → FFmpeg → MinIO upload)
- `GET /songs/{id}/stream` — StreamingResponse with trim on-the-fly
- `probe_metadata()` in `downloader.py` — yt-dlp metadata without download
- `trim_audio()` in `processor.py` — FFmpeg stream-copy with libmp3lame fallback
- `thumbnail_url`, `channel`, `upload_date`, `start`, `end` fields on Song model
- Dedup logic in `tasks.py` — skip re-download if `youtube_id` exists
- Task retry (max 3×) for unknown errors; immediate fail for `DownloadError`/`StorageError`
- `worker_ready` signal for MinIO bucket creation (once per process)

### Fixed
- yt-dlp playlist resolution bug: `noplaylist=True` + `extractor_args` skip flags
- Pinned format selector (`140/251/249/250/139/18`) — avoids JS-runtime formats

---

## [0.1.0] — Sprint 1 — 2026-04-20

### Added
- Docker Compose stack: FastAPI, Celery, PostgreSQL 16, Redis 7, MinIO, Adminer
- `POST /songs` — submit YouTube URL, returns 202 with job ID
- `GET /songs` — list all songs
- `GET /songs/{id}` — song detail + status
- `GET /health` — basic DB connectivity check
- Song model: `id`, `title`, `youtube_id`, `file_url`, `duration`, `speed`, `status`, `created_at`
- `APP_ENV`-driven env file loading (development / staging / production)
- structlog structured logging + request middleware
- Makefile with core targets

[Unreleased]: https://github.com/KarthikUdyawar/melo/compare/0.3.0...HEAD
[0.3.0]: https://github.com/KarthikUdyawar/melo/compare/0.2.0...0.3.0
[0.2.0]: https://github.com/KarthikUdyawar/melo/compare/0.1.0...0.2.0
[0.1.0]: https://github.com/KarthikUdyawar/melo/releases/tag/0.1.0
