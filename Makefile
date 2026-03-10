.PHONY: help dev api test lint fmt frontend docker clean setup install

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Development ────────────────────────────────────────

dev: ## Start API + frontend dev servers concurrently
	@make -j2 api frontend-dev

api: ## Start FastAPI dev server
	uvicorn presentation.api.app:app --reload --port 8000

frontend-dev: ## Start Vite dev server
	cd frontend && npm run dev

# ─── Testing ────────────────────────────────────────────

test: ## Run all Python tests
	pytest --tb=short -q

test-cov: ## Run tests with coverage report
	pytest --cov=domain --cov=application --cov=infrastructure --cov-report=html --cov-report=term-missing

test-frontend: ## Run frontend tests
	cd frontend && npm test -- --run

# ─── Code Quality ───────────────────────────────────────

lint: ## Run linter checks
	ruff check .
	cd frontend && npm run lint

fmt: ## Auto-format code
	ruff format .

typecheck: ## Type-check frontend
	cd frontend && npx tsc --noEmit

# ─── Build ──────────────────────────────────────────────

frontend: ## Build frontend for production
	cd frontend && npm ci && npm run build

docker: ## Build Docker image
	docker build -t stratum:latest .

docker-up: ## Start with docker-compose
	docker compose up -d

docker-down: ## Stop docker-compose
	docker compose down

# ─── OpenAPI ────────────────────────────────────────────

generate-client: ## Generate TypeScript API client from OpenAPI spec
	./scripts/generate-api-client.sh

# ─── Setup ──────────────────────────────────────────────

install: ## Install all dependencies
	pip install -e ".[dev]"
	cd frontend && npm install

setup: install ## Full project setup
	@test -f .env || cp .env.example .env
	@echo "Setup complete. Edit .env with your API keys."

# ─── Cleanup ────────────────────────────────────────────

clean: ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache htmlcov .coverage
	rm -rf frontend/dist frontend/node_modules/.vite
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
