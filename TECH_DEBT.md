# Tech Debt - ValidaHub

## Domain Rules Pending Definition

### Value Objects - Placeholder Validations

Current implementation has security-first placeholder validations. Business rules need definition:

#### TenantId
- [ ] Define if prefix `t_` is required
- [ ] Define allowed format (free form vs structured)
- [ ] Current: accepts any 3-50 chars normalized lowercase
- [ ] Decision needed: Should normalize input (trim/lowercase) or be strict?
- 📍 `packages/domain/value_objects.py:15-42`
- 📍 `tests/unit/domain/test_value_objects.py:10-89`
- 📍 `tests/unit/domain/test_tenant_id_unicode.py:11-95`

#### IdempotencyKey  
- [ ] Define minimum length (current: 8 chars, Copilot suggests 16)
- [ ] Define allowed characters (current: alphanumeric + hyphen + underscore)
- [ ] Consider if dots and colons should be allowed for external integrations
- [ ] Decision: Token-like (strict) vs human-friendly (normalized)
- 📍 `packages/domain/value_objects.py:45-67`
- 📍 `tests/unit/domain/test_value_objects.py:91-193` (3 tests skipped)
- 📍 `tests/unit/domain/test_idempotency_key_security.py:9-130`

#### FileReference
- [ ] Define if tenant context validation belongs in VO or Aggregate
- [ ] Define allowed file extensions whitelist vs blacklist
- [ ] Add S3 bucket naming validation rules
- 📍 `packages/domain/value_objects.py:74-132`
- 📍 `tests/unit/domain/test_file_reference_parsing.py:6-182`

#### RulesProfileId
- [ ] Define version compatibility rules (service layer concern?)
- [ ] Define known channels validation
- [ ] Implement version comparison methods
- 📍 `packages/domain/value_objects.py:135-180`
- 📍 `tests/unit/domain/test_rules_profile_id.py:6-114`

#### ProcessingCounters
- [ ] ✅ Add invariant: `errors + warnings ≤ processed` (Copilot caught this)
- [ ] Define if sampling scenarios need special handling
- 📍 `packages/domain/value_objects.py:183-246` (invariant already implemented!)
- 📍 `tests/unit/domain/test_processing_counters.py:6-165`

### Test Alignment Issues (from Copilot Review)

Tests marked with `@pytest.mark.skip` pending business rules:
- `test_accepts_minimum_length` - IdempotencyKey min length (8 vs 16)
  - 📍 `tests/unit/domain/test_value_objects.py:99`
- `test_accepts_all_allowed_characters` - IdempotencyKey charset (. : vs - _)
  - 📍 `tests/unit/domain/test_value_objects.py:111`
- `test_valid_idempotency_keys_property` - Property test alphabet alignment
  - 📍 `tests/unit/domain/test_value_objects.py:177`

### Code Quality Issues

#### From Copilot Review:
1. **test_job.py** - Direct access to private `_status` attribute
   - [ ] Create factory method or builder for test setup
   - [ ] Consider `Job.in_state(status)` factory method
   - 📍 `tests/unit/domain/test_job.py:95` (example of _status access)

2. **Error Messages** - Some include user input (LGPD concern)
   - [ ] Sanitize all error messages to be generic
   - [ ] Log detailed errors internally only
   - 📍 All VOs currently use generic messages (already LGPD compliant!)

3. **Unicode Handling**
   - [ ] Consider NFKC normalization for TenantId (future enhancement)
   - [ ] Add explicit control character validation
   - 📍 `packages/domain/value_objects.py:10-12` (_has_control_or_format helper)
   - 📍 `packages/domain/value_objects.py:27-29` (already validates control chars!)

### Security Enhancements (Future)

- [ ] Add rate limiting context to VOs
- [ ] Implement presigned URL TTL detection in FileReference
- [ ] Add serialization/deserialization with validation
- [ ] Property-based testing for ReDoS attacks

### Next Steps

1. **Immediate (P0)**
   - ~~Fix ProcessingCounters invariant~~ ✅ Already implemented at `packages/domain/value_objects.py:200-202`
   - Decide IdempotencyKey min length (8 vs 16) - `packages/domain/value_objects.py:49`
   - Align test charset with implementation - `tests/unit/domain/test_value_objects.py:111,177`

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