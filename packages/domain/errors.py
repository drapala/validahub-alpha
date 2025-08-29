"""Domain-specific exceptions and error types."""


class DomainError(Exception):
    """Base class for all domain-related errors.
    
    Domain errors represent business rule violations or invalid operations
    within the domain layer. They should be handled at the application boundary.
    """
    
    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__


class InvalidStateTransitionError(DomainError):
    """Raised when an invalid state transition is attempted.
    
    This occurs when trying to transition an aggregate from one state to another
    when that transition is not allowed by the business rules.
    """
    
    def __init__(self, from_state: str, to_state: str):
        message = f"Invalid state transition from '{from_state}' to '{to_state}'"
        super().__init__(message, "INVALID_STATE_TRANSITION")
        self.from_state = from_state
        self.to_state = to_state


class InvalidValueObjectError(DomainError):
    """Raised when a value object cannot be created due to invalid input.
    
    Value objects must always be in a valid state, so any attempt to create
    one with invalid data should raise this exception.
    """
    
    def __init__(self, value_object_type: str, validation_error: str):
        message = f"Invalid {value_object_type}: {validation_error}"
        super().__init__(message, "INVALID_VALUE_OBJECT")
        self.value_object_type = value_object_type
        self.validation_error = validation_error


class BusinessRuleViolationError(DomainError):
    """Raised when a business rule is violated.
    
    Business rules are domain-specific constraints that must be enforced
    to maintain data integrity and consistency.
    """
    
    def __init__(self, rule_name: str, violation_details: str):
        message = f"Business rule '{rule_name}' violated: {violation_details}"
        super().__init__(message, "BUSINESS_RULE_VIOLATION")
        self.rule_name = rule_name
        self.violation_details = violation_details


class AggregateNotFoundError(DomainError):
    """Raised when a requested aggregate cannot be found.
    
    This is typically used in repository implementations when an aggregate
    with a given identifier does not exist.
    """
    
    def __init__(self, aggregate_type: str, identifier: str):
        message = f"{aggregate_type} with identifier '{identifier}' not found"
        super().__init__(message, "AGGREGATE_NOT_FOUND")
        self.aggregate_type = aggregate_type
        self.identifier = identifier


class ConcurrencyError(DomainError):
    """Raised when a concurrency conflict is detected.
    
    This occurs when an aggregate has been modified by another process
    between the time it was loaded and when changes are being persisted.
    """
    
    def __init__(self, aggregate_type: str, identifier: str, expected_version: int, actual_version: int):
        message = (
            f"Concurrency conflict for {aggregate_type} '{identifier}': "
            f"expected version {expected_version}, actual version {actual_version}"
        )
        super().__init__(message, "CONCURRENCY_ERROR")
        self.aggregate_type = aggregate_type
        self.identifier = identifier
        self.expected_version = expected_version
        self.actual_version = actual_version


class TenantIsolationError(DomainError):
    """Raised when tenant isolation is violated.
    
    This occurs when an operation attempts to access or modify data
    belonging to a different tenant than the current context.
    """
    
    def __init__(self, requested_tenant: str, actual_tenant: str):
        message = f"Tenant isolation violation: requested '{requested_tenant}', but data belongs to '{actual_tenant}'"
        super().__init__(message, "TENANT_ISOLATION_VIOLATION")
        self.requested_tenant = requested_tenant
        self.actual_tenant = actual_tenant


class IdempotencyViolationError(DomainError):
    """Raised when idempotency constraints are violated.
    
    This occurs when an operation with an idempotency key is attempted
    but conflicts with an existing operation.
    """
    
    def __init__(self, idempotency_key: str, operation: str):
        message = f"Idempotency violation for key '{idempotency_key}' in operation '{operation}'"
        super().__init__(message, "IDEMPOTENCY_VIOLATION")
        self.idempotency_key = idempotency_key
        self.operation = operation


class RateLimitExceededError(DomainError):
    """Raised when rate limits are exceeded.
    
    This occurs when a tenant or user has exceeded their allowed
    request rate or quota.
    """
    
    def __init__(self, tenant_id: str, limit_type: str, reset_time: int):
        message = f"Rate limit exceeded for tenant '{tenant_id}' on '{limit_type}', resets at {reset_time}"
        super().__init__(message, "RATE_LIMIT_EXCEEDED")
        self.tenant_id = tenant_id
        self.limit_type = limit_type
        self.reset_time = reset_time


class SecurityViolationError(DomainError):
    """Raised when a security violation is detected.
    
    This includes attempts at injection attacks, unauthorized access,
    or other security-related violations.
    """
    
    def __init__(self, violation_type: str, details: str):
        message = f"Security violation detected: {violation_type} - {details}"
        super().__init__(message, "SECURITY_VIOLATION")
        self.violation_type = violation_type
        self.details = details