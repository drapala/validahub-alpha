"""Application configuration for ValidaHub with secure secrets management."""

from enum import Enum

from src.application.ports import SecretsManager


class IdempotencyCompatMode(Enum):
    """Idempotency compatibility mode for legacy key handling."""

    CANONICALIZE = "canonicalize"  # Transform legacy keys to secure format
    REJECT = "reject"  # Reject all legacy keys


class Environment(Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class Config:
    """Application configuration with secure secrets management."""

    def __init__(self, secrets_manager: SecretsManager):
        """Initialize configuration with secrets manager."""
        self.secrets = secrets_manager
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from secrets manager."""
        # Environment
        self.ENVIRONMENT = Environment(self.secrets.get("ENVIRONMENT", "development").lower())

        # Idempotency settings
        self.IDEMP_COMPAT_MODE = IdempotencyCompatMode(
            self.secrets.get("IDEMP_COMPAT_MODE", "canonicalize")
        )

        # Database
        self.DATABASE_URL = self.secrets.get_database_url()
        self.DATABASE_POOL_SIZE = int(self.secrets.get("DATABASE_POOL_SIZE", "20"))
        self.DATABASE_MAX_OVERFLOW = int(self.secrets.get("DATABASE_MAX_OVERFLOW", "40"))

        # Redis
        self.REDIS_URL = self.secrets.get_redis_url()
        self.REDIS_MAX_CONNECTIONS = int(self.secrets.get("REDIS_MAX_CONNECTIONS", "50"))

        # JWT Configuration
        public_key, private_key = self.secrets.get_jwt_keys()
        self.JWT_PUBLIC_KEY = public_key
        self.JWT_PRIVATE_KEY = private_key
        self.JWT_ALGORITHM = self.secrets.get("JWT_ALGORITHM", "RS256")
        self.JWT_ISSUER = self.secrets.get("JWT_ISSUER", "validahub")
        self.JWT_AUDIENCE = self.secrets.get("JWT_AUDIENCE", "validahub-api")
        self.JWT_ACCESS_TOKEN_TTL = int(self.secrets.get("JWT_ACCESS_TOKEN_TTL", "3600"))
        self.JWT_REFRESH_TOKEN_TTL = int(self.secrets.get("JWT_REFRESH_TOKEN_TTL", "86400"))

        # CORS Configuration
        cors_origins = self.secrets.get("CORS_ALLOWED_ORIGINS", "")
        if self.ENVIRONMENT == Environment.PRODUCTION:
            # Production: strict CORS from Doppler
            if not cors_origins:
                raise ValueError("CORS_ALLOWED_ORIGINS must be set in production")
            self.CORS_ALLOWED_ORIGINS = [
                origin.strip() for origin in cors_origins.split(",") if origin.strip()
            ]
        else:
            # Development/Staging: allow localhost
            default_origins = "http://localhost:3000,http://localhost:3001"
            origins_str = cors_origins or default_origins
            self.CORS_ALLOWED_ORIGINS = [
                origin.strip() for origin in origins_str.split(",") if origin.strip()
            ]

        # Trusted Hosts Configuration
        trusted_hosts = self.secrets.get("TRUSTED_HOSTS", "")
        if self.ENVIRONMENT == Environment.PRODUCTION:
            # Production: strict host validation
            if not trusted_hosts:
                raise ValueError("TRUSTED_HOSTS must be set in production")
            self.TRUSTED_HOSTS = [host.strip() for host in trusted_hosts.split(",") if host.strip()]
        else:
            # Development/Staging: allow common hosts
            default_hosts = "localhost,127.0.0.1,validahub.local"
            hosts_str = trusted_hosts or default_hosts
            self.TRUSTED_HOSTS = [host.strip() for host in hosts_str.split(",") if host.strip()]

        # Rate Limiting
        self.RATE_LIMIT_ENABLED = self.secrets.get("RATE_LIMIT_ENABLED", "true") == "true"
        self.RATE_LIMIT_REQUESTS_PER_MINUTE = int(
            self.secrets.get("RATE_LIMIT_REQUESTS_PER_MINUTE", "60")
        )
        self.RATE_LIMIT_BURST_SIZE = int(self.secrets.get("RATE_LIMIT_BURST_SIZE", "10"))

        # S3/MinIO Configuration
        self.S3_CONFIG = self.secrets.get_s3_config()

        # OpenTelemetry Configuration
        self.OTEL_CONFIG = self.secrets.get_opentelemetry_config()

        # Logging
        self.LOG_LEVEL = self.secrets.get("LOG_LEVEL", "INFO")
        self.LOG_FORMAT = self.secrets.get("LOG_FORMAT", "json")

        # Security Headers
        self.SECURITY_HEADERS_ENABLED = (
            self.secrets.get("SECURITY_HEADERS_ENABLED", "true") == "true"
        )
        self.CSP_POLICY = self.secrets.get(
            "CSP_POLICY",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
        )

        # Feature Flags
        self.FEATURE_WEBHOOKS_ENABLED = (
            self.secrets.get("FEATURE_WEBHOOKS_ENABLED", "false") == "true"
        )
        self.FEATURE_SSE_ENABLED = self.secrets.get("FEATURE_SSE_ENABLED", "true") == "true"

    def validate(self) -> None:
        """Validate critical configuration values."""
        # JWT validation
        if not self.JWT_PUBLIC_KEY:
            raise ValueError("JWT_PUBLIC_KEY must be configured in Doppler")

        if self.JWT_ALGORITHM not in ["RS256", "ES256", "RS512", "ES512"]:
            raise ValueError(
                f"JWT_ALGORITHM {self.JWT_ALGORITHM} not secure. "
                "Use RS256, ES256, RS512, or ES512"
            )

        # Environment-specific validation
        if self.ENVIRONMENT == Environment.PRODUCTION:
            # Production requires strict configuration
            if not self.CORS_ALLOWED_ORIGINS:
                raise ValueError("CORS_ALLOWED_ORIGINS must be set in production")

            if "*" in self.CORS_ALLOWED_ORIGINS:
                raise ValueError("Wildcard CORS origins not allowed in production")

            if not self.TRUSTED_HOSTS:
                raise ValueError("TRUSTED_HOSTS must be set in production")

            if "*" in self.TRUSTED_HOSTS:
                raise ValueError("Wildcard trusted hosts not allowed in production")

            if not self.RATE_LIMIT_ENABLED:
                raise ValueError("Rate limiting must be enabled in production")

            if not self.SECURITY_HEADERS_ENABLED:
                raise ValueError("Security headers must be enabled in production")

    def get_idemp_compat_mode(self) -> IdempotencyCompatMode:
        """Return current idempotency compatibility mode."""
        return self.IDEMP_COMPAT_MODE

    def reload(self) -> None:
        """Reload configuration from secrets manager."""
        self.secrets.refresh_cache()
        self._load_config()
        self.validate()


# Global configuration instance
_config: Config | None = None


def get_config(secrets_manager: SecretsManager | None = None) -> Config:
    """
    Get or create global configuration instance.

    Args:
        secrets_manager: SecretsManager implementation. If None, caller must provide it.

    Returns:
        Configuration instance

    Raises:
        ValueError: If secrets_manager is None and no global config exists
    """
    global _config
    if _config is None:
        if secrets_manager is None:
            raise ValueError(
                "SecretsManager must be provided when creating Config for the first time. "
                "This maintains clean architecture by requiring infrastructure dependencies "
                "to be injected from the composition root."
            )
        _config = Config(secrets_manager)
        _config.validate()
    return _config
