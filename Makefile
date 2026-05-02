.PHONY: up down down-v logs logs-api logs-worker ps shell-api shell-worker \
        health songs pre-commit-install pre-commit pre-commit-all \
        test test-unit test-integration test-cov smoke

# ── Docker ────────────────────────────────────────────────────────────────────
up:
	docker compose up --build -d
	@echo "\n✅  Melo stack is up"
	@echo "   API:          http://localhost:8000"
	@echo "   API docs:     http://localhost:8000/docs"
	@echo "   MinIO:        http://localhost:9001"
	@echo "   Adminer:      http://localhost:8080"

down:
	docker compose down

down-v:
	docker compose down -v

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

ps:
	docker compose ps

# ── Shell access ──────────────────────────────────────────────────────────────
shell-api:
	docker compose exec api bash

shell-worker:
	docker compose exec worker bash

# ── Dev helpers ───────────────────────────────────────────────────────────────
health:
	@curl -s http://localhost:8000/health | python3 -m json.tool

songs:
	@curl -s http://localhost:8000/songs | python3 -m json.tool

# ── Pre-commit ────────────────────────────────────────────────────────────────
pre-commit-install:
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg
	@echo "✅  pre-commit hooks installed"

pre-commit:
	uv run pre-commit run --all-files

pre-commit-all: pre-commit

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	uv run pytest

test-unit:
	uv run pytest tests/unit -v

test-integration:
	uv run pytest tests/integration -v

test-cov:
	uv run pytest --cov=app --cov-report=html:htmlcov --cov-report=term-missing
	@echo "\n📊  Coverage report: htmlcov/index.html"

test-smoke:
	chmod +x tests/smoke_test.sh
	@bash tests/smoke_test.sh $(if $(URL),--url "$(URL)",)
