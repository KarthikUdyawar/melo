# Melo — Decisions

> Grouped by the sprint that made the call, using each sprint's own decision log as source of truth (`docs/sprints/Sprint-N.md`). Where the current-state `DECISIONS.md` had a decision not listed in any sprint log verbatim, it's placed under the sprint whose scope it matches and left unmarked; check the sprint doc if you need the exact original wording.

---

## Sprint 1 — Infrastructure & Ingest

| Decision                                                | Reason                                                                                                                                                     |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dropped Alembic                                         | Solo project; `Base.metadata.create_all()` on startup is simpler and sufficient without schema drift risk                                                  |
| `APP_ENV`-driven env files                              | Clean separation: `.env.development` (localhost), `.env.staging` (Docker service names), `.env.production` (real infra)                                    |
| `reset_settings()` + `reset_db()`                       | Lets tests swap envs and DB state without process restart; no global state leaks between test cases                                                        |
| `expire_on_commit=False` on session                     | Avoids lazy-load errors after commit in async/Celery contexts                                                                                              |
| Pinned yt-dlp format selector (`140/251/…`)             | `bestaudio/best` requires a JS runtime for YouTube signature solving; explicit format IDs use plain HTTPS, no Node/Deno needed                             |
| `worker_ready` signal for MinIO bucket                  | Ensures bucket exists once per worker process at startup rather than checking on every task                                                                |
| `_BaseTask` with shared DB session                      | One SQLAlchemy session per worker process, closed in `after_return` — avoids per-task connection overhead                                                  |
| Proxy stream via FastAPI instead of presigned URL       | MinIO presigned URLs are signed against the internal Docker hostname (`minio:9000`); rewriting the host post-signing breaks HMAC. API proxies bytes itself |
| MinIO image tag pinned (`RELEASE.2024-05-01T01-11-10Z`) | Reproducibility; avoids silent breaking changes from `:latest`                                                                                             |
| `/tmp/melo` mounted as `tmpfs` in `api`/`worker`        | Avoids WSL2 Docker Desktop bind-mount permission/corruption issues                                                                                         |

---

## Sprint 2 — Processing, Metadata & API Polish

| Decision                                                                        | Reason                                                                                                                          |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Dedup reuses existing MinIO object                                              | Same audio source, different trim — no re-download; new DB row allows different `start`/`end` per record while sharing one file |
| FFmpeg trim on stream, not on ingest                                            | Avoids storing N trimmed variants per song; one source file in MinIO, trim applied ephemerally per stream request               |
| `probe_metadata(download=False)` before download                                | Populates `title`/`thumbnail_url`/`duration` immediately so `GET /songs/{id}` is useful while `status == processing`            |
| Global exception handler wraps all errors in envelope                           | Single place controls error shape; routers never build error responses manually                                                 |
| Envelope skipped for stream / `/metrics` / `/docs` / `/redoc` / `/openapi.json` | Binary/non-JSON responses can't be wrapped; documented exceptions, not inconsistencies                                          |
| Structured JSON logs, pretty console in dev                                     | JSON parseable by aggregators in staging/prod; human-readable locally without config change                                     |
| Uvicorn access logs disabled                                                    | Middleware already logs method + path + status + duration — duplicate lines add noise                                           |
| Removed `unique=True` on `youtube_id`                                           | Dedup-with-trim needs multiple rows per video; uniqueness enforced at task level, not DB level                                  |
| `noplaylist: True` on both probe and download                                   | A `?v=X&list=Y` URL must resolve to the single video, not the playlist context                                                  |
| Pinned format selector on probe too                                             | `download=False` still triggers JS-runtime format checks; same explicit IDs suppress the hang                                   |
| All new `SongResponse` fields default to `None`                                 | Record is serialized immediately after insert, pre-probe; fields populated async by the worker                                  |
| Stream copy (`-c copy`) first, re-encode fallback                               | Stream copy is instant and lossless; re-encode (`libmp3lame -q:a 2`) only fires on codec mismatch                               |
| Cleanup in generator `finally` block                                            | Ensures `/tmp/melo` files deleted after the last byte sent, even on client disconnect                                           |

---

## Sprint 3 — Speed, Library Features & Metadata UX

| Decision                                                                              | Reason                                                                                              |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| UUID v7 for all PKs (`uuid6.uuid7`)                                                   | String-sortable = chronological = natural cursor pagination key                                     |
| Cursor pagination (`?after=<uuid>`) on `GET /songs`, `bookmark` = last id or `null`   | Stable under concurrent inserts; no offset drift. `offset` kept as a secondary convenience          |
| `count` = total matching records before pagination                                    | Lets clients show "N results" without an extra count query                                          |
| Preview endpoint (`POST /songs/preview`) is stateless                                 | No DB writes; simpler system; worker still re-probes on ingest as source of truth                   |
| Speed applied at stream time, not stored per-variant                                  | Avoids storing N speed variants of the same audio in MinIO                                          |
| Chained `atempo` filters for speed outside `[0.5, 2.0]`                               | FFmpeg caps a single `atempo` stage to that range                                                   |
| Trim always applied before speed                                                      | Reduces data before the (potentially lossy) re-encode step                                          |
| Favorites idempotent via check-then-insert + `IntegrityError` catch                   | Clean UX (200 vs 201) with DB-level dedup as a backstop                                             |
| `unique=True` on `favorites.song_id`                                                  | DB-level dedup regardless of app logic                                                              |
| `is_favorite` populated per song (N+1)                                                | Acceptable at MVP scale                                                                             |
| Playlist ordering via `position`, auto-incremented server-side                        | Predictable playback order; same song reusable across multiple playlists                            |
| `db.refresh(playlist)` after add / `db.expire_all()` after remove                     | Different SQLAlchemy identity-map staleness patterns for add vs. remove — both needed               |
| Soft delete (`deleted_at`) on `songs`, `favorites`, `playlists`                       | Audit trail on user-facing entities; no Alembic migration needed since it's just a model column     |
| `playlist_songs` hard-deleted                                                         | Join table has no audit need                                                                        |
| `_song_utils.py` shared `serialize_song()`                                            | Eliminates duplicate serialization logic; avoids circular imports                                   |
| `effective_duration` = `(end - start, or duration) / speed`, skip when `speed == 1.0` | Reflects actual playback duration after both trim and speed                                         |
| `docs_url`/`redoc_url` disabled in production                                         | Reduces attack surface                                                                              |
| Health check probes DB + Redis + MinIO                                                | Silent infra failure was previously undetectable                                                    |
| `DELETE /songs/{id}` also removes the MinIO object                                    | Was in the PRD but not implemented until this sprint                                                |
| GIN trigram index (`pg_trgm`) on `songs.title`                                        | Supports leading-and-trailing `ILIKE '%search%'`; extension created idempotently, skipped on SQLite |
| Node.js removed from Dockerfile                                                       | Pinned format selector is plain HTTPS; saved ~180MB and ~40s build time                             |
| `uv sync --frozen --no-install-project`                                               | Reproducible builds from lockfile; `melo` itself isn't installed as a package                       |
| `.dockerignore` populated (was empty)                                                 | Prevents `.git`, tests, coverage HTML, `.env*` from leaking into the build context                  |
| `make help` as default Makefile target                                                | Discoverability across 20+ (now 40+) targets                                                        |
| Root `conftest.py` sets env vars in `pytest_configure`                                | Ensures `APP_ENV=test` is set before any module-level settings are read                             |
| Unit test isolation via `_truncate_all()`, not savepoint rollback                     | Savepoint rollback is unreliable once endpoints call `db.commit()` directly                         |

---

## Sprint 4 — Vanilla JS UI

| Decision                                                                        | Reason                                                                                                                              |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Vanilla HTML/JS/CSS over React/Vue                                              | Zero build step (~2s Docker build); avoids Node/pnpm/WSL2 memory pressure entirely — React/Vite was attempted first and scrapped    |
| ES modules (`type="module"`)                                                    | Clean imports without a bundler; native browser support                                                                             |
| Hash routing (`#/`)                                                             | No server-side routing config needed; nginx serves `index.html` for everything                                                      |
| Single `<audio>` element, module-scoped in `player.js`                          | Persistent playback across hash navigation without any framework state management                                                   |
| HTML strings + `innerHTML` rather than a virtual DOM                            | Simple and fast enough at this scale; no component framework needed                                                                 |
| `setInterval` for polling                                                       | Sufficient for a 2s poll; no reactive-query library needed                                                                          |
| nginx proxies `/api/*` → `api:8000`                                             | Single entry point; no CORS; `proxy_buffering off` required for audio streaming                                                     |
| No frontend tests                                                               | No framework = no component test surface; API already covered                                                                       |
| `ui/Dockerfile` is 3 lines                                                      | `FROM nginx:alpine` + `COPY` + done; ~2s build                                                                                      |
| Event delegation via one `document`-level click listener                        | Works for dynamically rendered cards without re-binding listeners per render                                                        |
| `httpx` proxy (no trim/speed) + `FileResponse` (trim/speed), chosen per-request | Only way to get real Range/206 support for the common case while still supporting FFmpeg-processed audio                            |
| Retry = delete old record + resubmit same params                                | Reuses the existing `POST /songs` path; original params read off the failed record; old record deleted only after resubmit succeeds |
| "New playlist" from the dropdown uses `window.prompt()`, not an inline field    | Simpler; no dedicated inline-input state needed                                                                                     |
| `hasMore = bookmark && records.length >= limit`                                 | A short page means end-of-results even with a non-null bookmark; prevents a ghost "Load more" button                                |
| No dedicated `renderModal()` — modal markup built inline in `app.js`            | Modals have divergent enough content that a shared template added little value                                                      |

---

## Sprint 5 — Observability & Monitoring

| Decision                                                                                | Reason                                                                                                                                                                                                        |
| --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Grafana's built-in Alertmanager over a standalone service                               | Zero extra container; YAML-provisioned contact points; sufficient for a solo deployment                                                                                                                       |
| Promtail scrapes the JSONL log file, not the Docker log driver                          | Structured label extraction from JSON fields; decouples log format from transport                                                                                                                             |
| Gzip + upload to MinIO on log roll (not batched)                                        | Minimizes local disk use; no cron; simpler failure model                                                                                                                                                      |
| APScheduler cleanup runs inside the API process                                         | No extra container; survives app restarts as part of the normal lifecycle                                                                                                                                     |
| stdout stays `ConsoleRenderer`; file output is `JSONRenderer` (JSONL)                   | `docker compose logs` stays readable; Loki scrapes the file, not stdout                                                                                                                                       |
| `trace_id` injected into every log line                                                 | Enables Grafana log↔trace correlation without leaving the UI                                                                                                                                                  |
| `X-Trace-Id` header on every API response                                               | Browser-side debugging without opening Grafana                                                                                                                                                                |
| OTEL `traceparent` propagated into Celery task headers, reconstructed at task start     | HTTP request span and async task span appear in the same trace                                                                                                                                                |
| Pyroscope continuous profiling, always-on                                               | Catches intermittent CPU spikes; low overhead at this scale                                                                                                                                                   |
| `configure_pyroscope()` no-ops if server URL unset                                      | Local dev unaffected; clean degradation                                                                                                                                                                       |
| Single `app/core/metrics.py` module for all metric definitions                          | Prevents duplicate-registration errors; one place to look                                                                                                                                                     |
| `relativeTimeRange` explicit on every Grafana alert data node                           | Grafana 13 rejects `{from: 0, to: 0}`; every query/`__expr__` node needs an explicit window                                                                                                                   |
| Monitoring stack in a separate Compose file                                             | Main compose stays clean; monitoring is optional (`make monitoring-up` vs `make monitoring-up-all`)                                                                                                           |
| `loki`/`tempo`/`pyroscope` use `service_started`, not `service_healthy`                 | Their `/ready` endpoints are slow on WSL2 Docker Desktop (ingester anti-flap) even when functionally ready                                                                                                    |
| `pyroscope` container runs as `user: root`                                              | Its named volume is created root-owned on first run; default non-root image user can't write to it                                                                                                            |
| `--wait` dropped from the monitoring `compose up` invocation                            | loki/tempo/pyroscope report cosmetically unhealthy on WSL2; `--wait` would fail the whole command                                                                                                             |
| cAdvisor matches containers by cgroup ID, not name, on WSL2                             | Docker Desktop's daemon storage lives inside its internal VM; cAdvisor's docker factory can't resolve overlay2 layerdb even with `--privileged`; `make cadvisor-ids` re-run needed after container recreation |
| Health check log suppression only when `GET /health` is `200`                           | Grafana's ~10s datasource probes across every datasource would otherwise flood Loki; a non-200 health check is itself worth keeping                                                                           |
| Streamlit admin password from env, `hmac.compare_digest`                                | Solo user; simplest secure option, consistent with existing `APP_ENV`-driven config pattern                                                                                                                   |
| Streamlit admin pages query Prometheus/Loki/Grafana/Melo API directly, no iframe embeds | Keeps the admin app decoupled from Grafana's own auth/session model                                                                                                                                           |
| `melo_melo_logs` is a named volume, not a bind mount                                    | Bind mounts caused Promtail/Loki to receive zero logs; the named volume matches Promtail's `external: true` reference exactly                                                                                 |
| Grafana Telegram contact point shipped as a commented-out stub                          | Grafana 13 validates contact point credentials at boot even with placeholder env vars; real setup deferred to manual UI config once credentials exist                                                         |
