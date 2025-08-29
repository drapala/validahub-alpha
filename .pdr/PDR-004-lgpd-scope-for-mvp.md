# PDR-004: LGPD scope for MVP

- Status: Accepted
- Date: 2025-08-29
- Supersedes: —

## Context

LGPD compliance spans multiple areas (consent, rights management, retention, anonymization, audit, security). Tests and docs outline the full target scope, but the MVP must focus to ship value quickly.

## Decision

- MVP focuses on: LGPD-compliant logging (masking, neutral errors), security incident logging, idempotency safety, and input validation to prevent data leaks.
- Broader LGPD features (consent management, subject rights operations, immutable audit storage, retention workflows) are deferred to upcoming milestones; related tests serve as executable specs.

## Rationale

- Deliver core CSV validation with strong privacy hygiene first; add advanced LGPD capabilities iteratively.

## Consequences

- Compliance posture improves incrementally; engineering roadmap aligns with the test suite.
- New PDRs will capture scope expansions as they are implemented.

