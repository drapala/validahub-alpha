"""Redis-based RateLimiter implementation with comprehensive logging.

This module implements the RateLimiter port using Redis
with token bucket algorithm and detailed logging.
"""

from typing import Dict, Any, Optional
import time
from datetime import datetime, timedelta

from src.application.ports import RateLimiter
from src.infrastructure.logging.utilities import log_rate_limit_check, LoggingPort
from src.domain.value_objects import TenantId
from shared.logging import get_logger
from shared.logging.context import get_correlation_id


class InMemoryRateLimiter(RateLimiter, LoggingPort):
    """
    In-memory implementation of RateLimiter for testing.
    Includes comprehensive logging of all rate limiting decisions.
    """
    
    def __init__(self, default_limit: int = 100, window_seconds: int = 60):
        """
        Initialize in-memory rate limiter with logging.
        
        Args:
            default_limit: Default requests per window
            window_seconds: Time window in seconds
        """
        super().__init__(logger_name="infrastructure.rate_limiter")
        self._default_limit = default_limit
        self._window_seconds = window_seconds
        self._buckets: Dict[str, Dict[str, Any]] = {}
        self._custom_limits: Dict[str, int] = {}
        
        self._logger.info(
            "rate_limiter_initialized",
            implementation="in_memory",
            default_limit=default_limit,
            window_seconds=window_seconds,
            correlation_id=get_correlation_id()
        )
    
    def get_component_name(self) -> str:
        """Get component name for logging context."""
        return "RateLimiter"
    
    @log_rate_limit_check
    def check_and_consume(self, tenant_id: TenantId, resource: str) -> bool:
        """
        Check rate limit and consume token if available.
        
        Args:
            tenant_id: Tenant identifier
            resource: Resource being rate limited
            
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        start_time = time.time()
        tenant_id_value = tenant_id.value
        bucket_key = f"{tenant_id_value}:{resource}"
        
        # Get current timestamp
        now = time.time()
        
        # Get or create bucket
        if bucket_key not in self._buckets:
            self._buckets[bucket_key] = {
                "tokens": self._get_limit(tenant_id_value, resource),
                "last_refill": now,
                "total_requests": 0,
                "denied_requests": 0
            }
            
            self._logger.debug(
                "rate_limit_bucket_created",
                tenant_id=tenant_id_value,
                resource=resource,
                initial_tokens=self._buckets[bucket_key]["tokens"],
                correlation_id=get_correlation_id()
            )
        
        bucket = self._buckets[bucket_key]
        limit = self._get_limit(tenant_id_value, resource)
        
        # Refill tokens based on time elapsed
        time_elapsed = now - bucket["last_refill"]
        tokens_to_add = (time_elapsed / self._window_seconds) * limit
        bucket["tokens"] = min(limit, bucket["tokens"] + tokens_to_add)
        bucket["last_refill"] = now
        
        # Track request
        bucket["total_requests"] += 1
        
        # Check if we have tokens available
        if bucket["tokens"] >= 1:
            # Consume token
            bucket["tokens"] -= 1
            
            duration_ms = (time.time() - start_time) * 1000
            
            self._logger.debug(
                "rate_limit_token_consumed",
                tenant_id=tenant_id_value,
                resource=resource,
                remaining_tokens=int(bucket["tokens"]),
                limit=limit,
                duration_ms=duration_ms,
                correlation_id=get_correlation_id()
            )
            
            # Log if getting close to limit
            if bucket["tokens"] < limit * 0.2:  # Less than 20% remaining
                self._logger.warning(
                    "rate_limit_approaching",
                    tenant_id=tenant_id_value,
                    resource=resource,
                    remaining_tokens=int(bucket["tokens"]),
                    limit=limit,
                    percentage_remaining=round((bucket["tokens"] / limit) * 100, 2),
                    correlation_id=get_correlation_id()
                )
            
            return True
        else:
            # Rate limit exceeded
            bucket["denied_requests"] += 1
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Calculate when tokens will be available
            tokens_needed = 1 - bucket["tokens"]
            seconds_until_available = (tokens_needed / limit) * self._window_seconds
            
            self._logger.warning(
                "rate_limit_exceeded_detailed",
                tenant_id=tenant_id_value,
                resource=resource,
                current_tokens=round(bucket["tokens"], 2),
                limit=limit,
                total_requests=bucket["total_requests"],
                denied_requests=bucket["denied_requests"],
                denial_rate=round((bucket["denied_requests"] / bucket["total_requests"]) * 100, 2),
                seconds_until_available=round(seconds_until_available, 2),
                duration_ms=duration_ms,
                correlation_id=get_correlation_id()
            )
            
            return False
    
    def _get_limit(self, tenant_id: str, resource: str) -> int:
        """
        Get rate limit for tenant/resource combination.
        
        Args:
            tenant_id: Tenant identifier
            resource: Resource being rate limited
            
        Returns:
            Rate limit value
        """
        # Check for custom limits
        custom_key = f"{tenant_id}:{resource}"
        if custom_key in self._custom_limits:
            return self._custom_limits[custom_key]
        
        # Check for tenant-wide custom limit
        if tenant_id in self._custom_limits:
            return self._custom_limits[tenant_id]
        
        # Return default limit
        return self._default_limit
    
    def set_custom_limit(self, tenant_id: str, limit: int, resource: Optional[str] = None) -> None:
        """
        Set custom rate limit for tenant or tenant/resource.
        
        Args:
            tenant_id: Tenant identifier
            limit: Custom rate limit
            resource: Optional resource for specific limit
        """
        if resource:
            key = f"{tenant_id}:{resource}"
        else:
            key = tenant_id
        
        old_limit = self._custom_limits.get(key, self._default_limit)
        self._custom_limits[key] = limit
        
        self._logger.info(
            "rate_limit_custom_set",
            tenant_id=tenant_id,
            resource=resource,
            old_limit=old_limit,
            new_limit=limit,
            correlation_id=get_correlation_id()
        )
    
    def get_usage(self, tenant_id: TenantId, resource: str) -> Dict[str, Any]:
        """
        Get current usage statistics for monitoring.
        
        Args:
            tenant_id: Tenant identifier
            resource: Resource being rate limited
            
        Returns:
            Usage statistics
        """
        tenant_id_value = tenant_id.value
        bucket_key = f"{tenant_id_value}:{resource}"
        
        if bucket_key not in self._buckets:
            return {
                "tenant_id": tenant_id_value,
                "resource": resource,
                "tokens_available": self._get_limit(tenant_id_value, resource),
                "limit": self._get_limit(tenant_id_value, resource),
                "total_requests": 0,
                "denied_requests": 0,
                "denial_rate": 0.0
            }
        
        bucket = self._buckets[bucket_key]
        limit = self._get_limit(tenant_id_value, resource)
        
        # Refill tokens for accurate count
        now = time.time()
        time_elapsed = now - bucket["last_refill"]
        tokens_to_add = (time_elapsed / self._window_seconds) * limit
        current_tokens = min(limit, bucket["tokens"] + tokens_to_add)
        
        usage = {
            "tenant_id": tenant_id_value,
            "resource": resource,
            "tokens_available": round(current_tokens, 2),
            "limit": limit,
            "usage_percentage": round(((limit - current_tokens) / limit) * 100, 2),
            "total_requests": bucket["total_requests"],
            "denied_requests": bucket["denied_requests"],
            "denial_rate": round((bucket["denied_requests"] / bucket["total_requests"]) * 100, 2) if bucket["total_requests"] > 0 else 0.0
        }
        
        self._logger.info(
            "rate_limit_usage_query",
            **usage,
            correlation_id=get_correlation_id()
        )
        
        return usage
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics for monitoring.
        
        Returns:
            Dictionary with rate limiter stats
        """
        total_requests = sum(b["total_requests"] for b in self._buckets.values())
        total_denied = sum(b["denied_requests"] for b in self._buckets.values())
        
        stats = {
            "total_buckets": len(self._buckets),
            "custom_limits": len(self._custom_limits),
            "total_requests": total_requests,
            "total_denied": total_denied,
            "overall_denial_rate": round((total_denied / total_requests) * 100, 2) if total_requests > 0 else 0.0,
            "buckets_near_limit": 0,
            "buckets_exceeded": 0
        }
        
        # Check bucket statuses
        for bucket_key, bucket in self._buckets.items():
            tenant_id, resource = bucket_key.split(":", 1)
            limit = self._get_limit(tenant_id, resource)
            
            # Refill tokens for accurate count
            now = time.time()
            time_elapsed = now - bucket["last_refill"]
            tokens_to_add = (time_elapsed / self._window_seconds) * limit
            current_tokens = min(limit, bucket["tokens"] + tokens_to_add)
            
            if current_tokens < limit * 0.2:
                stats["buckets_near_limit"] += 1
            if current_tokens <= 0:
                stats["buckets_exceeded"] += 1
        
        self._logger.info(
            "rate_limiter_stats",
            **stats,
            correlation_id=get_correlation_id()
        )
        
        return stats


class RedisRateLimiter(RateLimiter, LoggingPort):
    """
    Redis-based RateLimiter for production use.
    Implements token bucket algorithm with atomic operations.
    """
    
    def __init__(self, redis_client, default_limit: int = 100, window_seconds: int = 60):
        """
        Initialize Redis rate limiter.
        
        Args:
            redis_client: Redis client instance
            default_limit: Default requests per window
            window_seconds: Time window in seconds
        """
        super().__init__(logger_name="infrastructure.redis_rate_limiter")
        self._redis = redis_client
        self._default_limit = default_limit
        self._window_seconds = window_seconds
        
        self._logger.info(
            "redis_rate_limiter_initialized",
            default_limit=default_limit,
            window_seconds=window_seconds,
            correlation_id=get_correlation_id()
        )
    
    def get_component_name(self) -> str:
        """Get component name for logging context."""
        return "RedisRateLimiter"
    
    @log_rate_limit_check
    def check_and_consume(self, tenant_id: TenantId, resource: str) -> bool:
        """
        Check rate limit and consume token using Redis.
        
        Uses Redis sorted sets for sliding window rate limiting.
        
        Args:
            tenant_id: Tenant identifier
            resource: Resource being rate limited
            
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        start_time = time.time()
        tenant_id_value = tenant_id.value
        key = f"rate_limit:{tenant_id_value}:{resource}"
        
        # Get current timestamp
        now = time.time()
        window_start = now - self._window_seconds
        
        # Lua script for atomic check and consume
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window_start = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])
        
        -- Remove old entries
        redis.call('zremrangebyscore', key, '-inf', window_start)
        
        -- Count current entries
        local current = redis.call('zcard', key)
        
        if current < limit then
            -- Add new entry
            redis.call('zadd', key, now, now)
            redis.call('expire', key, ARGV[4])
            return 1
        else
            return 0
        end
        """
        
        try:
            # Execute atomic rate limit check
            limit = self._get_limit(tenant_id_value, resource)
            allowed = self._redis.eval(
                lua_script,
                1,
                key,
                now,
                window_start,
                limit,
                self._window_seconds * 2  # Expire after 2 windows
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            if allowed:
                self._logger.debug(
                    "redis_rate_limit_allowed",
                    tenant_id=tenant_id_value,
                    resource=resource,
                    limit=limit,
                    duration_ms=duration_ms,
                    correlation_id=get_correlation_id()
                )
            else:
                self._logger.warning(
                    "redis_rate_limit_exceeded",
                    tenant_id=tenant_id_value,
                    resource=resource,
                    limit=limit,
                    duration_ms=duration_ms,
                    correlation_id=get_correlation_id()
                )
            
            return bool(allowed)
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            self._logger.error(
                "redis_rate_limit_check_failed",
                tenant_id=tenant_id_value,
                resource=resource,
                duration_ms=duration_ms,
                error=str(e),
                error_type=e.__class__.__name__,
                correlation_id=get_correlation_id()
            )
            
            # Fail open or closed based on configuration
            # For now, fail open (allow request) to avoid blocking on Redis issues
            return True
    
    def _get_limit(self, tenant_id: str, resource: str) -> int:
        """Get rate limit from Redis or use default."""
        # Could check Redis for custom limits here
        # For now, return default
        return self._default_limit