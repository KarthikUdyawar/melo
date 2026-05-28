SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:

.PHONY: \
	help up down down-v restart rebuild logs logs-api logs-worker ps \
	shell-api shell-worker shell-postgres \
	health songs wait-api \
	reset-db seed clean-tmp \
	backup backup-db backup-minio restore-db restore-minio \
	pre-commit-install pre-commit \
	test test-unit test-integration test-cov \
	test-up test-down smoke \
	act-lint act-unit act-integration act-coverage act-ci

.DEFAULT_GOAL := help

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

include .env.development
export

BACKUP_DIR   := ./backups
TIMESTAMP    := $(shell date +%Y%m%d_%H%M%S)

PG_USER      := melo
PG_DB        := melo

MINIO_BUCKET := songs

COMPOSE      := docker compose
TEST_COMPOSE := docker compose -f tests/docker-compose.test.yml

GREEN := \033[0;32m
BLUE  := \033[0;34m
RED   := \033[0;31m
NC    := \033[0m

# ──────────────────────────────────────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────────────────────────────────────

help: ## Show available targets
	@echo ""
	@echo "🎵 Melo — available targets"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ { \
		printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2 \
	}' $(MAKEFILE_LIST)
	@echo ""

# ──────────────────────────────────────────────────────────────────────────────
# Docker
# ──────────────────────────────────────────────────────────────────────────────

up: ## Build + start all services detached
	$(COMPOSE) up --build -d
	$(MAKE) wait-api

	echo ""
	echo -e "$(GREEN)✅ Melo stack is up$(NC)"
	echo "   API:          http://localhost:8000"
	echo "   API docs:     http://localhost:8000/docs"
	echo "   MinIO:        http://localhost:9001"
	echo "   Adminer:      http://localhost:8080"

down: ## Stop all services
	$(COMPOSE) down

down-v: ## Stop all services and delete volumes
	$(COMPOSE) down -v

restart: ## Restart stack
	$(MAKE) down
	$(MAKE) up

rebuild: ## Rebuild all Docker images without cache
	$(COMPOSE) build --no-cache

logs: ## Tail all logs
	$(COMPOSE) logs -f

logs-api: ## Tail API logs
	$(COMPOSE) logs -f api

logs-worker: ## Tail worker logs
	$(COMPOSE) logs -f worker

ps: ## Show container status
	$(COMPOSE) ps

wait-api: ## Wait until API healthcheck passes
	until curl -sf http://localhost:8000/health >/dev/null; do
		echo "⏳ Waiting for API..."
		sleep 2
	done

# ──────────────────────────────────────────────────────────────────────────────
# Shell access
# ──────────────────────────────────────────────────────────────────────────────

shell-api: ## Open bash in API container
	$(COMPOSE) exec api bash

shell-worker: ## Open bash in worker container
	$(COMPOSE) exec worker bash

shell-postgres: ## Open psql shell
	$(COMPOSE) exec postgres psql -U $(PG_USER) $(PG_DB)

# ──────────────────────────────────────────────────────────────────────────────
# Dev helpers
# ──────────────────────────────────────────────────────────────────────────────

health: ## Hit /health endpoint
	curl -s http://localhost:8000/health | python3 -m json.tool

songs: ## List all songs
	curl -s http://localhost:8000/songs | python3 -m json.tool

reset-db: ## Destroy DB volumes and restart stack
	$(COMPOSE) down -v
	$(COMPOSE) up --build -d
	$(MAKE) wait-api

	echo ""
	echo -e "$(GREEN)🔄 Database reset complete$(NC)"

seed: ## Submit sample songs
	echo "⏳ Seeding sample songs..."

	curl -sf -X POST http://localhost:8000/songs \
		-H "Content-Type: application/json" \
		-d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","start":0,"end":30,"speed":1.0}' \
		| python3 -m json.tool

	curl -sf -X POST http://localhost:8000/songs \
		-H "Content-Type: application/json" \
		-d '{"url":"https://www.youtube.com/watch?v=jNQXAC9IVRw","speed":1.5}' \
		| python3 -m json.tool

	echo ""
	echo -e "$(GREEN)✅ Seed jobs submitted$(NC)"

clean-tmp: ## Clear /tmp/melo inside worker
	$(COMPOSE) exec worker \
		find /tmp/melo -mindepth 1 -delete

	echo -e "$(GREEN)🧹 /tmp/melo cleared$(NC)"

# ──────────────────────────────────────────────────────────────────────────────
# Backup & restore
# ──────────────────────────────────────────────────────────────────────────────

backup: backup-db backup-minio ## Backup DB + MinIO

backup-db: ## Backup PostgreSQL
	mkdir -p $(BACKUP_DIR)

	echo "🗄️ Dumping PostgreSQL..."

	$(COMPOSE) exec -T postgres \
		pg_dump -U $(PG_USER) $(PG_DB) \
		| gzip > $(BACKUP_DIR)/db_$(TIMESTAMP).sql.gz

	echo -e "$(GREEN)✅ DB backup created$(NC)"
	echo "   $(BACKUP_DIR)/db_$(TIMESTAMP).sql.gz"

backup-minio: ## Backup MinIO bucket
	mkdir -p $(BACKUP_DIR)

	echo "📦 Backing up MinIO bucket..."

	docker cp $$($(COMPOSE) ps -q minio):/data/$(MINIO_BUCKET) - \
		| gzip > $(BACKUP_DIR)/minio_$(TIMESTAMP).tar.gz

	echo -e "$(GREEN)✅ MinIO backup created$(NC)"
	echo "   $(BACKUP_DIR)/minio_$(TIMESTAMP).tar.gz"

restore-db: ## Restore PostgreSQL from FILE=<backup.sql.gz>
	test -n "$(FILE)" || (echo "Usage: make restore-db FILE=<file.sql.gz>" && exit 1)

	echo "⚠️ Restoring database from $(FILE)..."

	gunzip -c $(FILE) | $(COMPOSE) exec -T postgres \
		psql -U $(PG_USER) $(PG_DB)

	echo -e "$(GREEN)✅ Database restored$(NC)"

restore-minio: ## Restore MinIO bucket from FILE=<backup.tar.gz>
	test -n "$(FILE)" || (echo "Usage: make restore-minio FILE=<file.tar.gz>" && exit 1)

	echo "⚠️ Restoring MinIO bucket from $(FILE)..."

	$(COMPOSE) exec -T minio \
		sh -c 'rm -rf /data/$(MINIO_BUCKET)'

	cat $(FILE) | $(COMPOSE) exec -T minio \
		sh -c 'tar -xzf - -C /data'

	echo -e "$(GREEN)✅ MinIO restored$(NC)"

# ──────────────────────────────────────────────────────────────────────────────
# Pre-commit
# ──────────────────────────────────────────────────────────────────────────────

pre-commit-install: ## Install pre-commit hooks
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

	echo -e "$(GREEN)✅ pre-commit hooks installed$(NC)"

pre-commit: ## Run all pre-commit hooks
	uv run pre-commit run --all-files --show-diff-on-failure

# ──────────────────────────────────────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────────────────────────────────────

test-up: ## Start integration test services
	$(TEST_COMPOSE) up -d --wait

test-down: ## Stop integration test services
	$(TEST_COMPOSE) down -v

# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

test-unit: ## Run unit tests
	uv run pytest \
		-o addopts='' \
		tests/unit \
		-v

test-integration: ## Run integration tests
	trap '$(TEST_COMPOSE) down -v' EXIT

	echo "🐳 Starting integration test services..."
	$(TEST_COMPOSE) up -d --wait

	echo "✅ Running integration tests..."

	uv run pytest \
		-o addopts='' \
		tests/integration \
		-v

test: ## Run full test suite
	trap '$(TEST_COMPOSE) down -v' EXIT

	echo "🐳 Starting integration test services..."
	$(TEST_COMPOSE) up -d --wait

	echo "✅ Running full test suite..."

	uv run pytest -v

test-cov: ## Run tests with coverage report
	trap '$(TEST_COMPOSE) down -v' EXIT

	echo "🐳 Starting integration test services..."
	$(TEST_COMPOSE) up -d --wait

	echo "✅ Running tests with coverage..."

	uv run pytest \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-report=xml \
		-v

	echo ""
	echo -e "$(GREEN)📊 Coverage report generated$(NC)"
	echo "   htmlcov/index.html"

smoke: ## Run smoke test against running stack
	chmod +x tests/smoke_test.sh
	bash tests/smoke_test.sh $(if $(URL),--url "$(URL)",)

# ──────────────────────────────────────────────────────────────────────────────
# GitHub Actions locally via act
# ──────────────────────────────────────────────────────────────────────────────

act-lint: ## Run lint GitHub Action locally
	act -j lint --reuse --var ACT=true

act-unit: ## Run unit-test GitHub Action locally
	act -j test-unit --reuse --var ACT=true

act-integration: ## Run integration-test GitHub Action locally
	act -j test-integration \
		--reuse \
		--container-options "--network host" \
		--var ACT=true

act-coverage: ## Run coverage GitHub Action locally
	act -j coverage --reuse --var ACT=true

act-ci: ## Run full GitHub Actions pipeline locally
	act --reuse --var ACT=true
