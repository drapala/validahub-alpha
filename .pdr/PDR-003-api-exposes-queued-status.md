# PDR-003: API exposes 'queued' status post-submission

- Status: Accepted
- Date: 2025-08-29
- Supersedes: —

## Context

Users expect an immediate `queued` status after submission. The domain state machine remains minimal (SUBMITTED, RUNNING, COMPLETED, FAILED, RETRYING) to avoid overloading domain semantics with infrastructure/queueing concerns.

## Decision

- The API response for job submission reports status `queued` to clients, while the domain aggregate starts from `submitted`.
- The persisted/application model uses a string `queued` for compatibility and UX.

## Rationale

- Aligns with external expectations and simplifies UI flows without coupling domain logic to queue mechanics.

## Consequences

- Clear contract for clients; domain model stays pure and simple.
- Mapping layer responsibility to translate domain state to API-facing status where needed.

