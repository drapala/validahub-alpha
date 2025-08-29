# Job Aggregate Design

## Architecture Decision Record (ADR)

**Decision**: Implement Job aggregate as an immutable state machine with minimal states following DDD principles.

**Trade-offs**:
- **Pro**: Pure domain model with no framework dependencies ensures testability and portability
- **Pro**: Immutable design prevents accidental state corruption and simplifies reasoning
- **Pro**: Clear state transitions protect domain invariants
- **Con**: Additional memory allocation for state changes (acceptable for our scale)
- **Con**: Requires explicit state management in application layer

## State Machine

### States and Transitions

```
┌────────────┐
│  SUBMITTED │──────────┐
└────────────┘          │
      │                 ▼
      │          ┌─────────────┐
      └─────────▶│   RUNNING   │
                 └─────────────┘
                   │         │
                   ▼         ▼
            ┌──────────┐  ┌────────┐
            │COMPLETED │  │ FAILED │
            └──────────┘  └────────┘
                             │
                             ▼
                       ┌──────────┐
                       │ RETRYING │
                       └──────────┘
                             │
                             └──────┐
                                    │
                                    ▼
                              [RUNNING]
```

### State Transition Table

| From State | To State  | Method     | Business Rule                    |
|------------|-----------|------------|----------------------------------|
| SUBMITTED  | RUNNING   | start()    | Initial job execution            |
| RUNNING    | COMPLETED | complete() | Successful processing            |
| RUNNING    | FAILED    | fail()     | Processing error occurred        |
| FAILED     | RETRYING  | retry()    | Retry after failure              |
| RETRYING   | RUNNING   | start()    | Resume after retry preparation   |

## Domain Components

### Value Objects (Immutable, Local Invariants)

```python
# JobId: UUID validation only
JobId(value: UUID)

# TenantId: Normalization and validation
TenantId(value: str)  # lowercase, 3-50 chars, no control chars
```

### Aggregate Signatures

```python
class Job:
    # Factory method
    @classmethod
    def create(cls, tenant_id: TenantId) -> Job
    
    # State transitions (return new instances)
    def start() -> Job
    def complete() -> Job
    def fail() -> Job
    def retry() -> Job
    
    # Query methods
    def is_terminal() -> bool
    def can_retry() -> bool
```

### Domain Errors

```python
class DomainError(Exception)  # Base for all domain errors
class InvalidStateTransitionError(DomainError)  # Invalid state transition
```

## Domain Event Schema (CloudEvents 1.0)

```json
{
  "specversion": "1.0",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "validahub/job-aggregate",
  "type": "validahub.job.submitted",
  "time": "2025-08-29T10:00:00Z",
  "datacontenttype": "application/json",
  "data": {
    "tenant_id": "tenant_123",
    "job_id": "6c0e1234-5678-90ab-cdef-111111111111",
    "schema_version": "1.0.0"
  }
}
```

Event types:
- `validahub.job.submitted`
- `validahub.job.started`
- `validahub.job.completed`
- `validahub.job.failed`
- `validahub.job.retrying`

## Dependency Map

```
src/
├── domain/           # Pure domain, no external dependencies
│   ├── job.py       # Uses only: errors, value_objects
│   ├── errors.py    # No dependencies
│   └── value_objects.py  # No domain dependencies
├── application/      # Can import domain
│   └── use_cases/   # Orchestrates domain + ports
└── infra/           # Can import application + domain
    └── adapters/    # Implements ports
```

## Out of Scope for Value Objects

The following are NOT handled by Value Objects (belong in Aggregate/Service):

1. **FileReference path resolution** → Infrastructure concern
2. **RulesProfile compatibility checking** → Domain Service
3. **ProcessingCounters aggregation** → Aggregate method
4. **Idempotency key TTL** → Repository policy
5. **Tenant path mapping** → Application Service
6. **Job timeout/expiration** → Domain Service with time provider

## Testing Strategy

### RED Phase (Behavior)
- Focus on public API and state transitions
- No implementation details in test names
- Test invalid transitions raise appropriate errors

### GREEN Phase (Minimal)
- Implement just enough to pass tests
- Use dataclass with frozen=True for immutability
- Simple if/else for state validation

### REFACTOR Phase (Quality)
- Add __slots__ for memory optimization (if needed)
- Implement serialization support (if needed)
- Performance optimizations without breaking contracts

## Implementation Notes

1. **Immutability**: Used `@dataclass(frozen=True)` with `replace()` for state changes
2. **Pure Domain**: No logging or framework dependencies in domain layer
3. **Timezone Safety**: Enforced timezone-aware datetime for `created_at`
4. **PII Protection**: Error messages contain no user data, only state names
5. **Terminal States**: COMPLETED and FAILED are terminal (no further transitions)