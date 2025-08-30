"""Rule repository implementation for ValidaHub Smart Rules Engine.

This module implements the RuleRepository port with comprehensive logging
and performance monitoring.
"""

from typing import Optional, List, Dict, Any
import time
import json
from datetime import datetime, timezone

from src.application.ports.rules import RuleRepository
from src.domain.value_objects import TenantId
from src.domain.rules.value_objects import RuleSetId, SemVer
from src.domain.rules.aggregates import RuleSet
from src.shared.logging import get_logger
from src.shared.logging.context import get_correlation_id


class InMemoryRuleRepository(RuleRepository):
    """
    In-memory implementation of RuleRepository for testing and development.
    Includes comprehensive logging and monitoring.
    """
    
    def __init__(self):
        """Initialize in-memory rule repository."""
        self._logger = get_logger("infrastructure.rule_repository")
        self._storage: Dict[str, Dict[str, Any]] = {}  # rule_set_id -> rule_set_data
        self._tenant_index: Dict[str, List[str]] = {}  # tenant_id -> [rule_set_ids]
        self._name_index: Dict[str, str] = {}  # "tenant_id:name" -> rule_set_id
        
        self._logger.info(
            "rule_repository_initialized",
            implementation="in_memory",
            correlation_id=get_correlation_id()
        )
    
    def save(self, rule_set: RuleSet) -> RuleSet:
        """
        Save rule set to storage with detailed logging.
        
        Args:
            rule_set: RuleSet instance to save
            
        Returns:
            Saved rule set instance
        """
        start_time = time.time()
        rule_set_id = str(rule_set.id.value)
        tenant_id = rule_set.tenant_id.value
        
        # Serialize rule set to storage format
        rule_set_data = self._serialize_rule_set(rule_set)
        
        # Check if this is an update or insert
        is_update = rule_set_id in self._storage
        operation = "update" if is_update else "insert"
        
        # Store rule set
        self._storage[rule_set_id] = rule_set_data
        
        # Update tenant index
        if tenant_id not in self._tenant_index:
            self._tenant_index[tenant_id] = []
        
        if rule_set_id not in self._tenant_index[tenant_id]:
            self._tenant_index[tenant_id].append(rule_set_id)
        
        # Update name index
        name_key = f"{tenant_id}:{rule_set.name}"
        self._name_index[name_key] = rule_set_id
        
        duration_ms = (time.time() - start_time) * 1000
        
        self._logger.info(
            "rule_repository_save_completed",
            rule_set_id=rule_set_id,
            tenant_id=tenant_id,
            name=rule_set.name,
            channel=rule_set.channel.value,
            operation=operation,
            versions_count=len(rule_set.versions),
            current_version=str(rule_set.current_version) if rule_set.current_version else None,
            duration_ms=duration_ms,
            storage_size=len(self._storage),
            correlation_id=get_correlation_id()
        )
        
        return rule_set
    
    def find_by_id(self, tenant_id: TenantId, rule_set_id: RuleSetId) -> Optional[RuleSet]:
        """
        Find rule set by ID and tenant with logging.
        
        Args:
            tenant_id: Tenant identifier
            rule_set_id: Rule set identifier
            
        Returns:
            RuleSet if found, None otherwise
        """
        start_time = time.time()
        rule_set_id_value = str(rule_set_id.value)
        tenant_id_value = tenant_id.value
        
        rule_set_data = self._storage.get(rule_set_id_value)
        
        duration_ms = (time.time() - start_time) * 1000
        
        if not rule_set_data:
            self._logger.info(
                "rule_repository_find_by_id_miss",
                rule_set_id=rule_set_id_value,
                tenant_id=tenant_id_value,
                duration_ms=duration_ms,
                correlation_id=get_correlation_id()
            )
            return None
        
        # Verify tenant isolation
        if rule_set_data["tenant_id"] != tenant_id_value:
            self._logger.warning(
                "tenant_isolation_violation_attempted",
                requesting_tenant=tenant_id_value,
                rule_set_tenant=rule_set_data["tenant_id"],
                rule_set_id=rule_set_id_value,
                correlation_id=get_correlation_id()
            )
            return None
        
        self._logger.info(
            "rule_repository_find_by_id_hit",
            rule_set_id=rule_set_id_value,
            tenant_id=tenant_id_value,
            name=rule_set_data["name"],
            versions_count=len(rule_set_data["versions"]),
            duration_ms=duration_ms,
            correlation_id=get_correlation_id()
        )
        
        return self._deserialize_rule_set(rule_set_data)
    
    def find_by_name(self, tenant_id: TenantId, name: str) -> Optional[RuleSet]:
        """
        Find rule set by name and tenant with logging.
        
        Args:
            tenant_id: Tenant identifier
            name: Rule set name
            
        Returns:
            RuleSet if found, None otherwise
        """
        start_time = time.time()
        tenant_id_value = tenant_id.value
        name_key = f"{tenant_id_value}:{name}"
        
        rule_set_id = self._name_index.get(name_key)
        
        duration_ms = (time.time() - start_time) * 1000
        
        if not rule_set_id:
            self._logger.info(
                "rule_repository_find_by_name_miss",
                tenant_id=tenant_id_value,
                name=name,
                duration_ms=duration_ms,
                correlation_id=get_correlation_id()
            )
            return None
        
        rule_set_data = self._storage.get(rule_set_id)
        
        if not rule_set_data:
            # Index inconsistency
            self._logger.error(
                "rule_repository_name_index_inconsistency",
                tenant_id=tenant_id_value,
                name=name,
                rule_set_id=rule_set_id,
                correlation_id=get_correlation_id()
            )
            # Clean up inconsistent index
            del self._name_index[name_key]
            return None
        
        self._logger.info(
            "rule_repository_find_by_name_hit",
            tenant_id=tenant_id_value,
            name=name,
            rule_set_id=rule_set_id,
            versions_count=len(rule_set_data["versions"]),
            duration_ms=duration_ms,
            correlation_id=get_correlation_id()
        )
        
        return self._deserialize_rule_set(rule_set_data)
    
    def find_all_by_tenant(self, tenant_id: TenantId) -> List[RuleSet]:
        """
        Find all rule sets for a tenant with logging.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of rule sets
        """
        start_time = time.time()
        tenant_id_value = tenant_id.value
        
        rule_set_ids = self._tenant_index.get(tenant_id_value, [])
        rule_sets = []
        
        for rule_set_id in rule_set_ids:
            rule_set_data = self._storage.get(rule_set_id)
            if rule_set_data:
                rule_sets.append(self._deserialize_rule_set(rule_set_data))
            else:
                # Index inconsistency
                self._logger.warning(
                    "rule_repository_tenant_index_inconsistency",
                    tenant_id=tenant_id_value,
                    rule_set_id=rule_set_id,
                    correlation_id=get_correlation_id()
                )
        
        duration_ms = (time.time() - start_time) * 1000
        
        self._logger.info(
            "rule_repository_find_all_by_tenant_completed",
            tenant_id=tenant_id_value,
            rule_sets_found=len(rule_sets),
            rule_sets_indexed=len(rule_set_ids),
            duration_ms=duration_ms,
            correlation_id=get_correlation_id()
        )
        
        return rule_sets
    
    def delete(self, tenant_id: TenantId, rule_set_id: RuleSetId) -> bool:
        """
        Delete rule set by ID and tenant with logging.
        
        Args:
            tenant_id: Tenant identifier
            rule_set_id: Rule set identifier
            
        Returns:
            True if deleted, False if not found
        """
        start_time = time.time()
        rule_set_id_value = str(rule_set_id.value)
        tenant_id_value = tenant_id.value
        
        rule_set_data = self._storage.get(rule_set_id_value)
        
        if not rule_set_data:
            self._logger.info(
                "rule_repository_delete_miss",
                rule_set_id=rule_set_id_value,
                tenant_id=tenant_id_value,
                correlation_id=get_correlation_id()
            )
            return False
        
        # Verify tenant isolation
        if rule_set_data["tenant_id"] != tenant_id_value:
            self._logger.warning(
                "rule_repository_delete_tenant_violation",
                requesting_tenant=tenant_id_value,
                rule_set_tenant=rule_set_data["tenant_id"],
                rule_set_id=rule_set_id_value,
                correlation_id=get_correlation_id()
            )
            return False
        
        # Remove from storage
        del self._storage[rule_set_id_value]
        
        # Remove from tenant index
        if tenant_id_value in self._tenant_index:
            if rule_set_id_value in self._tenant_index[tenant_id_value]:
                self._tenant_index[tenant_id_value].remove(rule_set_id_value)
        
        # Remove from name index
        name_key = f"{tenant_id_value}:{rule_set_data['name']}"
        if name_key in self._name_index:
            del self._name_index[name_key]
        
        duration_ms = (time.time() - start_time) * 1000
        
        self._logger.info(
            "rule_repository_delete_completed",
            rule_set_id=rule_set_id_value,
            tenant_id=tenant_id_value,
            name=rule_set_data["name"],
            versions_deleted=len(rule_set_data["versions"]),
            duration_ms=duration_ms,
            correlation_id=get_correlation_id()
        )
        
        return True
    
    def _serialize_rule_set(self, rule_set: RuleSet) -> Dict[str, Any]:
        """Convert RuleSet to storage format."""
        versions_data = []
        for version in rule_set.versions:
            rules_data = []
            for rule in version.rules:
                rules_data.append(rule.to_dict())
            
            version_data = {
                "id": str(version.id.value),
                "version": str(version.version),
                "status": version.status.value,
                "rules": rules_data,
                "checksum": version.checksum,
                "created_at": version.created_at.isoformat(),
                "published_at": version.published_at.isoformat() if version.published_at else None,
                "deprecated_at": version.deprecated_at.isoformat() if version.deprecated_at else None,
                "metadata": {
                    "created_by": version.metadata.created_by,
                    "created_at": version.metadata.created_at.isoformat(),
                    "modified_by": version.metadata.modified_by,
                    "modified_at": version.metadata.modified_at.isoformat() if version.metadata.modified_at else None,
                    "tags": version.metadata.tags,
                    "description": version.metadata.description,
                    "documentation_url": version.metadata.documentation_url
                }
            }
            versions_data.append(version_data)
        
        return {
            "id": str(rule_set.id.value),
            "tenant_id": rule_set.tenant_id.value,
            "channel": rule_set.channel.value,
            "name": rule_set.name,
            "description": rule_set.description,
            "versions": versions_data,
            "current_version": str(rule_set.current_version) if rule_set.current_version else None,
            "published_versions": [str(v) for v in rule_set.published_versions],
            "deprecated_versions": [str(v) for v in rule_set.deprecated_versions],
            "compatibility_policy": rule_set.compatibility_policy,
            "created_at": rule_set.created_at.isoformat(),
            "updated_at": rule_set.updated_at.isoformat()
        }
    
    def _deserialize_rule_set(self, data: Dict[str, Any]) -> RuleSet:
        """Convert storage format to RuleSet."""
        from src.domain.rules.entities import RuleVersion
        from src.domain.rules.value_objects import (
            RuleSetId, RuleVersionId, RuleDefinition, RuleId, RuleType, 
            SemVer, RuleStatus, RuleMetadata
        )
        from src.domain.value_objects import TenantId, Channel
        from uuid import UUID
        
        # Deserialize versions
        versions = []
        for version_data in data["versions"]:
            # Deserialize rules
            rules = []
            for rule_data in version_data["rules"]:
                rule_def = RuleDefinition(
                    id=RuleId(rule_data["id"]),
                    type=RuleType(rule_data["type"]),
                    field=rule_data["field"],
                    condition=rule_data["condition"],
                    message=rule_data["message"],
                    severity=rule_data["severity"],
                    metadata=rule_data.get("metadata")
                )
                rules.append(rule_def)
            
            # Deserialize metadata
            metadata_data = version_data["metadata"]
            metadata = RuleMetadata(
                created_by=metadata_data["created_by"],
                created_at=datetime.fromisoformat(metadata_data["created_at"]),
                modified_by=metadata_data.get("modified_by"),
                modified_at=datetime.fromisoformat(metadata_data["modified_at"]) if metadata_data.get("modified_at") else None,
                tags=metadata_data.get("tags"),
                description=metadata_data.get("description"),
                documentation_url=metadata_data.get("documentation_url")
            )
            
            # Create version entity
            version = RuleVersion(
                id=RuleVersionId(UUID(version_data["id"])),
                version=SemVer.from_string(version_data["version"]),
                status=RuleStatus(version_data["status"]),
                rules=rules,
                checksum=version_data.get("checksum"),
                created_at=datetime.fromisoformat(version_data["created_at"]),
                published_at=datetime.fromisoformat(version_data["published_at"]) if version_data.get("published_at") else None,
                deprecated_at=datetime.fromisoformat(version_data["deprecated_at"]) if version_data.get("deprecated_at") else None,
                metadata=metadata,
                _domain_events=[]
            )
            versions.append(version)
        
        # Create rule set aggregate
        rule_set = RuleSet(
            id=RuleSetId(UUID(data["id"])),
            tenant_id=TenantId(data["tenant_id"]),
            channel=Channel(data["channel"]),
            name=data["name"],
            description=data.get("description"),
            versions=versions,
            current_version=SemVer.from_string(data["current_version"]) if data.get("current_version") else None,
            published_versions=[SemVer.from_string(v) for v in data.get("published_versions", [])],
            deprecated_versions=[SemVer.from_string(v) for v in data.get("deprecated_versions", [])],
            compatibility_policy=data.get("compatibility_policy", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )
        
        return rule_set
    
    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics for monitoring."""
        stats = {
            "total_rule_sets": len(self._storage),
            "tenant_count": len(self._tenant_index),
            "name_index_count": len(self._name_index),
            "rule_sets_by_tenant": {},
            "rule_sets_by_channel": {},
            "total_versions": 0,
            "published_versions": 0
        }
        
        # Calculate detailed stats
        for rule_set_data in self._storage.values():
            tenant = rule_set_data["tenant_id"]
            channel = rule_set_data["channel"]
            
            stats["rule_sets_by_tenant"][tenant] = stats["rule_sets_by_tenant"].get(tenant, 0) + 1
            stats["rule_sets_by_channel"][channel] = stats["rule_sets_by_channel"].get(channel, 0) + 1
            stats["total_versions"] += len(rule_set_data["versions"])
            stats["published_versions"] += len(rule_set_data.get("published_versions", []))
        
        self._logger.info(
            "rule_repository_stats",
            **stats,
            correlation_id=get_correlation_id()
        )
        
        return stats