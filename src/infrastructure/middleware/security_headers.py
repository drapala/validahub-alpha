"""Security headers middleware for FastAPI.

This module provides comprehensive security headers to protect
against common web vulnerabilities.
"""

from typing import Dict, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""
    
    def __init__(
        self,
        app,
        csp_policy: Optional[str] = None,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = True,
        enable_nosniff: bool = True,
        enable_xfo: bool = True,
        xfo_option: str = "DENY",
        enable_xss_protection: bool = True,
        referrer_policy: str = "strict-origin-when-cross-origin",
        permissions_policy: Optional[str] = None,
    ):
        """
        Initialize security headers middleware.
        
        Args:
            app: ASGI application
            csp_policy: Content Security Policy directive
            enable_hsts: Enable HTTP Strict Transport Security
            hsts_max_age: HSTS max age in seconds
            hsts_include_subdomains: Include subdomains in HSTS
            hsts_preload: Enable HSTS preload
            enable_nosniff: Enable X-Content-Type-Options
            enable_xfo: Enable X-Frame-Options
            xfo_option: X-Frame-Options value (DENY, SAMEORIGIN)
            enable_xss_protection: Enable X-XSS-Protection
            referrer_policy: Referrer-Policy value
            permissions_policy: Permissions-Policy directive
        """
        super().__init__(app)
        self.csp_policy = csp_policy or self._default_csp()
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload
        self.enable_nosniff = enable_nosniff
        self.enable_xfo = enable_xfo
        self.xfo_option = xfo_option
        self.enable_xss_protection = enable_xss_protection
        self.referrer_policy = referrer_policy
        self.permissions_policy = permissions_policy or self._default_permissions()
    
    def _default_csp(self) -> str:
        """Return default Content Security Policy."""
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "upgrade-insecure-requests;"
        )
    
    def _default_permissions(self) -> str:
        """Return default Permissions Policy."""
        return (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response = await call_next(request)
        
        # Content Security Policy
        if self.csp_policy:
            response.headers["Content-Security-Policy"] = self.csp_policy
        
        # HTTP Strict Transport Security
        if self.enable_hsts:
            hsts_value = f"max-age={self.hsts_max_age}"
            if self.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.hsts_preload:
                hsts_value += "; preload"
            response.headers["Strict-Transport-Security"] = hsts_value
        
        # X-Content-Type-Options
        if self.enable_nosniff:
            response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-Frame-Options
        if self.enable_xfo:
            response.headers["X-Frame-Options"] = self.xfo_option
        
        # X-XSS-Protection
        if self.enable_xss_protection:
            response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer-Policy
        if self.referrer_policy:
            response.headers["Referrer-Policy"] = self.referrer_policy
        
        # Permissions-Policy
        if self.permissions_policy:
            response.headers["Permissions-Policy"] = self.permissions_policy
        
        # Additional security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        
        return response


def get_security_headers(config) -> Dict[str, str]:
    """
    Get security headers based on configuration.
    
    Args:
        config: Application configuration object
        
    Returns:
        Dictionary of security headers
    """
    headers = {}
    
    if config.SECURITY_HEADERS_ENABLED:
        # CSP
        headers["Content-Security-Policy"] = config.CSP_POLICY
        
        # HSTS (only in production)
        if config.ENVIRONMENT.value == "production":
            headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        # Other security headers
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "DENY"
        headers["X-XSS-Protection"] = "1; mode=block"
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), "
            "microphone=(), payment=(), usb=()"
        )
    
    return headers