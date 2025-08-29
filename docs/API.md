# ValidaHub API Documentation

## Idempotency Policy

ValidaHub implements comprehensive idempotency protection to ensure request safety, prevent accidental duplicate operations, and maintain data consistency across all endpoints that create or modify resources.

### Overview

Idempotency keys provide a mechanism to safely retry requests without risk of duplicated operations. When you provide an idempotency key with a request, ValidaHub will return the same response for subsequent requests with the same key within a 24-hour window.

### Key Requirements

#### Strict Format Validation

Idempotency keys must conform to strict security requirements:

- **Length**: 16-128 characters
- **Characters**: Only alphanumeric (A-Z, a-z, 0-9), hyphens (-), and underscores (_)
- **Pattern**: `^[A-Za-z0-9\-_]{16,128}$`

#### CSV Formula Injection Protection

For security, idempotency keys **cannot** start with the following characters:
- `=` (equals sign)
- `+` (plus sign) 
- `-` (hyphen when at start)
- `@` (at symbol)

This prevents CSV formula injection attacks when keys are exported or processed.

### Auto-Generation Behavior

When no `Idempotency-Key` header is provided, ValidaHub automatically generates a secure 22-character key using:

1. **KSUID-like generation**: 20 random bytes encoded with base32
2. **Tenant isolation**: Keys are scoped to the specific tenant
3. **Endpoint isolation**: Keys are scoped to the HTTP method and route template
4. **Security hardening**: Generated keys are guaranteed safe (no formula characters)

**Example auto-generated key**: `k7x2m5qp8w9r3a6c1v4n8z`

### Legacy Compatibility

ValidaHub supports two compatibility modes for handling legacy idempotency keys:

#### Canonicalize Mode (Default)

Legacy keys are transformed into secure format using deterministic hashing:

```http
# Legacy key input
Idempotency-Key: order.123:item-456

# Becomes canonicalized to secure format
# k8h3n7qw9p2x5c1m4z6v0b (22 characters, safe)
```

**Legacy patterns detected:**
- Keys shorter than 16 characters
- Keys containing dots (`.`), colons (`:`), spaces, brackets, or other unsafe characters

#### Reject Mode

When `IDEMP_COMPAT_MODE=reject`, all legacy keys are rejected with error:

```json
{
  "error": "Legacy idempotency key format not supported",
  "code": "INVALID_IDEMPOTENCY_KEY"
}
```

### Scope Isolation

Idempotency keys are isolated by:

1. **Tenant**: Same key for different tenants are treated as separate
2. **HTTP Method + Route**: `POST /jobs` vs `PUT /jobs/123` are separate scopes

This prevents cross-contamination between different operations.

### Storage Design

#### Database Schema

```sql
CREATE TABLE idempotency_store (
  tenant_id text NOT NULL,
  idempotency_key text NOT NULL,
  response_hash text NOT NULL,
  response_data jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  
  -- Unique constraint ensures no duplicates per tenant
  CONSTRAINT unique_tenant_key UNIQUE (tenant_id, idempotency_key),
  
  -- Security validation at database level
  CONSTRAINT valid_key_format CHECK (
    idempotency_key ~ '^[A-Za-z0-9\-_]{16,128}$' 
    AND NOT (
      idempotency_key LIKE '=%' OR 
      idempotency_key LIKE '+%' OR 
      idempotency_key LIKE '-%' OR 
      idempotency_key LIKE '@%'
    )
  )
);

-- TTL cleanup index
CREATE INDEX idx_idempotency_expires ON idempotency_store (expires_at);
```

#### TTL and Cleanup

- **Default TTL**: 24 hours
- **Automatic cleanup**: Expired records are removed on access
- **Background cleanup**: Periodic job removes expired records

### Security Considerations

#### PII-Safe Logging

Idempotency keys may contain sensitive information, so logging follows strict guidelines:

```json
// ✓ GOOD - Only log metadata
{
  "message": "idempotency_key_canonicalized",
  "tenant_id": "t_seller123", 
  "original_length": 15,
  "canonical_length": 22,
  "scope": "a8f3d2b1"
}

// ✗ BAD - Never log actual keys
{
  "message": "idempotency_key_received",
  "key": "order.123:item-456"  // PII exposure risk
}
```

#### Neutral Error Messages

All validation errors return the same neutral message to prevent information leakage:

```json
{
  "error": "Invalid idempotency key format",
  "code": "INVALID_IDEMPOTENCY_KEY"
}
```

Detailed validation failures are logged securely for monitoring but never exposed to clients.

#### Constant-Time Comparisons

Response matching uses `hmac.compare_digest()` for constant-time comparison to prevent timing attacks.

### Examples

#### Valid Idempotency Keys

```http
# UUID format
Idempotency-Key: f47ac10b-58cc-4372-a567-0e02b2c3d479

# Custom format with allowed characters  
Idempotency-Key: order-2024-08-29-001
Idempotency-Key: batch_upload_20240829120000
Idempotency-Key: seller123-retry-3-attempt-456
Idempotency-Key: IMPORT-CSV-a1b2c3d4

# Base64-like format
Idempotency-Key: k8h3n7qw9p2x5c1m4z6v0b
```

#### Invalid Idempotency Keys

```http
# Too short
Idempotency-Key: abc123

# Contains forbidden characters
Idempotency-Key: order.123:item
Idempotency-Key: key with spaces
Idempotency-Key: key/with/slashes

# Starts with formula characters (CSV injection)
Idempotency-Key: =SUM(A1:A5)
Idempotency-Key: +1+1
Idempotency-Key: @calc
Idempotency-Key: -IMPORT()

# Too long (>128 chars)
Idempotency-Key: [129+ character string]
```

### Usage Examples

#### Creating a Job with Idempotency

```http
POST /api/v1/jobs
Content-Type: application/json
Authorization: Bearer <token>
X-Tenant-Id: t_seller123
Idempotency-Key: order-processing-2024-08-29-001

{
  "channel": "mercado_livre",
  "file_ref": "s3://my-bucket/products.csv",
  "rules_profile": "ml@1.2.3"
}
```

**Response (201 Created):**
```json
{
  "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "queued",
  "created_at": "2024-08-29T10:30:00Z",
  "idempotency_key": "order-processing-2024-08-29-001"
}
```

#### Retrying the Same Request

```http
POST /api/v1/jobs
Content-Type: application/json  
Authorization: Bearer <token>
X-Tenant-Id: t_seller123
Idempotency-Key: order-processing-2024-08-29-001

{
  "channel": "mercado_livre",
  "file_ref": "s3://my-bucket/products.csv", 
  "rules_profile": "ml@1.2.3"
}
```

**Response (200 OK):**
```json
{
  "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "running", 
  "created_at": "2024-08-29T10:30:00Z",
  "idempotency_key": "order-processing-2024-08-29-001"
}
```

#### Request Without Idempotency Key

```http
POST /api/v1/jobs
Content-Type: application/json
Authorization: Bearer <token>
X-Tenant-Id: t_seller123

{
  "channel": "mercado_livre", 
  "file_ref": "s3://my-bucket/products.csv",
  "rules_profile": "ml@1.2.3"
}
```

**Response (201 Created):**
```json
{
  "job_id": "a8f3d2b1-9e4c-4f7a-b6d5-1c8e9f2a3b4c",
  "status": "queued",
  "created_at": "2024-08-29T10:32:15Z", 
  "idempotency_key": "k7x2m5qp8w9r3a6c1v4n8z"
}
```

### Conflict Handling

#### Idempotency Conflict (409)

When the same key is used with different request data:

```http
POST /api/v1/jobs
Idempotency-Key: order-processing-2024-08-29-001

{
  "channel": "americanas",  // Different from original
  "file_ref": "s3://my-bucket/products.csv",
  "rules_profile": "ml@1.2.3"
}
```

**Response (409 Conflict):**
```json
{
  "error": "Idempotency conflict: key already exists with different response",
  "code": "IDEMPOTENCY_CONFLICT",
  "details": {
    "idempotency_key": "order-processing-2024-08-29-001",
    "tenant_id": "t_seller123"
  }
}
```

### Migration and Compatibility

#### Testing Compatibility Mode

You can test legacy key handling in development:

```bash
# Test canonicalize mode (default)
export IDEMP_COMPAT_MODE=canonicalize

# Test reject mode
export IDEMP_COMPAT_MODE=reject
```

#### Migration Strategy

For production migration from legacy keys:

1. **Phase 1**: Deploy with `IDEMP_COMPAT_MODE=canonicalize` 
2. **Phase 2**: Monitor legacy key usage and client updates
3. **Phase 3**: Switch to `IDEMP_COMPAT_MODE=reject` for new strict validation
4. **Phase 4**: Remove legacy canonicalization after full client migration

### Performance Considerations

#### Key Generation Performance

- Auto-generated keys use cryptographically secure random generation
- Generation time: ~0.1ms per key
- Base32 encoding provides optimal size vs. readability tradeoff

#### Storage Performance

- Unique index on `(tenant_id, idempotency_key)` for fast lookups
- TTL-based cleanup prevents unbounded growth
- Response data stored as JSONB for efficient querying

### Monitoring and Observability

#### Key Metrics

```
idemp_key_generated_total    # Auto-generated keys
idemp_key_canonicalized_total # Legacy keys transformed
idemp_key_rejected_total     # Legacy keys rejected
idemp_conflict_total         # Idempotency conflicts
idemp_lookup_duration        # Lookup performance
```

#### Security Events

```
csv_injection_attempt_total  # Formula character attempts  
invalid_key_format_total     # Malformed keys
legacy_key_usage_total       # Legacy pattern usage
```

These metrics help monitor security posture and migration progress.