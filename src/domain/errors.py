"""Domain errors for ValidaHub."""


class DomainError(Exception):
    """Base exception for all domain errors."""
    
    def __init__(self, message: str) -> None:
        """
        Initialize domain error.
        
        Args:
            message: Error message (must be PII-safe)
        """
        super().__init__(message)
        self.message = message


class InvalidStateTransitionError(DomainError):
    """Raised when an invalid state transition is attempted."""
    
    def __init__(self, from_state: str, to_state: str) -> None:
        """
        Initialize invalid state transition error.
        
        Args:
            from_state: Current state
            to_state: Attempted target state
        """
        # PII-safe message: no user data, just states
        message = f"Invalid state transition from {from_state} to {to_state}"
        super().__init__(message)
        self.from_state = from_state
        self.to_state = to_state