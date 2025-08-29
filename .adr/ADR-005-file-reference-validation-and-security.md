# ADR-005: FileReference validation and security policy

- Status: Accepted
- Date: 2025-08-29
- Related Commits: 313f86a

## Context

We ingest files referenced by URLs or storage keys. To prevent abuse and ensure predictable processing, references must be validated strictly.

## Decision

- Allow only text data formats: `.csv`, `.tsv`, `.txt`.
- Deny dangerous extensions (e.g., `.exe`, `.zip`, scripts, binaries).
- Block path traversal (including backslashes, URL-encoded variants), normalize duplicate slashes.
- Validate S3 bucket names per AWS conventions (lowercase, length/character constraints, no double-dots).
- Reject empty components (no bucket or no key), and require host in HTTP/HTTPS.

## Consequences

- Reduced attack surface and clearer product guarantees for supported inputs.
- Explicit user-facing errors for unsupported types.

## Alternatives Considered

- Permit broader set of file types (increases surface, requires per-type handling).

