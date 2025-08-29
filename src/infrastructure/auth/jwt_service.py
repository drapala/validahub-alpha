"""JWT authentication service implementation.

This module provides secure JWT token validation and generation
using PyJWT with RS256/ES256 algorithms for production security.
"""

import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from jwt import PyJWKClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.backends import default_backend

from packages.domain.errors import SecurityViolationError
from packages.shared.logging import get_logger


logger = get_logger("infrastructure.auth.jwt_service")


class JWTService:
    """Service for JWT token validation and generation with strong security."""
    
    def __init__(
        self,
        public_key: Optional[str] = None,
        private_key: Optional[str] = None,
        jwks_url: Optional[str] = None,
        algorithm: str = "RS256",
        issuer: str = "validahub",
        audience: str = "validahub-api",
        token_ttl_seconds: int = 3600,
        refresh_ttl_seconds: int = 86400,
        clock_skew_seconds: int = 30,
    ):
        """
        Initialize JWT service with asymmetric keys.
        
        Args:
            public_key: Public key for verification (PEM format)
            private_key: Private key for signing (PEM format, optional)
            jwks_url: URL for JWKS endpoint (alternative to public_key)
            algorithm: JWT algorithm (RS256, ES256 recommended)
            issuer: Expected token issuer
            audience: Expected token audience
            token_ttl_seconds: Access token lifetime
            refresh_ttl_seconds: Refresh token lifetime
            clock_skew_seconds: Allowed clock skew for validation
        """
        self.algorithm = algorithm
        self.issuer = issuer
        self.audience = audience
        self.token_ttl_seconds = token_ttl_seconds
        self.refresh_ttl_seconds = refresh_ttl_seconds
        self.clock_skew_seconds = clock_skew_seconds
        
        # Setup verification
        if jwks_url:
            self.jwks_client = PyJWKClient(jwks_url)
            self.public_key = None
        elif public_key:
            self.public_key = public_key
            self.jwks_client = None
        else:
            raise ValueError("Either public_key or jwks_url must be provided")
        
        # Setup signing (optional, only if we issue tokens)
        self.private_key = private_key
        
        # Token revocation cache (would use Redis in production)
        self._revoked_tokens: set[str] = set()
        
        logger.info(
            "jwt_service_initialized",
            algorithm=algorithm,
            issuer=issuer,
            audience=audience,
            using_jwks=bool(jwks_url),
        )
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token and extract claims.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token claims
            
        Raises:
            SecurityViolationError: If token is invalid
        """
        try:
            # Check revocation
            if token in self._revoked_tokens:
                raise SecurityViolationError(
                    message="Token has been revoked",
                    code="TOKEN_REVOKED"
                )
            
            # Get verification key
            if self.jwks_client:
                signing_key = self.jwks_client.get_signing_key_from_jwt(token)
                verification_key = signing_key.key
            else:
                verification_key = self.public_key
            
            # Decode and validate token
            claims = jwt.decode(
                token,
                verification_key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "require": ["exp", "iat", "sub", "jti"],
                },
                leeway=timedelta(seconds=self.clock_skew_seconds),
            )
            
            # Additional validation
            self._validate_claims(claims)
            
            # Log successful validation
            logger.info(
                "token_validated",
                user_id=claims.get("sub"),
                jti=claims.get("jti"),
                scopes=claims.get("scopes", []),
                tenants=claims.get("tenants", []),
            )
            
            return claims
            
        except jwt.ExpiredSignatureError:
            logger.warning("token_expired", token_jti=self._extract_jti(token))
            raise SecurityViolationError(
                message="Token has expired",
                code="TOKEN_EXPIRED"
            )
        except jwt.InvalidTokenError as e:
            logger.warning(
                "token_invalid",
                error=str(e),
                token_jti=self._extract_jti(token),
            )
            raise SecurityViolationError(
                message="Invalid token",
                code="TOKEN_INVALID"
            )
        except Exception as e:
            logger.error(
                "token_validation_error",
                error=str(e),
                error_type=e.__class__.__name__,
            )
            raise SecurityViolationError(
                message="Token validation failed",
                code="TOKEN_VALIDATION_FAILED"
            )
    
    def _validate_claims(self, claims: Dict[str, Any]) -> None:
        """Validate token claims for business rules."""
        # Check required claims
        if not claims.get("sub"):
            raise SecurityViolationError(
                message="Token missing subject claim",
                code="INVALID_CLAIMS"
            )
        
        # Check token type
        token_type = claims.get("token_type", "access")
        if token_type not in ["access", "refresh"]:
            raise SecurityViolationError(
                message=f"Invalid token type: {token_type}",
                code="INVALID_TOKEN_TYPE"
            )
        
        # Validate scopes format
        scopes = claims.get("scopes", [])
        if not isinstance(scopes, list):
            raise SecurityViolationError(
                message="Invalid scopes format",
                code="INVALID_SCOPES"
            )
        
        # Validate tenants format
        tenants = claims.get("tenants", [])
        if not isinstance(tenants, list):
            raise SecurityViolationError(
                message="Invalid tenants format",
                code="INVALID_TENANTS"
            )
    
    def _extract_jti(self, token: str) -> Optional[str]:
        """Extract JTI from token without full validation."""
        try:
            # Decode without verification to get JTI
            unverified = jwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=[self.algorithm],
            )
            return unverified.get("jti")
        except:
            return None
    
    async def revoke_token(self, token: str) -> None:
        """
        Revoke a token by adding it to revocation list.
        
        In production, this would use Redis with TTL.
        """
        jti = self._extract_jti(token)
        if jti:
            self._revoked_tokens.add(token)
            logger.info("token_revoked", jti=jti)
    
    async def generate_token(
        self,
        user_id: str,
        scopes: List[str],
        tenants: List[str],
        token_type: str = "access",
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a new JWT token (only if private key is configured).
        
        Args:
            user_id: User identifier
            scopes: List of permission scopes
            tenants: List of allowed tenant IDs
            token_type: Type of token (access or refresh)
            additional_claims: Extra claims to include
            
        Returns:
            Signed JWT token
            
        Raises:
            ValueError: If private key is not configured
        """
        if not self.private_key:
            raise ValueError("Private key required for token generation")
        
        # Determine TTL based on token type
        ttl = (
            self.token_ttl_seconds
            if token_type == "access"
            else self.refresh_ttl_seconds
        )
        
        # Generate unique JTI
        import uuid
        jti = str(uuid.uuid4())
        
        # Build claims
        now = datetime.now(timezone.utc)
        claims = {
            "sub": user_id,
            "iss": self.issuer,
            "aud": self.audience,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(seconds=ttl),
            "jti": jti,
            "token_type": token_type,
            "scopes": scopes,
            "tenants": tenants,
        }
        
        # Add additional claims
        if additional_claims:
            claims.update(additional_claims)
        
        # Generate token
        token = jwt.encode(
            claims,
            self.private_key,
            algorithm=self.algorithm,
        )
        
        logger.info(
            "token_generated",
            user_id=user_id,
            jti=jti,
            token_type=token_type,
            scopes=scopes,
            tenants=tenants,
        )
        
        return token


class JWTKeyGenerator:
    """Utility for generating JWT signing keys (development only)."""
    
    @staticmethod
    def generate_rsa_keys() -> tuple[str, str]:
        """Generate RSA key pair for RS256."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        
        return (
            public_pem.decode("utf-8"),
            private_pem.decode("utf-8"),
        )
    
    @staticmethod
    def generate_ec_keys() -> tuple[str, str]:
        """Generate EC key pair for ES256."""
        private_key = ec.generate_private_key(
            ec.SECP256R1(),
            backend=default_backend(),
        )
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        
        return (
            public_pem.decode("utf-8"),
            private_pem.decode("utf-8"),
        )