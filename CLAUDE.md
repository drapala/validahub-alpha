# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Quick Start
```bash
make up                 # Start PostgreSQL, Redis, MinIO, OpenTelemetry
make db.migrate         # Run Alembic migrations
make contracts.gen      # Generate TypeScript types from OpenAPI
make dev                # Start FastAPI development server
```

### Testing
```bash
# Run all tests with coverage
pytest tests/ -v --tb=short --cov=packages --cov-report=term-missing

# Run specific test categories
pytest tests/unit/ -v --tb=short              # Unit tests only
pytest tests/unit/domain/ -v --tb=short        # Domain layer tests
pytest tests/integration/ -v --tb=short        # Integration tests
pytest tests/architecture/ -v --tb=short       # Architecture validation

# Run single test file
pytest tests/unit/domain/test_job.py -v --tb=short

# Run with Docker
docker-compose run test                        # All tests
docker-compose run test-domain                 # Domain tests only
```

### Code Quality
```bash
make lint              # Run ruff linting
make format            # Format with black and ruff
make check.arch        # Validate layer dependencies
ruff check src/ tests/ # Check specific directories
black src/ tests/      # Format specific directories
```

### Infrastructure Management
```bash
make up                # Start all services
make down              # Stop all services  
make db.reset          # Reset database (asks for confirmation)
make logs              # Show Docker logs
make ps                # Show running containers
```

## Architecture Overview

### Domain-Driven Design with Clean Architecture

The codebase follows strict DDD principles with hexagonal architecture (Ports & Adapters):

```
src/
├── domain/           # Pure business logic - NO framework dependencies
│   ├── job.py       # Job aggregate with state transitions
│   ├── value_objects.py  # Immutable value objects (TenantId, JobId, etc.)
│   └── errors.py    # Domain-specific exceptions
│
├── application/      # Use cases and ports - NO infrastructure imports
│   ├── use_cases/   # Business operations (submit_job, retry_job, get_job)
│   ├── ports.py     # Abstract interfaces (JobRepository, EventBus, etc.)
│   └── idempotency/ # Idempotency handling for safe retries
│
└── infrastructure/   # Concrete implementations - CAN import from domain/application
    ├── repositories/ # Database access (SQLAlchemy)
    ├── event_bus/    # Redis event streaming
    ├── auth/         # JWT authentication
    └── middleware/   # FastAPI middleware
```

**Critical Rules:**
- `domain/` NEVER imports from `application/` or `infrastructure/`
- `application/` NEVER imports from `infrastructure/`
- `infrastructure/` can import from both `domain/` and `application/`
- Architecture tests in `tests/architecture/` enforce these rules

### Event Sourcing & Multi-Tenancy

Every operation generates CloudEvents with full audit trail:
- All data includes `tenant_id` for complete isolation
- Events follow CloudEvents 1.0 specification
- Idempotency keys prevent duplicate operations
- Complete audit log with who/when/what/request_id

### Key Domain Concepts

**Job Aggregate:**
- Central entity representing CSV validation/correction work
- State machine: queued → running → succeeded/failed
- Immutable after creation except for state transitions
- Contains counters for errors/warnings/total items

**Value Objects:**
- `TenantId`: Multi-tenant isolation identifier
- `JobId`: Unique job identifier (UUID)
- `IdempotencyKey`: Prevents duplicate submissions
- `RulesProfileId`: Marketplace rule version tracking

## Testing Strategy

### Test Organization
```
tests/
├── unit/           # Fast, isolated tests with mocks
│   ├── domain/     # Pure domain logic tests
│   ├── application/# Use case tests with mocked ports
│   └── compliance/ # LGPD compliance tests
├── integration/    # Tests with real databases/services
└── architecture/   # Layer dependency validation
```

### Golden Tests
For rule engine outputs, use golden tests that compare actual output against expected fixtures:
- Input: `tests/fixtures/input/*.csv`
- Expected: `tests/fixtures/expected/*.csv`
- Prevents unintended format changes

## Security & Compliance

### LGPD (Brazilian GDPR) Compliance
- Anonymous benchmarking without PII
- Data retention policies enforced
- Right to deletion implemented
- Audit trails for all data access
- Consent management system

### Security Requirements
- `Idempotency-Key` header required for POST /jobs
- Rate limiting per tenant via Redis
- CSV injection prevention (blocks formulas starting with =+-@)
- JWT authentication with scopes
- Secrets management via Doppler/Vault (never in .env)

## Conventional Commits & PR Guidelines

### Commit Format
```
type(scope): description

Types: feat, fix, chore, refactor, docs, test, perf, build, ci
Scopes: domain, application, infra, api, web, contracts, telemetry
```

### PR Size Limits
- Soft limit: 200 lines
- Hard limit: 400 lines (CI fails above)
- Override with `size/override` label + justification

### Branch Naming
```
feat/domain-job-validation
fix/api-rate-limiting
chore/deps-update
refactor/application-ports
```

## Telemetry & Observability

### Structured Logging
All logs must include:
- `tenant_id`: Multi-tenant context
- `request_id`: Correlation across services
- `trace_id`: OpenTelemetry trace context
- Use `src/shared/logging/` for consistent formatting

### Metrics (SLOs)
- Job success rate: ≥ 99%
- P95 latency: ≤ 30 seconds
- CSV processing: 50k lines ≤ 3 seconds

## API Development

### FastAPI Structure
```python
# apps/api/routers/jobs.py
@router.post("/jobs")
async def submit_job(
    request: SubmitJobRequest,
    idempotency_key: str = Header(...),
    tenant_id: str = Depends(get_tenant_id),
    job_repository: JobRepository = Depends(get_job_repository)
):
    # Use case instantiation and execution
    pass
```

### OpenAPI Contract
- Contract-first development
- OpenAPI 3.1 spec defines all endpoints
- Types generated automatically
- Located at `packages/contracts/openapi.yaml`

## Working with Rules Engine

### Rule Pack Structure
```
packages/rules/
  marketplace/
    mercado_livre/1.0/
      mapping.yaml     # Field mappings
      ruleset.yaml     # Validation rules
```

### Rule Versioning
- SemVer: major.minor.patch
- Patch versions auto-applied
- Minor versions with shadow period
- Major versions require opt-in

## Database Migrations

### Using Alembic
```bash
# Create new migration
alembic revision -m "Add job_metadata column"

# Run migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1
```

### Migration Requirements
- All migrations must be reversible
- Include both upgrade and downgrade functions
- Test rollback before merging

## Docker Development

### Service Ports
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- MinIO: `localhost:9000` (console: `9001`)
- Jaeger UI: `http://localhost:16686`
- FastAPI: `http://localhost:8000`

### Database Credentials (Development Only)
- Database: `validahub`
- User: `validahub`
- Password: `validahub123`

## Common Development Tasks

### Adding a New Use Case
1. Define the use case in `src/application/use_cases/`
2. Create required ports in `src/application/ports.py`
3. Implement ports in `src/infrastructure/`
4. Write unit tests with mocked ports
5. Add integration tests with real implementations

### Modifying Domain Logic
1. Update domain entities in `src/domain/`
2. Ensure no framework imports
3. Write comprehensive unit tests
4. Run architecture tests: `pytest tests/architecture/`

### Adding API Endpoints
1. Update OpenAPI spec if contract changes
2. Implement handler in `apps/api/routers/`
3. Use dependency injection for repositories
4. Include idempotency and tenant context
5. Add integration tests

## Performance Considerations

### Database Optimization
- Use indexes for tenant_id + frequently queried fields
- Consider partitioning for large tables
- Use JSONB for flexible schema fields
- Implement connection pooling

### Caching Strategy
- Redis for rate limiting
- Cache rule compilations
- Session-based caching for validations
- Use TTLs to prevent stale data

## Debugging Tips

### Structured Logging
```python
from src.shared.logging import get_logger

logger = get_logger(__name__)
logger.info("Processing job", job_id=job.id, tenant_id=tenant_id)
```

### Correlation IDs
Track requests across services using X-Request-Id header

### Docker Logs
```bash
docker-compose logs -f api     # Follow API logs
docker-compose logs postgres    # Check database logs
```

## Important File Locations

- API Implementation: `apps/api/main.py`
- Domain Models: `src/domain/job.py`
- Use Cases: `src/application/use_cases/`
- Database Models: `src/infrastructure/repositories/`
- Configuration: `src/application/config.py`
- Tests: `tests/unit/`, `tests/integration/`
- Documentation: `docs/architecture/`, `docs/adr/`