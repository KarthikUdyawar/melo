.PHONY: help up down down-v logs logs-api logs-worker ps shell-api shell-worker \
        health songs lint fmt reset-db seed clean-tmp \
        backup backup-db backup-minio restore-db restore-minio \
        pre-commit-install pre-commit \
        test test-unit test-integration test-cov smoke

.DEFAULT_GOAL := help

help: ## Show this help
	@echo ""
	@echo "  🎵 Melo — available targets"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""

BACKUP_DIR   := ./backups
TIMESTAMP    := $(shell date +%Y%m%d_%H%M%S)
PG_USER      := melo
PG_DB        := melo
MINIO_BUCKET := songs

# ── Docker ────────────────────────────────────────────────────────────────────
up: ## Build + start all services detached
	docker compose up --build -d
	@echo "\n✅  Melo stack is up"
	@echo "   API:          http://localhost:8000"
	@echo "   API docs:     http://localhost:8000/docs"
	@echo "   MinIO:        http://localhost:9001"
	@echo "   Adminer:      http://localhost:8080"

down: ## Stop all services
	docker compose down

down-v: ## Stop all services and delete volumes
	docker compose down -v

logs: ## Tail all service logs
	docker compose logs -f

logs-api: ## Tail API logs only
	docker compose logs -f api

logs-worker: ## Tail worker logs only
	docker compose logs -f worker

ps: ## Show service status
	docker compose ps

# ── Shell access ──────────────────────────────────────────────────────────────
shell-api: ## Bash into api container
	docker compose exec api bash

shell-worker: ## Bash into worker container
	docker compose exec worker bash

# ── Dev helpers ───────────────────────────────────────────────────────────────
health: ## Hit /health endpoint
	@curl -s http://localhost:8000/health | python3 -m json.tool

songs: ## List all songs
	@curl -s http://localhost:8000/songs | python3 -m json.tool

reset-db: ## Wipe all volumes and restart stack (destructive)
	docker compose down -v
	docker compose up --build -d
	@echo "\n🔄  DB wiped and stack restarted"

seed: ## Submit sample songs for development
	@echo "⏳  Seeding sample songs..."
	@curl -sf -X POST http://localhost:8000/songs \
	  -H "Content-Type: application/json" \
	  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","start":0,"end":30,"speed":1.0}' | python3 -m json.tool
	@curl -sf -X POST http://localhost:8000/songs \
	  -H "Content-Type: application/json" \
	  -d '{"url":"https://www.youtube.com/watch?v=jNQXAC9IVRw","speed":1.5}' | python3 -m json.tool
	@echo "\n✅  Seed submitted — poll GET /songs for status"

clean-tmp: ## Clear /tmp/melo inside worker container
	@docker compose exec worker \
	  sh -c 'mkdir -p /tmp/melo && rm -rf /tmp/melo/* /tmp/melo/.[!.]* /tmp/melo/..?* 2>/dev/null || true'
	@echo "🧹  /tmp/melo cleared inside worker"

# ── Backup & restore ──────────────────────────────────────────────────────────
# Backups land in ./backups/ (gitignored).
# DB    → backups/db_YYYYMMDD_HHMMSS.sql.gz
# MinIO → backups/minio_YYYYMMDD_HHMMSS.tar.gz

backup: backup-db backup-minio ## Backup DB + MinIO to ./backups/
	@echo "\n✅  Backup complete → $(BACKUP_DIR)/"

backup-db: ## Backup PostgreSQL to ./backups/db_<timestamp>.sql.gz
	@mkdir -p $(BACKUP_DIR)
	@echo "🗄️  Dumping PostgreSQL → $(BACKUP_DIR)/db_$(TIMESTAMP).sql.gz"
	@docker compose exec -T postgres \
	  pg_dump -U $(PG_USER) $(PG_DB) \
	  | gzip > $(BACKUP_DIR)/db_$(TIMESTAMP).sql.gz
	@echo "   ✔  $(BACKUP_DIR)/db_$(TIMESTAMP).sql.gz"

backup-minio: ## Backup MinIO bucket to ./backups/minio_<timestamp>.tar.gz
	`@mkdir` -p $(BACKUP_DIR)
	`@echo` "📦  Archiving MinIO bucket '$(MINIO_BUCKET)' → $(BACKUP_DIR)/minio_$(TIMESTAMP).tar.gz"
	`@docker` cp $$(docker compose ps -q minio):/data/$(MINIO_BUCKET) - \
	  | gzip > $(BACKUP_DIR)/minio_$(TIMESTAMP).tar.gz
	`@echo` "   ✔  $(BACKUP_DIR)/minio_$(TIMESTAMP).tar.gz"

restore-db: ## Restore DB from FILE=backups/<name>.sql.gz
	@test -n "$(FILE)" || (echo "❌  Usage: make restore-db FILE=backups/<filename>.sql.gz" && exit 1)
	@echo "⚠️  Restoring $(FILE) into $(PG_DB)..."
	@gunzip -c $(FILE) | docker compose exec -T postgres \
	  psql -U $(PG_USER) $(PG_DB)
	@echo "✅  DB restore complete"

restore-minio: ## Restore MinIO bucket from FILE=backups/<name>.tar.gz (overwrites)
	@test -n "$(FILE)" || (echo "❌  Usage: make restore-minio FILE=backups/<filename>.tar.gz" && exit 1)
	@echo "⚠️  Restoring MinIO bucket '$(MINIO_BUCKET)' from $(FILE)..."
	@docker compose exec -T minio sh -c 'rm -rf /data/$(MINIO_BUCKET)'
	@cat $(FILE) | docker compose exec -T minio \
	  sh -c 'tar -xzf - -C /data'
	@echo "✅  MinIO restore complete"

# ── Linting & formatting ──────────────────────────────────────────────────────
lint: ## Run ruff + mypy
	uv run ruff check .
	uv run mypy app

fmt: ## Auto-format with ruff
	uv run ruff format .
	uv run ruff check --fix .

# ── Pre-commit ────────────────────────────────────────────────────────────────
pre-commit-install: ## Install pre-commit hooks (run once)
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg
	@echo "✅  pre-commit hooks installed"

pre-commit: ## Run all pre-commit hooks on all files
	uv run pre-commit run --all-files

# ── Tests ─────────────────────────────────────────────────────────────────────
test: ## Run full test suite (unit + integration) with coverage
	@echo "🐳  Starting test services..."
	docker compose -f tests/docker-compose.test.yml up -d --wait
	@echo "✅  Services ready — running full test suite"
	uv run pytest; \
	  EXIT_CODE=$$?; \
	  echo "🧹  Tearing down test services..."; \
	  docker compose -f tests/docker-compose.test.yml down -v; \
	  exit $$EXIT_CODE

test-unit: ## Unit tests only (no Docker needed, fast)
	uv run pytest -o addopts='' tests/unit -v

test-integration: ## Integration tests — spins up Docker, runs tests, tears down
	@echo "🐳  Starting test services..."
	docker compose -f tests/docker-compose.test.yml up -d --wait
	@echo "✅  Services ready — running integration tests"
	uv run pytest -o addopts='' tests/integration -v; \
	  EXIT_CODE=$$?; \
	  echo "🧹  Tearing down test services..."; \
	  docker compose -f tests/docker-compose.test.yml down -v; \
	  exit $$EXIT_CODE

test-cov: ## Full test suite + open HTML coverage report → htmlcov/index.html
	@echo "🐳  Starting test services..."
	docker compose -f tests/docker-compose.test.yml up -d --wait
	@echo "✅  Services ready — running full test suite with coverage"
	uv run pytest --cov-report=html:htmlcov; \
	  EXIT_CODE=$$?; \
	  echo "🧹  Tearing down test services..."; \
	  docker compose -f tests/docker-compose.test.yml down -v; \
	  [ $$EXIT_CODE -eq 0 ] && echo "\n📊  Coverage report: htmlcov/index.html" || true; \
	  exit $$EXIT_CODE

smoke: ## End-to-end smoke test (requires stack running)
	chmod +x tests/smoke_test.sh
	@bash tests/smoke_test.sh $(if $(URL),--url "$(URL)",)
