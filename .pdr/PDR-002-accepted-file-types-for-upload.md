# PDR-002: Accepted file types for upload

- Status: Accepted
- Date: 2025-08-29
- Supersedes: —

## Context

ValidaHub processes CSV-like data for marketplaces. Allowing arbitrary file types increases complexity and security risk.

## Decision

- MVP accepts only `.csv`, `.tsv`, and `.txt` files for job submissions, regardless of storage scheme (S3/http/plain path).
- Non-text types (archives, binaries, PDFs, JSON, etc.) are rejected.
- Path traversal and malformed references are blocked, including Windows-style backslashes.

## Rationale

- Focus on core value (CSV validation/correction) while reducing attack surface.

## Consequences

- Clear user expectations for supported inputs; better security posture.
- Future expansions to other types will require a new PDR and corresponding validations.

