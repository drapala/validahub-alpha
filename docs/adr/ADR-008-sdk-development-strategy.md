# ADR 008 – SDK Development Strategy

**Date:** 2025-08-29
**Status:** Proposed
**Context:** ValidaHub needs client SDKs for rapid partner integration, but API stability and resource allocation must be balanced against time-to-market pressures.

## Options Considered
- Option A: Develop SDKs immediately alongside API development for faster partner onboarding
- Option B: Wait until API v1.0 is stable, then develop comprehensive SDKs with full feature parity
- Option C: Phased approach - start with OpenAPI-only, progress to auto-generated SDKs, then enhance DX

## Decision
- Delay SDK development until API v1 reaches stability milestone
- Implement phased rollout: Phase 0 (OpenAPI), Phase 1 (Auto-generated), Phase 2 (DX enhancements)
- Maintain minimal SDK scope focusing on thin client patterns without business logic
- Establish go/no-go checklist before SDK development begins

## Rationale / Trade-offs
- API changes during early development would require constant SDK maintenance overhead
- OpenAPI-first approach provides immediate client generation capabilities for early adopters
- Resource allocation prioritizes core platform stability over developer tooling initially
- Alignment with ValidaHub principle of contracts-first development (OpenAPI 3.1 as single source of truth)

## Scope & Boundaries
- In-scope: SDK architecture, phasing strategy, technical patterns for webhooks/idempotency/errors
- Out-of-scope: Specific implementation timelines, language-specific SDK features, partner-specific customizations

## Consequences
- Positive: Stable SDK foundation, reduced maintenance burden, cleaner API contracts
- Negative: Delayed partner integrations, potential competitive disadvantage, increased manual integration effort
- Neutral: OpenAPI provides baseline client generation, focused development resources on core platform

## Tests & Quality Gates
- RED: API stability metrics fail go/no-go checklist thresholds
- GREEN: Core API endpoints achieve 99% uptime, breaking changes < 1/month
- REFACTOR: SDK generation pipeline, developer experience improvements, comprehensive examples

## DDD Anchors
- VO: TenantId, ApiKey, WebhookSignature for SDK authentication patterns
- Aggregate: Job aggregate stability drives SDK method signatures
- Service/Ports: ClientPort interface defines SDK contract boundaries

## Telemetry & Security
- Metrics/Events: SDK usage telemetry, client error rates, webhook delivery success
- Threats/Mitigations: API key rotation, webhook signature validation, rate limiting per SDK client

## Implementation Phases

### Phase 0: OpenAPI-Only (Current)
- Partners use openapi-generator or similar tools
- Provide comprehensive OpenAPI 3.1 specification
- Include detailed examples and error schemas
- Go/No-Go Criteria:
  - [ ] Core endpoints stable for 30 days without breaking changes
  - [ ] API response times P95 < 200ms
  - [ ] Error handling patterns consistent across all endpoints
  - [ ] Webhook delivery success rate > 95%

### Phase 1: Auto-Generated SDKs
- JavaScript/TypeScript, Python, Java SDKs via code generation
- Thin client pattern: HTTP client + type safety, no business logic
- Standard patterns for: idempotency keys, retry logic, webhook validation
- Languages prioritized by partner demand

### Phase 2: Developer Experience Enhancements
- Fluent APIs, pagination helpers, webhook framework integration
- CLI tools for testing and development
- Comprehensive documentation and examples
- Partner feedback integration

## Technical Patterns

### Idempotency
```typescript
client.jobs.create(data, { idempotencyKey: "unique-key" })
```

### Error Handling
```python
try:
    job = client.jobs.get(job_id)
except ValidaHubNotFound:
    # Handle 404
except ValidaHubRateLimit as e:
    # Handle 429, retry_after in e.retry_after
```

### Webhooks
```javascript
const isValid = client.webhooks.verify(payload, signature, secret)
```

### Deprecation
- Semantic versioning with clear upgrade paths
- Minimum 6-month deprecation notices
- Automated migration tooling for breaking changes

## Links
- PR: #TBD
- Commit: TBD
- Issue: #TBD
- Related: ADR-001 (Database), contracts/openapi.yaml

---

_Supersedes:_ N/A
_Superseded by:_ N/A