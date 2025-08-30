# Rules Engine Architecture Review

**Date:** 2025-08-30  
**Review of:** ADR-009 Smart Rules Engine Architecture  
**Status:** Requires Refactoring  

## Executive Summary

The ADR-009 document describes important business capabilities but violates DDD principles by mixing domain, application, and infrastructure concerns. This review provides guidance for proper architectural separation.

## Critical Issues Identified

### 1. Domain Boundary Violations

The ADR incorrectly places infrastructure concerns in the domain layer:

**Current Issues:**
- Line 73: "Visual editor with Monaco" - UI implementation detail
- Line 108: "Visual rule builder with drag-and-drop" - UI interaction pattern  
- Lines 185-187: Frontend implementation details mixed with domain logic

**DDD Principle Violated:** Domain layer must be pure business logic without framework dependencies.

### 2. Layer Dependency Violations

The document suggests direct coupling between:
- Domain → UI (Monaco editor)
- Domain → Transport (SSE)
- Domain → Frontend Framework (Next.js)

**Clean Architecture Principle Violated:** Dependencies must flow inward (Infrastructure → Application → Domain).

## Correct Architectural Structure

### Domain Layer (Pure Business Logic)

```python
# src/domain/rules/value_objects.py
from dataclasses import dataclass
from typing import Optional
import re

@dataclass(frozen=True)
class RuleId:
    """Unique identifier for a rule"""
    value: str
    
    def __post_init__(self):
        if not re.match(r'^[a-z0-9\-]{8,64}$', self.value):
            raise ValueError("Invalid RuleId format")

@dataclass(frozen=True)
class RuleCondition:
    """Business rule condition - no UI knowledge"""
    field_path: str
    operator: str  # 'equals', 'greater_than', etc.
    value: Any
    
    def evaluate(self, data: dict) -> bool:
        """Pure business logic for condition evaluation"""
        pass

@dataclass(frozen=True)
class RuleVersion:
    """Semantic versioning for rules"""
    major: int
    minor: int
    patch: int
    
    def is_compatible_with(self, other: 'RuleVersion') -> bool:
        """Business logic for version compatibility"""
        return self.major == other.major

# src/domain/rules/rule_set.py
class RuleSet:
    """Rule set aggregate - manages rule lifecycle"""
    
    def __init__(self, tenant_id: TenantId, rules: List[Rule]):
        self._tenant_id = tenant_id
        self._rules = rules
        self._state = RuleSetState.DRAFT
        self._events = []
    
    def validate_syntax(self) -> ValidationResult:
        """Business validation - no UI concerns"""
        errors = []
        for rule in self._rules:
            if not rule.is_valid():
                errors.append(ValidationError(rule.id, "Invalid rule syntax"))
        return ValidationResult(errors)
    
    def publish(self) -> None:
        """State transition with domain event"""
        if self._state != RuleSetState.DRAFT:
            raise InvalidStateTransition()
        
        validation = self.validate_syntax()
        if not validation.is_valid():
            raise ValidationException(validation.errors)
        
        self._state = RuleSetState.PUBLISHED
        self._events.append(RuleSetPublished(
            tenant_id=self._tenant_id,
            rule_set_id=self.id,
            version=self.version
        ))
```

### Application Layer (Use Cases and Ports)

```python
# src/application/ports.py
from abc import ABC, abstractmethod

class RuleRepository(ABC):
    """Port for rule persistence - no database specifics"""
    
    @abstractmethod
    async def get_by_id(self, rule_id: RuleId, tenant_id: TenantId) -> Optional[RuleSet]:
        pass
    
    @abstractmethod
    async def save(self, rule_set: RuleSet) -> None:
        pass

class RuleCompiler(ABC):
    """Port for rule compilation - no implementation details"""
    
    @abstractmethod
    async def compile(self, rule_set: RuleSet) -> CompiledRuleSet:
        pass

class RuleMetricsProvider(ABC):
    """Port for metrics - no transport specifics"""
    
    @abstractmethod
    async def get_effectiveness(self, rule_id: RuleId) -> EffectivenessMetrics:
        pass
    
    @abstractmethod
    async def subscribe_to_updates(self, rule_id: RuleId) -> AsyncIterator[MetricUpdate]:
        """Returns metric updates - transport agnostic"""
        pass

# src/application/use_cases/edit_rule.py
class EditRuleUseCase:
    """Use case orchestrates domain and ports"""
    
    def __init__(
        self,
        rule_repository: RuleRepository,
        rule_compiler: RuleCompiler,
        event_bus: EventBus
    ):
        self._rule_repository = rule_repository
        self._rule_compiler = rule_compiler
        self._event_bus = event_bus
    
    async def execute(
        self,
        tenant_id: TenantId,
        rule_id: RuleId,
        rule_content: str
    ) -> EditRuleResult:
        # 1. Load aggregate
        rule_set = await self._rule_repository.get_by_id(rule_id, tenant_id)
        if not rule_set:
            raise RuleNotFound(rule_id)
        
        # 2. Parse and validate (domain logic)
        parsed_rule = RuleParser.parse(rule_content)
        rule_set.update_rule(parsed_rule)
        
        # 3. Compile (via port)
        compiled = await self._rule_compiler.compile(rule_set)
        
        # 4. Save (via port)
        await self._rule_repository.save(rule_set)
        
        # 5. Publish events
        for event in rule_set.collect_events():
            await self._event_bus.publish(event)
        
        return EditRuleResult(
            rule_id=rule_id,
            validation_result=rule_set.validate_syntax(),
            compiled_checksum=compiled.checksum
        )
```

### Infrastructure Layer (Concrete Implementations)

```python
# src/infrastructure/repositories/postgres_rule_repository.py
class PostgresRuleRepository(RuleRepository):
    """PostgreSQL implementation of RuleRepository port"""
    
    async def get_by_id(self, rule_id: RuleId, tenant_id: TenantId) -> Optional[RuleSet]:
        # SQL queries, ORM usage, etc.
        pass

# src/infrastructure/web/sse_metrics_adapter.py
class SSEMetricsAdapter(RuleMetricsProvider):
    """SSE implementation of metrics provider"""
    
    async def subscribe_to_updates(self, rule_id: RuleId) -> AsyncIterator[MetricUpdate]:
        # SSE-specific implementation
        async with self._sse_client.connect() as connection:
            async for event in connection:
                yield self._parse_metric_update(event)

# src/infrastructure/ui/monaco_adapter.py
class MonacoEditorAdapter:
    """Adapter for Monaco editor - infrastructure concern"""
    
    def __init__(self, rule_compiler: RuleCompiler):
        self._rule_compiler = rule_compiler
    
    async def provide_syntax_validation(self, content: str) -> List[EditorMarker]:
        """Adapts domain validation to Monaco markers"""
        try:
            parsed = RuleParser.parse(content)
            validation = await self._rule_compiler.validate(parsed)
            return self._convert_to_monaco_markers(validation)
        except ParseError as e:
            return [self._error_to_marker(e)]
```

### Frontend Implementation (Infrastructure)

```typescript
// apps/web/components/RuleEditor.tsx
import { useState, useEffect } from 'react';
import Monaco from '@monaco-editor/react';

export function RuleEditor({ ruleId, tenantId }) {
  // This is infrastructure - uses the API which uses the ports
  const { data: rule } = useQuery(`/api/rules/${ruleId}`);
  
  const handleSave = async (content: string) => {
    // Calls the EditRuleUseCase via API
    await api.put(`/api/rules/${ruleId}`, { content });
  };
  
  return (
    <Monaco
      language="yaml"
      value={rule?.content}
      onChange={handleSave}
      options={{ /* Monaco-specific config */ }}
    />
  );
}

// apps/web/components/RuleAnalyticsDashboard.tsx
export function RuleAnalyticsDashboard({ ruleId }) {
  const [metrics, setMetrics] = useState<MetricUpdate[]>([]);
  
  useEffect(() => {
    // SSE subscription - infrastructure concern
    const eventSource = new EventSource(`/api/rules/${ruleId}/metrics/stream`);
    
    eventSource.onmessage = (event) => {
      const update = JSON.parse(event.data);
      setMetrics(prev => [...prev, update]);
    };
    
    return () => eventSource.close();
  }, [ruleId]);
  
  return <MetricsChart data={metrics} />;
}
```

## Migration Path

### Phase 1: Domain Purity (Priority 1)
1. Extract pure domain models for rules
2. Remove all UI/transport references from domain
3. Define value objects and aggregates

### Phase 2: Port Definition (Priority 2)
1. Define abstract ports in application layer
2. Create use cases using only ports
3. Ensure no infrastructure imports

### Phase 3: Infrastructure Adapters (Priority 3)
1. Implement PostgreSQL repository adapter
2. Create SSE metrics adapter
3. Build Monaco editor integration

### Phase 4: API Integration (Priority 4)
1. Create FastAPI endpoints using use cases
2. Implement dependency injection for ports
3. Add authentication and tenant context

## PR Split Recommendations

The current PR (324 lines) should be split into smaller, focused PRs:

### PR 1: Domain Foundation (Target: ~150 lines)
```
feat(domain): add rules engine value objects and aggregates

- Add RuleId, RuleCondition, RuleVersion value objects
- Implement RuleSet aggregate with state transitions
- Define domain events for rule lifecycle
```

### PR 2: Application Ports (Target: ~100 lines)
```
feat(application): define rules engine ports and use cases

- Add RuleRepository, RuleCompiler, RuleMetricsProvider ports
- Implement EditRule, PublishRule use cases
- Ensure clean separation from infrastructure
```

### PR 3: Infrastructure Adapters (Target: ~180 lines)
```
feat(infra): implement rules engine infrastructure adapters

- Add PostgreSQL rule repository
- Implement Redis-based rule compiler cache
- Create SSE metrics adapter
```

### PR 4: API Endpoints (Target: ~120 lines)
```
feat(api): add rules engine REST endpoints

- Implement CRUD endpoints for rules
- Add SSE endpoint for metrics streaming
- Include idempotency and tenant context
```

### PR 5: Frontend Components (Target: ~200 lines)
```
feat(web): add rule editor and analytics dashboard

- Implement Monaco-based rule editor component
- Create real-time analytics dashboard with SSE
- Add drag-and-drop rule builder UI
```

## Commit Message Issues

Current commit follows conventional commits correctly. However, for future commits:

### Good Examples:
```bash
feat(domain): add RuleSet aggregate with state transitions
fix(application): resolve rule validation edge cases
test(domain): add golden tests for rule compilation
docs(adr): document rules engine architecture decisions
```

### Bad Examples (avoid):
```bash
Added rule engine  # Missing type and scope
feat: rules stuff  # Too vague
FEAT(rules): Add feature  # Wrong capitalization
```

## Architecture Validation Tests

Add these tests to ensure architectural compliance:

```python
# tests/architecture/test_rules_engine_layers.py
def test_domain_has_no_infrastructure_imports():
    """Domain must not import from infrastructure or frameworks"""
    domain_files = Path('src/domain/rules').glob('**/*.py')
    
    for file in domain_files:
        content = file.read_text()
        assert 'monaco' not in content.lower()
        assert 'sse' not in content.lower()
        assert 'fastapi' not in content.lower()
        assert 'sqlalchemy' not in content.lower()

def test_application_has_no_infrastructure_imports():
    """Application must not import from infrastructure"""
    app_files = Path('src/application/rules').glob('**/*.py')
    
    for file in app_files:
        content = file.read_text()
        assert 'from infrastructure' not in content
        assert 'import infrastructure' not in content
```

## Conclusion

The Rules Engine concept is valuable, but the current ADR violates core DDD and Clean Architecture principles. The features mentioned (Monaco editor, drag-and-drop builder, SSE analytics) are infrastructure concerns that should be:

1. **Abstracted** behind ports in the application layer
2. **Implemented** as adapters in the infrastructure layer
3. **Unknown** to the domain layer

This separation ensures:
- Domain logic remains pure and testable
- Infrastructure can be swapped without affecting business logic
- Clear boundaries between what the business needs vs. how it's implemented

## Next Steps

1. **Refactor ADR-009** to focus on domain concepts, not implementation details
2. **Create separate infrastructure ADRs** for UI/transport decisions
3. **Split the PR** into smaller, focused changes as recommended
4. **Implement architecture tests** to prevent future violations
5. **Update CLAUDE.md** with rules engine architectural guidelines