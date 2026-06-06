# Melo — Sprint 5: Observability & Monitoring

**Owner:** Karthik | **Repo:** `melo` | **Sprint:** 5 | **Timeline:** 1 week (solo)
**Stack additions:** Prometheus · Loki · Promtail · Tempo · Grafana · Pyroscope · Flower · Streamlit · OpenTelemetry · APScheduler · cAdvisor · Node Exporter · Postgres Exporter · Redis Exporter

---

## Problem

Melo has zero runtime visibility. Stuck song in `processing`, silent Celery retry, degraded MinIO — no signal. Debugging = `docker compose logs` + guesswork. Sprint 5 ships full three-pillar observability (logs, metrics, traces) + continuous profiling + Telegram alerting + Streamlit admin — all provisioned as code, all starting with `docker compose up`.

---

## Goal

> *Know what broke, when, and why — without touching the terminal.*

---

## Scope

### ✅ In

| Feature                      | Details                                                                         |
| ---------------------------- | ------------------------------------------------------------------------------- |
| Structured logging           | structlog dual renderer: string → stdout, JSONL → file                          |
| Log rotation                 | Size (10 MB) OR age (24 h), whichever first                                     |
| Log backup                   | Gzip on roll → upload MinIO `melo-log-backups/` immediately                     |
| Log retention                | APScheduler daily job: delete backups > 90 days                                 |
| Metrics                      | Prometheus: HTTP auto-instrumentation + custom counters/gauges/histograms       |
| Postgres metrics             | `postgres-exporter`: connection count, query latency, table bloat, locks        |
| Redis metrics                | `redis-exporter`: memory, hit/miss, client count, evicted keys, command latency |
| MinIO metrics                | Native `/minio/v1/metrics` scrape target with bearer token auth                 |
| Distributed tracing          | OTEL auto + manual spans → Tempo; `trace_id` in every log line                  |
| `X-Trace-Id` header          | Every API response carries active trace ID                                      |
| Celery event stream          | `CELERY_SEND_EVENTS=True` + `CELERY_TASK_TRACK_STARTED=True` in worker          |
| Profiling                    | Pyroscope continuous profiling on FastAPI + Celery worker                       |
| Grafana dashboards           | 3 dashboards provisioned as YAML/JSON                                           |
| Alerting                     | Grafana Alertmanager → Telegram bot (provisioned as YAML)                       |
| Celery monitor               | Flower at `:5555`, no auth                                                      |
| Admin dashboard              | Streamlit at `:8501`, single password from env                                  |
| Log coverage                 | `LogEvent` enum — every request, task state, service op, rotation event         |
| Health log noise suppression | Skip `REQUEST_STARTED`/`REQUEST_FINISHED` for `GET /health` if status = 200     |

### ❌ Out

Multi-user auth on admin, custom Alertmanager service, external SaaS log shipping, mobile Streamlit layout, SLO/error-budget tracking.

---

## Services

| Service             | Image                         | Port             | Purpose                                            |
| ------------------- | ----------------------------- | ---------------- | -------------------------------------------------- |
| `prometheus`        | `prom/prometheus`             | 9090             | Scrape all targets                                 |
| `loki`              | `grafana/loki`                | 3100             | Log aggregation                                    |
| `promtail`          | `grafana/promtail`            | —                | Scrape JSONL from shared log volume                |
| `tempo`             | `grafana/tempo`               | 4317 (OTLP gRPC) | Trace backend (72h retention)                      |
| `grafana`           | `grafana/grafana`             | 3001             | Dashboards + Alertmanager (named volume for state) |
| `pyroscope`         | `grafana/pyroscope`           | 4040             | Continuous profiling (7d retention)                |
| `celery-exporter`   | `danihodovic/celery-exporter` | 9808             | Celery → Prometheus metrics                        |
| `flower`            | `mher/flower`                 | 5555             | Celery task monitor, no auth                       |
| `cadvisor`          | `gcr.io/cadvisor/cadvisor`    | 8090             | Container CPU/mem/net/disk                         |
| `node-exporter`     | `prom/node-exporter`          | 9100             | Host OS metrics                                    |
| `postgres-exporter` | `prom/postgres-exporter`      | 9187             | PostgreSQL internals                               |
| `redis-exporter`    | `oliver006/redis_exporter`    | 9121             | Redis health + broker stats                        |
| `admin`             | custom (Streamlit)            | 8501             | Admin dashboard                                    |

All added to `docker-compose.yml`. Zero breaking changes to existing services.

> **Note — Node Exporter on Docker Desktop (Mac/Windows):** reports VM metrics, not host machine. Accurate on Linux only.

---

## Infra Config Notes

### `depends_on` health checks

Grafana, Promtail, Pyroscope need backends ready before start. Add `depends_on` with `condition: service_healthy` for all infra services in `docker-compose.yml`. Without this, datasource probes fail on first Grafana load.

### Grafana state persistence

Pin `GF_DATABASE_PATH` to named volume. Container wipe → dashboards survive. Sufficient for self-hosted.

### Celery exporter prerequisites

Worker config must have:

```
CELERY_SEND_EVENTS=True
CELERY_TASK_TRACK_STARTED=True
```

Without these, `celery-exporter` emits no metrics.

### MinIO metrics auth

MinIO native endpoint `/minio/v1/metrics` requires bearer token. Add dedicated Prometheus scrape job with `bearer_token` from MinIO env. Free disk usage, object count, API latency, error rate, S3 op counters.

### Retention

| Service           | Retention                         |
| ----------------- | --------------------------------- |
| Tempo             | 72 h (explicit in `tempo.yml`)    |
| Pyroscope         | 7 d (explicit in `pyroscope.yml`) |
| MinIO log backups | 90 d (APScheduler cleanup job)    |

---

## Log Strategy

### Dual renderer

```
stdout  → ConsoleRenderer   (human-readable string, dev-friendly)
file    → JSONRenderer      (/var/log/melo/<service>.jsonl, one JSON object per line)
```

Both share same structlog processor chain. `trace_id` injected from OTEL context into every record via middleware — present on both outputs.

### Rotation trigger

Roll when `file_size >= LOG_MAX_SIZE_MB` **OR** `file_age_hours >= LOG_MAX_AGE_HOURS` (background thread checks every 60 s).

### On-roll sequence

```
1. Close current file handle
2. Rename  → <service>.<ISO-timestamp>.jsonl
3. Gzip    → <service>.<ISO-timestamp>.jsonl.gz  (in-process, no shell)
4. Upload  → MinIO  melo-log-backups/<service>/<YYYY>/<MM>/<filename>.gz
5. Delete  local .gz
6. Open    fresh <service>.jsonl
7. Log     LogEvent.LOG_ROTATED + LogEvent.LOG_BACKUP_UPLOADED
```

### Retention cleanup

APScheduler daily at 02:00: list `melo-log-backups/`, delete objects older than `LOG_RETENTION_DAYS`. Emit `LogEvent.LOG_BACKUP_CLEANED` with deleted count.

### Health endpoint noise

Middleware: skip `REQUEST_STARTED`/`REQUEST_FINISHED` for `GET /health` when status = 200. Prevents Grafana datasource probes (every 10 s) from flooding Loki.

### `LogEvent` enum (`app/core/log_events.py`)

No raw string event names anywhere. Single source of truth.

```
Request:     REQUEST_STARTED, REQUEST_FINISHED, REQUEST_FAILED
Song API:    SONG_SUBMITTED, SONG_NOT_FOUND, SONG_DELETED,
             SONG_STREAM_STARTED, SONG_STREAM_FAILED,
             PREVIEW_FETCHED, PREVIEW_FAILED
Worker:      TASK_RECEIVED, TASK_PROCESSING, TASK_DONE,
             TASK_FAILED, TASK_RETRY
Download:    DOWNLOAD_STARTED, DOWNLOAD_DONE, DOWNLOAD_FAILED
FFmpeg:      FFMPEG_TRIM_STARTED, FFMPEG_TRIM_DONE,
             FFMPEG_SPEED_STARTED, FFMPEG_SPEED_DONE, FFMPEG_FAILED
Storage:     MINIO_UPLOAD_STARTED, MINIO_UPLOAD_DONE, MINIO_UPLOAD_FAILED,
             MINIO_STREAM_STARTED, MINIO_STREAM_FAILED
Log:         LOG_ROTATED, LOG_COMPRESSED, LOG_BACKUP_UPLOADED, LOG_BACKUP_CLEANED
Favorites:   FAVORITE_ADDED, FAVORITE_REMOVED
Playlists:   PLAYLIST_CREATED, PLAYLIST_DELETED,
             PLAYLIST_SONG_ADDED, PLAYLIST_SONG_REMOVED
Health:      HEALTH_CHECKED, HEALTH_DEGRADED
```

---

## Metrics

### HTTP auto (`prometheus_fastapi_instrumentator`)

Request count, latency histogram (p50/p95/p99), error rate — labelled by endpoint + method.

### Custom metrics (`app/core/metrics.py`)

All metric definitions live here. No metric name defined outside this file.

```
Counters
  songs_submitted_total
  songs_completed_total          labels: status=done|failed
  favorites_toggled_total        labels: action=add|remove
  playlist_ops_total             labels: action=create|delete|add_song|remove_song

Gauges  (polled every 30 s)
  celery_queue_depth
  celery_active_tasks
  minio_bucket_size_bytes
  songs_by_status_total          labels: status=pending|processing|done|failed

Histograms
  download_duration_seconds
  ffmpeg_duration_seconds        labels: op=trim|speed|trim_speed
  minio_upload_duration_seconds
  stream_duration_seconds
```

Celery task metrics (success/failure rate, runtime, queue depth) → `celery-exporter` sidecar, zero worker code changes.

PostgreSQL internals → `postgres-exporter`.
Redis health + broker stats → `redis-exporter`.
Container CPU/mem/net/disk → `cadvisor`.
Host OS → `node-exporter`.

---

## Distributed Tracing

### Auto-instrumented at startup

`FastAPIInstrumentor`, `SQLAlchemyInstrumentor`, `HTTPXClientInstrumentor`, `RedisInstrumentor` — zero per-endpoint code.

### Manual spans

```python
# services/downloader.py
with tracer.start_as_current_span("download_audio"):
    span.set_attribute("song.id", ...)
    span.set_attribute("youtube.id", ...)

# services/processor.py
with tracer.start_as_current_span("ffmpeg.trim"): ...
with tracer.start_as_current_span("ffmpeg.speed"): ...

# services/storage.py
with tracer.start_as_current_span("minio.upload"): ...
```

### Celery context propagation

`traceparent` baggage serialised into Celery task headers at enqueue. Worker reconstructs OTEL context on task receive → child spans appear in same trace as originating HTTP request.

### `X-Trace-Id` response header

Middleware extracts `trace_id` from active OTEL span → injects `X-Trace-Id` on every response. Same ID in log lines + Tempo → log ↔ trace correlation in Grafana without leaving UI.

---

## Grafana Dashboards

All dashboards + datasources provisioned via `infra/grafana/provisioning/`. No manual clicking after `docker compose up`.

### Dashboard 1 — API Health

Request rate, error rate, p50/p95/p99 latency by endpoint, active streams, top 5 slowest endpoints, `X-Trace-Id` drill-through to Tempo.

### Dashboard 2 — Celery Pipeline

Songs submitted/done/failed rate, queue depth over time, task duration percentiles, download duration, FFmpeg duration, MinIO upload duration, stuck task count (processing > 10 m).

### Dashboard 3 — System

Container CPU + memory (cAdvisor), host OS metrics (node-exporter), PostgreSQL stats (postgres-exporter), Redis stats (redis-exporter), MinIO bucket size + API latency, log backup count + age, Pyroscope flame graph embed.

---

## Alerting

All rules provisioned via `infra/grafana/provisioning/alerting/`. Contact point: Telegram bot (env vars).

| Rule                  | Condition                                  | Severity |
| --------------------- | ------------------------------------------ | -------- |
| Task failed storm     | ≥ 3 failures in 5 m                        | critical |
| Song stuck processing | Any song in `processing` > 10 m            | warning  |
| API latency high      | p99 > 2 s over 5 m                         | warning  |
| Queue depth high      | `celery_queue_depth` > 50                  | warning  |
| Service degraded      | Any health check ≠ `ok`                    | critical |
| MinIO bucket large    | Bucket > 10 GB                             | info     |
| Log backup gap        | `LOG_BACKUP_UPLOADED` absent > 2 h         | warning  |
| Target down           | Any `up` metric = 0 (covers all exporters) | critical |

Telegram message: alert name, summary annotation, severity, firing time.

---

## Profiling

`pyroscope-io` SDK at startup in `app/main.py` (FastAPI) + `app/workers/celery_app.py` (Celery). Continuous wall-clock + CPU. Flame graphs via Grafana Pyroscope datasource plugin. Always-on, no sampling.

Labels: `app=melo.api` / `app=melo.worker`, `env=$APP_ENV`.

---

## Streamlit Admin Dashboard

### Auth

`ADMIN_PASSWORD` env var. `st.session_state` guards every page. Wrong password → login redirect.

### Pages

| Page      | Data source                                                        |
| --------- | ------------------------------------------------------------------ |
| Overview  | Melo `GET /health` + key Prometheus queries                        |
| Songs     | Melo `GET /songs` — status breakdown, re-queue failed              |
| Logs      | Loki `/loki/api/v1/query_range` — tail recent lines                |
| Metrics   | Prometheus `/api/v1/query` — live query results                    |
| Alerts    | Grafana Alerts API — active alerts                                 |
| DB Health | Prometheus queries on `postgres-exporter` + `redis-exporter` stats |

### External links (sidebar, open new tab)

```
Grafana        http://localhost:3001
Prometheus     http://localhost:9090
MinIO Console  http://localhost:9001
Adminer        http://localhost:8080
Flower         http://localhost:5555
```

All live data via HTTP APIs. No iframe embeds.

---

## Security Notes

`GRAFANA_ADMIN_PASSWORD`, `TELEGRAM_BOT_TOKEN`, `ADMIN_PASSWORD` go in `.env.staging` (gitignored). Never committed. Consistent with existing `APP_ENV`-driven config pattern.

---

## Folder Structure (additions only)

```
melo/
├── infra/
│   ├── prometheus/
│   │   └── prometheus.yml          # scrape targets: api, celery-exporter, cadvisor,
│   │                               #   node-exporter, postgres-exporter, redis-exporter,
│   │                               #   minio (bearer token)
│   ├── loki/
│   │   └── loki.yml
│   ├── promtail/
│   │   └── promtail.yml
│   ├── tempo/
│   │   └── tempo.yml               # retention_period: 72h
│   ├── pyroscope/
│   │   └── pyroscope.yml           # retention: 7d
│   └── grafana/
│       └── provisioning/
│           ├── datasources/
│           │   └── all.yml         # Loki, Prometheus, Tempo, Pyroscope
│           ├── dashboards/
│           │   ├── all.yml
│           │   ├── api.json
│           │   ├── pipeline.json
│           │   └── system.json
│           └── alerting/
│               ├── rules.yml       # all alert rules
│               └── telegram.yml    # contact point + notification policy
├── admin/
│   ├── app.py                      # entry + login gate + sidebar
│   ├── auth.py                     # session password check
│   ├── pages/
│   │   ├── overview.py
│   │   ├── songs.py
│   │   ├── logs.py
│   │   ├── metrics.py
│   │   ├── alerts.py
│   │   └── db_health.py            # postgres + redis exporter stats
│   ├── Dockerfile
│   └── requirements.txt
└── app/
    └── core/
        ├── log_events.py           # LogEvent enum
        ├── log_manager.py          # rotation + gzip + MinIO upload + cleanup
        ├── logging.py              # dual renderer (rewrite)
        ├── metrics.py              # all Prometheus metric definitions
        └── tracing.py              # OTEL setup + X-Trace-Id middleware
```

---

## New Env Vars

```bash
# Grafana
GRAFANA_ADMIN_PASSWORD=admin

# Telegram alerts
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Streamlit
ADMIN_PASSWORD=

# Log rotation
LOG_MAX_SIZE_MB=10
LOG_MAX_AGE_HOURS=24
LOG_BACKUP_BUCKET=melo-log-backups
LOG_RETENTION_DAYS=90

# Pyroscope
PYROSCOPE_SERVER_URL=http://pyroscope:4040

# Celery (add to worker)
CELERY_SEND_EVENTS=True
CELERY_TASK_TRACK_STARTED=True
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

## New Makefile Targets

| Target            | Description                                       |
| ----------------- | ------------------------------------------------- |
| `make grafana`    | Open Grafana in browser                           |
| `make flower`     | Open Flower in browser                            |
| `make admin`      | Open Streamlit admin in browser                   |
| `make metrics`    | Curl `/metrics` endpoint                          |
| `make alerts`     | List active Grafana alerts via API                |
| `make logs-loki`  | Tail recent logs via Loki HTTP API                |
| `make log-rotate` | Manually trigger log rotation in worker container |

---

## Ticket Breakdown

| Ticket | Description                                                                                                                                         | Depends on          |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| OBS-0  | Docker Compose infra: all new services, volumes, configs, `depends_on` health checks, named Grafana volume, retention configs, `CELERY_SEND_EVENTS` | —                   |
| OBS-1  | Structured logging: dual renderer, `LogEvent` enum, full coverage, rotation + gzip + MinIO backup, APScheduler cleanup, health log suppression      | OBS-0               |
| OBS-2  | Metrics: `prometheus_fastapi_instrumentator` + custom metrics, MinIO bearer token scrape                                                            | OBS-0               |
| OBS-3  | Tracing: OTEL setup, auto + manual spans, Celery propagation, `X-Trace-Id` header, `trace_id` in logs                                               | OBS-0, OBS-1        |
| OBS-4  | Grafana: 3 dashboards + Alertmanager → Telegram + `TargetDown` alert rule (all provisioned as YAML)                                                 | OBS-1, OBS-2, OBS-3 |
| OBS-5  | Profiling: Pyroscope SDK in FastAPI + Celery, Grafana plugin                                                                                        | OBS-0, OBS-4        |
| OBS-6  | Streamlit admin: login, 6 pages, live data from all APIs, tool links, DB health page                                                                | OBS-0, OBS-4        |
| OBS-7  | Tests: log shape, metric counters, trace context, `X-Trace-Id`, smoke `/metrics`, Streamlit auth                                                    | all above           |

OBS-1, OBS-2 parallel after OBS-0. OBS-3 needs OBS-1. OBS-4 needs all three. OBS-5, OBS-6 parallel after OBS-4.

---

## Tests

TDD: one behavior per red-green cycle.

| Behavior                                                               | Type        |
| ---------------------------------------------------------------------- | ----------- |
| Every log line emits `trace_id` field                                  | Unit        |
| File output valid JSONL (one object per line, required fields present) | Unit        |
| Roll triggers when file size ≥ 10 MB                                   | Unit        |
| Roll triggers when file age ≥ 24 h                                     | Unit        |
| Rolled file compressed to `.gz`                                        | Unit        |
| MinIO upload called on roll with correct bucket path                   | Unit        |
| Cleanup deletes objects > 90 d, preserves newer                        | Unit        |
| `GET /health` logs suppressed when status = 200                        | Unit        |
| `songs_submitted_total` increments on `POST /songs`                    | Integration |
| `X-Trace-Id` header present on every API response                      | Integration |
| `GET /metrics` returns 200 + contains `songs_submitted_total`          | Integration |
| Celery task headers contain `traceparent` baggage                      | Unit        |
| Streamlit login rejects wrong password                                 | Unit        |
| Streamlit login accepts correct password from env                      | Unit        |

Coverage target: maintain ≥ 80% (currently 94.77%).

---

## Quality Constraints

- All infra config provisioned as code — zero manual steps after `docker compose up`
- `LogEvent` enum = single source of truth for event names — no raw strings in log calls
- No metric name defined outside `app/core/metrics.py`
- OTEL instrumentation applied at startup — no per-endpoint decoration
- Grafana dashboards checked into `infra/` — reproducible from scratch
- Sensitive env vars in `.env.staging` (gitignored) — never committed
- Clean Code contract from Sprint 4 extends to all new modules

---

## Decision Log

| Decision                                        | Reason                                                                              |
| ----------------------------------------------- | ----------------------------------------------------------------------------------- |
| Grafana Alertmanager over standalone            | Built-in to Grafana 10+; zero extra service; YAML-provisioned; sufficient for solo  |
| Promtail scrapes JSONL file (not Docker driver) | Label extraction from structured JSON; decouples format from transport              |
| Gzip + upload on roll (not batch)               | Minimises local disk; no cron; simpler failure model                                |
| APScheduler for cleanup (not cron container)    | Runs inside existing API process; no extra service; survives container restart      |
| stdout stays string format                      | Human-readable in `docker compose logs`; Loki scrapes file not stdout               |
| `trace_id` in log lines                         | Grafana log ↔ trace correlation without leaving UI                                  |
| Pyroscope continuous (not on-demand)            | Catches intermittent CPU spikes; low overhead at this scale                         |
| Streamlit password in env (not DB)              | Solo user; simplest; consistent with existing env-driven config                     |
| `X-Trace-Id` in every response                  | Browser-side debugging without opening Grafana                                      |
| Single `metrics.py` module                      | All definitions in one place; prevents duplicate registration errors                |
| cAdvisor + Node Exporter added                  | Standard Prometheus stack; container + host visibility; zero code change            |
| Postgres + Redis exporters added                | DB + broker visibility; no Melo code change required                                |
| MinIO native metrics scrape                     | Free data already exposed; just needs bearer token scrape job                       |
| `TargetDown` alert covers all exporters         | One rule; catches any silent exporter failure                                       |
| Grafana named volume                            | Survives container wipe; dashboards + alert state preserved                         |
| Tempo 72h retention                             | Adequate for debugging recent issues; controls disk on self-hosted                  |
| Pyroscope 7d retention                          | Sufficient for trend analysis; low disk footprint                                   |
| Health log suppression                          | Prevents 10s Grafana probe × all datasources from flooding Loki                     |
| Streamlit DB health page added                  | Postgres + Redis exporter stats directly queryable; completes admin coverage        |
| `depends_on` health checks                      | Prevents Grafana boot-before-backends race; datasource probes succeed on first load |
| `CELERY_SEND_EVENTS=True` explicit              | `celery-exporter` emits nothing without it; easy to miss                            |
