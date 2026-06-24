.PHONY: help install dev test lint format typecheck docker-build docker-run docker-stop docker-logs clean

help:
	@echo "HH Applicant Tool - Development Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install          - Install dependencies with poetry"
	@echo "  make dev              - Install dev dependencies"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             - Run ruff, isort, pylint checks"
	@echo "  make format           - Auto-format code (ruff, isort)"
	@echo "  make typecheck        - Run type checking (pyright)"
	@echo "  make test             - Run pytest"
	@echo "  make ci               - Run all checks (lint + typecheck + test)"
	@echo ""
	@echo "Scheduling (Auto-run):"
	@echo "  make schedule         - Setup cron for daily auto-run (9:00)"
	@echo "  make schedule-time    - Setup cron with custom time (TIME=10:30)"
	@echo "  make scheduler        - Run Python scheduler in foreground"
	@echo "  make scheduler-test   - Test scheduler (single run)"
	@echo "  make unschedule       - Remove cron jobs"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build     - Build Docker image"
	@echo "  make docker-run       - Start containers with docker-compose"
	@echo "  make docker-stop      - Stop containers"
	@echo "  make docker-logs      - Show container logs"
	@echo "  make docker-shell     - Open bash in container"
	@echo ""
	@echo "Utils:"
	@echo "  make clean            - Remove cache and build artifacts"
	@echo "  make setup-config     - Copy example configs"

install:
	poetry install

dev:
	poetry install --with dev
	poetry run pre-commit install

test:
	poetry run pytest tests/ -v

test-cov:
	poetry run pytest tests/ -v --cov=src/hh_applicant_tool --cov-report=term --cov-report=html

lint:
	@echo "🔍 Running linters..."
	poetry run ruff check src/ tests/
	poetry run isort --check-only src/ tests/
	poetry run pylint src/ tests/
	@echo "✅ All linters passed!"

format:
	@echo "📝 Formatting code..."
	poetry run ruff check --fix src/ tests/
	poetry run isort src/ tests/
	poetry run ruff format src/ tests/
	@echo "✅ Code formatted!"

lint-fix:
	@echo "🔧 Auto-fixing lint issues..."
	poetry run isort src/ tests/
	poetry run ruff check --fix src/ tests/
	@echo "✅ Auto-fixes applied!"

typecheck:
	poetry run basedpyright src/ tests/

ci: lint typecheck test
	@echo "✅ All checks passed!"

docker-build:
	docker compose build

docker-run:
	docker compose up -d
	@echo "🚀 Container started. Logs:"
	docker compose logs -f

docker-stop:
	docker compose down

docker-logs:
	docker compose logs -f hh_applicant_tool

docker-shell:
	docker compose exec hh_applicant_tool bash

docker-test:
	docker compose run --rm hh_applicant_tool poetry run pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytype" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage coverage.xml

setup-config:
	@if [ ! -f .env ]; then cp .env.example .env && echo "✅ Created .env"; else echo "⚠️  .env already exists"; fi
	@if [ ! -f config/config.yaml ]; then cp config/config.example.yaml config/config.yaml && echo "✅ Created config/config.yaml"; else echo "⚠️  config/config.yaml already exists"; fi
	@echo "📝 Edit these files with your values:"
	@echo "  - .env"
	@echo "  - config/config.yaml"

# === Scheduling / Auto-run ===

schedule:
	@echo "🕐 Setting up cron for daily auto-run at 09:00..."
	@bash scripts/setup-cron.sh

schedule-time:
	@if [ -z "$(TIME)" ]; then \
		echo "❌ Usage: make schedule-time TIME=10:30"; \
		exit 1; \
	fi
	@echo "🕐 Setting up cron for daily auto-run at $(TIME)..."
	@RUN_TIME=$(TIME) bash scripts/setup-cron.sh

scheduler:
	@echo "🕐 Running Python scheduler (foreground)..."
	@mkdir -p logs
	@python3 scripts/scheduler.py

scheduler-test:
	@echo "🧪 Testing scheduler (single run)..."
	@mkdir -p logs
	@python3 scripts/scheduler.py --once

scheduler-background:
	@echo "🕐 Starting scheduler in background..."
	@mkdir -p logs
	@nohup python3 scripts/scheduler.py > logs/scheduler.out 2>&1 &
	@echo "✅ Scheduler started (PID: $$!)"
	@echo "📝 Logs: logs/scheduler.log"

unschedule:
	@echo "🗑️  Removing cron jobs..."
	@(crontab -l 2>/dev/null | grep -v "hh-applicant-tool" | grep -v "boost-resume" | grep -v "apply-vacancies") | crontab -
	@echo "✅ Cron jobs removed"

.PHONY: help install dev test lint format typecheck docker-build docker-run docker-stop docker-logs clean setup-config docker-test docker-shell ci test-cov schedule schedule-time scheduler scheduler-test scheduler-background unschedule
