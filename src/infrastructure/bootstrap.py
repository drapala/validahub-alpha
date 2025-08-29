"""
Application bootstrap and dependency injection configuration.
This is the composition root where all dependencies are wired together.
"""

from src.application.config import Config, get_config
from src.infrastructure.secrets.secrets_adapter import get_secrets_adapter


def bootstrap_config() -> Config:
    """
    Bootstrap application configuration with proper dependency injection.
    
    This function serves as the composition root for configuration,
    ensuring clean architecture by keeping infrastructure dependencies
    out of the application layer.
    
    Returns:
        Configured Config instance
    """
    secrets_manager = get_secrets_adapter()
    return get_config(secrets_manager)


def get_bootstrapped_config() -> Config:
    """
    Get configuration with bootstrap applied.
    
    This is the preferred way to get configuration in the infrastructure
    layer and above (API layer, etc.).
    
    Returns:
        Configured Config instance
    """
    return bootstrap_config()