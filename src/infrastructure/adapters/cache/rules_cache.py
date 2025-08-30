"""Rules cache adapter implementation for ValidaHub Smart Rules Engine.

This module implements caching for compiled rule intermediate representations
using Redis as the backend store.
"""

import json
import pickle
import time
from typing import Optional, Dict, Any
from hashlib import sha256

from src.application.ports.rules import CachePort
from src.domain.value_objects import TenantId
from src.domain.rules.value_objects import RuleSetId, SemVer
from src.domain.rules.engine.ir_types import CompiledRuleSet
from src.shared.logging import get_logger
from src.shared.logging.context import get_correlation_id


class InMemoryRulesCache(CachePort):
    """
    In-memory implementation of rules cache for testing and development.
    
    This cache stores compiled rule intermediate representations with TTL support
    and comprehensive logging for monitoring and debugging.
    """
    
    def __init__(self, default_ttl_seconds: int = 3600):
        """
        Initialize in-memory rules cache.
        
        Args:
            default_ttl_seconds: Default time-to-live for cached entries
        """
        self._logger = get_logger("infrastructure.rules_cache")
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl_seconds
        
        self._logger.info(
            "rules_cache_initialized",
            implementation="in_memory",
            default_ttl_seconds=default_ttl_seconds,
            correlation_id=get_correlation_id()
        )
    
    def get_compiled_rules(
        self,
        tenant_id: TenantId,
        rule_set_id: RuleSetId,
        version: SemVer
    ) -> Optional[CompiledRuleSet]:
        """
        Get cached compiled rules with expiration checking.
        
        Args:
            tenant_id: Tenant identifier
            rule_set_id: Rule set identifier
            version: Rule version
            
        Returns:
            Cached compiled rules if available and not expired, None otherwise
        """
        start_time = time.time()
        cache_key = self._build_cache_key(tenant_id, rule_set_id, version)
        
        # Check if entry exists
        cache_entry = self._cache.get(cache_key)
        
        if not cache_entry:
            duration_ms = (time.time() - start_time) * 1000
            self._logger.info(
                "rules_cache_miss",
                tenant_id=tenant_id.value,
                rule_set_id=str(rule_set_id.value),
                version=str(version),
                cache_key=cache_key,
                duration_ms=duration_ms,
                correlation_id=get_correlation_id()
            )
            return None
        
        # Check expiration
        current_time = time.time()
        if cache_entry["expires_at"] <= current_time:
            # Entry expired, remove it
            del self._cache[cache_key]
            
            duration_ms = (time.time() - start_time) * 1000
            self._logger.info(
                "rules_cache_expired",
                tenant_id=tenant_id.value,
                rule_set_id=str(rule_set_id.value),
                version=str(version),
                cache_key=cache_key,
                expired_at=cache_entry["expires_at"],
                current_time=current_time,
                duration_ms=duration_ms,
                correlation_id=get_correlation_id()
            )
            return None
        
        # Entry is valid, deserialize and return
        try:
            compiled_rules = self._deserialize_compiled_rules(cache_entry["data"])
            
            duration_ms = (time.time() - start_time) * 1000
            age_seconds = current_time - cache_entry["stored_at"]
            
            self._logger.info(
                "rules_cache_hit",
                tenant_id=tenant_id.value,
                rule_set_id=str(rule_set_id.value),
                version=str(version),
                cache_key=cache_key,
                age_seconds=age_seconds,
                ttl_remaining=cache_entry["expires_at"] - current_time,
                duration_ms=duration_ms,
                correlation_id=get_correlation_id()
            )
            
            return compiled_rules
            
        except Exception as e:
            # Deserialization failed, remove corrupted entry
            del self._cache[cache_key]
            
            duration_ms = (time.time() - start_time) * 1000
            self._logger.error(
                "rules_cache_deserialization_failed",
                tenant_id=tenant_id.value,
                rule_set_id=str(rule_set_id.value),
                version=str(version),
                cache_key=cache_key,
                error=str(e),
                duration_ms=duration_ms,
                correlation_id=get_correlation_id()
            )
            return None
    
    def store_compiled_rules(
        self,
        tenant_id: TenantId,
        rule_set_id: RuleSetId,
        version: SemVer,
        compiled_rules: CompiledRuleSet,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Store compiled rules in cache with TTL.
        
        Args:
            tenant_id: Tenant identifier
            rule_set_id: Rule set identifier
            version: Rule version
            compiled_rules: Compiled rules to cache
            ttl_seconds: Time to live in seconds, None for default
        """
        start_time = time.time()
        cache_key = self._build_cache_key(tenant_id, rule_set_id, version)
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        
        try:
            # Serialize compiled rules
            serialized_data = self._serialize_compiled_rules(compiled_rules)
            
            # Calculate expiration time
            current_time = time.time()
            expires_at = current_time + ttl
            
            # Store in cache
            cache_entry = {
                "data": serialized_data,
                "stored_at": current_time,
                "expires_at": expires_at,
                "ttl_seconds": ttl,
                "tenant_id": tenant_id.value,
                "rule_set_id": str(rule_set_id.value),
                "version": str(version)
            }
            
            self._cache[cache_key] = cache_entry
            
            duration_ms = (time.time() - start_time) * 1000
            
            self._logger.info(
                "rules_cache_stored",
                tenant_id=tenant_id.value,
                rule_set_id=str(rule_set_id.value),
                version=str(version),
                cache_key=cache_key,
                ttl_seconds=ttl,
                expires_at=expires_at,
                data_size_bytes=len(serialized_data) if isinstance(serialized_data, (str, bytes)) else 0,
                duration_ms=duration_ms,
                total_cached_entries=len(self._cache),
                correlation_id=get_correlation_id()
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._logger.error(
                "rules_cache_store_failed",
                tenant_id=tenant_id.value,
                rule_set_id=str(rule_set_id.value),
                version=str(version),
                cache_key=cache_key,
                error=str(e),
                duration_ms=duration_ms,
                correlation_id=get_correlation_id()
            )
            # Don't raise exception, caching failures shouldn't break the application
    
    def invalidate_compiled_rules(
        self,
        tenant_id: TenantId,
        rule_set_id: RuleSetId,
        version: Optional[SemVer] = None
    ) -> None:
        """
        Invalidate cached compiled rules.
        
        Args:
            tenant_id: Tenant identifier
            rule_set_id: Rule set identifier
            version: Specific version to invalidate, None for all versions
        """
        start_time = time.time()
        invalidated_count = 0
        
        if version:
            # Invalidate specific version
            cache_key = self._build_cache_key(tenant_id, rule_set_id, version)
            if cache_key in self._cache:
                del self._cache[cache_key]
                invalidated_count = 1
        else:
            # Invalidate all versions for this rule set
            prefix = f"{tenant_id.value}:{rule_set_id.value}:"
            keys_to_remove = [key for key in self._cache.keys() if key.startswith(prefix)]
            
            for key in keys_to_remove:
                del self._cache[key]
            
            invalidated_count = len(keys_to_remove)
        
        duration_ms = (time.time() - start_time) * 1000
        
        self._logger.info(
            "rules_cache_invalidated",
            tenant_id=tenant_id.value,
            rule_set_id=str(rule_set_id.value),
            version=str(version) if version else "all_versions",
            invalidated_count=invalidated_count,
            remaining_entries=len(self._cache),
            duration_ms=duration_ms,
            correlation_id=get_correlation_id()
        )
    
    def _build_cache_key(
        self,
        tenant_id: TenantId,
        rule_set_id: RuleSetId,
        version: SemVer
    ) -> str:
        """Build cache key for tenant isolation."""
        # Use tenant_id:rule_set_id:version format for clear hierarchy
        return f"{tenant_id.value}:{rule_set_id.value}:{version}"
    
    def _serialize_compiled_rules(self, compiled_rules: CompiledRuleSet) -> str:
        """
        Serialize compiled rules for storage.
        
        This uses JSON serialization for the compiled rule IR which should be
        JSON-serializable by design.
        """
        # Convert compiled rules to dictionary format
        data = {
            "checksum": compiled_rules.checksum,
            "rules": compiled_rules.rules,
            "metadata": compiled_rules.metadata,
            "compiled_at": compiled_rules.compiled_at.isoformat() if compiled_rules.compiled_at else None,
            "compiler_version": compiled_rules.compiler_version
        }
        
        # Serialize to JSON
        return json.dumps(data, sort_keys=True)
    
    def _deserialize_compiled_rules(self, serialized_data: str) -> CompiledRuleSet:
        """
        Deserialize compiled rules from storage.
        """
        from datetime import datetime
        
        # Parse JSON
        data = json.loads(serialized_data)
        
        # Reconstruct CompiledRuleSet
        compiled_rules = CompiledRuleSet(
            checksum=data["checksum"],
            rules=data["rules"],
            metadata=data.get("metadata", {}),
            compiled_at=datetime.fromisoformat(data["compiled_at"]) if data.get("compiled_at") else None,
            compiler_version=data.get("compiler_version", "unknown")
        )
        
        return compiled_rules
    
    def cleanup_expired_entries(self) -> int:
        """
        Clean up expired cache entries.
        
        Returns:
            Number of entries cleaned up
        """
        start_time = time.time()
        current_time = time.time()
        
        expired_keys = []
        for key, entry in self._cache.items():
            if entry["expires_at"] <= current_time:
                expired_keys.append(key)
        
        # Remove expired entries
        for key in expired_keys:
            del self._cache[key]
        
        duration_ms = (time.time() - start_time) * 1000
        
        self._logger.info(
            "rules_cache_cleanup_completed",
            expired_entries=len(expired_keys),
            remaining_entries=len(self._cache),
            duration_ms=duration_ms,
            correlation_id=get_correlation_id()
        )
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        current_time = time.time()
        
        stats = {
            "total_entries": len(self._cache),
            "expired_entries": 0,
            "entries_by_tenant": {},
            "entries_by_rule_set": {},
            "memory_usage_estimate": 0,
            "oldest_entry_age": 0,
            "newest_entry_age": 0
        }
        
        entry_ages = []
        
        for key, entry in self._cache.items():
            # Check if expired
            if entry["expires_at"] <= current_time:
                stats["expired_entries"] += 1
            
            # Count by tenant
            tenant_id = entry.get("tenant_id", "unknown")
            stats["entries_by_tenant"][tenant_id] = stats["entries_by_tenant"].get(tenant_id, 0) + 1
            
            # Count by rule set
            rule_set_id = entry.get("rule_set_id", "unknown")
            stats["entries_by_rule_set"][rule_set_id] = stats["entries_by_rule_set"].get(rule_set_id, 0) + 1
            
            # Estimate memory usage
            data_size = len(entry["data"]) if isinstance(entry["data"], (str, bytes)) else 100  # rough estimate
            stats["memory_usage_estimate"] += data_size
            
            # Track ages
            age = current_time - entry["stored_at"]
            entry_ages.append(age)
        
        if entry_ages:
            stats["oldest_entry_age"] = max(entry_ages)
            stats["newest_entry_age"] = min(entry_ages)
        
        self._logger.info(
            "rules_cache_stats",
            **stats,
            correlation_id=get_correlation_id()
        )
        
        return stats