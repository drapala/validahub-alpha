# Changelog

All notable changes to ValidaHub will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### ✨ Features
- feat(domain): establish DDD foundation with multi-tenant value objects
- feat(domain): add Job aggregate with state machine
- feat(application): implement SubmitJobUseCase with idempotency
- feat(logging): implement LGPD-compliant structured logging system
- feat(app): add legacy idempotency adapter with canonicalization at HTTP boundary
- feat(agents): enhance git-pr-validator with automated PR configuration

### 🐛 Bug Fixes
- fix(domain): normalize TenantId with NFKC and enforce t_ prefix pattern
- fix(domain): enforce strict IdempotencyKey (16-128, [-_], CSV formula block)
- fix(ci): add GitHub token permissions for PR workflows

### 🔧 Maintenance
- refactor(project): organize project structure - move docs and scripts to proper folders
- test(domain): update legacy tests for new business rules
- test(domain): property tests for strict IdempotencyKey (Hypothesis)
- test(app): handler accepts legacy keys and generates canonical idempotency keys
- test(compliance): add comprehensive LGPD compliance test suite

### 📚 Documentation
- docs(api): document idempotency policy, legacy mapping and feature flag
- docs(security): add comprehensive security test implementation report
- docs(project): add comprehensive PR guidelines and automation
- docs: add comprehensive README positioning ValidaHub as marketplace intelligence platform

### 🔨 CI/CD
- ci(pipeline): enhance CI/CD with proper quality gates and PR validation
- ci: add conventional commits validation
- ci: add PR size check workflow
- ci: add security scanning with Bandit and Safety

### 🏗️ Infrastructure
- build: add Docker setup for development and testing
- build: add comprehensive Makefile with test commands
- build: add pyproject.toml with project metadata

---

## [0.1.0-alpha.1] - Coming Soon

Initial alpha release with core DDD foundation:
- Multi-tenant value objects with security validation
- Job aggregate with state machine
- LGPD-compliant logging
- Idempotency support with legacy compatibility
- CI/CD pipeline with quality gates

---

## Release Types

- **Major**: Breaking changes (1.0.0, 2.0.0)
- **Minor**: New features (0.1.0, 0.2.0)
- **Patch**: Bug fixes (0.0.1, 0.0.2)
- **Pre-release**: Alpha/Beta/RC (0.1.0-alpha.1, 0.1.0-beta.1, 0.1.0-rc.1)

## Commit Types

- `feat`: New feature (triggers MINOR)
- `fix`: Bug fix (triggers PATCH)
- `feat!` or `fix!`: Breaking change (triggers MAJOR)
- `chore`, `docs`, `style`, `refactor`, `perf`, `test`, `ci`: No version bump

---

[Unreleased]: https://github.com/drapala/validahub-alpha/compare/main...HEAD