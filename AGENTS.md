# Repository Guidelines

## Project Structure & Module Organization
- `packages/domain/`: Domain value objects (pure, side‑effect free).
- `packages/application/`: Use cases and ports (integration boundaries).
- `tests/`: Pytest suite organized by layer (e.g., `tests/unit/domain/`).
- `pytest.ini`: Pytest config (paths, markers).
- Other: `CLAUDE.md` (vision/notes), `.vh`, `.claude`, IDE configs.

## Build, Test, and Development Commands
- With Makefile (recommended):
  - `make test`: Run full suite (`PYTHONPATH=packages pytest -v`).
  - `make unit`: Run unit tests only (`-m unit`).
  - `make cov`: Run tests with coverage (fails under 80%).
  - `make clean`: Remove caches/coverage artifacts.
- Direct commands:
  - All tests: `PYTHONPATH=packages pytest -v`.
  - Marker/file focus: `pytest -m unit`, `pytest -k TenantId`, or `pytest tests/unit/domain/test_value_objects.py`.
  - Coverage: `pytest --cov=packages --cov-report=term-missing`.

## Coding Style & Naming Conventions
- Python: 4‑space indent, descriptive names, keep lines readable (<100 chars).
- Types: use type hints for public APIs and dataclasses; prefer `@dataclass(frozen=True)` for value objects.
- Modules: snake_case filenames; classes in PascalCase; functions/vars in snake_case.
- Imports: absolute from layer roots (e.g., `from domain.value_objects import JobId`).

## Testing Guidelines
- Frameworks: `pytest` with Hypothesis available for property tests.
- Layout: mirror code layers (e.g., `tests/unit/application/...`).
- Naming: files `test_*.py`; classes `Test*`; functions `test_*`.
- Write unit tests for domain logic; add property‑based tests where invariants exist (e.g., id normalization, key formats).

## Commit & Pull Request Guidelines
- Style: Conventional Commits (e.g., `feat(domain): add JobId.from_string`).
- Commits: small, focused; include rationale when behavior changes.
- PRs: clear description, linked issues, test coverage for changes, and examples/screenshots when relevant.

## CI & Coverage
- CI: GitHub Actions runs on push/PR (`.github/workflows/ci.yml`).
- Steps: set up Python, install dev deps, run `make cov`.
- Coverage: target >= 80% (enforced by `make cov`).

## Architecture Overview
- Approach: lightweight DDD.
  - Domain: pure logic and value objects only.
  - Application: orchestrates use cases via ports; keep I/O at edges.
- Principle: keep domain independent of frameworks; prefer immutable value objects and explicit validation.
