"""Domain exceptions for Rules bounded context.

These exceptions represent business rule violations and domain constraints.
"""


class RulesDomainError(Exception):
    """Base exception for rules domain errors."""
    pass


class InvalidStateTransitionError(RulesDomainError):
    """Raised when an invalid state transition is attempted."""
    
    def __init__(self, current_state: str, attempted_action: str):
        self.current_state = current_state
        self.attempted_action = attempted_action
        super().__init__(
            f"Cannot {attempted_action} rules in {current_state} status"
        )


class VersionAlreadyExistsError(RulesDomainError):
    """Raised when attempting to add a version that already exists."""
    
    def __init__(self, version: str):
        self.version = version
        super().__init__(f"Version {version} already exists")


class VersionNotFoundError(RulesDomainError):
    """Raised when a requested version is not found."""
    
    def __init__(self, version: str):
        self.version = version
        super().__init__(f"Version {version} not found")


class VersionSequenceError(RulesDomainError):
    """Raised when version sequence constraints are violated."""
    
    def __init__(self, message: str = "New version must be higher than existing versions"):
        super().__init__(message)


class CompatibilityPolicyViolationError(RulesDomainError):
    """Raised when a change violates the compatibility policy."""
    
    def __init__(self, message: str = "Breaking changes not allowed by policy"):
        super().__init__(message)


class CurrentVersionError(RulesDomainError):
    """Raised when an operation conflicts with the current version."""
    
    def __init__(self, message: str):
        super().__init__(message)


class EmptyRuleSetError(RulesDomainError):
    """Raised when a rule set or version has no rules."""
    
    def __init__(self, message: str = "Rule version must contain at least one rule"):
        super().__init__(message)


class DuplicateRuleIdError(RulesDomainError):
    """Raised when duplicate rule IDs are detected."""
    
    def __init__(self, message: str = "Duplicate rule IDs within version"):
        super().__init__(message)