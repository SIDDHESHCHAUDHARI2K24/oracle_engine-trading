# =============================================================================
# MBI Labs Oracle Engine — Root Makefile
# Targets delegate into backend/ and frontend/ sub-projects.
# =============================================================================

.PHONY: help dev dev-watch db-up db-down db-check migrate test test-backend test-frontend test-e2e lint format gen-api

# Default target
help: ## Show this help
	@echo "MBI Labs Oracle Engine — Development Targets"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Stack ---

dev: ## Start full local dev stack (no reload — fastest cold boot)
	@echo "Starting MinIO..."
	docker compose -f docker-compose.dev.yml up -d minio
	@echo "Starting backend (FastAPI)..."
	cd backend && uv run uvicorn app.app:create_app --factory --loop asyncio --host 0.0.0.0 --port 8000 &
	@echo "Starting frontend (Vite)..."
	cd frontend && pnpm dev &
	@echo "Dev stack running: backend http://localhost:8000, frontend http://localhost:5173, MinIO console http://localhost:9001"

dev-watch: ## Start backend with hot-reload (slower cold boot, faster iteration)
	@echo "Starting MinIO..."
	docker compose -f docker-compose.dev.yml up -d minio
	@echo "Starting backend (FastAPI) with hot-reload..."
	cd backend && uv run uvicorn app.app:create_app --factory --reload --loop asyncio --host 0.0.0.0 --port 8000 &
	@echo "Starting frontend (Vite)..."
	cd frontend && pnpm dev &
	@echo "Dev stack (watch) running: backend http://localhost:8000, frontend http://localhost:5173, MinIO console http://localhost:9001"

db-up: ## Start MinIO Docker service
	docker compose -f docker-compose.dev.yml up -d minio

db-down: ## Stop MinIO Docker service
	docker compose -f docker-compose.dev.yml down

db-check: ## Verify TimescaleDB extension is available
	@echo "Checking TimescaleDB..."
	@psql -h localhost -U mbi_user -d mbi -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';" 2>/dev/null || echo "TimescaleDB check failed — is Postgres running?"

# --- Migrations ---

migrate: ## Run Alembic migrations (upgrade to head)
	cd backend && uv run alembic upgrade head

# --- Testing ---

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests (pytest)
	cd backend && uv run python -m pytest

test-frontend: ## Run frontend tests (vitest)
	cd frontend && pnpm test

test-e2e: ## Run E2E tests (Playwright)
	cd e2e && npx playwright test

# --- Lint & Format ---

lint: ## Run all linters
	cd backend && uv run ruff check
	cd frontend && pnpm lint

format: ## Run all formatters
	cd backend && uv run ruff format
	cd frontend && pnpm format

# --- Code Generation ---

gen-api: ## Generate TypeScript types from OpenAPI schema
	@echo "Generating API types from http://localhost:8000/openapi.json..."
	cd frontend && npx openapi-typescript http://localhost:8000/openapi.json -o src/core/types/api.ts
