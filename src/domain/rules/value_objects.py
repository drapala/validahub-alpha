"""Value objects for Rules bounded context.

This module contains immutable value objects with validation and invariants.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import ClassVar, Optional, Dict, Any, List
from uuid import UUID
import re
import json


class RuleStatus(Enum):
    """Rule lifecycle status."""
    
    DRAFT = "draft"
    VALIDATED = "validated"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class RuleType(Enum):
    """Types of validation rules."""
    
    REQUIRED = "required"
    FORMAT = "format"
    LENGTH = "length"
    RANGE = "range"
    ENUM = "enum"
    PATTERN = "pattern"
    DEPENDENCY = "dependency"
    BUSINESS = "business"
    COMPOSITE = "composite"


class Compatibility(Enum):
    """Compatibility level for rule versions."""
    
    MAJOR = "major"  # Breaking changes
    MINOR = "minor"  # New features, backward compatible
    PATCH = "patch"  # Bug fixes, fully compatible


@dataclass(frozen=True)
class RuleSetId:
    """Rule set identifier."""
    
    value: UUID
    
    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise ValueError("Invalid rule set id format")
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __repr__(self) -> str:
        return f"RuleSetId('{self.value}')"


@dataclass(frozen=True)
class RuleId:
    """Individual rule identifier."""
    
    value: str
    _pattern: ClassVar[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
    
    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValueError("Invalid rule id format")
        
        # Normalize to lowercase
        normalized = self.value.strip().lower()
        
        # Validate pattern
        if not self._pattern.match(normalized):
            raise ValueError("Invalid rule id format")
        
        # Set normalized value
        object.__setattr__(self, 'value', normalized)
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"RuleId('{self.value}')"


@dataclass(frozen=True)
class RuleVersionId:
    """Rule version identifier."""
    
    value: UUID
    
    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise ValueError("Invalid rule version id format")
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __repr__(self) -> str:
        return f"RuleVersionId('{self.value}')"


@dataclass(frozen=True)
class SemVer:
    """Semantic version with validation."""
    
    major: int
    minor: int
    patch: int
    
    def __post_init__(self) -> None:
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("Version components must be non-negative")
        
        # Major version 0 is allowed only for initial development
        if self.major == 0 and (self.minor > 99 or self.patch > 999):
            raise ValueError("Pre-release versions limited to 0.99.999")
    
    @classmethod
    def from_string(cls, version_str: str) -> "SemVer":
        """Parse from 'major.minor.patch' format."""
        if not version_str:
            raise ValueError("Invalid version format")
        
        try:
            parts = version_str.strip().split('.')
            if len(parts) != 3:
                raise ValueError("Invalid version format")
            
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2])
            
            return cls(major, minor, patch)
        except (ValueError, IndexError):
            raise ValueError("Invalid version format")
    
    def increment_major(self) -> "SemVer":
        """Create new version with incremented major."""
        return SemVer(self.major + 1, 0, 0)
    
    def increment_minor(self) -> "SemVer":
        """Create new version with incremented minor."""
        return SemVer(self.major, self.minor + 1, 0)
    
    def increment_patch(self) -> "SemVer":
        """Create new version with incremented patch."""
        return SemVer(self.major, self.minor, self.patch + 1)
    
    def is_compatible_with(self, other: "SemVer") -> Compatibility:
        """Determine compatibility level with another version."""
        if self.major != other.major:
            return Compatibility.MAJOR
        elif self.minor != other.minor:
            return Compatibility.MINOR
        else:
            return Compatibility.PATCH
    
    def is_newer_than(self, other: "SemVer") -> bool:
        """Check if this version is newer than another."""
        if self.major != other.major:
            return self.major > other.major
        if self.minor != other.minor:
            return self.minor > other.minor
        return self.patch > other.patch
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def __repr__(self) -> str:
        return f"SemVer({self.major}, {self.minor}, {self.patch})"


@dataclass(frozen=True)
class RuleDefinition:
    """Rule definition with validation logic."""
    
    id: RuleId
    type: RuleType
    field: str
    condition: Dict[str, Any]
    message: str
    severity: str  # "error", "warning", "info"
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self) -> None:
        # Validate field name
        if not self.field or len(self.field) > 100:
            raise ValueError("Invalid field name")
        
        # Validate severity
        if self.severity not in ("error", "warning", "info"):
            raise ValueError("Invalid severity level")
        
        # Validate condition based on rule type
        self._validate_condition()
        
        # Validate message
        if not self.message or len(self.message) > 500:
            raise ValueError("Invalid error message")
    
    def _validate_condition(self) -> None:
        """Validate condition structure based on rule type."""
        if not self.condition:
            raise ValueError("Rule condition cannot be empty")
        
        if self.type == RuleType.REQUIRED:
            # Required rules need no additional condition
            pass
        elif self.type == RuleType.FORMAT:
            if "format" not in self.condition:
                raise ValueError("Format rule must specify format")
        elif self.type == RuleType.LENGTH:
            if "min" not in self.condition and "max" not in self.condition:
                raise ValueError("Length rule must specify min or max")
        elif self.type == RuleType.RANGE:
            if "min" not in self.condition and "max" not in self.condition:
                raise ValueError("Range rule must specify min or max")
        elif self.type == RuleType.ENUM:
            if "values" not in self.condition or not isinstance(self.condition["values"], list):
                raise ValueError("Enum rule must specify values list")
        elif self.type == RuleType.PATTERN:
            if "pattern" not in self.condition:
                raise ValueError("Pattern rule must specify regex pattern")
            # Validate regex compilation
            try:
                re.compile(self.condition["pattern"])
            except re.error:
                raise ValueError("Invalid regex pattern")
        elif self.type == RuleType.DEPENDENCY:
            if "depends_on" not in self.condition:
                raise ValueError("Dependency rule must specify depends_on field")
        elif self.type == RuleType.BUSINESS:
            if "expression" not in self.condition:
                raise ValueError("Business rule must specify expression")
        elif self.type == RuleType.COMPOSITE:
            if "rules" not in self.condition or not isinstance(self.condition["rules"], list):
                raise ValueError("Composite rule must specify rules list")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "type": self.type.value,
            "field": self.field,
            "condition": self.condition,
            "message": self.message,
            "severity": self.severity,
            "metadata": self.metadata or {}
        }
    
    def __str__(self) -> str:
        return f"Rule({self.id}, type={self.type.value}, field={self.field})"


@dataclass(frozen=True)
class RuleMetadata:
    """Metadata for rules with tracking information."""
    
    created_by: str
    created_at: datetime
    modified_by: Optional[str] = None
    modified_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    documentation_url: Optional[str] = None
    
    def __post_init__(self) -> None:
        # Validate timestamps are timezone-aware
        if not self.created_at.tzinfo:
            raise ValueError("created_at must be timezone-aware")
        
        if self.modified_at and not self.modified_at.tzinfo:
            raise ValueError("modified_at must be timezone-aware")
        
        # Validate modified_at is after created_at
        if self.modified_at and self.modified_at < self.created_at:
            raise ValueError("modified_at cannot be before created_at")
        
        # Validate tags
        if self.tags:
            for tag in self.tags:
                if not tag or len(tag) > 50:
                    raise ValueError("Invalid tag format")
        
        # Validate description length
        if self.description and len(self.description) > 1000:
            raise ValueError("Description too long")
        
        # Validate documentation URL
        if self.documentation_url and not self.documentation_url.startswith(("http://", "https://")):
            raise ValueError("Invalid documentation URL")