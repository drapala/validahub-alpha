# Rules Engine DDD Refactor Plan

## Executive Summary

The current rules engine violates clean architecture by having external dependencies (pandas, numpy, yaml, jsonschema, dateutil) in the domain layer. This refactor plan provides a pragmatic, incremental approach to properly separate concerns while maintaining functionality.

## Current Problems

### Domain Layer Violations
1. **runtime.py**: Uses pandas/numpy for vectorized operations
2. **compiler.py**: Uses yaml/jsonschema for parsing and validation  
3. **ccm.py**: Uses pandas, dateutil for data processing
4. **External imports**: All violate domain purity principle

## Proposed Architecture

### 1. New Directory Structure

```
src/
├── domain/
│   └── rules/
│       ├── value_objects.py          # SemVer, RuleId (existing)
│       ├── entities/                 # Pure domain entities
│       │   ├── rule.py              # Rule entity (pure)
│       │   ├── rule_set.py          # RuleSet aggregate
│       │   ├── ccm_field.py         # CCM field definitions (pure)
│       │   └── execution_result.py  # Execution results (pure)
│       ├── services/                 # Domain services
│       │   ├── rule_validator.py    # Pure validation logic
│       │   └── compatibility.py     # Version compatibility logic
│       └── ports/                    # Domain interfaces
│           ├── rule_compiler.py     # Compiler interface
│           ├── rule_executor.py     # Executor interface
│           └── data_processor.py    # Data processing interface
│
├── application/
│   └── rules/
│       ├── use_cases/
│       │   ├── compile_rules.py     # Orchestrates compilation
│       │   ├── execute_rules.py     # Orchestrates execution
│       │   └── validate_dataset.py  # Dataset validation use case
│       └── services/
│           └── rule_orchestrator.py # Coordinates rule operations
│
└── infrastructure/
    └── rules/
        ├── compilers/
        │   ├── yaml_compiler.py      # YAML to domain (uses yaml/jsonschema)
        │   └── schema_validator.py   # Schema validation implementation
        ├── executors/
        │   ├── pandas_executor.py    # Pandas-based vectorized executor
        │   ├── numpy_executor.py     # NumPy optimizations
        │   └── python_executor.py    # Pure Python fallback
        └── processors/
            ├── pandas_processor.py   # DataFrame operations
            └── csv_processor.py      # CSV I/O handling
```

## 2. Domain Layer Interfaces (Ports)

### Rule Compiler Port
```python
# src/domain/rules/ports/rule_compiler.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.domain.rules.entities import RuleSet, CompilationResult

class RuleCompilerPort(ABC):
    """Interface for rule compilation."""
    
    @abstractmethod
    def compile(self, source: Dict[str, Any]) -> CompilationResult:
        """Compile rules from parsed source."""
        pass
    
    @abstractmethod
    def validate_schema(self, source: Dict[str, Any]) -> bool:
        """Validate rule schema."""
        pass
```

### Rule Executor Port
```python
# src/domain/rules/ports/rule_executor.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from src.domain.rules.entities import RuleSet, ExecutionResult

class RuleExecutorPort(ABC):
    """Interface for rule execution."""
    
    @abstractmethod
    def execute(
        self, 
        ruleset: RuleSet, 
        data: List[Dict[str, Any]]
    ) -> ExecutionResult:
        """Execute rules on data."""
        pass
    
    @abstractmethod
    def execute_vectorized(
        self,
        ruleset: RuleSet,
        data_batch: Any  # Abstract data container
    ) -> ExecutionResult:
        """Execute rules with vectorization."""
        pass
```

### Data Processor Port
```python
# src/domain/rules/ports/data_processor.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Iterator

class DataProcessorPort(ABC):
    """Interface for data processing operations."""
    
    @abstractmethod
    def parse_csv(self, content: str) -> List[Dict[str, Any]]:
        """Parse CSV content to domain format."""
        pass
    
    @abstractmethod
    def apply_transformation(
        self,
        data: List[Dict[str, Any]],
        transformation: str,
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply transformation to data."""
        pass
    
    @abstractmethod
    def batch_process(
        self,
        data: List[Dict[str, Any]],
        batch_size: int
    ) -> Iterator[List[Dict[str, Any]]]:
        """Process data in batches."""
        pass
```

## 3. Domain Entities (Pure)

### Rule Entity
```python
# src/domain/rules/entities/rule.py
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

class RuleType(Enum):
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    SUGGESTION = "suggestion"

@dataclass(frozen=True)
class Rule:
    """Pure domain rule entity."""
    
    id: str
    field: str
    type: RuleType
    condition: 'Condition'
    action: 'Action'
    message: str
    severity: str = "error"
    
    def matches(self, value: Any) -> bool:
        """Check if value matches condition (pure logic)."""
        return self.condition.evaluate(value)
    
    def apply(self, value: Any) -> Any:
        """Apply action to value (pure transformation)."""
        return self.action.execute(value)
```

### Execution Result Entity
```python
# src/domain/rules/entities/execution_result.py
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class Violation:
    """Rule violation (pure data)."""
    rule_id: str
    field: str
    row_index: int
    message: str
    severity: str
    actual_value: Any
    expected_value: Optional[Any] = None

@dataclass
class ExecutionResult:
    """Execution result (pure data)."""
    
    violations: List[Violation] = field(default_factory=list)
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    
    @property
    def has_errors(self) -> bool:
        return any(v.severity == "error" for v in self.violations)
    
    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")
```

## 4. Infrastructure Implementations

### YAML Compiler Adapter
```python
# src/infrastructure/rules/compilers/yaml_compiler.py
import yaml
import jsonschema
from typing import Dict, Any
from src.domain.rules.ports import RuleCompilerPort
from src.domain.rules.entities import RuleSet, CompilationResult

class YamlRuleCompiler(RuleCompilerPort):
    """YAML compiler implementation."""
    
    def __init__(self, schema_path: str):
        self.schema = self._load_schema(schema_path)
    
    def compile(self, source: Dict[str, Any]) -> CompilationResult:
        """Compile YAML to domain entities."""
        # Convert YAML structure to domain entities
        # All YAML/JSON specific logic here
        rules = self._parse_rules(source)
        return CompilationResult(
            ruleset=RuleSet(rules=rules),
            stats=self._calculate_stats(rules)
        )
    
    def validate_schema(self, source: Dict[str, Any]) -> bool:
        """Validate using jsonschema."""
        try:
            jsonschema.validate(source, self.schema)
            return True
        except jsonschema.ValidationError:
            return False
```

### Pandas Executor Adapter
```python
# src/infrastructure/rules/executors/pandas_executor.py
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from src.domain.rules.ports import RuleExecutorPort
from src.domain.rules.entities import RuleSet, ExecutionResult

class PandasRuleExecutor(RuleExecutorPort):
    """Pandas-based vectorized executor."""
    
    def execute(
        self,
        ruleset: RuleSet,
        data: List[Dict[str, Any]]
    ) -> ExecutionResult:
        """Execute rules using pandas for vectorization."""
        df = pd.DataFrame(data)
        result = ExecutionResult()
        
        for rule in ruleset.rules:
            if rule.type == RuleType.VALIDATION:
                violations = self._validate_vectorized(df, rule)
                result.violations.extend(violations)
        
        return result
    
    def _validate_vectorized(self, df: pd.DataFrame, rule: Rule):
        """Vectorized validation using pandas."""
        # Pandas-specific optimizations here
        mask = self._evaluate_condition(df, rule.condition)
        violations = []
        for idx in df[~mask].index:
            violations.append(Violation(
                rule_id=rule.id,
                field=rule.field,
                row_index=idx,
                message=rule.message,
                severity=rule.severity,
                actual_value=df.loc[idx, rule.field]
            ))
        return violations
```

## 5. Application Layer Use Cases

### Compile Rules Use Case
```python
# src/application/rules/use_cases/compile_rules.py
from typing import Dict, Any
from src.domain.rules.ports import RuleCompilerPort
from src.domain.rules.entities import CompilationResult

class CompileRulesUseCase:
    """Orchestrates rule compilation."""
    
    def __init__(self, compiler: RuleCompilerPort):
        self.compiler = compiler
    
    def execute(self, yaml_content: str) -> CompilationResult:
        """Compile rules from YAML."""
        # Parse YAML to dict (this is OK in application layer)
        import yaml
        source = yaml.safe_load(yaml_content)
        
        # Validate schema
        if not self.compiler.validate_schema(source):
            raise ValueError("Invalid rule schema")
        
        # Compile to domain entities
        return self.compiler.compile(source)
```

### Execute Rules Use Case
```python
# src/application/rules/use_cases/execute_rules.py
from typing import List, Dict, Any
from src.domain.rules.ports import RuleExecutorPort, DataProcessorPort
from src.domain.rules.entities import RuleSet, ExecutionResult

class ExecuteRulesUseCase:
    """Orchestrates rule execution."""
    
    def __init__(
        self,
        executor: RuleExecutorPort,
        processor: DataProcessorPort
    ):
        self.executor = executor
        self.processor = processor
    
    def execute(
        self,
        ruleset: RuleSet,
        csv_content: str,
        use_vectorization: bool = True
    ) -> ExecutionResult:
        """Execute rules on CSV data."""
        # Parse CSV
        data = self.processor.parse_csv(csv_content)
        
        # Execute rules
        if use_vectorization:
            return self.executor.execute_vectorized(ruleset, data)
        else:
            return self.executor.execute(ruleset, data)
```

## 6. Migration Steps

### Phase 1: Create Domain Interfaces (Week 1)
1. Create `src/domain/rules/ports/` directory
2. Define abstract interfaces for compiler, executor, processor
3. Create pure domain entities in `src/domain/rules/entities/`
4. Write unit tests for domain entities

### Phase 2: Extract Pure Logic (Week 2)
1. Identify pure business logic in existing files
2. Move to domain entities and services
3. Replace complex conditions with domain methods
4. Ensure all domain tests pass without external deps

### Phase 3: Create Infrastructure Adapters (Week 3)
1. Implement YamlRuleCompiler in infrastructure
2. Implement PandasRuleExecutor in infrastructure  
3. Implement DataFrameProcessor in infrastructure
4. Write integration tests for adapters

### Phase 4: Create Application Use Cases (Week 4)
1. Create CompileRulesUseCase
2. Create ExecuteRulesUseCase
3. Wire dependencies through DI
4. Update API handlers to use use cases

### Phase 5: Refactor Existing Code (Week 5)
1. Update imports in existing code
2. Remove external dependencies from domain
3. Update tests to use new structure
4. Run full test suite

### Phase 6: Cleanup and Documentation (Week 6)
1. Remove old files from domain/rules/engine/
2. Update documentation
3. Create ADR for architecture decision
4. Performance testing and optimization

## 7. Dependency Injection Setup

```python
# src/infrastructure/di/container.py
from dependency_injector import containers, providers
from src.infrastructure.rules.compilers import YamlRuleCompiler
from src.infrastructure.rules.executors import PandasRuleExecutor
from src.infrastructure.rules.processors import DataFrameProcessor
from src.application.rules.use_cases import CompileRulesUseCase, ExecuteRulesUseCase

class RulesContainer(containers.DeclarativeContainer):
    """DI container for rules engine."""
    
    config = providers.Configuration()
    
    # Infrastructure providers
    yaml_compiler = providers.Singleton(
        YamlRuleCompiler,
        schema_path=config.rules.schema_path
    )
    
    pandas_executor = providers.Singleton(
        PandasRuleExecutor
    )
    
    data_processor = providers.Singleton(
        DataFrameProcessor
    )
    
    # Use case providers
    compile_rules = providers.Factory(
        CompileRulesUseCase,
        compiler=yaml_compiler
    )
    
    execute_rules = providers.Factory(
        ExecuteRulesUseCase,
        executor=pandas_executor,
        processor=data_processor
    )
```

## 8. Testing Strategy

### Domain Layer Tests (Pure)
```python
# tests/unit/domain/rules/test_rule.py
def test_rule_matches_condition():
    """Test pure domain logic."""
    rule = Rule(
        id="test",
        field="price",
        type=RuleType.VALIDATION,
        condition=GreaterThan(100),
        action=RejectAction(),
        message="Price must be > 100"
    )
    
    assert rule.matches(150) == True
    assert rule.matches(50) == False
```

### Infrastructure Tests (Integration)
```python
# tests/integration/infrastructure/rules/test_pandas_executor.py
def test_pandas_executor_performance():
    """Test vectorized execution performance."""
    executor = PandasRuleExecutor()
    ruleset = create_test_ruleset()
    data = generate_test_data(rows=10000)
    
    result = executor.execute_vectorized(ruleset, data)
    
    assert result.stats['processed'] == 10000
    assert execution_time < 1.0  # seconds
```

## 9. Performance Considerations

### Optimization Strategies
1. **Lazy Loading**: Load infrastructure implementations only when needed
2. **Caching**: Cache compiled rules in memory
3. **Batch Processing**: Process data in configurable batch sizes
4. **Fallback Mechanism**: Pure Python executor as fallback

### Benchmarks to Maintain
- 50k rows processing: < 3 seconds
- Rule compilation: < 100ms
- Memory usage: < 500MB for 100k rows

## 10. Rollback Plan

If issues arise during migration:

1. **Feature Flags**: Use flags to switch between old/new implementation
2. **Parallel Running**: Run both implementations and compare results
3. **Gradual Rollout**: Migrate one marketplace at a time
4. **Instant Rollback**: Keep old code in separate module for quick revert

## Benefits of This Refactor

1. **Clean Architecture**: Proper separation of concerns
2. **Testability**: Domain logic can be tested without external deps
3. **Flexibility**: Easy to swap implementations (e.g., Polars instead of Pandas)
4. **Maintainability**: Clear boundaries and responsibilities
5. **Performance**: Can optimize infrastructure without touching domain
6. **Compliance**: Architecture tests ensure rules are followed

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Performance regression | High | Benchmark before/after each phase |
| Breaking existing functionality | High | Comprehensive test suite, feature flags |
| Team learning curve | Medium | Pair programming, documentation |
| Migration timeline slip | Medium | Incremental approach, parallel work |

## Success Criteria

- [ ] All domain imports are standard library only
- [ ] Architecture tests pass (no illegal dependencies)
- [ ] Performance benchmarks maintained or improved
- [ ] 100% test coverage for domain layer
- [ ] Zero downtime during migration
- [ ] Team trained on new architecture

## Next Steps

1. Review and approve this plan with the team
2. Create feature branch for refactor
3. Set up architecture tests to enforce rules
4. Begin Phase 1 implementation
5. Weekly progress reviews

## Code Examples

### Before (Domain with External Deps)
```python
# BAD: src/domain/rules/engine/runtime.py
import pandas as pd  # VIOLATION!
import numpy as np   # VIOLATION!

class RuleEngine:
    def execute(self, df: pd.DataFrame):  # pandas in domain!
        # Complex pandas operations
        pass
```

### After (Clean Separation)
```python
# GOOD: src/domain/rules/entities/rule_engine.py
from typing import List, Dict, Any

class RuleEngine:
    def execute(self, data: List[Dict[str, Any]]):  # Pure Python types
        # Pure business logic only
        pass

# GOOD: src/infrastructure/rules/executors/pandas_executor.py
import pandas as pd  # OK in infrastructure!

class PandasExecutor(RuleExecutorPort):
    def execute(self, engine: RuleEngine, df: pd.DataFrame):
        # Convert to domain format
        data = df.to_dict('records')
        # Use domain logic
        result = engine.execute(data)
        # Convert back if needed
        return result
```

This refactor plan provides a clear, incremental path to properly separate the rules engine while maintaining functionality and performance.