# CapitalSpring MVP - Development Makefile

.PHONY: help install install-api install-frontend dev dev-api dev-frontend test test-api test-frontend lint lint-api lint-frontend build build-api build-frontend deploy clean db-migrate db-upgrade db-downgrade

# Default target
help:
	@echo "CapitalSpring MVP - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install all dependencies"
	@echo "  make install-api      Install API dependencies"
	@echo "  make install-frontend Install frontend dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make dev              Start both API and frontend dev servers"
	@echo "  make dev-api          Start API development server"
	@echo "  make dev-frontend     Start frontend development server"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-api         Run API tests"
	@echo "  make test-frontend    Run frontend tests"
	@echo ""
	@echo "Linting:"
	@echo "  make lint             Run all linters"
	@echo "  make lint-api         Run API linters (ruff, mypy)"
	@echo "  make lint-frontend    Run frontend linters (eslint)"
	@echo ""
	@echo "Build:"
	@echo "  make build            Build both API and frontend"
	@echo "  make build-api        Build API Docker image"
	@echo "  make build-frontend   Build frontend Docker image"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate       Generate new migration"
	@echo "  make db-upgrade       Apply migrations"
	@echo "  make db-downgrade     Revert last migration"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy           Deploy to GCP (staging)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Clean build artifacts"

# ============================================
# Installation
# ============================================

install: install-api install-frontend
	@echo "All dependencies installed!"

install-api:
	@echo "Installing API dependencies..."
	cd api && python -m venv venv
	cd api && venv/Scripts/activate && pip install -r requirements.txt -r requirements-dev.txt

install-frontend:
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# ============================================
# Development Servers
# ============================================

dev:
	@echo "Starting development servers..."
	@echo "Run 'make dev-api' and 'make dev-frontend' in separate terminals"

dev-api:
	@echo "Starting API development server..."
	cd api && venv/Scripts/activate && uvicorn app.main:app --reload --port 8000

dev-frontend:
	@echo "Starting frontend development server..."
	cd frontend && npm run dev

# ============================================
# Testing
# ============================================

test: test-api test-frontend
	@echo "All tests passed!"

test-api:
	@echo "Running API tests..."
	cd api && venv/Scripts/activate && pytest tests/ -v --cov=app --cov-report=term-missing

test-frontend:
	@echo "Running frontend tests..."
	cd frontend && npm run test -- --run

# ============================================
# Linting
# ============================================

lint: lint-api lint-frontend
	@echo "All linting passed!"

lint-api:
	@echo "Linting API code..."
	cd api && venv/Scripts/activate && ruff check app/ tests/
	cd api && venv/Scripts/activate && mypy app/ --ignore-missing-imports

lint-frontend:
	@echo "Linting frontend code..."
	cd frontend && npm run lint
	cd frontend && npm run type-check

# ============================================
# Building
# ============================================

build: build-api build-frontend
	@echo "All images built!"

build-api:
	@echo "Building API Docker image..."
	docker build -t capitalspring-api:latest -f api/Dockerfile api/

build-frontend:
	@echo "Building frontend Docker image..."
	docker build -t capitalspring-frontend:latest -f frontend/Dockerfile frontend/

# ============================================
# Database Migrations
# ============================================

db-migrate:
	@echo "Generating new migration..."
	@read -p "Migration message: " msg; \
	cd api && venv/Scripts/activate && alembic revision --autogenerate -m "$$msg"

db-upgrade:
	@echo "Applying migrations..."
	cd api && venv/Scripts/activate && alembic upgrade head

db-downgrade:
	@echo "Reverting last migration..."
	cd api && venv/Scripts/activate && alembic downgrade -1

# ============================================
# Deployment
# ============================================

deploy:
	@echo "Deploying to GCP staging..."
	gcloud builds submit --config cloudbuild.yaml

# ============================================
# Terraform
# ============================================

tf-init:
	@echo "Initializing Terraform..."
	cd terraform/environments/dev && terraform init

tf-plan:
	@echo "Planning Terraform changes..."
	cd terraform/environments/dev && terraform plan

tf-apply:
	@echo "Applying Terraform changes..."
	cd terraform/environments/dev && terraform apply

# ============================================
# Cleanup
# ============================================

clean:
	@echo "Cleaning build artifacts..."
	rm -rf api/__pycache__
	rm -rf api/.pytest_cache
	rm -rf api/.mypy_cache
	rm -rf api/.ruff_cache
	rm -rf api/htmlcov
	rm -rf api/.coverage
	rm -rf frontend/node_modules/.cache
	rm -rf frontend/dist
	docker image prune -f
	@echo "Cleanup complete!"
