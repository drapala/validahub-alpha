"""Application ports for Rules bounded context.

This module defines the contracts between the application layer and external systems
for the Smart Rules Engine functionality.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID

from src.domain.value_objects import TenantId
from src.domain.rules.value_objects import RuleSetId, SemVer, RuleDefinition
from src.domain.rules.aggregates import RuleSet
from src.domain.rules.engine.ir_types import CompiledRuleSet


class RuleRepository(ABC):
    """Port for rule set persistence operations."""
    
    @abstractmethod
    def save(self, rule_set: RuleSet) -> RuleSet:
        """
        Save rule set to storage.
        
        Args:
            rule_set: RuleSet instance to save
            
        Returns:
            Saved rule set instance
        """
        pass
    
    @abstractmethod
    def find_by_id(self, tenant_id: TenantId, rule_set_id: RuleSetId) -> Optional[RuleSet]:
        """
        Find rule set by ID and tenant.
        
        Args:
            tenant_id: Tenant identifier
            rule_set_id: Rule set identifier
            
        Returns:
            RuleSet if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_name(self, tenant_id: TenantId, name: str) -> Optional[RuleSet]:
        """
        Find rule set by name and tenant.
        
        Args:
            tenant_id: Tenant identifier
            name: Rule set name
            
        Returns:
            RuleSet if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_all_by_tenant(self, tenant_id: TenantId) -> List[RuleSet]:
        """
        Find all rule sets for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of rule sets
        """
        pass
    
    @abstractmethod
    def delete(self, tenant_id: TenantId, rule_set_id: RuleSetId) -> bool:
        """
        Delete rule set by ID and tenant.
        
        Args:
            tenant_id: Tenant identifier
            rule_set_id: Rule set identifier
            
        Returns:
            True if deleted, False if not found
        """
        pass


class RuleCompiler(ABC):
    """Port for compiling rules into intermediate representation (IR)."""
    
    @abstractmethod
    def compile_rules(self, rules: List[RuleDefinition]) -> CompiledRuleSet:
        """
        Compile rules into optimized intermediate representation.
        
        Args:
            rules: List of rule definitions to compile
            
        Returns:
            Compiled rule set ready for execution
            
        Raises:
            CompilationError: If rules cannot be compiled
        """
        pass
    
    @abstractmethod
    def validate_rules(self, rules: List[RuleDefinition]) -> List[str]:
        """
        Validate rules syntax and dependencies.
        
        Args:
            rules: List of rule definitions to validate
            
        Returns:
            List of validation errors, empty if valid
        """
        pass


class SuggestionEngine(ABC):
    """Port for rule suggestion and smart completion."""
    
    @abstractmethod
    def get_rule_suggestions(
        self,
        tenant_id: TenantId,
        field: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get rule suggestions for a field based on context.
        
        Args:
            tenant_id: Tenant identifier
            field: Field name to suggest rules for
            context: Additional context (channel, existing rules, etc.)
            
        Returns:
            List of rule suggestions with confidence scores
        """
        pass
    
    @abstractmethod
    def learn_from_corrections(
        self,
        tenant_id: TenantId,
        field: str,
        original_value: str,
        corrected_value: str,
        context: Dict[str, Any]
    ) -> None:
        """
        Learn from user corrections to improve suggestions.
        
        Args:
            tenant_id: Tenant identifier
            field: Field that was corrected
            original_value: Original field value
            corrected_value: User-corrected value
            context: Additional context for learning
        """
        pass


class CachePort(ABC):
    """Port for caching compiled rule intermediate representations."""
    
    @abstractmethod
    def get_compiled_rules(
        self,
        tenant_id: TenantId,
        rule_set_id: RuleSetId,
        version: SemVer
    ) -> Optional[CompiledRuleSet]:
        """
        Get cached compiled rules.
        
        Args:
            tenant_id: Tenant identifier
            rule_set_id: Rule set identifier
            version: Rule version
            
        Returns:
            Cached compiled rules if available, None otherwise
        """
        pass
    
    @abstractmethod
    def store_compiled_rules(
        self,
        tenant_id: TenantId,
        rule_set_id: RuleSetId,
        version: SemVer,
        compiled_rules: CompiledRuleSet,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Store compiled rules in cache.
        
        Args:
            tenant_id: Tenant identifier
            rule_set_id: Rule set identifier
            version: Rule version
            compiled_rules: Compiled rules to cache
            ttl_seconds: Time to live in seconds, None for default
        """
        pass
    
    @abstractmethod
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
        pass


class EventBusPort(ABC):
    """Port for publishing rule-related domain events."""
    
    @abstractmethod
    def publish_rule_events(self, events: List[Any]) -> None:
        """
        Publish rule domain events.
        
        Args:
            events: List of domain events to publish
        """
        pass
    
    @abstractmethod
    def send_webhook(
        self,
        tenant_id: TenantId,
        event_type: str,
        payload: Dict[str, Any],
        webhook_url: str
    ) -> bool:
        """
        Send webhook notification for rule changes.
        
        Args:
            tenant_id: Tenant identifier
            event_type: Type of event (rule_published, rule_deprecated, etc.)
            payload: Event payload
            webhook_url: Webhook URL to notify
            
        Returns:
            True if webhook sent successfully, False otherwise
        """
        pass


class CorrectionStore(ABC):
    """Port for storing and retrieving correction data."""
    
    @abstractmethod
    def log_correction(
        self,
        tenant_id: TenantId,
        field: str,
        original_value: str,
        corrected_value: str,
        rule_set_id: Optional[RuleSetId] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log a correction made by a user.
        
        Args:
            tenant_id: Tenant identifier
            field: Field that was corrected
            original_value: Original field value
            corrected_value: User-corrected value
            rule_set_id: Rule set that was applied (optional)
            context: Additional context (job_id, seller_id, etc.)
            
        Returns:
            Correction ID for tracking
        """
        pass
    
    @abstractmethod
    def get_corrections(
        self,
        tenant_id: TenantId,
        field: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get correction history for analysis.
        
        Args:
            tenant_id: Tenant identifier
            field: Specific field to filter by (optional)
            limit: Maximum number of corrections to return
            
        Returns:
            List of correction records
        """
        pass


class RuleJobAdapter(ABC):
    """Port for integrating rules with job processing pipeline."""
    
    @abstractmethod
    def apply_rules(
        self,
        tenant_id: TenantId,
        job_id: str,
        rule_set_id: RuleSetId,
        version: SemVer,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply rules to job data during processing.
        
        Args:
            tenant_id: Tenant identifier
            job_id: Job identifier
            rule_set_id: Rule set to apply
            version: Rule version to use
            data: Data to validate/correct
            
        Returns:
            Processing results with validation errors and corrections
        """
        pass
    
    @abstractmethod
    def get_rule_performance_metrics(
        self,
        tenant_id: TenantId,
        rule_set_id: RuleSetId,
        version: SemVer,
        time_range_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get performance metrics for rules.
        
        Args:
            tenant_id: Tenant identifier
            rule_set_id: Rule set identifier
            version: Rule version
            time_range_hours: Time range for metrics
            
        Returns:
            Performance metrics (execution time, error rates, etc.)
        """
        pass