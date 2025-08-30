"""FastAPI application for ValidaHub API.

This module provides the main FastAPI application with:
- OpenAPI contract loading and validation
- Middleware for security, logging, and observability
- JWT authentication and authorization
- Multi-tenant request context
- Comprehensive error handling
- Health and readiness endpoints

The application follows the hexagonal architecture with
dependency injection for all external services.
"""

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from packages.application.config import get_config
from packages.domain.errors import (
    DomainError,
    IdempotencyViolationError,
    RateLimitExceededError,
    SecurityViolationError,
    TenantIsolationError,
)
from packages.infra.auth.jwt_service import JWTService
from packages.infra.middleware.security_headers import SecurityHeadersMiddleware

try:
    from packages.shared.logging import get_logger
    from packages.shared.telemetry import get_metrics, get_tracer
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)
    
    class MockTracer:
        def start_span(self, *args, **kwargs):
            return self
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    
    class MockMetrics:
        def increment(self, *args, **kwargs):
            pass
        def histogram(self, *args, **kwargs):
            pass
    
    def get_tracer(name: str):
        return MockTracer()
    
    def get_metrics():
        return MockMetrics()


# Global instances
logger = get_logger("apps.api")
tracer = get_tracer("apps.api")
metrics = get_metrics()
security = HTTPBearer()
config = get_config()
jwt_service = JWTService(
    public_key=config.JWT_PUBLIC_KEY,
    private_key=config.JWT_PRIVATE_KEY,
    algorithm=config.JWT_ALGORITHM,
    issuer=config.JWT_ISSUER,
    audience=config.JWT_AUDIENCE,
    token_ttl_seconds=config.JWT_ACCESS_TOKEN_TTL,
    refresh_ttl_seconds=config.JWT_REFRESH_TOKEN_TTL,
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware for request context management and observability."""
    
    async def dispatch(self, request: Request, call_next):
        # Generate request ID if not present
        request_id = request.headers.get("x-request-id")
        if not request_id:
            from uuid import uuid4
            request_id = str(uuid4())
        
        # Start timing
        start_time = time.time()
        
        # Add request context
        request.state.request_id = request_id
        request.state.tenant_id = request.headers.get("x-tenant-id")
        request.state.user_id = None  # Set by auth middleware
        
        # Create tracing span
        with tracer.start_span("http_request") as span:
            span.set_attributes({
                "http.method": request.method,
                "http.url": str(request.url),
                "http.route": request.url.path,
                "request.id": request_id,
                "tenant.id": request.state.tenant_id,
            })
            
            try:
                response = await call_next(request)
                
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Add response headers
                response.headers["x-request-id"] = request_id
                response.headers["x-response-time"] = f"{duration_ms:.2f}ms"
                
                # Record metrics
                metrics.increment(
                    "http_requests_total",
                    tags={
                        "method": request.method,
                        "status": str(response.status_code),
                        "route": request.url.path,
                    }
                )
                
                metrics.histogram(
                    "http_request_duration_ms",
                    duration_ms,
                    tags={
                        "method": request.method,
                        "status": str(response.status_code),
                        "route": request.url.path,
                    }
                )
                
                # Set span attributes
                span.set_attributes({
                    "http.status_code": response.status_code,
                    "http.response_size": len(response.body) if hasattr(response, 'body') else 0,
                })
                
                # Log request
                logger.info(
                    "http_request_completed",
                    method=request.method,
                    path=request.url.path,
                    status=response.status_code,
                    duration_ms=round(duration_ms, 2),
                    request_id=request_id,
                    tenant_id=request.state.tenant_id,
                    user_id=request.state.user_id,
                )
                
                return response
                
            except Exception as error:
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Record error metrics
                metrics.increment(
                    "http_requests_total",
                    tags={
                        "method": request.method,
                        "status": "500",
                        "route": request.url.path,
                        "error": error.__class__.__name__,
                    }
                )
                
                # Set span error
                span.record_exception(error)
                span.set_attributes({
                    "http.status_code": 500,
                    "error.type": error.__class__.__name__,
                })
                
                # Log error
                logger.error(
                    "http_request_failed",
                    method=request.method,
                    path=request.url.path,
                    duration_ms=round(duration_ms, 2),
                    request_id=request_id,
                    tenant_id=request.state.tenant_id,
                    user_id=request.state.user_id,
                    error=str(error),
                    error_type=error.__class__.__name__,
                )
                
                raise


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for JWT authentication and authorization."""
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for health endpoints
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return await call_next(request)
        
        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        try:
            # Get authorization header
            auth_header = request.headers.get("authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing or invalid authorization header",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Extract token
            token = auth_header.split(" ", 1)[1]
            
            # Validate token (mock implementation)
            user_claims = await self._validate_token(token)
            
            # Set user context
            request.state.user_id = user_claims.get("sub")
            request.state.user_scopes = user_claims.get("scopes", [])
            
            # Validate tenant access
            tenant_id = request.headers.get("x-tenant-id")
            if tenant_id and tenant_id not in user_claims.get("tenants", []):
                logger.warning(
                    "tenant_access_denied",
                    user_id=request.state.user_id,
                    requested_tenant=tenant_id,
                    allowed_tenants=user_claims.get("tenants", []),
                    request_id=request.state.request_id,
                )
                
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied for requested tenant",
                )
            
            return await call_next(request)
            
        except HTTPException:
            raise
        except Exception as error:
            logger.error(
                "authentication_error",
                error=str(error),
                error_type=error.__class__.__name__,
                request_id=getattr(request.state, 'request_id', None),
            )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    async def _validate_token(self, token: str) -> dict[str, Any]:
        """
        Validate JWT token and extract claims using secure JWT service.
        
        This validates:
        1. JWT signature using public key (RS256/ES256)
        2. Token expiration and not-before times
        3. Token revocation status
        4. Issuer and audience claims
        5. Required claims (sub, jti, exp, iat)
        """
        return await jwt_service.validate_token(token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("validahub_api_starting", version="1.0.0")
    
    # Initialize services (database connections, etc.)
    # This would be where you initialize your dependency injection container
    
    yield
    
    # Shutdown
    logger.info("validahub_api_shutting_down")
    
    # Cleanup resources
    # Close database connections, message queues, etc.


# Create FastAPI application
app = FastAPI(
    title="ValidaHub API",
    description="Multi-tenant CSV validation and data processing API",
    version="1.0.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add security middleware with proper configuration
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=config.TRUSTED_HOSTS
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["X-Tenant-Id", "X-Request-Id", "Idempotency-Key", "Content-Type", "Authorization"],
    max_age=3600,
)

# Add security headers middleware
if config.SECURITY_HEADERS_ENABLED:
    app.add_middleware(
        SecurityHeadersMiddleware,
        csp_policy=config.CSP_POLICY,
        enable_hsts=(config.ENVIRONMENT.value == "production"),
        enable_nosniff=True,
        enable_xfo=True,
        xfo_option="DENY",
        enable_xss_protection=True,
        referrer_policy="strict-origin-when-cross-origin",
    )

# Add custom middleware
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(RequestContextMiddleware)


# Exception handlers
@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    """Handle domain-specific errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    
    # Map specific domain errors to HTTP status codes
    if isinstance(exc, RateLimitExceededError):
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(exc, SecurityViolationError):
        status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, TenantIsolationError):
        status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, IdempotencyViolationError):
        status_code = status.HTTP_409_CONFLICT
    
    return JSONResponse(
        status_code=status_code,
        content={
            "code": exc.code or exc.__class__.__name__,
            "message": exc.message,
            "request_id": getattr(request.state, 'request_id', None),
            "timestamp": time.time(),
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "code": "VALIDATION_ERROR",
            "message": str(exc),
            "request_id": getattr(request.state, 'request_id', None),
            "timestamp": time.time(),
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=exc.__class__.__name__,
        request_id=getattr(request.state, 'request_id', None),
        path=request.url.path,
        method=request.method,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "request_id": getattr(request.state, 'request_id', None),
            "timestamp": time.time(),
        }
    )


# Health endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    # Check dependencies (database, Redis, etc.)
    dependencies = {
        "database": "healthy",  # Would check actual database connection
        "redis": "healthy",     # Would check actual Redis connection
        "storage": "healthy",   # Would check actual object storage
    }
    
    # Determine overall readiness
    is_ready = all(status == "healthy" for status in dependencies.values())
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "dependencies": dependencies,
            "timestamp": time.time(),
        }
    )


# Dependency injection helpers
def get_request_context(request: Request) -> dict[str, Any]:
    """Get request context for dependency injection."""
    return {
        "request_id": getattr(request.state, 'request_id', None),
        "tenant_id": getattr(request.state, 'tenant_id', None),
        "user_id": getattr(request.state, 'user_id', None),
        "user_scopes": getattr(request.state, 'user_scopes', []),
    }


# Include routers
from .routers import jobs  # noqa: E402

app.include_router(
    jobs.router,
    prefix="/v1/jobs",
    tags=["jobs"],
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None,  # Use our custom logging
    )