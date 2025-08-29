# ADR-004: Audit logging in domain job lifecycle

- Status: Accepted
- Date: 2025-08-29
- Related Commits: 8b5c16d, d515968

## Context

LGPD Article 37 requires accountability and auditability. We need an immutable audit trail for job lifecycle events close to the source of truth, independent of transport or adapters.

## Decision

- Emit audit events from the domain `Job` aggregate when lifecycle changes occur: submitted (create), started, completed, failed, retried.
- Use `AuditLogger` with standardized event types and automatic context enrichment.
- Keep domain audit minimal (no PII, no external dependencies), delegating persistence/transport to observers/sinks later.

## Consequences

- Reliable lifecycle audit events regardless of application transport.
- Clear separation between domain decisions and infrastructure concerns.

## Alternatives Considered

- Emit audit only at application/infrastructure layers (risk of gaps, harder to reason about invariants).

