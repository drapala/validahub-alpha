# ADR-009 Refactored Sections (DDD-Compliant)

## Suggested Replacements for ADR-009 Violations

### REPLACE Lines 73, 102, 108, 185-187

**Current (Violates DDD):**
```markdown
- **Developer Experience**: Visual editor with Monaco, drag-and-drop builder, real-time validation
```

**Refactored (DDD-Compliant):**
```markdown
### Domain Capabilities
- **Rule Authoring**: Support for complex validation rule definitions with syntax validation
- **Rule Composition**: Ability to combine multiple conditions and actions into rule sets  
- **Live Validation**: Real-time syntax and semantic validation of rule definitions

### Application Ports (Abstract Interfaces)
- **RuleEditorPort**: Interface for rule editing operations (get, validate, save drafts)
- **RuleBuilderPort**: Interface for visual rule composition (combine conditions/actions)
- **ValidationFeedbackPort**: Interface for real-time validation results streaming

### Infrastructure Implementations (Separate ADR)
- See ADR-010 for frontend implementation choices (Monaco, drag-and-drop, SSE)
```

---

### REPLACE Section "7. Frontend Developer (Completed: commit a49de41)"

**Current (Mixes Layers):**
```markdown
#### 7. Frontend Developer (Completed: commit a49de41)
- **Deliverables**: Next.js editor, Monaco integration, visual analytics, SSE
- **Key Decisions**: Real-time validation feedback, drag-and-drop rule builder
- **Files**: React components, Playwright E2E tests, responsive dashboard
```

**Refactored (Proper Separation):**
```markdown
#### 7. UI/UX Port Implementation
- **Domain Deliverables**: 
  - Rule editing capabilities via RuleEditorPort
  - Rule composition logic via RuleBuilderPort  
  - Metrics subscription via RuleMetricsPort
  
- **Application Integration**:
  - Use cases consume ports without knowing implementation
  - Port adapters handle UI-specific concerns
  
- **Infrastructure Choices** (See ADR-010):
  - Web framework and component library selection
  - Editor component implementation details
  - Real-time communication transport mechanism
```

---

### ADD New Section: "Port and Adapter Architecture"

```markdown
## Port and Adapter Architecture

### Domain Core (No External Dependencies)
```python
# Pure business logic - knows nothing about UI or infrastructure
class RuleSet:
    def validate_syntax(self) -> ValidationResult
    def compile_to_ir(self) -> IntermediateRepresentation
    def check_compatibility(self, version: RuleVersion) -> bool
```

### Application Ports (Abstract Interfaces)
```python
# Abstractions that domain operations need
class RuleEditorPort(ABC):
    @abstractmethod
    async def get_rule_content(self, rule_id: RuleId) -> str
    
    @abstractmethod
    async def validate_syntax(self, content: str) -> ValidationResult

class RuleMetricsPort(ABC):
    @abstractmethod
    async def stream_metrics(self, rule_id: RuleId) -> AsyncIterator[Metric]
```

### Infrastructure Adapters (Concrete Implementations)
```python
# Specific technology choices - can be swapped
class MonacoEditorAdapter(RuleEditorPort):
    """Monaco-specific implementation"""
    
class SSEMetricsAdapter(RuleMetricsPort):
    """Server-Sent Events implementation"""
    
class WebSocketMetricsAdapter(RuleMetricsPort):
    """WebSocket alternative implementation"""
```

This architecture ensures:
1. Domain logic is pure and testable
2. Infrastructure can be changed without affecting business logic
3. Clear separation of concerns across layers
```

---

### REPLACE "Positive Benefits" Section Line 73

**Current:**
```markdown
- **Developer Experience**: Visual editor with Monaco, drag-and-drop builder, real-time validation
```

**Refactored:**
```markdown
- **Developer Experience**: Comprehensive rule authoring with syntax validation, visual composition support, and real-time feedback (implementation details in infrastructure layer)
```

---

### ADD Architecture Compliance Checklist

```markdown
## Architecture Compliance Checklist

### Domain Layer ✓
- [ ] No imports from application or infrastructure layers
- [ ] No framework-specific code (FastAPI, SQLAlchemy, React)
- [ ] Only standard library imports and domain imports
- [ ] Pure business logic and rules

### Application Layer ✓
- [ ] No imports from infrastructure layer
- [ ] Defines abstract ports (interfaces)
- [ ] Use cases orchestrate domain and ports
- [ ] No concrete implementations

### Infrastructure Layer ✓
- [ ] Implements application ports
- [ ] Contains all framework-specific code
- [ ] Handles external integrations
- [ ] Can import from domain and application

### Testing ✓
- [ ] Domain tests use no mocks (pure logic)
- [ ] Application tests mock only ports
- [ ] Infrastructure tests may use real implementations
- [ ] Architecture tests validate layer dependencies
```

---

## Summary of Changes

1. **Remove** all references to specific UI technologies (Monaco, drag-and-drop) from domain sections
2. **Move** infrastructure choices to separate sections or ADRs
3. **Add** clear port definitions in application layer
4. **Emphasize** that frontend components are infrastructure adapters
5. **Include** architecture validation checklist

These changes ensure ADR-009 focuses on business capabilities and architectural patterns rather than implementation details, maintaining proper DDD boundaries.