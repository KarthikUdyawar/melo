#!/usr/bin/env bash
# infra/setup-infra.sh
# Creates all infra/ config files and infra/docker-compose.monitoring.yml.
# Safe to re-run — skips files that already exist.
# Run from repo root: ./infra/setup-infra.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

log()  { echo "[setup-infra] $*"; }

write_file() {
  local path="$1"
  local content="$2"
  mkdir -p "$(dirname "${path}")"
  if [[ -f "${path}" ]]; then
    log "exists — skipping: ${path}"
  else
    printf '%s\n' "${content}" > "${path}"
    log "created: ${path}"
  fi
}

# ── infra/loki/loki.yml ───────────────────────────────────────────────────────
write_file infra/loki/loki.yml \
'auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100

schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: 168h

analytics:
  reporting_enabled: false'

# ── infra/prometheus/prometheus.yml ──────────────────────────────────────────
write_file infra/prometheus/prometheus.yml \
'global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: melo_api
    static_configs:
      - targets: ["api:8000"]

  - job_name: celery_exporter
    static_configs:
      - targets: ["celery-exporter:9808"]

  - job_name: cadvisor
    static_configs:
      - targets: ["cadvisor:8090"]

  - job_name: node_exporter
    static_configs:
      - targets: ["node-exporter:9100"]

  - job_name: postgres_exporter
    static_configs:
      - targets: ["postgres-exporter:9187"]

  - job_name: redis_exporter
    static_configs:
      - targets: ["redis-exporter:9121"]

  - job_name: minio
    metrics_path: /minio/v1/metrics/cluster
    authorization:
      credentials_file: /etc/prometheus/minio_token
    static_configs:
      - targets: ["minio:9000"]'

# ── infra/prometheus/minio_token (placeholder — overwritten by monitoring.sh) -
write_file infra/prometheus/minio_token ''

# ── infra/promtail/promtail.yml ───────────────────────────────────────────────
write_file infra/promtail/promtail.yml \
'server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: melo_logs
    static_configs:
      - targets:
          - localhost
        labels:
          job: melo
          __path__: /var/log/melo/*.jsonl

    pipeline_stages:
      - json:
          expressions:
            level: level
            service: service
            event: event
            trace_id: trace_id

      - labels:
          level:
          service:
          event:
          trace_id:'

# ── infra/tempo/tempo.yml ─────────────────────────────────────────────────────
write_file infra/tempo/tempo.yml \
'stream_over_http_enabled: true

server:
  http_listen_port: 3200
  log_level: info

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318

storage:
  trace:
    backend: local
    local:
      path: /var/tempo/blocks
    wal:
      path: /var/tempo/wal'

# ── infra/pyroscope/pyroscope.yml ─────────────────────────────────────────────
write_file infra/pyroscope/pyroscope.yml \
'server:
  http_listen_port: 4040

storage:
  backend: filesystem
  filesystem:
    dir: /var/lib/pyroscope

limits:
  max_query_lookback: 168h'

# ── infra/grafana/provisioning/datasources/all.yml ────────────────────────────
write_file infra/grafana/provisioning/datasources/all.yml \
'apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    uid: prometheus
    url: http://prometheus:9090
    access: proxy
    isDefault: true
    jsonData:
      timeInterval: 15s

  - name: Loki
    type: loki
    uid: loki
    url: http://loki:3100
    access: proxy
    jsonData:
      derivedFields:
        - datasourceUid: tempo
          matcherRegex: "\"trace_id\":\"([a-f0-9]+)\""
          name: TraceID
          url: "${__value.raw}"

  - name: Tempo
    type: tempo
    uid: tempo
    url: http://tempo:3200
    access: proxy
    jsonData:
      tracesToLogsV2:
        datasourceUid: loki
        filterByTraceID: true
        customQuery: true
        query: "{service=\"${__span.tags.service.name}\"} | json | trace_id=\"${__trace.traceId}\""
      serviceMap:
        datasourceUid: prometheus

  - name: Pyroscope
    type: grafana-pyroscope-datasource
    uid: pyroscope
    url: http://pyroscope:4040
    access: proxy'

# ── infra/grafana/provisioning/dashboards/all.yml ─────────────────────────────
write_file infra/grafana/provisioning/dashboards/all.yml \
'apiVersion: 1

providers:
  - name: melo
    orgId: 1
    folder: Melo
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
      foldersFromFilesStructure: false'

# ── infra/grafana/provisioning/alerting/ (empty dir, filled in OBS-4) ─────────
mkdir -p infra/grafana/provisioning/alerting
log "ensured: infra/grafana/provisioning/alerting/"

# ── infra/docker-compose.monitoring.yml ──────────────────────────────────────
write_file infra/docker-compose.monitoring.yml \
'services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./prometheus/minio_token:/etc/prometheus/minio_token:ro
      - prometheus_data:/prometheus
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.retention.time=15d
      - --web.enable-lifecycle
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:9090/-/healthy"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - melo_default

  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - ./loki/loki.yml:/etc/loki/loki.yml:ro
      - loki_data:/loki
    command: -config.file=/etc/loki/loki.yml
    healthcheck:
      test: ["CMD", "/bin/sh", "-c", "curl -fsS http://localhost:3100/ready || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 60s
    restart: unless-stopped
    networks:
      - melo_default

  promtail:
    image: grafana/promtail:latest
    volumes:
      - ./promtail/promtail.yml:/etc/promtail/promtail.yml:ro
      - melo_melo_logs:/var/log/melo:ro
    command: -config.file=/etc/promtail/promtail.yml
    depends_on:
      loki:
        condition: service_started
    restart: unless-stopped
    networks:
      - melo_default

  tempo:
    image: grafana/tempo:latest
    ports:
      - "4317:4317"
      - "4318:4318"
      - "3200:3200"
    volumes:
      - ./tempo/tempo.yml:/etc/tempo/tempo.yml:ro
      - tempo_data:/var/tempo
    command: -config.file=/etc/tempo/tempo.yml
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:3200/ready"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 60s
    restart: unless-stopped
    networks:
      - melo_default

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:-admin}
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_INSTALL_PLUGINS: grafana-pyroscope-app
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - grafana_data:/var/lib/grafana
    depends_on:
      prometheus:
        condition: service_healthy
      loki:
        condition: service_started
      tempo:
        condition: service_started
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3000/api/health"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 60s
    restart: unless-stopped
    networks:
      - melo_default

  pyroscope:
    image: grafana/pyroscope:latest
    user: root
    ports:
      - "4040:4040"
    volumes:
      - ./pyroscope/pyroscope.yml:/etc/pyroscope/pyroscope.yml:ro
      - pyroscope_data:/var/lib/pyroscope
    command: -config.file=/etc/pyroscope/pyroscope.yml
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:4040/ready"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 60s
    restart: unless-stopped
    networks:
      - melo_default

  celery-exporter:
    image: danihodovic/celery-exporter:latest
    ports:
      - "9808:9808"
    environment:
      CE_BROKER_URL: ${CELERY_BROKER:-redis://redis:6379/0}
    restart: unless-stopped
    networks:
      - melo_default

  flower:
    image: mher/flower:latest
    ports:
      - "5555:5555"
    environment:
      CELERY_BROKER_URL: ${CELERY_BROKER:-redis://redis:6379/0}
      FLOWER_PORT: 5555
    restart: unless-stopped
    networks:
      - melo_default

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    ports:
      - "8090:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    restart: unless-stopped
    networks:
      - melo_default

  node-exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - --path.procfs=/host/proc
      - --path.rootfs=/rootfs
      - --path.sysfs=/host/sys
      - --collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)
    restart: unless-stopped
    networks:
      - melo_default

  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    ports:
      - "9187:9187"
    environment:
      DATA_SOURCE_NAME: postgresql://${POSTGRES_USER:-melo}:${POSTGRES_PASSWORD:-melo}@postgres:5432/${POSTGRES_DB:-melo}?sslmode=disable
    restart: unless-stopped
    networks:
      - melo_default

  redis-exporter:
    image: oliver006/redis_exporter:latest
    ports:
      - "9121:9121"
    environment:
      REDIS_ADDR: ${REDIS_URL:-redis://redis:6379/0}
    restart: unless-stopped
    networks:
      - melo_default

volumes:
  prometheus_data:
  loki_data:
  tempo_data:
  pyroscope_data:
  grafana_data:
  melo_melo_logs:
    external: true

networks:
  melo_default:
    external: true
    name: ${COMPOSE_PROJECT_NAME:-melo}_default'

log ""
log "Done. All infra files created."
log "Next: make monitoring-up"
