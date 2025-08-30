# Domain Immutability Best Practices

## Overview

This document explains why we use immutable collections (Tuple, Mapping) instead of mutable ones (List, Dict) in our domain layer, particularly in aggregates and entities.

## Why Immutability Matters in DDD

### Problem with Mutable Collections

When using mutable collections in frozen dataclasses, external code can bypass domain validation:

```python
# ❌ BAD: Using List allows external mutation
@dataclass(frozen=True)
class RuleSet:
    versions: List[RuleVersion]  # Mutable!
    
# External code can bypass validation:
rule_set.versions.append(invalid_version)  # No validation!
rule_set.versions.clear()  # Violates business rules!
```

### Solution with Immutable Collections

Using immutable collections forces modifications through proper domain methods:

```python
# ✅ GOOD: Using Tuple prevents external mutation
@dataclass(frozen=True) 
class RuleSet:
    versions: Tuple[RuleVersion, ...]  # Immutable!
    
    def add_version(self, version: RuleVersion) -> "RuleSet":
        # Proper validation and event emission
        if self._version_exists(version):
            raise ValueError("Version already exists")
        
        return replace(self, versions=self.versions + (version,))

# External code must use proper methods:
rule_set = rule_set.add_version(new_version)  # Validated!
```

## Implementation Guidelines

### 1. Collections in Aggregates and Entities

Always use immutable collection types:

```python
# Domain collections
versions: Tuple[RuleVersion, ...]           # Instead of List[RuleVersion]
published_versions: Tuple[SemVer, ...]      # Instead of List[SemVer]
rules: Tuple[RuleDefinition, ...]           # Instead of List[RuleDefinition]
compatibility_policy: Mapping[str, Any]     # Instead of Dict[str, Any]
```

### 2. Factory Methods and Constructors

Initialize with immutable collections:

```python
rule_set = RuleSet(
    # ...other fields
    versions=(),                    # Empty tuple, not []
    published_versions=(),          # Empty tuple, not []
    compatibility_policy={}         # Dict is OK for construction, becomes Mapping
)
```

### 3. Modification Methods

Use tuple concatenation and replacement:

```python
def add_item(self, item: Item) -> "Aggregate":
    # Add to tuple using concatenation
    new_items = self.items + (item,)
    
    # Use replace() to create new instance
    return replace(self, items=new_items)

def remove_item(self, item_id: str) -> "Aggregate":
    # Filter tuple using generator expression
    new_items = tuple(item for item in self.items if item.id != item_id)
    
    return replace(self, items=new_items)
```

### 4. Query Methods

Return immutable collections from queries:

```python
def get_published_versions(self) -> Tuple[RuleVersion, ...]:
    """Return immutable tuple, not list."""
    return tuple(v for v in self.versions if v.status == Status.PUBLISHED)
```

## Performance Considerations

### When Immutability is Worth It

- **Domain Layer**: Always use immutable collections
- **Small-Medium Collections**: Tuple performance is excellent
- **Aggregates**: Immutability ensures consistency

### When to Consider Alternatives

- **Large Collections** (>1000 items): Consider using libraries like `pyrsistent`
- **Infrastructure Layer**: Lists/Dicts are acceptable for data transfer
- **Performance Critical Paths**: Profile first, optimize if needed

## Common Patterns

### 1. Tuple Concatenation

```python
# Adding items
new_versions = self.versions + (new_version,)

# Adding multiple items  
new_versions = self.versions + tuple(additional_versions)
```

### 2. Tuple Filtering

```python
# Removing items
new_versions = tuple(v for v in self.versions if v.id != version_id)

# Conditional filtering
active_versions = tuple(v for v in self.versions if v.status == Status.ACTIVE)
```

### 3. Tuple Mapping

```python
# Transforming items
updated_versions = tuple(
    updated_version if v.id == target_id else v
    for v in self.versions
)
```

## Testing Immutability

### Verify Collections Are Immutable

```python
def test_rule_set_versions_are_immutable():
    """Ensure versions collection cannot be mutated externally."""
    rule_set = create_rule_set_with_versions()
    
    # This should fail at runtime
    with pytest.raises(AttributeError):
        rule_set.versions.append(new_version)
    
    # This should also fail
    with pytest.raises(TypeError):
        rule_set.versions[0] = different_version
```

### Test Proper Modification Methods

```python
def test_add_version_creates_new_instance():
    """Ensure modifications create new instances."""
    original = create_rule_set()
    modified = original.add_version(new_version)
    
    # Different instances
    assert original is not modified
    assert len(original.versions) == 0
    assert len(modified.versions) == 1
```

## Migration Strategy

When converting existing code:

1. **Change Type Annotations**: `List[T]` → `Tuple[T, ...]`
2. **Update Constructors**: `[]` → `()`  
3. **Fix Concatenation**: `.append()` → `+ (item,)`
4. **Fix Filtering**: List comprehension → Tuple comprehension
5. **Update Return Types**: Methods returning `List[T]` → `Tuple[T, ...]`
6. **Run Tests**: Ensure no runtime errors from immutability

## Benefits Achieved

- ✅ **Domain Integrity**: Mutations only through proper methods
- ✅ **Event Consistency**: All changes emit appropriate domain events
- ✅ **Thread Safety**: Immutable objects are inherently thread-safe
- ✅ **Debugging**: Easier to track state changes
- ✅ **Code Clarity**: Clear distinction between queries and commands

## References

- [Domain-Driven Design by Eric Evans](https://www.domainlanguage.com/ddd/)
- [Clean Architecture by Robert Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Effective Python: Item 23 - Accept Functions Instead of Classes for Simple Interfaces](https://effectivepython.com/)