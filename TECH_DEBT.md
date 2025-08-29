# Tech Debt - ValidaHub

## Domain Rules Pending Definition

### Value Objects - Placeholder Validations

Current implementation has security-first placeholder validations. Business rules need definition:

#### TenantId
- [ ] Define if prefix `t_` is required
- [ ] Define allowed format (free form vs structured)
- [ ] Current: accepts any 3-50 chars normalized lowercase

#### IdempotencyKey  
- [ ] Define minimum length (8 vs 16 chars)
- [ ] Define allowed characters (current: alphanumeric + hyphen + underscore)
- [ ] Consider if dots and colons should be allowed

#### FileReference
- [ ] Define if tenant context validation belongs in VO or Aggregate
- [ ] Define allowed file extensions whitelist vs blacklist

#### RulesProfileId
- [ ] Define version compatibility rules (service layer concern?)
- [ ] Define known channels validation

### Test Alignment Issues

Tests marked with `@pytest.mark.skip` pending business rules:
- `test_accepts_minimum_length` - IdempotencyKey min length
- `test_accepts_all_allowed_characters` - IdempotencyKey charset
- `test_valid_idempotency_keys_property` - Property test alphabet

### Next Steps

1. Product team to define domain rules
2. Align tests with decided rules
3. Update implementation if needed
4. Remove skip markers from tests

Created: 2024-08-29
Priority: P1 (not blocking but should be resolved soon)