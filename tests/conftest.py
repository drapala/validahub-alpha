"""Test configuration and shared fixtures."""

from uuid import uuid4

import pytest


@pytest.fixture
def tenant_id() -> str:
    """Valid tenant ID for tests."""
    return "tenant_123"


@pytest.fixture
def seller_id() -> str:
    """Valid seller ID for tests."""
    return "seller_456"


@pytest.fixture
def channel() -> str:
    """Valid channel for tests."""
    return "mercado_livre"


@pytest.fixture
def idempotency_key() -> str:
    """Valid idempotency key for tests."""
    return "test-key-123.csv"


@pytest.fixture
def job_id() -> str:
    """Valid job UUID for tests."""
    return str(uuid4())


@pytest.fixture
def file_ref() -> str:
    """Valid file reference for tests."""
    return "s3://bucket/tenant_123/jobs/test-file.csv"


@pytest.fixture
def rules_profile_id() -> str:
    """Valid rules profile ID for tests."""
    return "ml@1.2.3"
