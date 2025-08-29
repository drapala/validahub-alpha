"""
Context management for structured logging.
"""

import uuid
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional, TypeVar

import structlog

# Context variables for request tracking
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
_tenant_id: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)
_actor_id: ContextVar[Optional[str]] = ContextVar("actor_id", default=None)

T = TypeVar("T")


def with_request_context(
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to add request context to all logs within a function.
    
    Args:
        request_id: Unique request identifier
        correlation_id: Correlation ID for distributed tracing
        tenant_id: Tenant identifier for multi-tenant context
        actor_id: Actor (user/seller) identifier
        
    Returns:
        Decorated function with logging context
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Generate IDs if not provided
            req_id = request_id or generate_request_id()
            corr_id = correlation_id or req_id
            
            # Set context variables
            _request_id.set(req_id)
            _correlation_id.set(corr_id)
            if tenant_id:
                _tenant_id.set(tenant_id)
            if actor_id:
                _actor_id.set(actor_id)
            
            # Bind to structlog context
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(
                request_id=req_id,
                correlation_id=corr_id,
            )
            
            if tenant_id:
                structlog.contextvars.bind_contextvars(tenant_id=tenant_id)
            if actor_id:
                structlog.contextvars.bind_contextvars(actor_id=actor_id)
            
            try:
                return func(*args, **kwargs)
            finally:
                # Clear context after execution
                structlog.contextvars.clear_contextvars()
                _request_id.set(None)
                _correlation_id.set(None)
                _tenant_id.set(None)
                _actor_id.set(None)
        
        return wrapper
    return decorator


def with_tenant_context(tenant_id: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to add tenant context to all logs within a function.
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        Decorated function with tenant context
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            _tenant_id.set(tenant_id)
            structlog.contextvars.bind_contextvars(tenant_id=tenant_id)
            
            try:
                return func(*args, **kwargs)
            finally:
                structlog.contextvars.unbind_contextvars("tenant_id")
                _tenant_id.set(None)
        
        return wrapper
    return decorator


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return f"req_{uuid.uuid4().hex[:12]}"


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for distributed tracing."""
    return f"corr_{uuid.uuid4().hex[:16]}"


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    return _correlation_id.get()


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return _request_id.get()


def get_tenant_id() -> Optional[str]:
    """Get the current tenant ID from context."""
    return _tenant_id.get()


def inject_correlation_id(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Inject correlation ID into HTTP headers for distributed tracing.
    
    Args:
        headers: Dictionary of HTTP headers
        
    Returns:
        Headers with correlation ID added
    """
    corr_id = get_correlation_id()
    if corr_id:
        headers["X-Correlation-Id"] = corr_id
        headers["X-Request-Id"] = get_request_id() or corr_id
    
    tenant_id = get_tenant_id()
    if tenant_id:
        headers["X-Tenant-Id"] = tenant_id
    
    return headers