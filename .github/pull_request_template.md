## Context
<!-- Why this change is needed -->

## Changes
- <!-- Bullet points of what was changed -->

## Breaking Changes
<!-- If applicable, describe migration path -->

## Related Issues
<!-- Use keywords: Closes #XX, Fixes #XX, Relates to #XX -->
Closes #

## Checklist
- [ ] Title follows Conventional Commits (type(scope): message ≤100 chars)
- [ ] OpenAPI updated if contract changed
- [ ] Tests added/adjusted for new functionality
- [ ] Respects architecture layers (domain → application → infra)
- [ ] Logs include tenant_id and request_id
- [ ] DB migration is reversible (if applicable)
- [ ] PR size within limits (≤200 soft, ≤400 hard or `size/override` label)
- [ ] Code follows style guidelines (ruff, mypy, black)
- [ ] Self-review completed
- [ ] Security implications considered
- [ ] Performance impact assessed
- [ ] Documentation updated (if needed)

## Type of Change
- [ ] feat: New feature
- [ ] fix: Bug fix
- [ ] chore: Maintenance
- [ ] refactor: Code restructuring
- [ ] docs: Documentation
- [ ] test: Test improvements
- [ ] perf: Performance improvement
- [ ] build: Build system
- [ ] ci: CI/CD changes
- [ ] revert: Revert changes
- [ ] rules: Rule pack changes
- [ ] contracts: API contract changes
- [ ] telemetry: Observability changes

## Architecture Validation
- [ ] Domain layer has no framework dependencies
- [ ] Application layer doesn't import infra/*
- [ ] All external integrations use ports/adapters
- [ ] Multi-tenant context preserved (tenant_id)
- [ ] LGPD compliance maintained

## Testing
- [ ] Unit tests pass (`pytest tests/unit/`)
- [ ] Integration tests pass (`pytest tests/integration/`)
- [ ] Architecture tests pass (`pytest tests/architecture/`)
- [ ] Coverage ≥80%
- [ ] Golden tests updated (if applicable)

## Security & Compliance
- [ ] No PII in logs or error messages
- [ ] CSV formula injection protection
- [ ] Audit logging for data changes
- [ ] Rate limiting considered
- [ ] Idempotency implemented (for state changes)

## Screenshots (if applicable)
<!-- Add screenshots for UI changes -->

## Performance Impact
<!-- Describe any performance implications, especially for CSV processing -->

## Rollback Plan
<!-- How to rollback if this causes issues in production -->

## Additional Notes
<!-- Any additional context or notes for reviewers -->