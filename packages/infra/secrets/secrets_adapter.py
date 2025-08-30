"""
Secrets manager adapter implementing the SecretsManager port.
This adapter bridges the gap between the application layer and Doppler client.
"""


from packages.application.ports import SecretsManager
from packages.infra.secrets.doppler_client import get_secrets_manager as get_doppler_client


class DopplerSecretsAdapter(SecretsManager):
    """Doppler implementation of the SecretsManager port."""

    def __init__(self):
        """Initialize with Doppler client."""
        self._doppler_client = get_doppler_client()

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get configuration value by key."""
        return self._doppler_client.get(key, default)

    def get_database_url(self) -> str:
        """Get database connection URL."""
        return self._doppler_client.get_database_url()

    def get_redis_url(self) -> str:
        """Get Redis connection URL."""
        return self._doppler_client.get_redis_url()

    def get_jwt_keys(self) -> tuple[str, str]:
        """Get JWT public and private keys."""
        return self._doppler_client.get_jwt_keys()

    def get_s3_config(self) -> dict:
        """Get S3/MinIO configuration."""
        return self._doppler_client.get_s3_config()

    def get_opentelemetry_config(self) -> dict:
        """Get OpenTelemetry configuration."""
        return self._doppler_client.get_opentelemetry_config()

    def refresh_cache(self) -> None:
        """Refresh cached configuration values."""
        self._doppler_client.doppler.refresh_cache()


def get_secrets_adapter() -> SecretsManager:
    """Factory function to create secrets adapter."""
    return DopplerSecretsAdapter()
