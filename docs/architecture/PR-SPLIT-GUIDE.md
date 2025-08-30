# PR Split Guide for Rules Engine Implementation

## Current Situation

- **Current PR**: 324 lines (exceeds soft limit of 200)
- **Branch**: `docs/rules-architecture-adr`
- **Issues**: 
  - Mixes domain, application, and infrastructure concerns
  - Documents features that don't exist yet
  - Violates DDD principles

## Recommended PR Structure

### PR #1: Fix ADR-009 Domain Violations
**Branch**: `fix/adr-009-domain-purity`  
**Size**: ~50 lines changed  
**Commit Message**: 
```
fix(docs): correct domain boundary violations in ADR-009

- Remove UI implementation details from domain sections
- Replace infrastructure specifics with abstract ports
- Focus on business capabilities over technical implementation
```

**Changes**:
1. Edit ADR-009 to remove Monaco, drag-and-drop, SSE references from domain
2. Add port definitions section
3. Move infrastructure details to "Future Implementation" section

---

### PR #2: Domain Foundation for Rules Engine
**Branch**: `feat/rules-domain-foundation`  
**Size**: ~150 lines  
**Commit Message**:
```
feat(domain): add rules engine value objects and aggregates

- Add RuleId, RuleCondition, RuleVersion value objects
- Implement RuleSet aggregate with state management
- Define validation and compilation domain logic
- Add comprehensive unit tests for domain invariants
```

**Files**:
```
src/domain/rules/
├── __init__.py
├── value_objects.py  # RuleId, RuleCondition, RuleVersion
├── rule_set.py       # RuleSet aggregate
├── events.py         # RulePublished, RuleValidated events
└── errors.py         # Domain-specific exceptions

tests/unit/domain/rules/
├── test_value_objects.py
└── test_rule_set.py
```

---

### PR #3: Application Layer Ports and Use Cases
**Branch**: `feat/rules-application-layer`  
**Size**: ~120 lines  
**Commit Message**:
```
feat(application): add rules engine ports and use cases

- Define RuleRepository and RuleCompiler ports
- Implement EditRule and PublishRule use cases
- Add RuleMetricsProvider port for analytics
- Ensure clean separation from infrastructure
```

**Files**:
```
src/application/rules/
├── __init__.py
├── ports.py          # Abstract interfaces
└── use_cases/
    ├── __init__.py
    ├── edit_rule.py
    ├── publish_rule.py
    └── validate_rule.py

tests/unit/application/rules/
└── test_use_cases.py  # With mocked ports
```

---

### PR #4: Infrastructure Adapters
**Branch**: `feat/rules-infrastructure`  
**Size**: ~180 lines  
**Commit Message**:
```
feat(infra): implement rules engine repository and cache

- Add PostgreSQL rule repository with tenant isolation
- Implement Redis-based compiled rule cache
- Create rule compiler with checksum validation
- Add integration tests with real databases
```

**Files**:
```
src/infrastructure/rules/
├── __init__.py
├── postgres_rule_repository.py
├── redis_rule_cache.py
└── yaml_rule_compiler.py

tests/integration/rules/
├── test_rule_repository.py
└── test_rule_cache.py
```

---

### PR #5: API Endpoints
**Branch**: `feat/rules-api-endpoints`  
**Size**: ~140 lines  
**Commit Message**:
```
feat(api): add rules engine REST endpoints

- Implement CRUD endpoints for rule management
- Add validation endpoint with real-time feedback
- Include idempotency and tenant context
- Add OpenAPI documentation
```

**Files**:
```
apps/api/routers/rules.py
apps/api/dependencies/rules.py
tests/integration/api/test_rules_endpoints.py
packages/contracts/openapi-rules.yaml
```

---

### PR #6: Frontend Components (Optional - Infrastructure)
**Branch**: `feat/rules-frontend`  
**Size**: ~200 lines  
**Commit Message**:
```
feat(web): add rule editor and analytics components

- Implement rule editor component with syntax highlighting
- Add real-time validation feedback display
- Create rule effectiveness dashboard
- Add E2E tests for rule editing flow
```

**Files**:
```
apps/web/components/rules/
├── RuleEditor.tsx
├── RuleValidator.tsx
├── RuleAnalytics.tsx
└── RuleBuilder.tsx

apps/web/hooks/
└── useRuleValidation.ts

tests/e2e/rules/
└── rule-editing.spec.ts
```

---

## Implementation Order

1. **Week 1**: Fix ADR + Domain Foundation
2. **Week 2**: Application Layer + Infrastructure
3. **Week 3**: API + Frontend

## Review Checklist for Each PR

### Domain PRs
- [ ] No infrastructure imports
- [ ] All value objects are immutable
- [ ] Aggregates enforce invariants
- [ ] Comprehensive unit tests
- [ ] No framework dependencies

### Application PRs
- [ ] Only abstract ports (no concrete implementations)
- [ ] Use cases orchestrate domain objects
- [ ] Tests use mocked ports
- [ ] Clean separation of concerns

### Infrastructure PRs
- [ ] Implements application ports
- [ ] Handles all technical concerns
- [ ] Integration tests with real services
- [ ] Proper error handling and logging

### API PRs
- [ ] Uses dependency injection for ports
- [ ] Includes idempotency handling
- [ ] Proper tenant isolation
- [ ] OpenAPI documentation updated

## Git Workflow

```bash
# Start from main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feat/rules-domain-foundation

# Make changes
# ... edit files ...

# Commit with conventional format
git add src/domain/rules/
git commit -m "feat(domain): add rules engine value objects and aggregates

- Add RuleId, RuleCondition, RuleVersion value objects
- Implement RuleSet aggregate with state management
- Define validation and compilation domain logic"

# Push and create PR
git push origin feat/rules-domain-foundation
```

## Architecture Validation

Add this test to prevent future violations:

```python
# tests/architecture/test_rules_layers.py
def test_rules_domain_purity():
    """Ensure rules domain has no infrastructure dependencies"""
    domain_path = Path('src/domain/rules')
    
    for py_file in domain_path.glob('**/*.py'):
        content = py_file.read_text()
        
        # Check for infrastructure imports
        assert 'monaco' not in content.lower()
        assert 'fastapi' not in content
        assert 'sqlalchemy' not in content
        assert 'redis' not in content
        assert 'sse' not in content.lower()
        
        # Check for proper imports
        for line in content.split('\n'):
            if line.startswith('from ') or line.startswith('import '):
                assert 'infrastructure' not in line
                assert 'application' not in line
```

## Success Criteria

Each PR should:
1. **Pass CI/CD** - All tests green
2. **Stay under 200 lines** - Focused changes
3. **Follow conventions** - Commit messages, code style
4. **Maintain architecture** - Clean layer separation
5. **Include tests** - Appropriate for the layer

## Notes

- The features mentioned in ADR-009 (Monaco, SSE, drag-and-drop) are valid but should be documented as infrastructure choices, not domain features
- Consider creating ADR-010 specifically for "Frontend Infrastructure Choices"
- The commit `a49de41` mentioned in the ADR appears to be fictional as these features don't exist in the codebase yet