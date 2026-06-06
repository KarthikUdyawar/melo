# Melo Sprint 5 — OBS-0 Handoff

## Skills
`/caveman ultra` `/clean-code` `/tdd`

## Context
- Repo: `KarthikUdyawar/melo`, branch `feature/observability-stack`
- Sprint 5 spec: `docs/sprints/Sprint-5.md`, PRD: `docs/PRD.md`
- OBS-0 only ticket in progress — OBS-1 through OBS-7 not started

## What OBS-0 Is
Docker Compose infra for full obs stack: Prometheus, Loki, Promtail, Tempo, Grafana, Pyroscope, Celery-exporter, Flower, cAdvisor, Node-exporter, Postgres-exporter, Redis-exporter. Separate from main `docker-compose.yml`. Lives in `infra/docker-compose.monitoring.yml`. Started via `make monitoring-up` → `infra/monitoring.sh`.

## Current Repo State

```
infra/
  docker-compose.monitoring.yml   ✓
  monitoring.sh                   ✓
  setup-infra.sh                  ✓
  loki/loki.yml                   ✓
  prometheus/prometheus.yml       ✓
  prometheus/minio_token          ✓ (ASCII text, token present)
  promtail/promtail.yml           ✓
  tempo/tempo.yml                 ✓
  pyroscope/pyroscope.yml         ✓
  grafana/provisioning/
    datasources/all.yml           ✓
    dashboards/all.yml            ✓
    alerting/                     ✓ empty dir
```

## Blocker — Prometheus Bind-Mount (WSL2 Docker Desktop Bug)

**Error:**
```
error mounting ".../Ubuntu/4029166f..." to "/etc/prometheus/prometheus.yml":
cannot create subdirectories in overlay2/merged/etc/prometheus/prometheus.yml: not a directory
```

**Cause:** First attempt to mount `prometheus.yml` failed (file didn't exist yet) → Docker created a **directory** at that overlay2 path → stale layer persists in container image across rm/recreate. Hash `4029166f` appears every attempt — same corrupted layer reused.

**Tried:** `docker rm -f`, `docker volume rm`, `sudo rm -rf infra/infra/` (Docker had created root-owned nested dirs). All config files confirmed correct on host.

**Not tried yet — likely fix:**
```bash
make monitoring-down
docker system prune -f        # clears dangling layers
# If still fails, restart Docker Desktop from system tray
make monitoring-up
```

Nuclear option: `docker system prune -f --volumes` (loses all unused volumes incl. app data — do `make down` first).

## Fixes Applied This Session
- Loki: `path_prefix: /loki`, volume `loki_data:/loki` (was `/tmp/loki` → permission denied)
- Tempo: removed invalid `ingester:` / `compactor:` top-level fields (Tempo v2 schema)
- postgres-exporter image: `prometheuscommunity/postgres-exporter` (prom/ moved)
- minio_token: generated via `minio/mc` throwaway container, `MC_HOST_local` env var, bash-only YAML parse (no grep/awk — distroless image)
- `infra/infra/` nested dirs: Docker created root-owned dirs from failed mounts → `sudo rm -rf`

## Orphan Warning
Both composes share `--project-name melo` → cosmetic orphan warning. Add `--remove-orphans` to `cmd_up` in `monitoring.sh` if annoying.

## After OBS-0 — Next Tickets
OBS-1 (logging) + OBS-2 (metrics) parallel. OBS-3 needs OBS-1. OBS-4 needs all three. OBS-5+6 after OBS-4.
