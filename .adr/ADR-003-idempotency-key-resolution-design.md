# ADR-003: Idempotency key resolution design

- Status: Accepted
- Date: 2025-08-29
- Related Commits: 8cb5a2c, 313f86a, 2d3bc2c, 9d38f5b

## Context

Clients may send legacy idempotency keys (dots/colons/spaces, or too short), or omit keys. Keys must be safe against CSV formula injection, tenant- and scope-isolated, and deterministic to enable idempotent replays.

## Decision

- Accept secure keys that match `[A-Za-z0-9_-]{16,128}` and do not start with `= + - @`.
- For legacy/short/unsafe-start keys, canonicalize deterministically using SHA-256 over `tenant_id + scope_hash + raw_key`, base64url-encode first 16 bytes (22 chars), and ensure a safe first character.
- Define scope hash as `sha256(HTTP_METHOD_UPPER + ':' + route_template)[:8]` for isolation.
- Provide compatibility modes: `canonicalize` (default) and `reject`, driven by env (`IDEMP_COMPAT_MODE`) read dynamically at runtime.
- Enforce final validation: 16–128 chars, allowed alphabet, safe first character.

## Consequences

- Backward compatibility with legacy clients via canonicalization.
- Strong safety against CSV injection and predictable idempotent behavior.
- Deterministic per-tenant and per-scope replay handling.

## Alternatives Considered

- Reject all non-conforming keys (simpler, but hurts compatibility).
- Generate server-only keys always (limits client-driven idempotency strategies).

