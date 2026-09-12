# Melo — Roadmap

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

### Sprint 6 — Frontend Polish ✅ done
- FE-0 Responsive layout (desktop/tablet/phone breakpoints, bottom tab bar + icon rail nav) ✅
- FE-1 Player features (volume, shuffle, loop, autoplay-next, queue) ✅
- FE-2 Drag-reorder playlists — `PATCH /playlists/{id}/songs/{song_id}` + native HTML5 DnD ✅
- FE-3 Waveform display — new Now Playing panel, client-side decode + peaks cache ✅
- FE-4 Accessibility audit — Escape chain, focus trap, aria-live, dropdown roles, keyboard playlist reorder ✅
- FE-5 UX bug fixes — audit-driven, ongoing batch logged in `TODO.md` ✅ (2 items still flagged for Karthik's confirm/override, not blocking)
- FE-6 Tests — backend TDD for reorder endpoint + smoke suites ✅ (manual frontend smoke checklist still outstanding, non-automatable)

Reverses Sprint 4's "desktop-only, no mobile" call and the "drag-reorder/waveform post-v1" items below — see Decision Log in `PRD.md`.

---

## Now

Housekeeping only — see `TODO.md`:
- Version numbering decision (`pyproject.toml` vs. CHANGELOG's `0.3.0`→`0.4.0`→`0.5.0`)
- `make alerts` / `make log-rotate` — implement or drop from docs
- `make admin` Makefile syntax bug

Plus Sprint 6 loose ends (see `TODO.md` FE-4/FE-5/FE-6):
- Manual tab-order pass across all pages/breakpoints (needs a browser)
- Manual frontend smoke checklist (responsive, player controls, drag-drop, waveform, focus trap)
- Karthik confirm/override: `prev()` >3s-restart convention, phone song-card stacking layout

---

## Now — Sprint 7: Frontend Rewrite (Next.js/TS/Tailwind), scoped

- FE7-0 Scaffold (Next 14 App Router, TS, pnpm, ESLint, Tailwind, Jest/RTL/msw)
- FE7-1 Design tokens → Tailwind theme + minimal `globals.css`
- FE7-2 Port all components 1:1
- FE7-3 Typed API client
- FE7-4 `PlayerProvider` — queue/shuffle/loop/volume/waveform parity
- FE7-5 Real routes, client-resolved `/playlists/[id]`
- FE7-6 Player Bar + Now Playing panel
- FE7-7 Drag-reorder + keyboard alt
- FE7-8 Add Song modal
- FE7-9 Jest/RTL/msw tests, ≥80% coverage (new FE test surface)
- FE7-10 HTTPS — self-signed cert baked into nginx image
- FE7-11 Docker multi-stage build (pnpm build → static export → nginx)

## Next — Sprint 8+ (scope not yet defined)

Candidates deferred from Sprint 6, still pending:

- Waveform click-to-seek
- Bulk/multi-select playlist reorder
- Fix drag-preview showing only thumbnail
- Alertmanager → Telegram going live (real creds, no longer a stub)
- Revisit static-export dynamic-route workaround vs. `next start` (see `DECISIONS.md` Sprint 7, "Still open")

---

## Explicitly Out of Scope (v1)

Carried forward from sprint docs — not roadmapped, listed so they aren't rediscovered as "missing":

- Multi-user auth (main app or admin)
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
| 6      | Frontend Polish                  | ✅ done       |
| 7      | TBD                              | ⬜ not scoped |
