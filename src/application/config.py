"""Application configuration for ValidaHub."""

import os
from enum import Enum
from typing import Optional


class IdempotencyCompatMode(Enum):
    """Idempotency compatibility mode for legacy key handling."""
    CANONICALIZE = "canonicalize"  # Transform legacy keys to secure format
    REJECT = "reject"  # Reject all legacy keys


class Config:
    """Application configuration with security defaults."""
    
    # Idempotency settings
    IDEMP_COMPAT_MODE: IdempotencyCompatMode = IdempotencyCompatMode(
        os.getenv("IDEMP_COMPAT_MODE", "canonicalize")
    )
    
    # Rate limiting settings
    RATE_LIMIT_REDIS_URL: str = os.getenv("RATE_LIMIT_REDIS_URL", "redis://localhost:6379/0")
    
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://localhost/validahub")
    
    # Security settings
    JWT_SECRET_KEY: Optional[str] = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    
    # CORS settings
    CORS_ALLOWED_ORIGINS: list[str] = [
        origin.strip() 
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls) -> None:
        """Validate critical configuration values."""
        if not cls.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY must be set in environment")
        
        if len(cls.JWT_SECRET_KEY) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")

    @classmethod
    def get_idemp_compat_mode(cls) -> IdempotencyCompatMode:
        """Return current idempotency compatibility mode (reads env at call time)."""
        return IdempotencyCompatMode(os.getenv("IDEMP_COMPAT_MODE", cls.IDEMP_COMPAT_MODE.value))
