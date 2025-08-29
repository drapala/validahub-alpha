"""
Domain Value Objects for ValidaHub.

Value Objects are immutable objects that are defined by their attributes rather than identity.
They encapsulate domain concepts and provide validation, ensuring business invariants are
maintained at the lowest level of the domain model.

This module contains no framework dependencies, following DDD principles.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, ClassVar
from uuid import UUID, uuid4


@dataclass(frozen=True)
class JobId:
    """
    Represents a unique identifier for a Job in the system.
    
    Business Rules:
    - Must be a valid UUID v4
    - Cannot be empty or None
    - Immutable once created
    """
    value: UUID
    
    def __post_init__(self) -> None:
        """Validate JobId invariants."""
        if not isinstance(self.value, UUID):
            raise ValueError(f"JobId must be a UUID, got {type(self.value)}")
        if self.value.version != 4:
            raise ValueError(f"JobId must be UUID v4, got version {self.value.version}")
    
    @classmethod
    def generate(cls) -> JobId:
        """Generate a new JobId with UUID v4."""
        return cls(uuid4())
    
    @classmethod
    def from_string(cls, value: str) -> JobId:
        """Create JobId from string representation."""
        try:
            return cls(UUID(value))
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid JobId format: {value}") from e
    
    def __str__(self) -> str:
        """Return string representation of JobId."""
        return str(self.value)


@dataclass(frozen=True)
class TenantId:
    """
    Represents a tenant identifier in the multi-tenant system.
    
    Business Rules:
    - Must follow pattern: t_[alphanumeric]+ (e.g., t_123, t_acme)
    - Minimum 3 characters after prefix
    - Maximum 50 total characters
    - Case-insensitive (stored as lowercase)
    """
    value: str
    _pattern: ClassVar[re.Pattern[str]] = re.compile(r"^t_[a-z0-9]{1,47}$")
    
    def __post_init__(self) -> None:
        """Validate and normalize TenantId."""
        # Normalize to lowercase
        normalized = self.value.lower() if isinstance(self.value, str) else ""
        object.__setattr__(self, "value", normalized)
        
        if not self._pattern.match(normalized):
            raise ValueError(
                f"TenantId must match pattern 't_[alphanumeric]{{1,47}}', got '{self.value}'"
            )
    
    def __str__(self) -> str:
        """Return string representation of TenantId."""
        return self.value


@dataclass(frozen=True)
class SellerId:
    """
    Represents a seller identifier within a tenant context.
    
    Business Rules:
    - Must be alphanumeric with optional underscores and hyphens
    - Minimum 1 character, maximum 100 characters
    - Cannot start or end with special characters
    """
    value: str
    _pattern: ClassVar[re.Pattern[str]] = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,98}[a-zA-Z0-9]$|^[a-zA-Z0-9]$")
    
    def __post_init__(self) -> None:
        """Validate SellerId format."""
        if not isinstance(self.value, str):
            raise ValueError(f"SellerId must be a string, got {type(self.value)}")
        
        if not self._pattern.match(self.value):
            raise ValueError(
                f"SellerId must be alphanumeric (optionally with _ or -), "
                f"1-100 chars, got '{self.value}'"
            )
    
    def __str__(self) -> str:
        """Return string representation of SellerId."""
        return self.value


@dataclass(frozen=True)
class Channel:
    """
    Represents a sales channel/marketplace.
    
    Business Rules:
    - Must be lowercase alphanumeric with optional underscores
    - Predefined set of valid channels (extensible via configuration)
    - Examples: mercado_livre, magalu, shopee, amazon_br
    """
    value: str
    _pattern: ClassVar[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,49}$")
    
    # Known channels (can be extended via configuration)
    KNOWN_CHANNELS: ClassVar[set[str]] = {
        "mercado_livre",
        "magalu", 
        "shopee",
        "amazon_br",
        "b2w",
        "via_varejo",
        "carrefour",
        "custom"
    }
    
    def __post_init__(self) -> None:
        """Validate Channel format and optionally check against known channels."""
        if not isinstance(self.value, str):
            raise ValueError(f"Channel must be a string, got {type(self.value)}")
        
        normalized = self.value.lower()
        object.__setattr__(self, "value", normalized)
        
        if not self._pattern.match(normalized):
            raise ValueError(
                f"Channel must be lowercase alphanumeric with optional underscores, "
                f"got '{self.value}'"
            )
    
    def is_known(self) -> bool:
        """Check if this is a known/supported channel."""
        return self.value in self.KNOWN_CHANNELS
    
    def __str__(self) -> str:
        """Return string representation of Channel."""
        return self.value


@dataclass(frozen=True)
class IdempotencyKey:
    """
    Represents an idempotency key for ensuring exactly-once processing.
    
    Business Rules:
    - Must be between 16 and 128 characters
    - Alphanumeric with optional hyphens and underscores
    - Used to prevent duplicate job submissions
    - Unique within a tenant context
    """
    value: str
    _pattern: ClassVar[re.Pattern[str]] = re.compile(r"^[a-zA-Z0-9\-_]{16,128}$")
    
    def __post_init__(self) -> None:
        """Validate IdempotencyKey format."""
        if not isinstance(self.value, str):
            raise ValueError(f"IdempotencyKey must be a string, got {type(self.value)}")
        
        if not self._pattern.match(self.value):
            raise ValueError(
                f"IdempotencyKey must be 16-128 alphanumeric characters "
                f"(with optional - or _), got '{self.value}' with length {len(self.value)}"
            )
    
    @classmethod
    def generate(cls) -> IdempotencyKey:
        """Generate a new IdempotencyKey using UUID."""
        return cls(str(uuid4()))
    
    def __str__(self) -> str:
        """Return string representation of IdempotencyKey."""
        return self.value


@dataclass(frozen=True)
class FileReference:
    """
    Represents a reference to a file in object storage.
    
    Business Rules:
    - Must be a valid S3/object storage path
    - Format: bucket/path/to/file or full URL
    - Immutable once created
    """
    value: str
    _url_pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"^(https?://[^/]+/|s3://[^/]+/|)[a-zA-Z0-9\-_./%]+$"
    )
    
    def __post_init__(self) -> None:
        """Validate FileReference format."""
        if not isinstance(self.value, str):
            raise ValueError(f"FileReference must be a string, got {type(self.value)}")
        
        if len(self.value) < 3 or len(self.value) > 1024:
            raise ValueError(
                f"FileReference must be between 3 and 1024 characters, "
                f"got {len(self.value)}"
            )
        
        if not self._url_pattern.match(self.value):
            raise ValueError(f"Invalid FileReference format: '{self.value}'")
    
    def get_bucket(self) -> str | None:
        """Extract bucket name from S3 URL if applicable."""
        if self.value.startswith("s3://"):
            parts = self.value[5:].split("/", 1)
            return parts[0] if parts else None
        return None
    
    def get_key(self) -> str:
        """Extract object key from reference."""
        if self.value.startswith("s3://"):
            parts = self.value[5:].split("/", 1)
            return parts[1] if len(parts) > 1 else ""
        elif self.value.startswith("http"):
            # Remove protocol and host
            parts = self.value.split("/", 3)
            return parts[3] if len(parts) > 3 else ""
        return self.value
    
    def __str__(self) -> str:
        """Return string representation of FileReference."""
        return self.value


@dataclass(frozen=True)
class JobType:
    """
    Represents the type of job/operation.
    
    Business Rules:
    - Predefined set of job types
    - Each type has specific validation and processing rules
    """
    value: str
    
    # Standard job types
    VALIDATION: ClassVar[str] = "validation"
    ENRICHMENT: ClassVar[str] = "enrichment"
    CORRECTION: ClassVar[str] = "correction"
    FULL_PIPELINE: ClassVar[str] = "full_pipeline"
    
    VALID_TYPES: ClassVar[set[str]] = {
        VALIDATION,
        ENRICHMENT,
        CORRECTION,
        FULL_PIPELINE
    }
    
    def __post_init__(self) -> None:
        """Validate JobType."""
        if not isinstance(self.value, str):
            raise ValueError(f"JobType must be a string, got {type(self.value)}")
        
        normalized = self.value.lower()
        object.__setattr__(self, "value", normalized)
        
        if normalized not in self.VALID_TYPES:
            raise ValueError(
                f"JobType must be one of {self.VALID_TYPES}, got '{self.value}'"
            )
    
    def __str__(self) -> str:
        """Return string representation of JobType."""
        return self.value


@dataclass(frozen=True)
class RulesProfileId:
    """
    Represents a rules profile with version.
    
    Business Rules:
    - Format: channel@version (e.g., mercado_livre@1.2.3)
    - Version follows SemVer
    - Immutable for audit trail
    """
    channel: str
    version: str
    _version_pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"^\d+\.\d+\.\d+(-[a-zA-Z0-9\-\.]+)?(\+[a-zA-Z0-9\-\.]+)?$"
    )
    
    def __post_init__(self) -> None:
        """Validate RulesProfileId format."""
        if not isinstance(self.channel, str) or not isinstance(self.version, str):
            raise ValueError("RulesProfileId channel and version must be strings")
        
        if not self._version_pattern.match(self.version):
            raise ValueError(f"Version must follow SemVer format, got '{self.version}'")
    
    @classmethod
    def from_string(cls, value: str) -> RulesProfileId:
        """Parse RulesProfileId from string format."""
        if "@" not in value:
            raise ValueError(f"RulesProfileId must be in format 'channel@version', got '{value}'")
        
        parts = value.rsplit("@", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid RulesProfileId format: '{value}'")
        
        return cls(channel=parts[0], version=parts[1])
    
    def __str__(self) -> str:
        """Return string representation as channel@version."""
        return f"{self.channel}@{self.version}"


@dataclass(frozen=True)
class ProcessingCounters:
    """
    Immutable counters for job processing results.
    
    Business Rules:
    - All counters must be non-negative
    - errors + warnings should not exceed total
    - processed <= total (some items might be skipped)
    """
    total: int = 0
    processed: int = 0
    errors: int = 0
    warnings: int = 0
    
    def __post_init__(self) -> None:
        """Validate counter invariants."""
        if any(v < 0 for v in [self.total, self.processed, self.errors, self.warnings]):
            raise ValueError("All counters must be non-negative")
        
        if self.processed > self.total:
            raise ValueError(f"Processed ({self.processed}) cannot exceed total ({self.total})")
        
        if self.errors > self.processed:
            raise ValueError(f"Errors ({self.errors}) cannot exceed processed ({self.processed})")
    
    def with_incremented_error(self) -> ProcessingCounters:
        """Return new instance with incremented error count."""
        return ProcessingCounters(
            total=self.total,
            processed=self.processed,
            errors=self.errors + 1,
            warnings=self.warnings
        )
    
    def with_incremented_warning(self) -> ProcessingCounters:
        """Return new instance with incremented warning count."""
        return ProcessingCounters(
            total=self.total,
            processed=self.processed,
            errors=self.errors,
            warnings=self.warnings + 1
        )
    
    def with_item_processed(self, had_error: bool = False, had_warning: bool = False) -> ProcessingCounters:
        """Return new instance with an item marked as processed."""
        return ProcessingCounters(
            total=self.total,
            processed=self.processed + 1,
            errors=self.errors + (1 if had_error else 0),
            warnings=self.warnings + (1 if had_warning else 0)
        )
    
    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary for serialization."""
        return {
            "total": self.total,
            "processed": self.processed,
            "errors": self.errors,
            "warnings": self.warnings
        }