# ValidaHub Engineering Makefile
# Bootstrap commands for development workflow

.PHONY: help up down db.migrate db.reset contracts.gen contracts.check rules.compile rules.validate test test.unit test.integration test.architecture test.golden check.arch lint format clean install dev

# Default target
help: ## Show this help message
	@echo "ValidaHub Development Commands"
	@echo "============================="
	@grep -E '^[a-zA-Z0-9_.-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Infrastructure
up: ## Start development environment with Docker Compose
	docker-compose up -d postgres redis minio otel-collector jaeger
	@echo "✅ Development infrastructure started"
	@echo "   PostgreSQL: localhost:5432"
	@echo "   Redis: localhost:6379" 
	@echo "   MinIO: localhost:9000 (console: localhost:9001)"
	@echo "   Jaeger UI: http://localhost:16686"

down: ## Stop development environment
	docker-compose down
	@echo "✅ Development infrastructure stopped"

dev: up ## Start development environment and API server
	@echo "Starting FastAPI development server..."
	docker-compose up api

# Database
db.migrate: ## Run database migrations
	@echo "Running Alembic migrations..."
	@if [ -d "alembic" ]; then \
		alembic upgrade head; \
	else \
		echo "⚠️  Alembic not yet configured. Run 'make install' first."; \
	fi

db.reset: ## Reset database (development only)
	@echo "⚠️  Resetting database..."
	@read -p "This will delete all data. Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down postgres; \
		docker volume rm validahub-alpha_postgres_data 2>/dev/null || true; \
		docker-compose up -d postgres; \
		sleep 5; \
		make db.migrate; \
	fi

db.partitions.setup: ## Set up automated partition management
	@echo "Setting up partition management..."
	docker-compose exec -T postgres psql -U validahub -d validahub -f /docker-entrypoint-initdb.d/setup_partition_automation.sql
	@echo "✅ Partition automation configured"

db.partitions.check: ## Check partition health status
	@echo "Checking partition health..."
	@docker-compose exec -T postgres psql -U validahub -d validahub -c "SELECT * FROM check_partition_health();"

db.partitions.maintain: ## Manually run partition maintenance
	@echo "Running partition maintenance..."
	@docker-compose exec -T postgres psql -U validahub -d validahub -c "SELECT maintain_partitions();"

db.partitions.status: ## View current partition status
	@docker-compose exec -T postgres psql -U validahub -d validahub -c "SELECT * FROM partition_status ORDER BY partition_month DESC;"

# Contracts
contracts.gen: ## Generate TypeScript types from OpenAPI
	@echo "Generating TypeScript types from OpenAPI..."
	@if [ -f "packages/contracts/openapi.yaml" ]; then \
		npx openapi-typescript packages/contracts/openapi.yaml -o packages/contracts/types.ts; \
		echo "✅ TypeScript types generated"; \
	else \
		echo "❌ OpenAPI spec not found at packages/contracts/openapi.yaml"; \
	fi

contracts.check: ## Validate OpenAPI contract
	@echo "Validating OpenAPI contract..."
	@if [ -f "packages/contracts/openapi.yaml" ]; then \
		npx swagger-cli validate packages/contracts/openapi.yaml; \
		echo "✅ OpenAPI contract is valid"; \
	else \
		echo "❌ OpenAPI spec not found at packages/contracts/openapi.yaml"; \
	fi

# Rules
rules.compile: ## Compile rule packs from YAML to IR
	@echo "Compiling rule packs..."
	@if [ -d "packages/rules" ]; then \
		find packages/rules -name "*.yaml" -o -name "*.yml" | while read file; do \
			echo "Validating $$file..."; \
			python -c "import yaml; yaml.safe_load(open('$$file'))"; \
		done; \
		echo "✅ Rule packs compiled and validated"; \
	else \
		echo "⚠️  Rules directory not found. Will be created later."; \
	fi

rules.validate: ## Validate rule pack YAML files
	@echo "Validating rule pack schemas..."
	@find packages/rules -name "*.yaml" -o -name "*.yml" 2>/dev/null | while read file; do \
		echo "Checking $$file..."; \
		python -c "import yaml; yaml.safe_load(open('$$file'))"; \
	done || echo "⚠️  No rule files found yet"

# Testing
test: ## Run all tests
	@echo "Running all tests..."
	pytest tests/ -v --tb=short --cov=packages --cov-report=term-missing --cov-fail-under=80

test.unit: ## Run unit tests only
	@echo "Running unit tests..."
	pytest tests/unit/ -v --tb=short

test.integration: ## Run integration tests only  
	@echo "Running integration tests..."
	pytest tests/integration/ -v --tb=short

test.architecture: ## Run architecture validation tests
	@echo "Running architecture tests..."
	pytest tests/architecture/ -v --tb=short

test.golden: ## Run golden tests for rule engine outputs
	@echo "Running golden tests..."
	@if [ -d "tests/golden" ]; then \
		pytest tests/golden/ -v --tb=short; \
	else \
		echo "⚠️  Golden tests not yet implemented"; \
	fi

# Architecture validation
check.arch: ## Validate layer dependencies
	@python3 scripts/check_arch.py

# Code quality
lint: ## Run linting with ruff
	@echo "Running ruff linting..."
	ruff check packages/ apps/ tests/

format: ## Format code with black and ruff
	@echo "Formatting code..."
	black packages/ apps/ tests/
	ruff --fix packages/ apps/ tests/

# Development setup
install: ## Install development dependencies
	@echo "Installing development dependencies..."
	pip install -r requirements-dev.txt
	@if [ ! -f "alembic.ini" ]; then \
		echo "Initializing Alembic..."; \
		alembic init alembic; \
	fi

clean: ## Clean up temporary files
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Docker shortcuts
logs: ## Show Docker logs
	docker-compose logs -f

restart: ## Restart all services
	docker-compose restart

ps: ## Show running containers
	docker-compose ps

# Quick development workflow
quick-start: up db.migrate contracts.gen rules.compile ## Quick start: infrastructure + migrations + contracts
	@echo "🚀 Development environment ready!"
	@echo ""
	@echo "Next steps:"
	@echo "  make dev     # Start API server"
	@echo "  make test    # Run tests"
	@echo "  make lint    # Check code quality"