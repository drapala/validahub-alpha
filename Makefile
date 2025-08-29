# ValidaHub Development Makefile
# Based on CLAUDE.md section 10 bootstrap commands

.PHONY: help setup clean test lint format check install dev-deps

# Colors for output
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

help: ## Show this help message
	@echo "$(GREEN)ValidaHub Development Commands$(RESET)"
	@echo "Based on CLAUDE.md engineering playbook"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "$(GREEN)%-20s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Setup and Installation
install: ## Install project dependencies
	@echo "$(YELLOW)Installing ValidaHub dependencies...$(RESET)"
	python -m pip install --upgrade pip
	pip install -e ".[dev]"

dev-deps: ## Install development dependencies only
	@echo "$(YELLOW)Installing development dependencies...$(RESET)"
	pip install pytest pytest-cov hypothesis ruff black mypy

setup: install ## Full development environment setup
	@echo "$(GREEN)ValidaHub development environment ready!$(RESET)"
	@echo "Run 'make help' to see available commands"

# Code Quality
lint: ## Run linting (ruff + mypy)
	@echo "$(YELLOW)Running linters...$(RESET)"
	ruff check src tests
	mypy src --strict

format: ## Format code with black
	@echo "$(YELLOW)Formatting code...$(RESET)"
	black src tests

format-check: ## Check code formatting
	@echo "$(YELLOW)Checking code formatting...$(RESET)"
	black --check src tests

# Testing
test: ## Run all tests
	@echo "$(YELLOW)Running tests...$(RESET)"
	pytest -v --tb=short

test.unit: ## Run unit tests only
	@echo "$(YELLOW)Running unit tests...$(RESET)"
	pytest tests/unit/ -v --tb=short

test.integration: ## Run integration tests only
	@echo "$(YELLOW)Running integration tests...$(RESET)"
	pytest tests/integration/ -v --tb=short

test.architecture: ## Run architecture tests
	@echo "$(YELLOW)Running architecture tests...$(RESET)"
	pytest tests/architecture/ -v --tb=short

test.coverage: ## Run tests with coverage report
	@echo "$(YELLOW)Running tests with coverage...$(RESET)"
	pytest --cov=src --cov-report=html --cov-report=term-missing --cov-fail-under=80

test.security: ## Run security tests
	@echo "$(YELLOW)Running security tests...$(RESET)"
	bandit -r src -ll
	safety check --json

# Architecture Validation
check.arch: test.architecture ## Validate architecture layers (alias)

check: lint format-check test.architecture ## Run all quality checks

# Database & Migrations
db.migrate: ## Run database migrations
	@echo "$(YELLOW)Running database migrations...$(RESET)"
	@if [ -f "alembic.ini" ]; then \
		alembic upgrade head; \
	else \
		echo "$(RED)No alembic.ini found. Database migrations not configured yet.$(RESET)"; \
	fi

# Contracts & Code Generation
contracts.gen: ## Generate types from OpenAPI
	@echo "$(YELLOW)Generating types from OpenAPI contracts...$(RESET)"
	@if [ -f "packages/contracts/openapi.yaml" ]; then \
		echo "OpenAPI contract found, generating types..."; \
		echo "$(RED)Type generation not implemented yet$(RESET)"; \
	else \
		echo "$(RED)No OpenAPI contract found at packages/contracts/openapi.yaml$(RESET)"; \
	fi

contracts.check: ## Validate OpenAPI contracts
	@echo "$(YELLOW)Validating OpenAPI contracts...$(RESET)"
	@if [ -f "packages/contracts/openapi.yaml" ]; then \
		echo "$(GREEN)OpenAPI contract validation would run here$(RESET)"; \
	else \
		echo "$(RED)No OpenAPI contract found$(RESET)"; \
	fi

# Rules Engine
rules.compile: ## Compile rule packs from YAML
	@echo "$(YELLOW)Compiling rule packs...$(RESET)"
	@if [ -d "packages/rules" ]; then \
		echo "$(GREEN)Rule pack compilation would run here$(RESET)"; \
	else \
		echo "$(RED)No packages/rules directory found$(RESET)"; \
	fi

# Docker & Development Environment
up: ## Start development environment
	@echo "$(YELLOW)Starting development environment...$(RESET)"
	@if [ -f "docker-compose.yml" ]; then \
		docker-compose up -d postgres redis minio; \
		echo "$(GREEN)Development services started$(RESET)"; \
	else \
		echo "$(RED)No docker-compose.yml found$(RESET)"; \
	fi

down: ## Stop development environment
	@echo "$(YELLOW)Stopping development environment...$(RESET)"
	@if [ -f "docker-compose.yml" ]; then \
		docker-compose down; \
	else \
		echo "$(RED)No docker-compose.yml found$(RESET)"; \
	fi

# Release & Version Management
release.check: ## Check if ready for release
	@echo "$(YELLOW)Checking release readiness...$(RESET)"
	@echo "✓ Running all quality checks..."
	@$(MAKE) check
	@echo "$(GREEN)✅ Ready for release!$(RESET)"

version: ## Show current version
	@python -c "import toml; print('v' + toml.load('pyproject.toml')['project']['version'])"

# Cleanup
clean: ## Clean up generated files
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".coverage" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)Cleanup completed$(RESET)"

# Git & PR helpers
pr.check: ## Check PR requirements
	@echo "$(YELLOW)Checking PR requirements...$(RESET)"
	@$(MAKE) check
	@echo "$(YELLOW)Checking commit messages...$(RESET)"
	@git log --oneline -10 | head -5
	@echo "$(GREEN)PR checks completed$(RESET)"

# Development shortcuts
dev: format lint test ## Run development workflow (format, lint, test)

ci: format-check lint test.coverage test.architecture ## Run CI workflow

# Default target
all: check test.coverage ## Run all checks and tests