"""Secure idempotency key resolver with legacy compatibility."""

import base64
import hashlib
import hmac
import re
import secrets
from typing import Optional

from src.application.config import Config, IdempotencyCompatMode
from src.domain.value_objects import TenantId

# Graceful handling of logging dependencies
try:
    from shared.logging import get_logger
    from shared.logging.security import SecurityLogger, SecurityEventType
except ImportError:
    # Fallback logging for testing without full dependencies
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)
    
    class SecurityLogger:
        def __init__(self, name: str):
            self.logger = logging.getLogger(name)
        
        def injection_attempt(self, **kwargs):
            self.logger.warning("Injection attempt detected", extra=kwargs)
        
        def log_security_event(self, event_type, message, **kwargs):
            self.logger.warning(f"Security event: {message}", extra=kwargs)
        
        class SecurityEventType:
            LEGACY_KEY_REJECTED = "legacy_key_rejected"
            INVALID_KEY = "invalid_key"


# CSV injection prevention: formula characters that cannot start a key
CSV_FORMULA_CHARS = {'=', '+', '-', '@'}

# Valid idempotency key pattern (current secure format)
SECURE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")

# Legacy patterns that need canonicalization
LEGACY_INDICATORS = {'.', ':', ' ', '<', '>', '[', ']', '{', '}', '|', '\\'}


def _is_legacy_key(key: str) -> bool:
    """Check if key appears to be in legacy format."""
    if len(key) < 16:
        return True
    
    # Check for legacy characters
    if any(char in key for char in LEGACY_INDICATORS):
        return True
    
    # If it matches secure pattern and is long enough, it's not legacy
    return not SECURE_KEY_PATTERN.match(key)


def _generate_ksuid_like() -> str:
    """Generate a KSUID-like identifier (base32 encoded random bytes)."""
    # Generate 20 random bytes (160 bits)
    random_bytes = secrets.token_bytes(20)
    # Base32 encode (no padding, lowercase)
    return base64.b32encode(random_bytes).decode('ascii').rstrip('=').lower()


def _safe_base64url_encode(data: bytes) -> str:
    """Base64url encode with padding removal."""
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _canonicalize_key(tenant_id: str, raw_key: str) -> str:
    """Canonicalize legacy key using secure hash."""
    # Create deterministic hash using tenant_id as salt
    input_data = f"{tenant_id}:{raw_key}".encode('utf-8')
    hash_bytes = hashlib.sha256(input_data).digest()
    
    # Take first 16 bytes and base64url encode (22 chars without padding)
    canonical = _safe_base64url_encode(hash_bytes[:16])
    
    return canonical


def _ensure_safe_first_char(key: str) -> str:
    """Ensure key doesn't start with CSV formula characters."""
    if key and key[0] in CSV_FORMULA_CHARS:
        # Prefix with 'k' to make it safe
        return f"k{key}"
    return key


def _create_scope_hash(method: str, route_template: str) -> str:
    """Create scope hash for method and route template."""
    scope_input = f"{method.upper()}:{route_template}".encode('utf-8')
    return hashlib.sha256(scope_input).hexdigest()[:8]


def resolve_idempotency_key(
    raw_key: Optional[str], 
    tenant_id: TenantId, 
    method: str,
    route_template: str
) -> str:
    """
    Resolve idempotency key with secure canonicalization and CSV injection prevention.
    
    Args:
        raw_key: Raw idempotency key from request (can be None, legacy, or secure)
        tenant_id: Tenant identifier for isolation
        method: HTTP method (e.g., "POST")  
        route_template: Route template (e.g., "/jobs")
        
    Returns:
        Resolved secure idempotency key (16-128 chars, safe first char)
        
    Raises:
        ValueError: If legacy key rejected in REJECT mode
    """
    logger = get_logger("application.idempotency.resolver")
    security_logger = SecurityLogger("application.idempotency.resolver")
    
    compat_mode = Config.get_idemp_compat_mode()
    scope_hash = _create_scope_hash(method, route_template)
    
    # Case 1: No key provided - generate new secure key
    if not raw_key:
        logger.debug(
            "idempotency_key_generated",
            tenant_id=tenant_id.value,
            method=method,
            route_template=route_template,
            compat_mode=compat_mode.value
        )
        
        # Generate KSUID-like identifier
        ksuid = _generate_ksuid_like()
        
        # Create hash input with tenant isolation and scope
        hash_input = f"{tenant_id.value}:{scope_hash}:{ksuid}".encode('utf-8')
        hash_bytes = hashlib.sha256(hash_input).digest()
        
        # Take first 16 bytes and base64url encode for 22-char key
        key_candidate = _safe_base64url_encode(hash_bytes[:16])
        
        # Ensure safe first character
        resolved_key = _ensure_safe_first_char(key_candidate)
        
        logger.info(
            "idempotency_key_auto_generated",
            tenant_id=tenant_id.value,
            key_length=len(resolved_key),
            scope=scope_hash
        )
        
        return resolved_key
    
    # Case 2: Key provided - validate and potentially canonicalize
    raw_key = raw_key.strip()
    
    # Check if it's already in secure format
    if SECURE_KEY_PATTERN.match(raw_key) and raw_key[0] not in CSV_FORMULA_CHARS:
        logger.debug(
            "idempotency_key_accepted_as_secure",
            tenant_id=tenant_id.value,
            key_length=len(raw_key)
        )
        return raw_key
    
    # It's a legacy key - check compatibility mode
    if _is_legacy_key(raw_key):
        if compat_mode == IdempotencyCompatMode.REJECT:
            security_logger.log_security_event(
                SecurityEventType.SUSPICIOUS_ACTIVITY if hasattr(SecurityEventType, 'SUSPICIOUS_ACTIVITY') else SecurityEventType.INVALID_FILE_TYPE,
                "Legacy idempotency key rejected",
                severity="WARNING",
                tenant_id=tenant_id.value,
                key_length=len(raw_key),
                has_legacy_chars=any(char in raw_key for char in LEGACY_INDICATORS)
            )
            raise ValueError("Legacy idempotency key format not supported")
        
        # Canonicalize mode - transform to secure format
        logger.info(
            "idempotency_key_canonicalizing_legacy",
            tenant_id=tenant_id.value,
            original_length=len(raw_key),
            has_dots='.' in raw_key,
            has_colons=':' in raw_key,
            has_spaces=' ' in raw_key
        )
        
        # Add scope to canonicalization for method/route isolation
        canonical_input = f"{scope_hash}:{raw_key}"
        canonical_key = _canonicalize_key(tenant_id.value, canonical_input)
        
        # Ensure safe first character  
        resolved_key = _ensure_safe_first_char(canonical_key)
        
        logger.info(
            "idempotency_key_canonicalized",
            tenant_id=tenant_id.value,
            original_length=len(raw_key),
            canonical_length=len(resolved_key),
            scope=scope_hash
        )
        
        return resolved_key
    
    # Key has dangerous first character - needs canonicalization
    if raw_key[0] in CSV_FORMULA_CHARS:
        security_logger.injection_attempt(
            injection_type="csv_formula",
            field_name="idempotency_key_raw",
            first_char=raw_key[0]
        )
        
        if compat_mode == IdempotencyCompatMode.REJECT:
            raise ValueError("Idempotency key cannot start with formula characters")
        
        # Canonicalize to make safe
        canonical_input = f"{scope_hash}:{raw_key}"
        canonical_key = _canonicalize_key(tenant_id.value, canonical_input)
        resolved_key = _ensure_safe_first_char(canonical_key)
        
        logger.warning(
            "idempotency_key_formula_char_canonicalized", 
            tenant_id=tenant_id.value,
            dangerous_first_char=raw_key[0],
            resolved_length=len(resolved_key)
        )
        
        return resolved_key
    
    # Should not reach here - return the key as-is with safety check
    return _ensure_safe_first_char(raw_key)


def validate_resolved_key(key: str) -> bool:
    """
    Validate that resolved key meets security requirements.
    
    Args:
        key: Resolved idempotency key
        
    Returns:
        True if key is valid and secure
    """
    # Must be 16-128 characters
    if not (16 <= len(key) <= 128):
        return False
    
    # Must not start with CSV formula characters
    if key and key[0] in CSV_FORMULA_CHARS:
        return False
    
    # Must contain only safe characters
    if not re.match(r"^[A-Za-z0-9_-]+$", key):
        return False
    
    return True
