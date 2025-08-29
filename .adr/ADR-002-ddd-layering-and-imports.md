# ADR-002: DDD layering and import scheme

- Status: Accepted
- Date: 2025-08-29
- Related Commits: 313f86a

## Context

We follow a lightweight DDD approach with clear separation of domain (pure), application (use cases/ports), and shared utilities. Initial imports used `src.*` prefixes causing friction outside pytest where `pythonpath=src` is injected.

## Decision

- Keep `package-dir = {"" = "src"}` and expose packages as `domain`, `application`, and `shared`.
- Unify imports across the codebase to `from domain...`, `from application...`, `from shared...` and drop `src.` prefixes.
- Remove legacy symlink/paths.

## Consequences

- Cleaner import paths that work in all environments (tests, runtime, packaging).
- Reduced confusion with multiple path styles.

## Alternatives Considered

- Keep `src.*` imports everywhere (requires consistent `PYTHONPATH` configuration in all contexts).

