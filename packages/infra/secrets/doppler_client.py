"""Doppler secrets management client.

This module provides secure secrets management using Doppler,
ensuring no secrets are stored in environment variables or code.
"""

import os
import subprocess
from typing import Any

import httpx
from pydantic import BaseModel, Field, SecretStr

from packages.shared.logging import get_logger

logger = get_logger("infrastructure.secrets.doppler")


class DopplerConfig(BaseModel):
    """Configuration for Doppler client."""

    token: SecretStr = Field(description="Doppler service token")
    project: str = Field(default="validahub", description="Doppler project")
    config: str = Field(default="dev", description="Doppler config/environment")
    api_host: str = Field(default="https://api.doppler.com", description="Doppler API host")
    timeout_seconds: int = Field(default=30, description="API timeout")
    cache_ttl_seconds: int = Field(default=300, description="Secrets cache TTL")
    fallback_enabled: bool = Field(default=False, description="Enable fallback to env vars")


class DopplerClient:
    """Client for fetching secrets from Doppler."""

    def __init__(self, config: DopplerConfig | None = None):
        """
        Initialize Doppler client.

        Args:
            config: Doppler configuration. If not provided, attempts to
                   load from DOPPLER_TOKEN environment variable.
        """
        if config:
            self.config = config
        else:
            # Try to load token from environment (bootstrap only)
            token = os.environ.get("DOPPLER_TOKEN")
            if not token:
                # Try to get from CLI if installed
                token = self._get_cli_token()

            if not token:
                raise ValueError(
                    "Doppler token not found. Set DOPPLER_TOKEN environment variable "
                    "or provide DopplerConfig"
                )

            self.config = DopplerConfig(
                token=SecretStr(token),
                project=os.environ.get("DOPPLER_PROJECT", "validahub"),
                config=os.environ.get("DOPPLER_CONFIG", "dev"),
            )

        self._client = httpx.Client(
            base_url=self.config.api_host,
            headers={
                "Authorization": f"Bearer {self.config.token.get_secret_value()}",
                "Accept": "application/json",
            },
            timeout=self.config.timeout_seconds,
        )

        # Cache for secrets
        self._cache: dict[str, Any] = {}
        self._cache_timestamp: float = 0

        logger.info(
            "doppler_client_initialized",
            project=self.config.project,
            config=self.config.config,
            api_host=self.config.api_host,
        )

    def _get_cli_token(self) -> str | None:
        """Try to get token from Doppler CLI if installed."""
        try:
            result = subprocess.run(
                ["doppler", "configure", "get", "token", "--plain"],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def fetch_secrets(self, include_dynamic: bool = True) -> dict[str, str]:
        """
        Fetch all secrets from Doppler.

        Args:
            include_dynamic: Include dynamic secrets (computed values)

        Returns:
            Dictionary of secret names to values

        Raises:
            RuntimeError: If secrets cannot be fetched
        """
        import time

        # Check cache
        if self._cache and (time.time() - self._cache_timestamp) < self.config.cache_ttl_seconds:
            logger.debug("doppler_secrets_from_cache")
            return self._cache

        try:
            # Fetch secrets from Doppler API
            response = self._client.get(
                "/v3/configs/config/secrets",
                params={
                    "project": self.config.project,
                    "config": self.config.config,
                    "include_dynamic_secrets": include_dynamic,
                    "format": "json",
                },
            )
            response.raise_for_status()

            # Extract secrets
            data = response.json()
            secrets = {}

            for key, value_obj in data.get("secrets", {}).items():
                if isinstance(value_obj, dict):
                    secrets[key] = value_obj.get("computed", value_obj.get("raw", ""))
                else:
                    secrets[key] = str(value_obj)

            # Update cache
            self._cache = secrets
            self._cache_timestamp = time.time()

            logger.info(
                "doppler_secrets_fetched",
                project=self.config.project,
                config=self.config.config,
                secret_count=len(secrets),
            )

            return secrets

        except httpx.HTTPStatusError as e:
            logger.error(
                "doppler_api_error",
                status_code=e.response.status_code,
                error=str(e),
            )

            # Fallback to environment if enabled
            if self.config.fallback_enabled:
                logger.warning("doppler_fallback_to_env")
                return dict(os.environ)

            raise RuntimeError(f"Failed to fetch secrets from Doppler: {e}")

        except Exception as e:
            logger.error(
                "doppler_client_error",
                error=str(e),
                error_type=e.__class__.__name__,
            )

            # Fallback to environment if enabled
            if self.config.fallback_enabled:
                logger.warning("doppler_fallback_to_env")
                return dict(os.environ)

            raise RuntimeError(f"Doppler client error: {e}")

    def get_secret(self, key: str, default: str | None = None) -> str | None:
        """
        Get a specific secret value.

        Args:
            key: Secret name
            default: Default value if secret not found

        Returns:
            Secret value or default
        """
        secrets = self.fetch_secrets()
        return secrets.get(key, default)

    def get_required_secret(self, key: str) -> str:
        """
        Get a required secret value.

        Args:
            key: Secret name

        Returns:
            Secret value

        Raises:
            ValueError: If secret not found
        """
        value = self.get_secret(key)
        if value is None:
            raise ValueError(f"Required secret '{key}' not found in Doppler")
        return value

    def get_secrets_by_prefix(self, prefix: str) -> dict[str, str]:
        """
        Get all secrets with a specific prefix.

        Args:
            prefix: Secret name prefix

        Returns:
            Dictionary of matching secrets
        """
        secrets = self.fetch_secrets()
        return {key: value for key, value in secrets.items() if key.startswith(prefix)}

    def refresh_cache(self) -> None:
        """Force refresh of secrets cache."""
        self._cache.clear()
        self._cache_timestamp = 0
        self.fetch_secrets.cache_clear()
        logger.info("doppler_cache_cleared")

    def close(self) -> None:
        """Close HTTP client."""
        self._client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class SecretsManager:
    """
    High-level secrets manager with fallback support.

    This provides a unified interface for secrets management
    with support for multiple backends.
    """

    def __init__(self, doppler_client: DopplerClient | None = None):
        """
        Initialize secrets manager.

        Args:
            doppler_client: Doppler client instance
        """
        self.doppler = doppler_client or DopplerClient()
        self._overrides: dict[str, str] = {}

    def get(self, key: str, default: str | None = None) -> str | None:
        """
        Get a secret value with fallback chain.

        Priority order:
        1. Override values (for testing)
        2. Doppler
        3. Default value
        """
        # Check overrides first
        if key in self._overrides:
            return self._overrides[key]

        # Try Doppler
        try:
            return self.doppler.get_secret(key, default)
        except Exception as e:
            logger.warning(
                "secrets_manager_fallback",
                key=key,
                error=str(e),
            )
            return default

    def require(self, key: str) -> str:
        """
        Get a required secret value.

        Raises:
            ValueError: If secret not found
        """
        value = self.get(key)
        if value is None:
            raise ValueError(f"Required secret '{key}' not found")
        return value

    def set_override(self, key: str, value: str) -> None:
        """
        Set an override value (for testing only).

        Args:
            key: Secret name
            value: Override value
        """
        self._overrides[key] = value
        logger.warning(
            "secret_override_set",
            key=key,
            masked_value=f"{value[:3]}..." if len(value) > 3 else "***",
        )

    def clear_overrides(self) -> None:
        """Clear all override values."""
        self._overrides.clear()
        logger.info("secret_overrides_cleared")

    def get_database_url(self) -> str:
        """Get database connection URL."""
        return self.require("DATABASE_URL")

    def get_redis_url(self) -> str:
        """Get Redis connection URL."""
        return self.require("REDIS_URL")

    def get_jwt_keys(self) -> tuple[str, str | None]:
        """
        Get JWT public and private keys.

        Returns:
            Tuple of (public_key, private_key)
        """
        public_key = self.require("JWT_PUBLIC_KEY")
        private_key = self.get("JWT_PRIVATE_KEY")  # Optional for validation-only
        return public_key, private_key

    def get_s3_config(self) -> dict[str, str]:
        """Get S3/MinIO configuration."""
        return {
            "endpoint_url": self.get("S3_ENDPOINT_URL"),
            "access_key_id": self.require("S3_ACCESS_KEY_ID"),
            "secret_access_key": self.require("S3_SECRET_ACCESS_KEY"),
            "bucket_name": self.require("S3_BUCKET_NAME"),
            "region": self.get("S3_REGION", "us-east-1"),
        }

    def get_opentelemetry_config(self) -> dict[str, str]:
        """Get OpenTelemetry configuration."""
        return {
            "endpoint": self.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
            "service_name": self.get("OTEL_SERVICE_NAME", "validahub-api"),
            "environment": self.get("OTEL_ENVIRONMENT", "development"),
            "traces_enabled": self.get("OTEL_TRACES_ENABLED", "true") == "true",
            "metrics_enabled": self.get("OTEL_METRICS_ENABLED", "true") == "true",
        }


# Global instance (singleton)
_secrets_manager: SecretsManager | None = None


def get_secrets_manager() -> SecretsManager:
    """Get or create global secrets manager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager
