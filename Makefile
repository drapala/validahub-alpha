.PHONY: help install lint format test test-unit test-verbose test-docker coverage clean docker-build

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install package in editable mode with dev dependencies
	pip install -e .[dev]

lint:  ## Run linting with ruff
	ruff check src tests
	mypy src

format:  ## Format code with black and ruff
	black src tests
	ruff check --fix src tests

test:  ## Run all tests with pytest (Docker fallback for portability)
	@if command -v docker >/dev/null 2>&1; then \
		echo "🐳 Running tests in Docker container..."; \
		docker compose run --rm dev pytest -q tests/; \
	elif command -v python3 >/dev/null 2>&1 && python3 -c "import pytest" 2>/dev/null; then \
		echo "🐍 Running tests with local Python..."; \
		python3 -m pytest -q tests/; \
	elif [ -d venv ] && [ -f venv/bin/python ]; then \
		echo "🐍 Running tests with venv..."; \
		venv/bin/python -m pytest -q tests/; \
	else \
		echo "⚠️  No test runner available. Install Docker or Python with pytest."; \
		exit 2; \
	fi

test-unit:  ## Run only unit tests
	@if command -v docker >/dev/null 2>&1; then \
		docker compose run --rm dev pytest -q -m unit tests/; \
	else \
		pytest -q -m unit; \
	fi

test-verbose:  ## Run tests with verbose output
	@if command -v docker >/dev/null 2>&1; then \
		docker compose run --rm dev pytest -v --tb=short tests/; \
	else \
		pytest -v --tb=short; \
	fi

coverage:  ## Run tests with coverage report
	coverage run -m pytest -q
	coverage report
	coverage html
	@echo "Coverage report available at htmlcov/index.html"

clean:  ## Clean up cache and build artifacts
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache
	rm -rf build dist *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

docker-build:  ## Build the Docker test image
	docker compose build dev

test-docker:  ## Force run tests in Docker (useful for CI/CD)
	docker compose run --rm dev pytest -q tests/

test-docker-domain:  ## Run domain tests in Docker
	docker compose run --rm test-domain

