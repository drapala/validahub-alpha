# ADR-001: Structured logging with structlog

- Status: Accepted
- Date: 2025-08-29
- Related Commits: d515968, 313f86a

## Context

We require LGPD-compliant structured logging with masking of sensitive data, request/correlation context propagation, and security/audit event tracking. Logs should be JSON in production, human-friendly in development, and easy to integrate with observability backends.

## Decision

- Adopt `structlog` for structured logging.
- Provide a logging factory that configures processors: context vars, timestamp, level, logger name, unicode decoder, and a custom LGPD masking processor.
- Implement `LGPDProcessor` to sanitize known sensitive fields (tenant_id, idempotency_key, email, file_ref, generic secrets) recursively.
- Provide `SecurityLogger` and `AuditLogger` for security and audit events with enriched context (request_id, correlation_id, tenant_id, timestamps).
- Use JSON renderer in production; key-value renderer in development; include callsite info in development only.

## Consequences

- Consistent, compliant structured logs across layers.
- Reduced risk of PII leakage in logs.
- Clear separation of security/audit streams for monitoring.

## Alternatives Considered

- Standard `logging` only (insufficient ergonomics for structured logs and masking).
- Third-party log shippers providing masking (less control at source, harder to test).

