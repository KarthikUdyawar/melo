# Melo — Infrastructure

> Verified against `docker-compose.yml`, `infra/docker-compose.monitoring.yml`, `Makefile`, `app/core/config.py`.

---

## Compose Files

Two separate Compose files, sharing a network and a volume:

| File                                  | Contents                                                                                                                                                                                                     |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docker-compose.yml`                  | Core app: `ui`, `api`, `worker`, `postgres`, `redis`, `minio`, `adminer`                                                                                                                                     |
| `infra/docker-compose.monitoring.yml` | Observability stack: `prometheus`, `loki`, `promtail`, `tempo`, `grafana`, `pyroscope`, `celery-exporter`, `flower`, `cadvisor`, `node-exporter`, `postgres-exporter`, `redis-exporter`, `admin` (Streamlit) |

The monitoring compose references the main compose's network and log volume as external:
```yaml
networks:
  melo_default:
    external: true
    name: ${COMPOSE_PROJECT_NAME:-melo}_default
volumes:
  melo_melo_logs:
    external: true
    name: ${COMPOSE_PROJECT_NAME:-melo}_melo_logs
```
Started independently via `make monitoring-up` (app must already be running) or together via `make monitoring-up-all`.

---

## Core Services (`docker-compose.yml`)

| Service    | Image / Build                              | Port(s)    | Health check                                      | Notes                                                                                                |
| ---------- | ------------------------------------------ | ---------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `ui`       | `./ui` (nginx:alpine)                      | 3000→80    | —                                                 | `depends_on: api: service_healthy`                                                                   |
| `api`      | `.` (repo root)                            | 8000       | `curl -f http://localhost:8000/health`            | `uvicorn --reload`; `/tmp/melo` tmpfs; live-reload volume `./app:/app/app`                           |
| `worker`   | `.` (repo root)                            | —          | `celery inspect ping -t 5`                        | `CELERY_SEND_EVENTS=true`, `CELERY_TASK_TRACK_STARTED=true`; same tmpfs + live-reload mount as `api` |
| `postgres` | `postgres:16-alpine`                       | 5432       | `pg_isready`                                      | named volume `postgres_data`                                                                         |
| `redis`    | `redis:7-alpine`                           | 6379       | `redis-cli ping`                                  | named volume `redis_data`                                                                            |
| `minio`    | `minio/minio:RELEASE.2024-05-01T01-11-10Z` | 9000, 9001 | `curl -f http://localhost:9000/minio/health/live` | pinned image tag; named volume `minio_data`                                                          |
| `adminer`  | `adminer:latest`                           | 8080       | —                                                 | `depends_on: postgres: service_healthy`                                                              |

All services `restart: unless-stopped`. `api` and `worker` both depend on `postgres`/`redis`/`minio` being `service_healthy` before starting.

## Monitoring Services (`infra/docker-compose.monitoring.yml`)

| Service             | Port                                         | Health check                                                                                                            |
| ------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `prometheus`        | 9090                                         | `wget http://localhost:9090/-/healthy`                                                                                  |
| `loki`              | 3100                                         | `curl http://localhost:3100/ready` (60s start period)                                                                   |
| `promtail`          | —                                            | none; `depends_on: loki: service_started`                                                                               |
| `tempo`             | 4317 (OTLP gRPC), 4318 (HTTP), 3200 (UI/API) | `curl http://localhost:3200/ready` (60s start period)                                                                   |
| `grafana`           | 3001→3000                                    | `wget http://localhost:3000/api/health`; `depends_on: prometheus: service_healthy, loki/tempo: service_started`         |
| `pyroscope`         | 4040                                         | `curl http://localhost:4040/ready`; runs as `user: root` (named volume ownership)                                       |
| `celery-exporter`   | 9808                                         | —                                                                                                                       |
| `flower`            | 5555                                         | — (no auth)                                                                                                             |
| `cadvisor`          | 8090→8080                                    | — (`privileged: true`, pinned `v0.47.2`)                                                                                |
| `node-exporter`     | 9100                                         | —                                                                                                                       |
| `postgres-exporter` | 9187                                         | —                                                                                                                       |
| `redis-exporter`    | 9121                                         | —                                                                                                                       |
| `admin` (Streamlit) | 8501                                         | — ; requires `ADMIN_PASSWORD` and `GRAFANA_ADMIN_PASSWORD` env vars (fails fast if unset, via `${VAR:?message}` syntax) |

`loki`/`tempo`/`pyroscope` intentionally use `service_started` rather than `service_healthy` as a dependency condition elsewhere — their `/ready` endpoints are slow on WSL2 Docker Desktop (ingester anti-flap) even though the services are functionally ready sooner.

---

## Ports (Full List)

| Service                       | URL                        |
| ----------------------------- | -------------------------- |
| UI                            | http://localhost:3000      |
| API                           | http://localhost:8000      |
| API Docs                      | http://localhost:8000/docs |
| MinIO Console                 | http://localhost:9001      |
| Adminer                       | http://localhost:8080      |
| PostgreSQL                    | localhost:5432             |
| Redis                         | localhost:6379             |
| Grafana                       | http://localhost:3001      |
| Prometheus                    | http://localhost:9090      |
| Loki                          | http://localhost:3100      |
| Tempo (OTLP gRPC / HTTP / UI) | :4317 / :4318 / :3200      |
| Pyroscope                     | http://localhost:4040      |
| Flower                        | http://localhost:5555      |
| cAdvisor                      | http://localhost:8090      |
| Node Exporter                 | http://localhost:9100      |
| Postgres Exporter             | http://localhost:9187      |
| Redis Exporter                | http://localhost:9121      |
| Streamlit admin               | http://localhost:8501      |

---

## Environments (`app/core/config.py`)

Four valid `APP_ENV` values, not three: `development`, `staging`, `production`, `test`. Each maps to `.env.{app_env}`, loaded via `_env_file()` and merged with explicit override priority in `force_env_file_priority` (env-file values win over process env). `get_settings()` is `lru_cache`d; `reset_settings()` clears it for tests.

| Env           | Purpose                                                                                          |
| ------------- | ------------------------------------------------------------------------------------------------ |
| `development` | Local machine, localhost endpoints                                                               |
| `staging`     | Docker Compose, service-name hostnames (used by `docker-compose.yml`'s `env_file: .env.staging`) |
| `production`  | Real infra, `CHANGE_ME` placeholders, `MINIO_SECURE=true` expected (warns if not)                |
| `test`        | Used by the test suite; loads `.env.test`                                                        |

---

## Makefile Targets (selected)

Full list via `make help`. Grouped by area:

**Stack lifecycle:** `up`, `down`, `down-v`, `restart`, `rebuild`, `logs`, `logs-api`, `logs-worker`, `logs-ui`, `ps`, `wait-api`

**Dev shells:** `shell-api`, `shell-worker`, `shell-postgres`

**Dev helpers:** `health`, `songs`, `reset-db`, `seed`, `clean-tmp`

**Backup/restore:** `backup`, `backup-db`, `backup-minio`, `restore-db FILE=...`, `restore-minio FILE=...`

**Quality:** `lint`, `fmt`, `pre-commit-install`, `pre-commit`

**Testing:** `test-up`, `test-down`, `test-unit`, `test-integration`, `test`, `test-cov`, `smoke`, `smoke-ui`

**CI locally (`act`):** `act-lint`, `act-unit`, `act-integration`, `act-coverage`, `act-ci`

**Monitoring:** `monitoring-up`, `monitoring-up-all`, `monitoring-down`, `monitoring-restart`, `monitoring-status`, `grafana`, `flower`, `admin`, `metrics`, `alerts`, `logs-loki`, `log-rotate`

**Misc:** `tree` (`tree --gitignore -I '__pycache__|*.pyc|*.egg-info'` → source for `PROJECT.tree`), `cadvisor-ids` (prints container IDs since cAdvisor can't resolve container names on WSL2 Docker Desktop — see `DECISIONS.md`)

`help` is the `.DEFAULT_GOAL` — running bare `make` lists every target with its `##` comment.
