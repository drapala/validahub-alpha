"""Tests for critical security fixes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import jwt
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from src.application.config import Config, Environment
from src.infrastructure.auth.jwt_service import JWTKeyGenerator, JWTService
from src.infrastructure.secrets.doppler_client import DopplerClient, SecretsManager

from packages.domain.errors import SecurityViolationError


class TestJWTSecurity:
    """Test JWT authentication security."""

    @pytest.fixture
    def rsa_keys(self):
        """Generate RSA keys for testing."""
        return JWTKeyGenerator.generate_rsa_keys()

    @pytest.fixture
    def jwt_service(self, rsa_keys):
        """Create JWT service with test keys."""
        public_key, private_key = rsa_keys
        return JWTService(
            public_key=public_key,
            private_key=private_key,
            algorithm="RS256",
            issuer="test-issuer",
            audience="test-audience",
        )

    async def test_jwt_validation_with_valid_token(self, jwt_service):
        """Test that valid JWT tokens are accepted."""
        # Generate a valid token
        token = await jwt_service.generate_token(
            user_id="user_123",
            scopes=["jobs:read", "jobs:write"],
            tenants=["t_123", "t_456"],
        )

        # Validate the token
        claims = await jwt_service.validate_token(token)

        assert claims["sub"] == "user_123"
        assert claims["scopes"] == ["jobs:read", "jobs:write"]
        assert claims["tenants"] == ["t_123", "t_456"]
        assert claims["iss"] == "test-issuer"
        assert claims["aud"] == "test-audience"

    async def test_jwt_validation_rejects_expired_token(self, jwt_service):
        """Test that expired tokens are rejected."""
        # Generate an expired token
        now = datetime.now(UTC)
        expired_claims = {
            "sub": "user_123",
            "iss": "test-issuer",
            "aud": "test-audience",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),  # Expired 1 hour ago
            "jti": "test-jti",
            "scopes": [],
            "tenants": [],
        }

        expired_token = jwt.encode(expired_claims, jwt_service.private_key, algorithm="RS256")

        with pytest.raises(SecurityViolationError) as exc_info:
            await jwt_service.validate_token(expired_token)

        assert exc_info.value.code == "TOKEN_EXPIRED"

    async def test_jwt_validation_rejects_invalid_signature(self, jwt_service):
        """Test that tokens with invalid signatures are rejected."""
        # Generate a token with a different key
        fake_private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        fake_private_pem = fake_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        now = datetime.now(UTC)
        claims = {
            "sub": "user_123",
            "iss": "test-issuer",
            "aud": "test-audience",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "jti": "test-jti",
            "scopes": ["jobs:read"],
            "tenants": ["t_123"],
        }

        # Sign with different key
        invalid_token = jwt.encode(claims, fake_private_pem, algorithm="RS256")

        with pytest.raises(SecurityViolationError) as exc_info:
            await jwt_service.validate_token(invalid_token)

        assert exc_info.value.code == "TOKEN_INVALID"

    async def test_jwt_validation_checks_issuer(self, jwt_service):
        """Test that tokens with wrong issuer are rejected."""
        now = datetime.now(UTC)
        wrong_issuer_claims = {
            "sub": "user_123",
            "iss": "wrong-issuer",  # Wrong issuer
            "aud": "test-audience",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "jti": "test-jti",
            "scopes": [],
            "tenants": [],
        }

        wrong_token = jwt.encode(wrong_issuer_claims, jwt_service.private_key, algorithm="RS256")

        with pytest.raises(SecurityViolationError) as exc_info:
            await jwt_service.validate_token(wrong_token)

        assert exc_info.value.code == "TOKEN_INVALID"

    async def test_jwt_validation_checks_audience(self, jwt_service):
        """Test that tokens with wrong audience are rejected."""
        now = datetime.now(UTC)
        wrong_audience_claims = {
            "sub": "user_123",
            "iss": "test-issuer",
            "aud": "wrong-audience",  # Wrong audience
            "iat": now,
            "exp": now + timedelta(hours=1),
            "jti": "test-jti",
            "scopes": [],
            "tenants": [],
        }

        wrong_token = jwt.encode(wrong_audience_claims, jwt_service.private_key, algorithm="RS256")

        with pytest.raises(SecurityViolationError) as exc_info:
            await jwt_service.validate_token(wrong_token)

        assert exc_info.value.code == "TOKEN_INVALID"

    async def test_jwt_revocation(self, jwt_service):
        """Test that revoked tokens are rejected."""
        # Generate a valid token
        token = await jwt_service.generate_token(
            user_id="user_123",
            scopes=["jobs:read"],
            tenants=["t_123"],
        )

        # Validate it works
        claims = await jwt_service.validate_token(token)
        assert claims["sub"] == "user_123"

        # Revoke the token
        await jwt_service.revoke_token(token)

        # Try to use revoked token
        with pytest.raises(SecurityViolationError) as exc_info:
            await jwt_service.validate_token(token)

        assert exc_info.value.code == "TOKEN_REVOKED"


class TestDopplerIntegration:
    """Test Doppler secrets management."""

    @pytest.fixture
    def mock_doppler_response(self):
        """Mock Doppler API response."""
        return {
            "secrets": {
                "DATABASE_URL": {"computed": "postgresql://secure@doppler/db"},
                "REDIS_URL": {"computed": "redis://secure@doppler:6379"},
                "JWT_PUBLIC_KEY": {
                    "computed": "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
                },
                "JWT_PRIVATE_KEY": {
                    "computed": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
                },
                "S3_ACCESS_KEY_ID": {"computed": "AKIA_FROM_DOPPLER"},
                "S3_SECRET_ACCESS_KEY": {"computed": "secret_from_doppler"},
                "S3_BUCKET_NAME": {"computed": "validahub-prod"},
            }
        }

    @patch("httpx.Client")
    def test_doppler_fetches_secrets(self, mock_client_class, mock_doppler_response):
        """Test that Doppler client fetches secrets correctly."""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_doppler_response
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Create client with test token
        from src.infrastructure.secrets.doppler_client import DopplerConfig

        config = DopplerConfig(
            token="dp.st.test.xxx",
            project="test",
            config="test",
        )
        client = DopplerClient(config)

        # Fetch secrets
        secrets = client.fetch_secrets()

        assert secrets["DATABASE_URL"] == "postgresql://secure@doppler/db"
        assert secrets["REDIS_URL"] == "redis://secure@doppler:6379"
        assert "JWT_PUBLIC_KEY" in secrets
        assert "JWT_PRIVATE_KEY" in secrets

        # Verify API call
        mock_client.get.assert_called_once_with(
            "/v3/configs/config/secrets",
            params={
                "project": "test",
                "config": "test",
                "include_dynamic_secrets": True,
                "format": "json",
            },
        )

    @patch("httpx.Client")
    def test_doppler_fallback_on_error(self, mock_client_class):
        """Test that Doppler falls back to env vars on error if enabled."""
        # Setup mock to raise error
        mock_client = Mock()
        mock_client.get.side_effect = Exception("API Error")
        mock_client_class.return_value = mock_client

        # Create client with fallback enabled
        from src.infrastructure.secrets.doppler_client import DopplerConfig

        config = DopplerConfig(
            token="dp.st.test.xxx",
            project="test",
            config="test",
            fallback_enabled=True,
        )
        client = DopplerClient(config)

        # Set environment variable
        import os

        os.environ["TEST_SECRET"] = "fallback_value"

        try:
            # Fetch secrets (should fallback)
            secrets = client.fetch_secrets()
            assert secrets["TEST_SECRET"] == "fallback_value"
        finally:
            del os.environ["TEST_SECRET"]

    @patch("httpx.Client")
    def test_secrets_manager_interface(self, mock_client_class, mock_doppler_response):
        """Test the high-level SecretsManager interface."""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_doppler_response
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Create manager
        manager = SecretsManager()

        # Test required secrets
        assert manager.get_database_url() == "postgresql://secure@doppler/db"
        assert manager.get_redis_url() == "redis://secure@doppler:6379"

        # Test JWT keys
        public_key, private_key = manager.get_jwt_keys()
        assert public_key.startswith("-----BEGIN PUBLIC KEY-----")
        assert private_key.startswith("-----BEGIN PRIVATE KEY-----")

        # Test S3 config
        s3_config = manager.get_s3_config()
        assert s3_config["access_key_id"] == "AKIA_FROM_DOPPLER"
        assert s3_config["secret_access_key"] == "secret_from_doppler"
        assert s3_config["bucket_name"] == "validahub-prod"

    def test_secrets_not_in_environment_variables(self):
        """Test that secrets are not loaded from environment variables directly."""
        import os

        # These should NOT be in environment
        assert "JWT_SECRET_KEY" not in os.environ
        assert "DATABASE_URL" not in os.environ or "doppler" in os.environ.get("DATABASE_URL", "")

        # Config should use Doppler, not os.getenv
        with patch("src.infrastructure.secrets.doppler_client.get_secrets_manager") as mock_get:
            mock_manager = Mock()
            mock_manager.get.return_value = "from_doppler"
            mock_manager.get_database_url.return_value = "postgresql://from_doppler/db"
            mock_manager.get_redis_url.return_value = "redis://from_doppler"
            mock_manager.get_jwt_keys.return_value = ("public", "private")
            mock_manager.get_s3_config.return_value = {}
            mock_manager.get_opentelemetry_config.return_value = {}
            mock_get.return_value = mock_manager

            config = Config()
            assert config.DATABASE_URL == "postgresql://from_doppler/db"


class TestCORSConfiguration:
    """Test CORS and trusted hosts configuration."""

    @patch("src.infrastructure.secrets.doppler_client.get_secrets_manager")
    def test_production_cors_validation(self, mock_get_manager):
        """Test that production requires strict CORS configuration."""
        mock_manager = Mock()
        mock_manager.get.side_effect = lambda key, default=None: {
            "ENVIRONMENT": "production",
            "CORS_ALLOWED_ORIGINS": "https://app.validahub.com,https://api.validahub.com",
            "TRUSTED_HOSTS": "app.validahub.com,api.validahub.com",
            "DATABASE_URL": "postgresql://prod/db",
            "REDIS_URL": "redis://prod",
            "JWT_PUBLIC_KEY": "key",
            "JWT_ALGORITHM": "RS256",
            "RATE_LIMIT_ENABLED": "true",
            "SECURITY_HEADERS_ENABLED": "true",
        }.get(key, default)
        mock_manager.get_database_url.return_value = "postgresql://prod/db"
        mock_manager.get_redis_url.return_value = "redis://prod"
        mock_manager.get_jwt_keys.return_value = ("public", None)
        mock_manager.get_s3_config.return_value = {}
        mock_manager.get_opentelemetry_config.return_value = {}
        mock_get_manager.return_value = mock_manager

        config = Config()
        config.validate()

        assert config.ENVIRONMENT == Environment.PRODUCTION
        assert "https://app.validahub.com" in config.CORS_ALLOWED_ORIGINS
        assert "https://api.validahub.com" in config.CORS_ALLOWED_ORIGINS
        assert "localhost" not in config.CORS_ALLOWED_ORIGINS
        assert "*" not in config.CORS_ALLOWED_ORIGINS

        assert "app.validahub.com" in config.TRUSTED_HOSTS
        assert "api.validahub.com" in config.TRUSTED_HOSTS
        assert "*" not in config.TRUSTED_HOSTS

    @patch("src.infrastructure.secrets.doppler_client.get_secrets_manager")
    def test_production_rejects_wildcards(self, mock_get_manager):
        """Test that production rejects wildcard CORS/hosts."""
        mock_manager = Mock()
        mock_manager.get.side_effect = lambda key, default=None: {
            "ENVIRONMENT": "production",
            "CORS_ALLOWED_ORIGINS": "*",  # Invalid wildcard
            "TRUSTED_HOSTS": "app.validahub.com",
            "DATABASE_URL": "postgresql://prod/db",
            "REDIS_URL": "redis://prod",
            "JWT_PUBLIC_KEY": "key",
            "JWT_ALGORITHM": "RS256",
        }.get(key, default)
        mock_manager.get_database_url.return_value = "postgresql://prod/db"
        mock_manager.get_redis_url.return_value = "redis://prod"
        mock_manager.get_jwt_keys.return_value = ("public", None)
        mock_manager.get_s3_config.return_value = {}
        mock_manager.get_opentelemetry_config.return_value = {}
        mock_get_manager.return_value = mock_manager

        config = Config()

        with pytest.raises(ValueError) as exc_info:
            config.validate()

        assert "Wildcard CORS origins not allowed in production" in str(exc_info.value)

    @patch("src.infrastructure.secrets.doppler_client.get_secrets_manager")
    def test_development_allows_localhost(self, mock_get_manager):
        """Test that development allows localhost origins."""
        mock_manager = Mock()
        mock_manager.get.side_effect = lambda key, default=None: {
            "ENVIRONMENT": "development",
            "JWT_ALGORITHM": "RS256",
        }.get(key, default)
        mock_manager.get_database_url.return_value = "postgresql://dev/db"
        mock_manager.get_redis_url.return_value = "redis://dev"
        mock_manager.get_jwt_keys.return_value = ("public", None)
        mock_manager.get_s3_config.return_value = {}
        mock_manager.get_opentelemetry_config.return_value = {}
        mock_get_manager.return_value = mock_manager

        config = Config()
        config.validate()

        assert config.ENVIRONMENT == Environment.DEVELOPMENT
        assert "http://localhost:3000" in config.CORS_ALLOWED_ORIGINS
        assert "localhost" in config.TRUSTED_HOSTS
        assert "127.0.0.1" in config.TRUSTED_HOSTS


class TestSecurityHeaders:
    """Test security headers middleware."""

    def test_security_headers_configuration(self):
        """Test that security headers are properly configured."""
        from src.infrastructure.middleware.security_headers import SecurityHeadersMiddleware

        # Create middleware with test config
        app = Mock()
        middleware = SecurityHeadersMiddleware(
            app,
            csp_policy="default-src 'self'",
            enable_hsts=True,
            enable_nosniff=True,
            enable_xfo=True,
            xfo_option="DENY",
        )

        assert middleware.csp_policy == "default-src 'self'"
        assert middleware.enable_hsts is True
        assert middleware.enable_nosniff is True
        assert middleware.enable_xfo is True
        assert middleware.xfo_option == "DENY"

    async def test_security_headers_applied(self):
        """Test that security headers are added to responses."""
        from src.infrastructure.middleware.security_headers import SecurityHeadersMiddleware
        from starlette.requests import Request
        from starlette.responses import Response

        # Create test app
        async def app(scope, receive, send):
            response = Response("test")
            await response(scope, receive, send)

        # Add middleware
        middleware = SecurityHeadersMiddleware(
            app,
            csp_policy="default-src 'self'",
            enable_hsts=True,
            enable_nosniff=True,
            enable_xfo=True,
        )

        # Create test request
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "url": {"path": "/test"},
                "headers": [],
            }
        )

        # Mock call_next
        async def call_next(request):
            response = Response("test")
            return response

        # Process request
        response = await middleware.dispatch(request, call_next)

        # Check headers
        assert response.headers["Content-Security-Policy"] == "default-src 'self'"
        assert "max-age=" in response.headers["Strict-Transport-Security"]
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
