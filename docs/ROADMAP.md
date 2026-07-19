# Melo — Roadmap

> Derived from `docs/sprints/Sprint-1.md` … `Sprint-5.md`. Status reflects sprint docs, not memory — sprint docs are source of truth.

---

## Shipped

### Sprint 1 — Infrastructure & Ingest ✅
Docker Compose stack (api/worker/postgres/redis/minio), DB models + soft-delete/UUID groundwork, `POST /songs` → Celery → MinIO pipeline, `GET /songs/{id}/stream` (basic).

### Sprint 2 — Processing, Metadata & API Polish ✅
Response envelope + global exception handlers, structured JSON logging + request middleware, YouTube metadata probe on ingest, dedup-with-trim, FFmpeg trim-on-stream.

### Sprint 3 — Speed, Library Features & Metadata UX ✅
`atempo` speed processing (chained for out-of-range values), `POST /songs/preview` (stateless), favorites, playlists, filter/sort/cursor-pagination on `GET /songs`, computed fields (`effective_duration`, `stream_url`), soft delete rollout, CI/lint/pre-commit/test infra (94.77% coverage).

### Sprint 4 — Vanilla JS UI ✅
Full SPA (`ui/`) on vanilla HTML/JS/CSS + nginx — library/favorites/playlists pages, Add Song modal, persistent player bar with Range-seek support, retry-on-failed, toasts, health banner. Zero build step (React/Vite scrapped for WSL2 memory pressure).

### Sprint 5 — Observability & Monitoring ✅ done
- OBS-0 Docker Compose monitoring stack ✅ (`CELERY_SEND_EVENTS`/`CELERY_TASK_TRACK_STARTED` in compose, all 9 obs env vars in `example.env`)
- OBS-1 Structured logging (dual renderer, rotation, MinIO backup) ✅
- OBS-2 Prometheus metrics ✅
- OBS-3 Distributed tracing (OTEL → Tempo, `X-Trace-Id`, Celery propagation) ✅
- OBS-4 Grafana dashboards + alert rules, Telegram alerting live and confirmed firing ✅
- OBS-5 Pyroscope continuous profiling, flame graph confirmed in Grafana ✅
- OBS-6 Streamlit admin dashboard (6 pages) ✅
- OBS-7 Tests & smoke ✅ — 425 tests passing, 91% coverage, S25/S26 smoke sections, `test_admin_auth.py` passing
- README.md + CHANGELOG.md updated ✅

All runtime checks (Grafana dashboards load, Tempo trace spans visible, Pyroscope flame graph, log rotation → MinIO `.gz`, Telegram alert firing) manually confirmed.

---

## Now

Housekeeping only — see `TODO.md`:
- Version numbering decision (`pyproject.toml` vs. CHANGELOG's `0.3.0`→`0.4.0`→`0.5.0`)
- `make alerts` / `make log-rotate` — implement or drop from docs
- `make admin` Makefile syntax bug

---

## Next — Sprint 6 (scope not yet defined)

No backlog committed yet. Candidate directions surfaced across docs but not scheduled:

- Alertmanager → Telegram going live (real creds, no longer a stub)
- Any post-v1 items explicitly deferred in `README.md` / sprint docs (see below)

---

## Explicitly Out of Scope (v1)

Carried forward from sprint docs — not roadmapped, listed so they aren't rediscovered as "missing":

- Multi-user auth (main app or admin)
- Mobile / responsive layout (desktop-first, 1280px min)
- Drag-to-reorder playlists, waveform display
- AI recommendations
- Caching processed audio variants
- `GET /favorites` cursor pagination
- Alembic migrations (deliberate — `create_all()` only)
- External SaaS log shipping
- SLO / error-budget tracking
- Custom standalone Alertmanager service

---

## Sprint Index

| Sprint | Theme                            | Status       |
| ------ | -------------------------------- | ------------ |
| 1      | Infra & Ingest                   | ✅ done       |
| 2      | Processing, Metadata, API Polish | ✅ done       |
| 3      | Speed, Library, Metadata UX      | ✅ done       |
| 4      | Vanilla JS UI                    | ✅ done       |
| 5      | Observability & Monitoring       | ✅ done       |
| 6      | TBD                              | ⬜ not scoped |
