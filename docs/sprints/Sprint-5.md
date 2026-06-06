# Melo — Sprint 5: Observability & Monitoring

**Duration:** Week 5
**Goal:** Ship full three-pillar observability (logs, metrics, traces) + continuous profiling + Telegram alerting + Streamlit admin — all provisioned as code, all starting with `docker compose up`.
**Branch strategy:** `develop` base → feature branches → PR → CodeRabbit review → merge

---

## Sprint Goal

> *Know what broke, when, and why — without touching the terminal.*

---

## Why This Stack

- **Grafana** as single pane of glass — dashboards, alerting, trace drill-through, profiling, all in one UI
- **Promtail + Loki** over Docker log driver — structured label extraction from JSONL; decouples log format from transport
- **OTEL auto-instrumentation** at startup — zero per-endpoint decoration; `trace_id` in every log line enables log ↔ trace correlation
- **Pyroscope continuous profiling** — catches intermittent CPU spikes; low overhead at this scale
- **Gzip + upload on roll** — minimises local disk; no cron; simpler failure model than batch
- **APScheduler cleanup** — runs inside existing API process; no extra container
- **`celery-exporter` sidecar** — Celery metrics with zero worker code changes
- **Postgres + Redis exporters** — DB and broker health without Melo code changes
- **cAdvisor + Node Exporter** — container and host OS visibility; standard in every Prometheus stack

---

## File Structure (additions only)

```text
infra/
  prometheus/
    prometheus.yml          # all scrape targets
  loki/
    loki.yml
  promtail/
    promtail.yml
  tempo/
    tempo.yml               # retention_period: 72h
  pyroscope/
    pyroscope.yml           # retention: 7d
  grafana/
    provisioning/
      datasources/
        all.yml             # Loki, Prometheus, Tempo, Pyroscope
      dashboards/
        all.yml
        api.json
        pipeline.json
        system.json
      alerting/
        rules.yml           # all alert rules
        telegram.yml        # contact point + notification policy

admin/
  app.py                    # entry point + login gate + sidebar
  auth.py                   # session password check
  pages/
    overview.py
    songs.py
    logs.py
    metrics.py
    alerts.py
    db_health.py            # postgres + redis exporter stats
  Dockerfile
  requirements.txt

app/
  core/
    log_events.py           # LogEvent enum — single source of truth
    log_manager.py          # rotation + gzip + MinIO upload + APScheduler cleanup
    logging.py              # rewrite: dual renderer (stdout string + file JSONL)
    metrics.py              # all Prometheus metric definitions
    tracing.py              # OTEL setup + X-Trace-Id middleware helper
```

---

## Backlog

---

### OBS-0 — Docker Compose Infra

All new services, volumes, configs. Zero breaking changes to existing services.

#### New services in `docker-compose.yml`
* [ ] `prometheus` — `prom/prometheus:latest`, port 9090, mounts `infra/prometheus/prometheus.yml`
* [ ] `loki` — `grafana/loki:latest`, port 3100, mounts `infra/loki/loki.yml`
* [ ] `promtail` — `grafana/promtail:latest`, no external port, mounts shared log volume + `infra/promtail/promtail.yml`
* [ ] `tempo` — `grafana/tempo:latest`, port 4317 (OTLP gRPC), mounts `infra/tempo/tempo.yml`
* [ ] `grafana` — `grafana/grafana:latest`, port 3001, mounts `infra/grafana/provisioning/`, named volume for state persistence
* [ ] `pyroscope` — `grafana/pyroscope:latest`, port 4040, mounts `infra/pyroscope/pyroscope.yml`
* [ ] `celery-exporter` — `danihodovic/celery-exporter:latest`, port 9808, `CELERY_BROKER_URL` from env
* [ ] `flower` — `mher/flower:latest`, port 5555, no auth, broker URL from env
* [ ] `cadvisor` — `gcr.io/cadvisor/cadvisor:latest`, port 8090, Docker socket + cgroup mounts
* [ ] `node-exporter` — `prom/node-exporter:latest`, port 9100, `/proc` + `/sys` + `/` bind mounts
* [ ] `postgres-exporter` — `prom/postgres-exporter:latest`, port 9187, `DATA_SOURCE_NAME` from env
* [ ] `redis-exporter` — `oliver006/redis_exporter:latest`, port 9121, `REDIS_ADDR` from env
* [ ] `admin` — custom Streamlit, port 8501, `Dockerfile` in `admin/`

#### Volumes & config
* [ ] Named volume `grafana-data` — pins Grafana SQLite DB; dashboard + alert state survives container wipe
* [ ] Named volume `melo-logs` — shared between `api`, `worker`, `promtail`; path `/var/log/melo/`
* [ ] `tmpfs` for Tempo WAL (if needed per image version)

#### `depends_on` health checks
* [ ] `grafana` waits for `prometheus`, `loki`, `tempo`, `pyroscope` (`condition: service_healthy`)
* [ ] `promtail` waits for `loki`
* [ ] Health check probes defined for each new infra service

#### Infra configs
* [ ] `infra/prometheus/prometheus.yml` — scrape targets: `api:8000/metrics`, `celery-exporter:9808`, `cadvisor:8090`, `node-exporter:9100`, `postgres-exporter:9187`, `redis-exporter:9121`, MinIO `/minio/v1/metrics` (bearer token auth)
* [ ] `infra/loki/loki.yml` — filesystem storage, local retention
* [ ] `infra/promtail/promtail.yml` — scrape `/var/log/melo/*.jsonl`, parse JSON labels (`service`, `level`, `event`, `trace_id`)
* [ ] `infra/tempo/tempo.yml` — OTLP gRPC receiver, `retention_period: 72h`
* [ ] `infra/pyroscope/pyroscope.yml` — retention `168h` (7 days)

#### Worker env additions
* [ ] `CELERY_SEND_EVENTS=True` added to worker service env
* [ ] `CELERY_TASK_TRACK_STARTED=True` added to worker service env

#### New env vars (added to `example.env`)
* [ ] `GRAFANA_ADMIN_PASSWORD`
* [ ] `TELEGRAM_BOT_TOKEN`
* [ ] `TELEGRAM_CHAT_ID`
* [ ] `ADMIN_PASSWORD`
* [ ] `LOG_MAX_SIZE_MB` (default `10`)
* [ ] `LOG_MAX_AGE_HOURS` (default `24`)
* [ ] `LOG_BACKUP_BUCKET` (default `melo-log-backups`)
* [ ] `LOG_RETENTION_DAYS` (default `90`)
* [ ] `PYROSCOPE_SERVER_URL` (default `http://pyroscope:4040`)

---

### OBS-1 — Structured Logging

Depends on: OBS-0

#### `app/core/log_events.py` — `LogEvent` enum
* [ ] All log event names as enum members — no raw strings anywhere else in codebase
* [ ] Members: `REQUEST_STARTED`, `REQUEST_FINISHED`, `REQUEST_FAILED`
* [ ] Members: `SONG_SUBMITTED`, `SONG_NOT_FOUND`, `SONG_DELETED`, `SONG_STREAM_STARTED`, `SONG_STREAM_FAILED`, `PREVIEW_FETCHED`, `PREVIEW_FAILED`
* [ ] Members: `TASK_RECEIVED`, `TASK_PROCESSING`, `TASK_DONE`, `TASK_FAILED`, `TASK_RETRY`
* [ ] Members: `DOWNLOAD_STARTED`, `DOWNLOAD_DONE`, `DOWNLOAD_FAILED`
* [ ] Members: `FFMPEG_TRIM_STARTED`, `FFMPEG_TRIM_DONE`, `FFMPEG_SPEED_STARTED`, `FFMPEG_SPEED_DONE`, `FFMPEG_FAILED`
* [ ] Members: `MINIO_UPLOAD_STARTED`, `MINIO_UPLOAD_DONE`, `MINIO_UPLOAD_FAILED`, `MINIO_STREAM_STARTED`, `MINIO_STREAM_FAILED`
* [ ] Members: `LOG_ROTATED`, `LOG_COMPRESSED`, `LOG_BACKUP_UPLOADED`, `LOG_BACKUP_CLEANED`
* [ ] Members: `FAVORITE_ADDED`, `FAVORITE_REMOVED`
* [ ] Members: `PLAYLIST_CREATED`, `PLAYLIST_DELETED`, `PLAYLIST_SONG_ADDED`, `PLAYLIST_SONG_REMOVED`
* [ ] Members: `HEALTH_CHECKED`, `HEALTH_DEGRADED`

#### `app/core/logging.py` — dual renderer rewrite
* [ ] `configure_logging(service: str)` — sets up structlog processor chain
* [ ] Processor chain: timestamp → log level → `trace_id` injector (from OTEL context) → event → renderer fork
* [ ] stdout renderer → `ConsoleRenderer` (human-readable string for `docker compose logs`)
* [ ] file renderer → `JSONRenderer` writing to `/var/log/melo/<service>.jsonl`, one JSON object per line
* [ ] Required fields on every line: `timestamp`, `level`, `event`, `service`, `trace_id`
* [ ] `setup_logging()` called at app startup (`app/main.py`) and Celery startup (`celery_app.py`)

#### `app/core/log_manager.py` — rotation + backup + cleanup
* [ ] Background thread checks every 60 s: roll if `file_size >= LOG_MAX_SIZE_MB MB` OR `file_age >= LOG_MAX_AGE_HOURS h`
* [ ] On-roll sequence (exact order):
  1. Close current file handle
  2. Rename → `<service>.<ISO-timestamp>.jsonl`
  3. Gzip → `<service>.<ISO-timestamp>.jsonl.gz` (in-process, no shell)
  4. Upload → MinIO `melo-log-backups/<service>/<YYYY>/<MM>/<filename>.gz`
  5. Delete local `.gz`
  6. Open fresh `<service>.jsonl`
  7. Log `LogEvent.LOG_ROTATED` then `LogEvent.LOG_BACKUP_UPLOADED`
* [ ] APScheduler daily job at 02:00 UTC: list `melo-log-backups/`, delete objects older than `LOG_RETENTION_DAYS` days
* [ ] Cleanup emits `LogEvent.LOG_BACKUP_CLEANED` with `deleted_count` field

#### Middleware — health log suppression
* [ ] `GET /health` with status 200: skip `REQUEST_STARTED` + `REQUEST_FINISHED` log events
* [ ] `GET /health` with status ≠ 200: log normally (infra degraded = signal worth keeping)

#### Log coverage — all existing call sites
* [ ] `app/api/songs.py` — emit correct `LogEvent` on each route
* [ ] `app/api/favorites.py` — emit `FAVORITE_ADDED`, `FAVORITE_REMOVED`
* [ ] `app/api/playlists.py` — emit `PLAYLIST_CREATED`, `PLAYLIST_DELETED`, `PLAYLIST_SONG_ADDED`, `PLAYLIST_SONG_REMOVED`
* [ ] `app/services/downloader.py` — emit `DOWNLOAD_STARTED`, `DOWNLOAD_DONE`, `DOWNLOAD_FAILED`
* [ ] `app/services/processor.py` — emit `FFMPEG_TRIM_STARTED`, `FFMPEG_TRIM_DONE`, `FFMPEG_SPEED_STARTED`, `FFMPEG_SPEED_DONE`, `FFMPEG_FAILED`
* [ ] `app/services/storage.py` — emit `MINIO_UPLOAD_STARTED`, `MINIO_UPLOAD_DONE`, `MINIO_UPLOAD_FAILED`, `MINIO_STREAM_STARTED`, `MINIO_STREAM_FAILED`
* [ ] `app/workers/tasks.py` — emit `TASK_RECEIVED`, `TASK_PROCESSING`, `TASK_DONE`, `TASK_FAILED`, `TASK_RETRY`
* [ ] `app/api/health.py` — emit `HEALTH_CHECKED` (skip if 200 in middleware); `HEALTH_DEGRADED` if any service ≠ ok

#### TDD slices (vertical, one behavior per cycle)
* [ ] Log line emits `trace_id` field (unit — mock OTEL context)
* [ ] File output is valid JSONL — one JSON object per line, required fields present (unit)
* [ ] Roll triggers when `file_size >= LOG_MAX_SIZE_MB` (unit — mock file stat)
* [ ] Roll triggers when `file_age >= LOG_MAX_AGE_HOURS` (unit — mock time)
* [ ] Rolled file compressed to `.gz` in-process (unit)
* [ ] MinIO upload called on roll with correct bucket path (unit — mock storage)
* [ ] Cleanup deletes objects older than 90 days, preserves newer (unit — mock MinIO list)
* [ ] `GET /health` 200 — `REQUEST_STARTED` not logged (unit — check log output)
* [ ] `GET /health` 500 — `REQUEST_STARTED` is logged (unit)

---

### OBS-2 — Metrics

Depends on: OBS-0

#### `app/core/metrics.py` — all metric definitions
* [ ] All metric objects defined here; nothing imported from elsewhere
* [ ] `songs_submitted_total` — Counter
* [ ] `songs_completed_total` — Counter, label `status` (`done` | `failed`)
* [ ] `favorites_toggled_total` — Counter, label `action` (`add` | `remove`)
* [ ] `playlist_ops_total` — Counter, label `action` (`create` | `delete` | `add_song` | `remove_song`)
* [ ] `celery_queue_depth` — Gauge (polled every 30 s)
* [ ] `celery_active_tasks` — Gauge (polled every 30 s)
* [ ] `minio_bucket_size_bytes` — Gauge (polled every 30 s)
* [ ] `songs_by_status_total` — Gauge, label `status`, polled every 30 s
* [ ] `download_duration_seconds` — Histogram
* [ ] `ffmpeg_duration_seconds` — Histogram, label `op` (`trim` | `speed` | `trim_speed`)
* [ ] `minio_upload_duration_seconds` — Histogram
* [ ] `stream_duration_seconds` — Histogram

#### HTTP auto-instrumentation
* [ ] `prometheus_fastapi_instrumentator` applied at startup in `app/main.py`
* [ ] Exposes `GET /metrics` endpoint
* [ ] Labels: method, endpoint, HTTP status code

#### Call site instrumentation
* [ ] `app/api/songs.py` — increment `songs_submitted_total` on `POST /songs`; increment `songs_completed_total` in task callback
* [ ] `app/api/favorites.py` — increment `favorites_toggled_total`
* [ ] `app/api/playlists.py` — increment `playlist_ops_total`
* [ ] `app/services/downloader.py` — observe `download_duration_seconds`
* [ ] `app/services/processor.py` — observe `ffmpeg_duration_seconds` with correct `op` label
* [ ] `app/services/storage.py` — observe `minio_upload_duration_seconds`
* [ ] `app/api/songs.py` stream route — observe `stream_duration_seconds`

#### MinIO native metrics
* [ ] Prometheus scrape job for MinIO `/minio/v1/metrics` with bearer token from env
* [ ] Documented in `infra/prometheus/prometheus.yml` with `authorization` block

#### TDD slices
* [ ] `songs_submitted_total` increments on `POST /songs` (integration — TestClient)
* [ ] `favorites_toggled_total` increments with correct label on add and remove (integration)
* [ ] `playlist_ops_total` increments on create and delete (integration)
* [ ] `GET /metrics` returns 200 and body contains `songs_submitted_total` (integration)
* [ ] `download_duration_seconds` histogram has at least one observation after download (unit — mock timer)

---

### OBS-3 — Distributed Tracing

Depends on: OBS-0, OBS-1

#### `app/core/tracing.py` — OTEL setup
* [ ] `configure_tracing(service_name: str)` — sets up OTEL SDK with OTLP gRPC exporter to Tempo
* [ ] Auto-instrumentation applied at startup: `FastAPIInstrumentor`, `SQLAlchemyInstrumentor`, `HTTPXClientInstrumentor`, `RedisInstrumentor`
* [ ] `get_tracer(name: str) -> Tracer` — returns named tracer for manual spans
* [ ] `extract_trace_id() -> str` — extracts hex trace ID from active span context; returns `"unknown"` if no active span
* [ ] `X-Trace-Id` middleware: injects `extract_trace_id()` into every response header

#### Manual spans in services
* [ ] `app/services/downloader.py` — `download_audio` wrapped in `tracer.start_as_current_span("download_audio")` with `song.id` + `youtube.id` attributes
* [ ] `app/services/processor.py` — `trim_audio` → `"ffmpeg.trim"` span; `apply_speed` → `"ffmpeg.speed"` span
* [ ] `app/services/storage.py` — `upload_file` → `"minio.upload"` span; `get_object` → `"minio.stream"` span

#### Celery context propagation
* [ ] At task enqueue: serialise `traceparent` baggage into Celery task headers
* [ ] At task receive: reconstruct OTEL context from headers → child spans appear in same trace as originating HTTP request
* [ ] `app/workers/tasks.py` — `process_song_task` starts child span `"celery.process_song"`

#### `trace_id` in log lines
* [ ] `app/core/logging.py` processor chain injects `trace_id` from `extract_trace_id()` into every structlog record
* [ ] `trace_id` present in both stdout and JSONL outputs

#### TDD slices
* [ ] `X-Trace-Id` header present on every API response (integration — TestClient, check headers)
* [ ] `X-Trace-Id` value is a non-empty hex string (integration)
* [ ] Celery task headers contain `traceparent` key after enqueue (unit — mock task apply_async, inspect headers)
* [ ] `extract_trace_id()` returns `"unknown"` when no active span (unit)
* [ ] Log record contains `trace_id` field matching active span (unit — mock OTEL context)

---

### OBS-4 — Grafana Dashboards & Alerting

Depends on: OBS-1, OBS-2, OBS-3

All provisioned as code. No manual clicking after `docker compose up`.

#### Datasources — `infra/grafana/provisioning/datasources/all.yml`
* [ ] Prometheus datasource — `http://prometheus:9090`
* [ ] Loki datasource — `http://loki:3100`; label `service` as stream selector
* [ ] Tempo datasource — `http://tempo:4317`; trace-to-logs correlation via `trace_id` field
* [ ] Pyroscope datasource — `http://pyroscope:4040`

#### Dashboard 1 — API Health (`infra/grafana/provisioning/dashboards/api.json`)
* [ ] Request rate by endpoint (Prometheus)
* [ ] Error rate by endpoint (Prometheus)
* [ ] p50 / p95 / p99 latency by endpoint (Prometheus histogram)
* [ ] Active streams gauge (Prometheus)
* [ ] Top 5 slowest endpoints table
* [ ] `X-Trace-Id` drill-through link to Tempo trace detail

#### Dashboard 2 — Celery Pipeline (`pipeline.json`)
* [ ] Songs submitted / done / failed rate (Prometheus counters)
* [ ] Queue depth over time (celery-exporter gauge)
* [ ] Task duration percentiles (celery-exporter histogram)
* [ ] Download duration p50/p95 (Prometheus histogram)
* [ ] FFmpeg duration by op label (Prometheus histogram)
* [ ] MinIO upload duration (Prometheus histogram)
* [ ] Stuck task count — songs in `processing` > 10 m (Prometheus query on `songs_by_status_total` + time)

#### Dashboard 3 — System (`system.json`)
* [ ] Container CPU + memory (cAdvisor metrics)
* [ ] Host OS CPU + memory + disk (node-exporter metrics)
* [ ] PostgreSQL connection count + query latency (postgres-exporter)
* [ ] Redis memory + hit/miss ratio (redis-exporter)
* [ ] MinIO bucket size + API latency (MinIO native metrics)
* [ ] Log backup count + age (Loki query on `LogEvent.LOG_BACKUP_UPLOADED`)
* [ ] Pyroscope flame graph embed panel

#### Alerting — `infra/grafana/provisioning/alerting/`
* [ ] `telegram.yml` — Telegram contact point: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` from env; notification policy routes all alerts to Telegram
* [ ] `rules.yml` — alert rules:
  * [ ] **Task failed storm** — ≥ 3 task failures in 5 m → severity: critical
  * [ ] **Song stuck processing** — any song in `processing` > 10 m → severity: warning
  * [ ] **API latency high** — p99 > 2 s over 5 m → severity: warning
  * [ ] **Queue depth high** — `celery_queue_depth` > 50 → severity: warning
  * [ ] **Service degraded** — any health check value ≠ `ok` → severity: critical
  * [ ] **MinIO bucket large** — bucket > 10 GB → severity: info
  * [ ] **Log backup gap** — `LOG_BACKUP_UPLOADED` absent > 2 h → severity: warning
  * [ ] **Target down** — any `up` metric = 0 (covers all exporters) → severity: critical
* [ ] Telegram message template: alert name + summary annotation + severity + firing time

---

### OBS-5 — Continuous Profiling

Depends on: OBS-0, OBS-4

#### Pyroscope SDK integration
* [ ] `pyroscope-io` added to `pyproject.toml` dependencies
* [ ] `app/main.py` — `pyroscope.configure(app_name="melo.api", server_address=PYROSCOPE_SERVER_URL, tags={"env": APP_ENV})` at startup
* [ ] `app/workers/celery_app.py` — same config with `app_name="melo.worker"`
* [ ] Always-on (no sampling); wall-clock + CPU profiling

#### Grafana Pyroscope plugin
* [ ] Pyroscope datasource panel embedded in system dashboard (OBS-4 already planned)
* [ ] Flame graph accessible from system dashboard without leaving Grafana

---

### OBS-6 — Streamlit Admin Dashboard

Depends on: OBS-0, OBS-4

#### `admin/auth.py` — session password check
* [ ] `is_authenticated() -> bool` — checks `st.session_state["authenticated"]`
* [ ] `login_page()` — renders password input; on submit: compare against `ADMIN_PASSWORD` env var; set session on match
* [ ] Wrong password → error message, session stays unauthenticated

#### `admin/app.py` — entry point
* [ ] `is_authenticated()` guard on every load; redirect to login page if false
* [ ] Sidebar: page nav + external tool links (each opens new tab)
* [ ] External links: Grafana `:3001`, Prometheus `:9090`, MinIO Console `:9001`, Adminer `:8080`, Flower `:5555`

#### `admin/pages/overview.py`
* [ ] `GET /health` → live status badges per service (DB / Redis / MinIO)
* [ ] Key Prometheus metrics: `songs_by_status_total`, `celery_queue_depth`, active streams

#### `admin/pages/songs.py`
* [ ] `GET /songs` → song table with status breakdown
* [ ] Failed songs: [Re-queue] button → `POST /songs` with same url + params
* [ ] Status filter dropdown

#### `admin/pages/logs.py`
* [ ] Loki `/loki/api/v1/query_range` — tail recent log lines
* [ ] Filter by `service` label (api / worker)
* [ ] Filter by `level` label
* [ ] Renders as scrollable table: timestamp, level, event, trace_id, message

#### `admin/pages/metrics.py`
* [ ] Free-form Prometheus query input
* [ ] Prometheus `/api/v1/query` → result table
* [ ] Preset query buttons: queue depth, error rate, p99 latency

#### `admin/pages/alerts.py`
* [ ] Grafana Alerts API → list active alerts
* [ ] Table: alert name, severity, state, firing since
* [ ] Red badge on sidebar nav if any critical alert firing

#### `admin/pages/db_health.py`
* [ ] Prometheus queries on `postgres-exporter` metrics: connection count, query latency, dead tuples
* [ ] Prometheus queries on `redis-exporter` metrics: memory, hit/miss ratio, connected clients, evicted keys
* [ ] Renders as two side-by-side metric tables

#### `admin/Dockerfile`
* [ ] `FROM python:3.12-slim`
* [ ] `pip install streamlit` + deps from `requirements.txt`
* [ ] `CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]`

#### TDD slices
* [ ] `is_authenticated()` returns `False` when session key absent (unit — mock `st.session_state`)
* [ ] `login_page()` sets session `authenticated=True` on correct password (unit — mock env + session)
* [ ] `login_page()` leaves session unauthenticated on wrong password (unit)

---

### OBS-7 — Tests & Smoke

Depends on: OBS-1 through OBS-6

#### Unit tests (`tests/unit/`)
* [ ] `test_log_events.py` — `LogEvent` enum has all expected members
* [ ] `test_logging.py` — every log line emits `trace_id`; file output valid JSONL; required fields present
* [ ] `test_log_manager.py` — roll on size; roll on age; `.gz` produced; MinIO upload called with correct path; cleanup deletes old objects, preserves recent
* [ ] `test_tracing.py` — `extract_trace_id()` returns `"unknown"` with no span; Celery headers contain `traceparent`
* [ ] `test_admin_auth.py` — correct/wrong password behavior

#### Integration tests (`tests/integration/`)
* [ ] `test_metrics_api.py` — `GET /metrics` returns 200 + contains `songs_submitted_total`; counter increments on `POST /songs`
* [ ] `test_tracing_api.py` — `X-Trace-Id` header present on every response; value is non-empty hex string

#### Smoke test additions (`tests/smoke_test.sh`)
* [ ] S25: `GET /metrics` returns 200
* [ ] S26: Response has `X-Trace-Id` header

#### Coverage
* [ ] Maintain ≥ 80% (currently 94.77%); new modules included in coverage report

---

## New Makefile Targets

```makefile
grafana:    ## Open Grafana in browser
flower:     ## Open Flower in browser
admin:      ## Open Streamlit admin in browser
metrics:    ## Curl /metrics endpoint
alerts:     ## List active Grafana alerts via API
logs-loki:  ## Tail recent logs via Loki HTTP API
log-rotate: ## Manually trigger log rotation in worker container
```

---

## New Ports

| Service           | URL                               |
| ----------------- | --------------------------------- |
| Grafana           | http://localhost:3001             |
| Prometheus        | http://localhost:9090             |
| Loki              | http://localhost:3100             |
| Tempo             | http://localhost:4317 (OTLP gRPC) |
| Pyroscope         | http://localhost:4040             |
| Flower            | http://localhost:5555             |
| cAdvisor          | http://localhost:8090             |
| Node Exporter     | http://localhost:9100             |
| Postgres Exporter | http://localhost:9187             |
| Redis Exporter    | http://localhost:9121             |
| Streamlit admin   | http://localhost:8501             |

---

## Definition of Done

* [ ] `docker compose up` starts all 13 new services cleanly — no manual steps
* [ ] `GET /metrics` returns 200 and contains all custom metric names
* [ ] Every API response carries `X-Trace-Id` header
* [ ] Trace visible in Grafana Tempo with child spans from download, FFmpeg, MinIO
* [ ] Log lines in JSONL file have `trace_id` field matching Tempo trace
* [ ] Grafana dashboards load from provisioning — no manual import
* [ ] Telegram alert fires when a test rule triggers
* [ ] Pyroscope flame graph visible in Grafana system dashboard
* [ ] Streamlit admin: login works; all 6 pages render live data
* [ ] Log rotation: roll triggers on size, `.gz` appears in MinIO `melo-log-backups/`
* [ ] Smoke tests S25–S26 pass
* [ ] Coverage stays ≥ 80%
* [ ] `README.md` updated: new ports table, new `make` targets, observability section

---

## Clean Code Contract

Per the clean-code skill, all new Python modules must:

- Single responsibility: `log_manager.py` rotates, `logging.py` configures, `metrics.py` defines, `tracing.py` instruments
- Intention-revealing names: `extract_trace_id` not `get_id`, `configure_logging` not `setup`, `roll_log_file` not `rotate`
- Functions under 20 lines; extract named helpers for on-roll sequence steps
- No metric name defined outside `app/core/metrics.py`
- No raw string log event names — only `LogEvent` enum members
- `LogEvent` enum docstrings on every member

---

## Decision Log

| Decision                                            | Reason                                                                                        |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Grafana Alertmanager over standalone                | Built-in Grafana 10+; zero extra service; YAML-provisioned contact point; sufficient for solo |
| Promtail scrapes JSONL file (not Docker log driver) | Structured label extraction from JSON fields; decouples log format from transport             |
| Gzip + upload on roll (not batch)                   | Minimises local disk; no cron; simpler failure model                                          |
| APScheduler cleanup inside API process              | No extra container; survives restart; consistent with existing app lifecycle                  |
| stdout stays ConsoleRenderer (string)               | Human-readable in `docker compose logs`; Loki scrapes file, not stdout                        |
| `trace_id` in every log line                        | Grafana log ↔ trace correlation without leaving UI                                            |
| Pyroscope continuous, always-on                     | Catches intermittent spikes; negligible overhead at this scale                                |
| Streamlit password from env                         | Solo user; simplest secure option; consistent with `APP_ENV`-driven config pattern            |
| `X-Trace-Id` on every response                      | Browser-side debugging without opening Grafana                                                |
| Single `metrics.py` module                          | All definitions in one place; prevents duplicate Prometheus registration errors               |
| cAdvisor + Node Exporter added                      | Standard Prometheus stack; zero code change; container + host visibility                      |
| Postgres + Redis exporters added                    | DB and broker health with zero Melo code change                                               |
| MinIO native metrics scrape + bearer token          | Free telemetry already exposed; just needs scrape config                                      |
| `TargetDown` alert covers all exporters             | One rule catches any silent exporter; `up` metric is universal                                |
| Grafana named volume                                | Dashboard + alert state survives container wipe                                               |
| Tempo 72h retention                                 | Adequate for recent debugging; controls disk on self-hosted                                   |
| Pyroscope 7d retention                              | Sufficient for trend analysis; low disk footprint                                             |
| `GET /health` log suppression at 200                | Grafana datasource probes every 10s × all datasources = Loki flood without this               |
| Streamlit `db_health.py` page                       | Postgres + Redis exporter stats complete admin coverage                                       |
| `depends_on` health checks                          | Prevents Grafana boot-before-backends race; all datasource probes succeed on first load       |
| `CELERY_SEND_EVENTS=True` explicit in env           | `celery-exporter` emits zero metrics without it; easy to miss                                 |
| Sensitive env vars in `.env.staging` (gitignored)   | `GRAFANA_ADMIN_PASSWORD`, `TELEGRAM_BOT_TOKEN`, `ADMIN_PASSWORD` never committed              |
