# Tech Debt - ValidaHub

## Domain Rules Pending Definition

### Value Objects - Placeholder Validations

Current implementation has security-first placeholder validations. Business rules need definition:

#### TenantId
- [ ] Define if prefix `t_` is required
- [ ] Define allowed format (free form vs structured)
- [ ] Current: accepts any 3-50 chars normalized lowercase
- [ ] Decision needed: Should normalize input (trim/lowercase) or be strict?

#### IdempotencyKey  
- [ ] Define minimum length (current: 8 chars, Copilot suggests 16)
- [ ] Define allowed characters (current: alphanumeric + hyphen + underscore)
- [ ] Consider if dots and colons should be allowed for external integrations
- [ ] Decision: Token-like (strict) vs human-friendly (normalized)

#### FileReference
- [ ] Define if tenant context validation belongs in VO or Aggregate
- [ ] Define allowed file extensions whitelist vs blacklist
- [ ] Add S3 bucket naming validation rules

#### RulesProfileId
- [ ] Define version compatibility rules (service layer concern?)
- [ ] Define known channels validation
- [ ] Implement version comparison methods

#### ProcessingCounters
- [ ] ✅ Add invariant: `errors + warnings ≤ processed` (Copilot caught this)
- [ ] Define if sampling scenarios need special handling

### Test Alignment Issues (from Copilot Review)

Tests marked with `@pytest.mark.skip` pending business rules:
- `test_accepts_minimum_length` - IdempotencyKey min length (8 vs 16)
- `test_accepts_all_allowed_characters` - IdempotencyKey charset (. : vs - _)
- `test_valid_idempotency_keys_property` - Property test alphabet alignment

### Code Quality Issues

#### From Copilot Review:
1. **test_job.py** - Direct access to private `_status` attribute
   - [ ] Create factory method or builder for test setup
   - [ ] Consider `Job.in_state(status)` factory method

2. **Error Messages** - Some include user input (LGPD concern)
   - [ ] Sanitize all error messages to be generic
   - [ ] Log detailed errors internally only

3. **Unicode Handling**
   - [ ] Consider NFKC normalization for TenantId (future enhancement)
   - [ ] Add explicit control character validation

### Security Enhancements (Future)

- [ ] Add rate limiting context to VOs
- [ ] Implement presigned URL TTL detection in FileReference
- [ ] Add serialization/deserialization with validation
- [ ] Property-based testing for ReDoS attacks

### Next Steps

1. **Immediate (P0)**
   - Fix ProcessingCounters invariant
   - Decide IdempotencyKey min length (8 vs 16)
   - Align test charset with implementation

2. **Short-term (P1)**
   - Product team to define domain rules
   - Create factory methods for test data
   - Sanitize error messages

3. **Long-term (P2)**
   - Unicode normalization strategy
   - Performance optimization
   - Comprehensive security audit

Created: 2024-08-29
Updated: 2024-08-29 (after Copilot review)
Priority: P1 (not blocking but should be resolved soon)