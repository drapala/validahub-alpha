"""
Example logging configuration for ValidaHub (for local demos).

This file is not used by the application/tests; it demonstrates how to initialize
the LGPD-compliant logging system manually.
"""

import os

from shared.logging import configure_logging


def setup_logging():
    """
    Configure ValidaHub logging with LGPD compliance.
    
    This should be called at application startup.
    """
    # Get configuration from environment
    environment = os.getenv("ENVIRONMENT", "development")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    
    # Use JSON logs in production, readable format in development
    json_logs = environment in ["production", "staging"]
    
    # Include caller info only in development for debugging
    include_caller = environment == "development"
    
    # Configure the logging system
    configure_logging(
        environment=environment,
        log_level=log_level,
        json_logs=json_logs,
        include_caller_info=include_caller,
    )
    
    print(f"✅ Logging configured for {environment} environment")
    print(f"   - Log level: {log_level}")
    print(f"   - Format: {'JSON' if json_logs else 'Key-Value'}")
    print("   - LGPD compliance: ENABLED")
    print("   - Sensitive data masking: ACTIVE")
    

if __name__ == "__main__":
    # Example usage
    setup_logging()
    
    from shared.logging import get_logger
    from shared.logging.security import AuditLogger, SecurityLogger
    
    # Regular logging
    logger = get_logger("example")
    logger.info("application_started", version="1.0.0", environment="development")
    
    # Security logging
    security = SecurityLogger("example.security")
    security.injection_attempt(
        injection_type="sql",
        field_name="search_query",
        input_value="'; DROP TABLE users; --"
    )
    
    # Audit logging
    audit = AuditLogger("example.audit")
    audit.job_lifecycle(
        event_type=audit.AuditEventType.JOB_SUBMITTED,
        job_id="job_123",
        status="queued",
        actor_id="seller_456",
        channel="mercado_livre",
    )
    
    # Example with sensitive data (will be masked)
    logger.info(
        "user_action",
        tenant_id="tenant_company_xyz_123",  # Will be masked to "ten***123"
        idempotency_key="key_1234567890abcdef",  # Will be masked to "key_1234***"
        email="user@example.com",  # Will be masked to "u***@example.com"
        file_ref="s3://my-bucket/path/to/file.csv",  # Will be masked to "s3://my-bucket/***"
    )
