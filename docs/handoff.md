# Melo — Sprint 5 Handoff

**Date:** 2026-06-07  
**Sprint:** 5 — Observability & Monitoring  
**Repo:** `KarthikUdyawar/melo`  
**Branch:** `develop` base → feature branches → PR

---

## Sprint 5 Status

| Ticket | Title                            | Status                         |
| ------ | -------------------------------- | ------------------------------ |
| OBS-0  | Docker Compose Infra             | ✅ Done                         |
| OBS-1  | Structured Logging               | ✅ Done                         |
| OBS-2  | Metrics                          | ✅ Done                         |
| OBS-3  | Distributed Tracing              | ✅ Done                         |
| OBS-4  | Grafana Dashboards & Alerting    | ✅ Done (rules.yml fix applied) |
| OBS-5  | Continuous Profiling (Pyroscope) | ✅ Done                         |
| OBS-6  | Streamlit Admin Dashboard        | ✅ Done                         |
| OBS-7  | Tests & Smoke                    | ⬜ NOT STARTED — next session   |

---

## What Was Done This Session

### OBS-4 fix
`infra/grafana/provisioning/alerting/rules.yml` — all 8 alert rules were missing `relativeTimeRange` on every `data` block. Grafana 13 rejects `{from: 0, to: 0}`. Fixed: add `relativeTimeRange: { from: 600, to: 0 }` (7200 for log-backup-gap) to every query node and expression node.

### OBS-5 — Pyroscope SDK
- New: `app/core/profiling.py` — `configure_pyroscope(app_name)`, no-ops if `PYROSCOPE_SERVER_URL` unset
- `app/main.py` — calls `configure_pyroscope("melo.api")` inside lifespan after `configure_tracing`
- `app/workers/celery_app.py` — calls `configure_pyroscope("melo.worker")` inside `on_worker_init`
- `pyproject.toml` — add `"pyroscope-io>=0.8.0"` to `[project] dependencies`, then `uv lock && uv sync`

### OBS-6 — Streamlit Admin
Full `admin/` directory delivered:
- `auth.py` — `is_authenticated()`, `login_page()` with `ADMIN_PASSWORD` env check
- `app.py` — login gate, sidebar nav, page dispatch via `exec`, logout button
- `pages/overview.py` — health badges + 4 Prometheus metric cards
- `pages/songs.py` — paginated song table, status breakdown, re-queue button for failed
- `pages/logs.py` — Loki `query_range` tail, service + level filters
- `pages/metrics.py` — free-form PromQL input + 5 preset buttons
- `pages/alerts.py` — Grafana Alertmanager firing alerts + all rules table
- `pages/db_health.py` — postgres-exporter + redis-exporter metrics side by side
- `Dockerfile` — `FROM python:3.12-slim`, `requirements.txt`, `streamlit run app.py`
- `requirements.txt` — `streamlit>=1.35.0`, `requests>=2.32.0`

Docker Compose: add `admin` service to `infra/docker-compose.monitoring.yml` (snippet delivered).  
Makefile: add `make admin` target.

---

## Outstanding Items for Next Session

### OBS-7 — Tests & Smoke (the only remaining ticket)

**Unit tests** (all files already exist in `tests/unit/`, contents unknown — verify before writing):
- `test_admin_auth.py` — NEW: 3 behaviors
  - `is_authenticated()` returns `False` when session key absent (mock `st.session_state`)
  - `login_page()` sets `authenticated=True` on correct password (mock env + session)
  - `login_page()` leaves session unauthenticated on wrong password

Existing test files to check pass (may already be complete from earlier sessions):
- `test_log_events.py`, `test_logging.py`, `test_log_manager.py`, `test_tracing.py`, `test_metrics_unit.py`, `test_middleware_health.py`
- `tests/integration/test_metrics_api.py`, `tests/integration/test_tracing_api.py`

**Smoke test additions** (`tests/smoke_test.sh`):
- S25: `GET /metrics` returns 200
- S26: Any API response has `X-Trace-Id` header

**Coverage:** must stay ≥ 80% (was 94.77%). Add `app/core/profiling.py` to coverage source; it will be mostly covered by the no-op branch in unit tests.

**Definition of Done checks** still open:
- `GET /metrics` 200 + custom metric names present → covered by `test_metrics_api.py`
- `X-Trace-Id` on every response → covered by `test_tracing_api.py`
- Smoke S25/S26 pass
- Coverage ≥ 80%
- `README.md` update: new ports table, new `make` targets, observability section
- `CHANGELOG.md` entry for v0.4.0 (Sprint 5)
- `docs/sprints/Sprint-5.md` — mark OBS-7 done after tests pass

---

## Key Files Changed This Sprint

```
app/core/profiling.py          NEW
app/core/log_events.py         NEW
app/core/log_manager.py        NEW
app/core/logging.py            REWRITE
app/core/metrics.py            NEW
app/core/tracing.py            NEW
app/main.py                    MODIFIED (tracing + profiling + metrics)
app/workers/celery_app.py      MODIFIED (tracing + profiling)
admin/                         NEW (entire directory)
infra/                         NEW (entire directory)
infra/grafana/provisioning/alerting/rules.yml  FIXED (relativeTimeRange)
```

---

## Known Gotchas

- `relativeTimeRange` required on **every** data block in Grafana 13 alert rules — `{from:0, to:0}` crashes provisioning
- `pyroscope-io` must be in `pyproject.toml` deps and `uv sync` run; otherwise `configure_pyroscope` logs and no-ops
- Streamlit `admin/app.py` uses `exec()` for page dispatch — ruff `S102` noqa needed
- Admin container service name in compose must be `admin` (not `streamlit`) to match PRD
- `CELERY_SEND_EVENTS=True` + `CELERY_TASK_TRACK_STARTED=True` still need to be added to worker env in `docker-compose.yml` (OBS-0 outstanding checkbox)
- `example.env` additions (`GRAFANA_ADMIN_PASSWORD`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ADMIN_PASSWORD`, log rotation vars, `PYROSCOPE_SERVER_URL`) still need to be verified as present

---

## Skills for Next Session

- `/tdd` — OBS-7 test writing
- `/clean-code` — standard
- `/caveman ultra` — output style
