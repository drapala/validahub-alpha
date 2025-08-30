# Factory Pattern for External Data Parsing

## Team Agreement

**Status**: Accepted  
**Date**: 2025-08-30  
**Authors**: ValidaHub Team  

## Context

When building systems with Domain-Driven Design (DDD) and Clean Architecture, we face a tension between domain purity and practical needs for parsing external data. The domain layer should focus on business logic, not the mechanics of parsing strings into dates, decimals, or other complex types.

## Decision

We adopt the **Factory Pattern in the Application Layer** for all external data parsing needs.

## Implementation Guidelines

### 1. Domain Layer Expectations

The domain layer should:
- Accept only properly typed objects (datetime, Decimal, etc.)
- Return validation errors if it receives unparsed data
- Focus solely on business rules and invariants
- Never import parsing libraries

```python
# ✅ GOOD - Domain expects parsed data
class Event:
    def __init__(self, name: str, date: datetime):
        if not isinstance(date, datetime):
            raise ValueError("Expected datetime object")
        self.name = name
        self.date = date

# ❌ BAD - Domain does parsing
class Event:
    def __init__(self, name: str, date: str):
        from dateutil import parser  # ❌ Domain importing parser
        self.name = name
        self.date = parser.parse(date)  # ❌ Domain doing parsing
```

### 2. Application Layer Factories

The application layer should provide factories that:
- Handle all parsing of external data
- Use utility libraries (dateutil, decimal, etc.)
- Return domain objects or validation results
- Encapsulate parsing complexity

```python
# src/application/factories/event_factory.py
from datetime import datetime
from dateutil import parser as date_parser
from domain.events import Event

class EventFactory:
    @staticmethod
    def create_from_api_data(data: dict) -> Event:
        """Parse external API data into domain Event."""
        # Application layer handles parsing
        parsed_date = date_parser.parse(data['date'])
        
        # Return clean domain object
        return Event(
            name=data['name'],
            date=parsed_date  # Pass parsed datetime
        )
    
    @staticmethod
    def parse_date(date_string: str) -> datetime:
        """Parse date string with flexible formats."""
        return date_parser.parse(date_string)
```

### 3. Service Orchestration

Application services orchestrate between external data and domain:

```python
# src/application/services/event_service.py
class EventService:
    def __init__(self):
        self.factory = EventFactory()
        self.repository = EventRepository()
    
    def create_event(self, api_data: dict) -> Event:
        # Use factory to parse external data
        event = self.factory.create_from_api_data(api_data)
        
        # Domain validation happens with clean objects
        event.validate()
        
        # Persist
        return self.repository.save(event)
```

### 4. API/Infrastructure Layer

The API layer passes raw data to application services:

```python
# src/infrastructure/api/endpoints.py
@router.post("/events")
async def create_event(request: CreateEventRequest):
    # Pass raw data to application service
    event = event_service.create_event(request.dict())
    return EventResponse.from_domain(event)
```

## Benefits

1. **Clear Separation of Concerns**
   - Domain: Business logic only
   - Application: Parsing and orchestration
   - Infrastructure: External interfaces

2. **Testability**
   - Domain tests don't need to mock parsers
   - Factory tests focus on parsing edge cases
   - Service tests can use clean domain objects

3. **Maintainability**
   - Parsing logic centralized in factories
   - Easy to change parsing libraries
   - Domain remains stable

4. **Type Safety**
   - Domain works with proper types
   - Parsing errors caught early
   - Better IDE support

## Common Parsing Scenarios

### Dates and Times
```python
class DateFactory:
    @staticmethod
    def parse_flexible(value: Any) -> datetime:
        """Parse various date formats."""
        if isinstance(value, datetime):
            return value
        return date_parser.parse(str(value))
```

### Decimals and Money
```python
class MoneyFactory:
    @staticmethod
    def parse_amount(value: Any) -> Decimal:
        """Parse monetary amounts."""
        if isinstance(value, Decimal):
            return value
        # Handle different decimal separators
        clean = str(value).replace(',', '.')
        return Decimal(clean)
```

### Complex Nested Objects
```python
class ProductFactory:
    @staticmethod
    def create_from_csv_row(row: dict) -> Product:
        """Parse CSV row into Product aggregate."""
        return Product(
            sku=row['sku'].strip(),
            title=row['title'].strip(),
            price=MoneyFactory.parse_amount(row['price']),
            available_from=DateFactory.parse_flexible(row['date'])
        )
```

## Anti-Patterns to Avoid

### ❌ Domain Parsing
```python
# BAD - Domain shouldn't parse
class Product:
    def __init__(self, sku: str, price_str: str):
        self.price = Decimal(price_str)  # Parsing in domain
```

### ❌ Scattered Parsing
```python
# BAD - Parsing logic everywhere
@router.post("/products")
async def create_product(data: dict):
    # Parsing in API layer
    data['price'] = Decimal(data['price'])
    data['date'] = parser.parse(data['date'])
    return product_service.create(data)
```

### ❌ Mixed Responsibilities
```python
# BAD - Service doing parsing
class ProductService:
    def create(self, data: dict):
        # Service shouldn't parse
        from dateutil import parser
        data['date'] = parser.parse(data['date'])
        return Product(**data)
```

## Testing Strategy

### Domain Tests
```python
def test_product_with_negative_price():
    # Test with clean objects, no parsing
    with pytest.raises(ValueError):
        Product(sku="ABC", price=Decimal("-10.00"))
```

### Factory Tests
```python
def test_factory_parses_various_date_formats():
    # Test parsing edge cases
    assert DateFactory.parse("2024-01-01") == datetime(2024, 1, 1)
    assert DateFactory.parse("01/01/2024") == datetime(2024, 1, 1)
    assert DateFactory.parse("Jan 1, 2024") == datetime(2024, 1, 1)
```

### Integration Tests
```python
def test_api_creates_product_with_parsing():
    # Test full flow with raw data
    response = client.post("/products", json={
        "sku": "ABC",
        "price": "19.99",
        "date": "2024-01-01T10:00:00"
    })
    assert response.status_code == 201
```

## Migration Path

For existing code that has parsing in the domain:

1. **Identify** all parsing locations in domain layer
2. **Create** factories in application layer
3. **Update** services to use factories
4. **Refactor** domain to expect parsed objects
5. **Test** thoroughly at each step
6. **Document** any temporary exceptions

## Exceptions

Some pragmatic exceptions may be allowed during migration:

- **Temporary**: Keep parsing in domain with TODO and migration plan
- **Performance**: If factory overhead is measurable (benchmark first!)
- **Third-party**: When integrating with libraries that expect specific formats

All exceptions must be:
- Documented in code with rationale
- Have a migration plan
- Be reviewed quarterly

## References

- [ADR-006: Pragmatic Domain Dependencies](../../.adr/ADR-006-pragmatic-domain-dependencies.md)
- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Domain-Driven Design by Eric Evans](https://www.domainlanguage.com/ddd/)
- [Hexagonal Architecture by Alistair Cockburn](https://alistair.cockburn.us/hexagonal-architecture/)

## Team Agreement

By adopting this pattern, we agree to:

1. **Always** use factories for parsing external data
2. **Never** parse in the domain layer (except documented exceptions)
3. **Centralize** parsing logic in application factories
4. **Test** parsing separately from business logic
5. **Review** this pattern quarterly and update as needed

---

*This document represents our team's shared understanding and agreement on handling external data parsing in our DDD/Clean Architecture systems.*