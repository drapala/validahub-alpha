# ADR-006: Pragmatic approach to domain layer dependencies

**Date:** 2025-08-30
**Status:** Accepted
**Context:** After attempting pure DDD with zero external dependencies in domain layer, we reverted to pragmatic approach allowing utility libraries while maintaining strict boundaries against data frameworks.

## Options Considered

- **Option A: Pure DDD (zero dependencies)**: Domain layer with absolutely no external dependencies, reimplementing all utilities
  - Pros: Perfect theoretical purity, complete control over all code
  - Cons: 20+ lines of fragile date parsing replacing 1 robust dateutil line, maintenance burden
  
- **Option B: Framework-inclusive approach**: Allow any useful library in domain including pandas/numpy
  - Pros: Maximum convenience and performance
  - Cons: Domain entities coupled to data structures, loss of business language, testing complexity
  
- **Option C: Pragmatic utility approach**: Allow lightweight utility libraries (dateutil, uuid) but forbid data frameworks (pandas/numpy)
  - Pros: Robust utilities without coupling to complex data structures, maintains business focus
  - Cons: Requires judgment calls on what constitutes "utility vs framework"

## Decision

- Accept lightweight utility libraries in domain layer (dateutil, uuid, typing-extensions)
- Strictly forbid data manipulation frameworks (pandas, numpy, scipy) in domain layer
- Maintain "utility vs framework" distinction based on structural impact
- Use architecture tests to enforce framework boundaries

## Rationale / Trade-offs

**Why utility libraries are acceptable:**
- dateutil provides robust date parsing without changing domain object structure
- uuid generates identifiers without introducing new data types to domain
- These tools enhance domain capabilities without architectural coupling

**Why data frameworks are problematic:**
- Pandas DataFrame fundamentally changes how business rules are expressed
- Domain rule "order total cannot exceed $10,000" becomes pandas operation (`df['price'].sum() > 10000`)
- Domain entities lose POPO (Plain Old Python Object) simplicity
- Business language replaced with framework-specific operations

**Trade-off accepted:** Some dependency on external libraries for robust date/UUID handling vs theoretical purity that leads to fragile reimplementation.

## Scope & Boundaries

- **In-scope:** Guidelines for utility vs framework distinction in domain layer
- **In-scope:** Architecture test enforcement of framework boundaries
- **Out-of-scope:** Application/infrastructure layer dependency rules (already established)

## Consequences

- **Positive:** Robust date handling without fragile custom code, clear framework boundaries
- **Positive:** Domain maintains business language focus while leveraging proven utilities  
- **Negative:** Dependency on external libraries breaks theoretical DDD purity
- **Neutral:** Requires ongoing judgment on new dependencies (utility vs framework)

## Tests & Quality Gates

- **RED:** Architecture tests failing when pandas/numpy imported in domain
- **GREEN:** dateutil/uuid usage in domain passes architecture validation
- **REFACTOR:** Establish clear criteria for utility vs framework classification

## DDD Anchors

- **VO:** Value objects can use dateutil for parsing, uuid for generation
- **Aggregate:** Business rules expressed in domain language, not pandas operations
- **Service/Ports:** Data frameworks belong in application/infrastructure layers only

## Telemetry & Security

- **Metrics/Events:** No new telemetry impact from utility libraries
- **Threats/Mitigations:** Reduced attack surface vs heavy data frameworks

## Utility vs Framework Classification

### ✅ Acceptable Utilities
- `dateutil`: Date parsing/manipulation without structural changes
- `uuid`: Identifier generation
- `typing-extensions`: Type hints and annotations
- `enum`: Standard library enumerations
- `dataclasses`: Simple data containers

### ❌ Forbidden Frameworks  
- `pandas`: DataFrame introduces complex data structures to domain
- `numpy`: ndarray changes how business rules are expressed
- `scipy`: Scientific computing framework
- `sklearn`: Machine learning framework
- `sqlalchemy`: Database ORM framework

### 🤔 Gray Area (Case-by-case)
- `pydantic`: Data validation (acceptable for value object validation)
- `attrs`: Alternative to dataclasses (acceptable if purely structural)
- `marshmallow`: Serialization framework (belongs in infrastructure)

## Migration Strategy

**Current State → Ideal State:**

1. **Phase 1 (Completed):** Remove pandas/numpy from domain entities
2. **Phase 2:** Refactor data processing to application layer using pandas for CSV→domain conversion
3. **Phase 3:** Analytics layer uses pandas for domain→DataFrame conversion for reporting
4. **Phase 4:** Establish architecture tests preventing future framework leakage

**Ideal Data Flow:**
```
Raw Data (CSV) → [Application uses pandas] → Pure Domain Objects → [Use Cases] → [Analytics uses pandas] → Reports
```

## Links

- **PR:** #3 (pragmatic refactor)
- **Commit:** 4c91648 (pragmatic approach adoption)
- **Issue:** Domain layer purity vs pragmatism discussion

---

_Supersedes:_ Initial pure DDD attempt
_Superseded by:_ N/A