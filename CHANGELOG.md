# Changelog

All notable changes to Melo are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

Nothing yet.

---

## [0.6.0] — Sprint 6 — Frontend Polish

### Added
- Responsive layout: desktop (≥1280px, unchanged), tablet (768–1279px, 56px icon-rail sidebar), phone (≤767px, bottom tab bar + floating Add Song FAB) — CSS-only breakpoint switching, no JS layout logic
- Player features: volume slider + mute toggle (`localStorage['melo:volume']`), 3-state loop button off/one/all (`localStorage['melo:loop']`), session-only shuffle (Fisher–Yates, keeps current song in place), player queue built from the on-screen song list, autoplay-next on `audio.onended`
- `PATCH /playlists/{id}/songs/{song_id}` — reorder a song to a given 0-indexed position, shifts intermediate songs' positions (not a swap); `200`/`404`/`422`, no `409` (sentinel-position swap runs inside one transaction)
- Native HTML5 drag-and-drop playlist reordering on Playlist Detail rows, optimistic UI update + re-fetch-on-failure resync
- Now Playing panel: new full-screen surface (thumbnail, title, channel, waveform, transport controls), opened from the player bar's thumbnail/title
- Client-side waveform: `AudioContext.decodeAudioData()` → ~200 peak buckets → `<canvas>`, in-memory peaks cache (`Map<songId, peaks>`) in `player.js`, played/unplayed bar coloring redrawn per `timeupdate` tick
- Accessibility: `Escape` closes topmost surface only (Now Playing panel → dropdown → modal); manual focus trap (`trapFocus()`) shared between `.modal` and the Now Playing panel; `aria-live="polite"` on `#toast-root`; `aria-label` on status pills; `aria-haspopup`/`aria-expanded`/`role="menu"` on the overflow dropdown; keyboard playlist reorder via `ArrowUp`/`ArrowDown` reusing the same optimistic-reorder path as drag
- Custom favicon + sidebar logo mark (`ui/assets/logo.png`)
- New backend tests for the reorder endpoint (unit: position-shift correctness; integration: `422`/`404`/full-reorder-reflected); `smoke_test.sh` S17 (reorder end-to-end) and expanded `smoke_ui.sh` coverage

### Fixed
- Playlist Detail song card not stretching full row width (`.playlist-song-row .song-card { flex: 1; min-width: 0; }`)
- Scrubber/volume sliders had no progress-fill color — added `--progress` CSS custom property, set from JS on every tick
- Now Playing panel scrubber seek silently uncommitted on some browsers — unified into a single `commitSeek()` guarded by `state.npSeeking`
- Loop-mode "1" badge only rendered on the player bar, not the Now Playing panel — switched from an ID selector to a shared `.loop-btn[data-mode="one"]` class
- Now Playing panel volume icon misaligned above its slider (missing `display:flex`)
- Playlist grid card delete button rendered at the bottom of the card instead of top-right
- Player bar showed nothing when no song was loaded — added a placeholder icon+text state

### Changed
- Reverses Sprint 4's "desktop-only, 1280px minimum" decision — mobile support now in scope
- Player bar shuffle button moved to sit next to the loop button (Now Playing panel's control order left unchanged)

### Known limitations
- Waveform is display-only this sprint — click-to-seek on the waveform itself is out of scope (the separate scrubber handles seeking)
- Bulk/multi-select playlist reorder not supported — one song moved at a time
- Playlist drag-preview shows only the dragged song's thumbnail, not the full row (cosmetic; reorder logic unaffected) — deferred to Sprint 7
- Manual tab-order pass and manual frontend smoke checklist (responsive breakpoints, player controls, drag-drop, waveform, focus trap) still outstanding — require an actual browser
- No automated frontend tests — consistent with Sprint 4's decision (no component framework, no test surface)

---

## [0.5.0] — Sprint 5 — Observability & Monitoring

### Added
- Full observability stack via `infra/docker-compose.monitoring.yml`: Prometheus, Loki, Promtail, Tempo, Grafana, Pyroscope, celery-exporter, Flower, cAdvisor, Node Exporter, Postgres Exporter, Redis Exporter
- Structured logging: structlog dual renderer (stdout `ConsoleRenderer` + file `JSONRenderer`/JSONL), `LogEvent` enum as sole source of event names
- Log rotation on size (10MB) or age (24h), gzip + upload to MinIO `melo-log-backups/`, APScheduler daily cleanup (90-day retention)
- Prometheus metrics: `GET /metrics`, HTTP auto-instrumentation + custom counters/gauges/histograms (`songs_submitted_total`, `songs_completed_total`, `favorites_toggled_total`, `playlist_ops_total`, `download_duration_seconds`, `ffmpeg_duration_seconds`, `minio_upload_duration_seconds`, `stream_duration_seconds`)
- Distributed tracing: OpenTelemetry auto + manual spans → Tempo; `X-Trace-Id` header on every API response; `trace_id` in every log line; Celery task context propagation via `apply_async()` headers
- Continuous profiling via Pyroscope SDK in FastAPI and Celery worker (`configure_pyroscope()`, no-ops if URL unset)
- 3 Grafana dashboards (API, Pipeline, System) + 8 alert rules, all provisioned as YAML/JSON — zero manual setup after `docker compose up`
- Grafana Alertmanager → Telegram contact point (commented-out stub until real bot credentials are supplied — Grafana 13 validates credentials at boot)
- Streamlit admin dashboard (`admin/`) at `:8501` — Overview, Songs, Logs, Metrics, Alerts, DB Health pages; single `ADMIN_PASSWORD` env-gated login (`hmac.compare_digest`)
- `CELERY_SEND_EVENTS` / `CELERY_TASK_TRACK_STARTED` on the worker service, required for `celery-exporter`
- Gauge poller (`app/core/pollers.py`) — `celery_queue_depth`, `celery_active_tasks`, `minio_bucket_size_bytes`, `songs_by_status_total`, polled every 30s
- New Makefile targets: `monitoring-up`, `monitoring-up-all`, `monitoring-down`, `monitoring-restart`, `monitoring-status`, `grafana`, `flower`, `admin`, `metrics`, `logs-loki`, `cadvisor-ids`
- New tests: `test_log_events.py`, `test_logging.py`, `test_log_manager.py`, `test_tracing.py`, `test_metrics_unit.py`, `test_middleware_health.py`, `test_pollers.py`, `test_admin_auth.py`, `test_metrics_api.py`, `test_tracing_api.py`
- Smoke test sections S25 (`GET /metrics` returns 200) and S26 (`X-Trace-Id` header present on every response)

### Fixed
- `relativeTimeRange` made explicit on every Grafana alert rule data node — Grafana 13 rejects `{from: 0, to: 0}`

### Changed
- `loki`/`tempo`/`pyroscope` use `service_started` rather than `service_healthy` as their Compose dependency condition — `/ready` endpoints are slow to report on WSL2 Docker Desktop even when functionally ready
- Coverage target maintained at ≥80%; currently 91% across 425 tests (was 94.77% pre-Sprint-5; new surface area — logging/tracing/metrics/pollers — brought the percentage down while adding meaningful coverage)

### Known limitations
- Telegram alerting requires manual Grafana UI setup once real `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` are available — the provisioned contact point ships as a stub

---

## [0.4.0] — Sprint 4 — Vanilla JS UI

### Added
- Full single-page browser UI (`ui/`) served by nginx at `http://localhost:3000` — vanilla HTML/JS/CSS, ES modules, zero build step
- Hash router: `#/` (Library), `#/favorites`, `#/playlists`, `#/playlists/:id`
- Library page: filter (status), search (300ms debounce), sort, cursor-paginated "Load more", 2s auto-poll while any song is `pending`/`processing`
- Add Song modal: two-step flow (URL → preview → trim/speed params), inline error handling, loading spinner during metadata fetch
- Persistent player bar: single module-scoped `<audio>` element, survives hash navigation, scrubber sync, Range-header seeking (`206` support)
- Favorites: optimistic heart-icon toggle with revert on error
- Playlists: grid view, create via inline input, detail view with ordered song list and remove-song action, "add to playlist" via song-card overflow menu (`window.prompt()` for new playlist name)
- Retry button on failed songs — deletes the old record and resubmits the same URL/trim/speed as a new song, only after the resubmit succeeds
- Toast notifications (success/error variants, 3s auto-dismiss), health banner on unreachable API, keyboard shortcuts (`Space` play/pause, `Esc` close modal)
- `ui/Dockerfile` — `FROM nginx:alpine`, ~2s build; `ui/nginx.conf` — SPA fallback + `/api/*` proxy with `proxy_buffering off`

### Fixed
- `GET /songs/{id}/stream` seeking: no-trim/no-speed path now proxies via `httpx` and forwards the browser's `Range` header, returning `206 Partial Content`
- Event delegation bug where an early `return` in the global click handler blocked song-card clicks
- `worker`/`api` `/tmp/melo` permission errors — switched to `tmpfs` mount

### Changed
- React/Vite frontend attempt scrapped mid-sprint — WSL2 Docker Desktop memory pressure during builds made it impractical; vanilla JS adopted instead

---

## [0.3.0] — Sprint 3 — Speed Processing, Library Features & Metadata UX

### Added
- `POST /songs/preview` — stateless YouTube metadata fetch (no DB write)
- `GET /songs` filtering: `status`, `favorite`, `search`, `sort_by`, `order`
- `GET /songs` cursor-based pagination via `?after=<uuid>` + `bookmark` in response
- `POST /favorites/{song_id}`, `DELETE /favorites/{song_id}`, `GET /favorites`
- `POST /playlists`, `GET /playlists`, `GET /playlists/{id}`, `DELETE /playlists/{id}`
- `POST /playlists/{id}/songs/{song_id}`, `DELETE /playlists/{id}/songs/{song_id}`
- `DELETE /songs/{id}` — soft delete + MinIO object removal
- Speed processing via FFmpeg `atempo` filter (chained for values outside `[0.5, 2.0]`)
- `effective_duration` computed field on `SongResponse` (reflects trim and speed)
- `stream_url` field on `SongResponse` — status-driven, never null
- `upload_date` normalised from yt-dlp `"YYYYMMDD"` → ISO `"YYYY-MM-DD"`
- `is_favorite` field on all song responses
- Soft delete (`deleted_at`) on `songs`, `favorites`, `playlists`
- UUID v7 PKs via `uuid6` package (string-sortable = natural cursor key)
- `_song_utils.py` shared serializer (eliminates 3 copies of `_serialize_song`)
- Health check now probes Redis + MinIO alongside PostgreSQL
- Swagger/OpenAPI: `summary`, `responses`, `Field(description=...)` on all routes
- `docs_url=None` / `redoc_url=None` in production
- Pre-commit hook suite: ruff, bandit, gitleaks, mypy --strict, pydocstyle
- pytest suite: 200+ tests, 94.77% coverage (unit + integration)
- Smoke test: 24-section end-to-end bash script
- `.github/`: CI workflow, issue templates, PR template
- `CONTRIBUTING.md`, `LICENSE`, `SECURITY.md`, `CHANGELOG.md`
- Makefile targets: `lint`, `fmt`, `reset-db`, `seed`, `clean-tmp`, `backup`, `backup-db`, `backup-minio`, `restore-db`, `restore-minio`
- `.dockerignore` — excludes tests, dev tooling, env files, backups from image

### Fixed
- Route ordering bug: `/songs/preview` must precede `/{song_id}`
- `_is_favorited` now filters `Favorite.deleted_at.is_(None)` — soft-deleted favorites no longer show as active
- Dockerfile: removed Node.js (unused — format selector is plain HTTPS); added `uv sync --frozen --no-install-project` for reproducible builds
- `clean-tmp` Makefile target: exec inside worker container (volume is not on host)

### Changed
- All model PKs migrated to UUID v7
- `paginated_response` gains a `bookmark` field
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

[Unreleased]: https://github.com/KarthikUdyawar/melo/compare/0.6.0...HEAD
[0.6.0]: https://github.com/KarthikUdyawar/melo/compare/0.5.0...0.6.0
[0.5.0]: https://github.com/KarthikUdyawar/melo/compare/0.4.0...0.5.0
[0.4.0]: https://github.com/KarthikUdyawar/melo/compare/0.3.0...0.4.0
[0.3.0]: https://github.com/KarthikUdyawar/melo/compare/0.2.0...0.3.0
[0.2.0]: https://github.com/KarthikUdyawar/melo/compare/0.1.0...0.2.0
[0.1.0]: https://github.com/KarthikUdyawar/melo/releases/tag/0.1.0
