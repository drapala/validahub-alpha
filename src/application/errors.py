"""Application layer errors for ValidaHub."""


class ApplicationError(Exception):
    """Base exception for all application layer errors."""

    def __init__(self, message: str) -> None:
        """
        Initialize application error.

        Args:
            message: Error message (must be PII-safe)
        """
        super().__init__(message)
        self.message = message


class RateLimitExceeded(ApplicationError):
    """Raised when rate limit is exceeded for a tenant."""

    def __init__(self, tenant_id: str, resource: str) -> None:
        """
        Initialize rate limit exceeded error.

        Args:
            tenant_id: Tenant identifier
            resource: Rate-limited resource name
        """
        # PII-safe message: tenant_id is an opaque identifier
        message = f"Rate limit exceeded for tenant {tenant_id}"
        super().__init__(message)
        self.tenant_id = tenant_id
        self.resource = resource


class ValidationError(ApplicationError):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str) -> None:
        """
        Initialize validation error.

        Args:
            field: Field name that failed validation
            message: Error message (must be PII-safe)
        """
        super().__init__(f"{field}: {message}")
        self.field = field
        self.validation_message = message
