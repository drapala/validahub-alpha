# PDR-001: Idempotency compatibility policy

- Status: Accepted
- Date: 2025-08-29
- Supersedes: —

## Context

Clients may send legacy idempotency keys. We need a predictable product behavior for idempotent submission and replay while maintaining backward compatibility and strong safety.

## Decision

- Default compatibility mode is CANONICALIZE: legacy/short/unsafe keys are transformed deterministically into secure keys. A REJECT mode exists as a feature flag (`IDEMP_COMPAT_MODE=reject`).
- Idempotency key validation and canonicalization happen at the HTTP boundary. The SubmitJob use case treats keys as opaque for persistence/idempotency lookup.
- Replays with the same resolved key return the original job response without re-processing, including metadata to indicate replay.

## Rationale

- Smooth migration path for existing clients.
- Clear, deterministic product behavior for retries and network errors.

## Consequences

- Product exposes stable idempotency semantics independent of client key format.
- Operators can harden policy by switching to REJECT mode without code changes.

