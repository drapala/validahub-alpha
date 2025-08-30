# ValidaHub Smart Rules Engine Test Strategy

This document describes the comprehensive test strategy for ValidaHub's Smart Rules Engine, designed to ensure production-ready quality through rigorous testing methodologies.

## Overview

The test strategy follows Test-Driven Development (TDD) principles with strict RED→GREEN→REFACTOR cycles and implements multiple layers of validation:

- **Unit Tests**: Fast, isolated tests with comprehensive coverage
- **Golden Tests**: Marketplace compatibility validation 
- **Performance Tests**: Benchmarks ensuring 50k rows < 3 seconds
- **Mutation Tests**: Validation of test quality and effectiveness
- **Chaos Tests**: Resilience testing under failure conditions
- **CI/CD Pipeline**: Automated quality gates with 90%+ coverage

## Test Categories

### 1. Unit Tests (`tests/unit/rules/`)

**Purpose**: Validate individual components in isolation using test doubles for dependencies.

**Key Features**:
- Domain isolation with no I/O operations
- Port-based mocking at boundaries
- Property-based testing with Hypothesis for edge cases
- Comprehensive condition and rule logic testing

**Examples**:
```python
def test_compile_yaml__with_valid_rules__creates_optimized_execution_plan()
def test_execute_vectorized__with_50k_rows__completes_under_3_seconds()
def test_condition_evaluation__with_regex_patterns__caches_compiled_expressions()
```

**Coverage Target**: 95%+ for domain and application layers

### 2. Golden Tests (`tests/golden/`)

**Purpose**: Ensure consistent behavior across marketplace rule implementations by comparing against known-good fixtures.

**Structure**:
```
tests/golden/
├── conftest.py              # Shared fixtures and helpers
├── test_mercado_livre.py    # Mercado Livre marketplace tests
├── test_amazon.py           # Amazon marketplace tests
└── fixtures/
    ├── input/               # Test CSV data
    ├── rules/               # YAML rule definitions
    └── expected/            # Expected validation results
```

**Key Features**:
- Marketplace-specific rule validation
- Regression prevention for rule engine changes
- Automated fixture updates with `--update-golden`

**Usage**:
```bash
# Run golden tests
pytest tests/golden/ -v

# Update fixtures
pytest tests/golden/ --update-golden

# Test specific marketplace
pytest tests/golden/test_amazon.py -v
```

### 3. Performance Tests (`tests/perf/benchmark_50k.py`)

**Purpose**: Validate performance requirements and scalability characteristics.

**Primary Requirement**: Process 50,000 CSV rows in under 3 seconds

**Test Scenarios**:
- **Primary Benchmark**: 50k rows with comprehensive rules
- **Scalability**: Linear performance across dataset sizes
- **Complexity**: Performance impact of different rule patterns
- **Concurrency**: Multi-threading efficiency
- **Memory**: Memory usage and leak detection

**Usage**:
```bash
# Run performance tests
pytest tests/perf/ --run-perf -v

# Run specific benchmark
python tests/perf/benchmark_50k.py

# CI-friendly subset
pytest tests/perf/ --run-perf --tb=short
```

**Metrics Tracked**:
- Execution time (primary: <3.0s)
- Throughput (rows/second)
- Memory usage (MB/1k rows)
- CPU utilization
- Vectorization effectiveness

### 4. Mutation Testing (`tests/mutation/`)

**Purpose**: Validate test quality by introducing code mutations and verifying tests detect them.

**Configuration**:
- Target survival rate: ≤15%
- Focus areas: Rule compiler, runtime engine, domain logic
- Mutation types: Arithmetic, comparison, boolean, assignment

**Usage**:
```bash
# Run mutation tests
pytest tests/mutation/ --run-mutation -v

# Target specific module
python tests/mutation/rules_mutation_config.py src/domain/rules/engine/compiler.py

# Generate mutation report
python mutation_test.py --output mutation_report.json
```

**Quality Thresholds**:
- **Excellent**: ≤5% survival rate
- **Good**: ≤15% survival rate  
- **Fair**: ≤30% survival rate
- **Poor**: >30% survival rate

### 5. Chaos Engineering (`tests/chaos/`)

**Purpose**: Validate system resilience under various failure conditions.

**Failure Scenarios**:
- **Cache Failures**: Redis unavailable
- **Network Failures**: Kafka/webhook failures
- **Memory Pressure**: High memory usage conditions
- **Disk I/O Failures**: File system errors
- **Concurrency Stress**: Race condition detection
- **Malformed Data**: Adversarial input handling
- **Performance Degradation**: CPU/resource constraints

**Usage**:
```bash
# Run chaos tests
pytest tests/chaos/ --run-chaos --chaos-intensity=medium

# Specific scenario
python chaos_runner.py --scenario cache_failure

# Extended endurance test
pytest tests/chaos/ --run-chaos -m slow
```

## Test Execution

### Quick Test Commands

```bash
# Unit tests only
pytest tests/unit/rules/ -v --cov=src/domain/rules

# Golden tests for all marketplaces
pytest tests/golden/ -v

# Performance benchmark (critical)
pytest tests/perf/benchmark_50k.py::TestRulesEnginePerformance::test_benchmark_50k_rows_under_3_seconds__primary_performance_requirement --run-perf

# Complete test suite
python run_rules_tests.py --suite all --coverage --report
```

### Comprehensive Test Runner

The `run_rules_tests.py` script provides unified test execution:

```bash
# Basic usage
python run_rules_tests.py                    # Run all tests
python run_rules_tests.py --suite unit       # Unit tests only
python run_rules_tests.py --coverage         # With coverage
python run_rules_tests.py --report          # Generate report

# CI-optimized
python run_rules_tests.py --suite ci --coverage

# Development workflow
python run_rules_tests.py --suite unit --coverage --report
```

## Quality Gates

### Coverage Requirements
- **Domain Layer**: ≥95% line coverage
- **Application Layer**: ≥90% line coverage
- **Overall**: ≥90% line coverage
- **Branch Coverage**: ≥85%

### Performance Requirements
- **Primary**: 50,000 rows in <3.0 seconds
- **Throughput**: >16,600 rows/second
- **Memory**: <20 MB per 1k rows
- **Scalability**: Linear performance up to 100k rows

### Code Quality Standards
- **Complexity**: McCabe complexity ≤10
- **Type Coverage**: 100% for domain layer
- **Lint Score**: Zero violations
- **Security**: Zero high/medium Bandit issues

### Test Quality Metrics
- **Mutation Survival**: ≤15%
- **Test Execution Time**: Unit tests <30s total
- **Test Reliability**: Zero flaky tests
- **Coverage Quality**: Meaningful assertions (no generic tests)

## CI/CD Integration

### GitHub Actions Pipeline (`.github/workflows/rules-ci.yml`)

**Phase 1: Quality Gates**
- Code formatting (Black)
- Import sorting (isort)  
- Linting (Ruff)
- Type checking (mypy)
- Security scanning (Bandit)
- Complexity analysis (Radon)
- Architecture validation

**Phase 2: Test Suite**
- Unit tests with coverage
- Golden tests for all marketplaces
- Integration tests
- Multi-Python version testing (3.10, 3.11, 3.12)

**Phase 3: Performance Benchmarks**
- Primary 50k row benchmark
- Scalability validation
- Memory efficiency tests
- Performance regression detection

**Phase 4: Advanced Quality (main branch only)**
- Mutation testing
- Chaos engineering
- Extended endurance tests

**Phase 5: Deployment Gate**
- Quality gate evaluation
- Comprehensive reporting
- PR comments with results
- Deployment readiness assessment

### Pipeline Triggers
- **Push**: `main`, `develop`, feature branches
- **Pull Request**: `main`, `develop`
- **Paths**: Rules engine code and tests only

### Quality Gate Thresholds
```yaml
MIN_COVERAGE_PERCENT: 90
MAX_COMPLEXITY: 10
PERFORMANCE_THRESHOLD_SECONDS: 3.0
MAX_MUTATION_SURVIVAL_PERCENT: 15
```

## Test Data Management

### Fixtures and Test Data
- **Unit Tests**: Generated test data with realistic patterns
- **Golden Tests**: Marketplace-specific product catalogs
- **Performance Tests**: Scalable dataset generation (1k-100k rows)
- **Chaos Tests**: Adversarial and malformed data patterns

### Data Generation Strategy
```python
# Realistic marketplace data patterns
products = PerformanceBenchmark().generate_benchmark_data(50000)

# Marketplace-specific validation data  
ml_products = load_golden_fixture("mercado_livre_products.csv")

# Adversarial data for chaos testing
chaos_data = MalformedDataScenario().create_malicious_dataframe(base_data)
```

## Development Workflow

### TDD Cycle Implementation
1. **RED**: Write failing test for new functionality
2. **GREEN**: Implement minimum code to pass test
3. **REFACTOR**: Improve code while keeping tests green
4. **VALIDATE**: Run full test suite before commit

### Pre-commit Hooks
```bash
# Install pre-commit hooks
pre-commit install

# Manual pre-commit check
python run_rules_tests.py --suite unit --coverage
```

### Test Naming Convention
```python
def test_<behavior>__<condition>__<expected_result>():
    """
    Test that <behavior> when <condition> results in <expected_result>
    """
```

Examples:
```python
def test_compile_rules__with_invalid_regex__raises_compilation_error()
def test_execute_vectorized__with_50k_rows__completes_under_3_seconds()
def test_cache_failure__redis_unavailable__continues_processing_gracefully()
```

### Code Coverage Analysis
```bash
# Generate coverage report
pytest tests/unit/rules/ --cov=src/domain/rules --cov-report=html

# View coverage
open htmlcov/index.html

# Coverage by module
coverage report --show-missing
```

## Performance Monitoring

### Continuous Performance Tracking
- Benchmark results stored in CI artifacts
- Performance regression detection
- Throughput trend analysis
- Memory usage monitoring

### Benchmark Result Format
```json
{
  "primary_benchmark": {
    "execution_time_seconds": 2.847,
    "throughput_rows_per_second": 17572,
    "memory_used_mb": 234.5,
    "performance_requirement_met": true
  },
  "scalability": [
    {"rows": 10000, "throughput": 18230},
    {"rows": 25000, "throughput": 17891},
    {"rows": 50000, "throughput": 17572}
  ]
}
```

## Troubleshooting

### Common Issues

**Performance Tests Failing**:
```bash
# Check system resources
pytest tests/perf/ --run-perf -s -v

# Run with profiling
python -m cProfile -o profile.stats tests/perf/benchmark_50k.py
```

**Golden Tests Failing**:
```bash
# Update fixtures
pytest tests/golden/ --update-golden

# Compare differences
pytest tests/golden/test_mercado_livre.py -v --tb=long
```

**Coverage Below Threshold**:
```bash
# Identify missing coverage
coverage report --show-missing --skip-covered

# Focus on untested lines
pytest tests/unit/rules/ --cov=src/domain/rules --cov-report=term-missing
```

**Mutation Tests Failing**:
```bash
# Run limited mutation set
pytest tests/mutation/ --run-mutation -k compiler

# Generate detailed report
python mutation_test.py --max-mutations 20 --output detailed_report.json
```

### Debug Mode
```bash
# Verbose test output
pytest tests/unit/rules/ -v -s --tb=long

# Keep temporary files
pytest tests/golden/ --basetemp=/tmp/test_debug

# Single test debugging
pytest tests/unit/rules/test_compiler.py::TestRuleCompiler::test_compile_yaml__with_valid_rules__compiles_successfully -v -s
```

## Contributing

### Adding New Tests
1. Follow TDD methodology (RED→GREEN→REFACTOR)
2. Use descriptive test names
3. Include both positive and negative test cases
4. Add performance considerations for large datasets
5. Update golden fixtures when rule behavior changes

### Test Review Checklist
- [ ] Tests follow naming convention
- [ ] Both success and failure paths tested
- [ ] Edge cases and boundary conditions covered
- [ ] Performance impact considered
- [ ] No external dependencies in unit tests
- [ ] Appropriate use of test doubles
- [ ] Clear and descriptive assertions

## Resources

### Documentation
- [Testing Best Practices](../docs/testing-best-practices.md)
- [TDD Guidelines](../docs/tdd-guidelines.md)
- [Performance Requirements](../docs/performance-requirements.md)

### Tools and Libraries
- **pytest**: Test framework
- **hypothesis**: Property-based testing
- **mutmut**: Mutation testing
- **coverage**: Code coverage analysis
- **black/ruff**: Code formatting and linting
- **mypy**: Static type checking

### External Resources
- [Mutation Testing Introduction](https://mutation-testing.org/)
- [Chaos Engineering Principles](https://principlesofchaos.org/)
- [Property-Based Testing with Hypothesis](https://hypothesis.readthedocs.io/)

---

**Test Strategy Version**: 1.0.0  
**Last Updated**: 2024-08-30  
**Maintainers**: ValidaHub Engineering Team