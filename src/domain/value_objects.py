"""Value Objects for ValidaHub domain."""

from dataclasses import dataclass
from typing import ClassVar
import re
import unicodedata
from urllib.parse import urlparse
from uuid import UUID


def _has_control_or_format(s: str) -> bool:
    """Check if string contains control or format characters (includes zero-width)."""
    return any(unicodedata.category(ch) in ("Cc", "Cf") for ch in s)


@dataclass(frozen=True)
class JobId:
    """Job identifier value object."""
    value: UUID
    
    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise ValueError("Invalid job id format")
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __repr__(self) -> str:
        return f"JobId('{self.value}')"


@dataclass(frozen=True)
class TenantId:
    """Tenant identifier with normalization and validation."""
    value: str
    _pattern: ClassVar[re.Pattern[str]] = re.compile(r"^t_[a-z0-9_]{1,47}$")
    
    def __post_init__(self) -> None:
        # Import here to avoid circular dependency
        from src.domain.events import (
            ValueObjectValidationEvent,
            SecurityThreatDetectedEvent,
            DomainEventCollector
        )
        
        if not isinstance(self.value, str):
            # Emit validation failed event
            event = ValueObjectValidationEvent.create_validation_failed(
                value_object_type="TenantId",
                error_type="invalid_type",
                error_reason="Invalid tenant id format",
                value_type=type(self.value).__name__
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid tenant id format")
        
        # Normalize with NFKC Unicode normalization
        normalized = unicodedata.normalize("NFKC", self.value).strip().lower()
        
        # Unicode validation
        if _has_control_or_format(normalized):
            # Emit security threat event
            event = SecurityThreatDetectedEvent.create(
                threat_type="unicode_control",
                field_name="tenant_id",
                severity="ERROR",
                injection_type="unicode_control"
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid tenant id format")
        
        # Regex validation for t_ prefix pattern
        if not self._pattern.match(normalized):
            # Emit validation failed event
            event = ValueObjectValidationEvent.create_validation_failed(
                value_object_type="TenantId",
                error_type="pattern_mismatch",
                error_reason="Invalid tenant id format",
                value=normalized
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid tenant id format")
        
        # Set normalized value
        object.__setattr__(self, 'value', normalized)
        
        # Emit successful validation event
        event = ValueObjectValidationEvent.create_validation_success(
            value_object_type="TenantId",
            tenant_id=normalized
        )
        DomainEventCollector.collect_event(event)
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"TenantId('{self.value}')"


@dataclass(frozen=True)
class IdempotencyKey:
    """Idempotency key with CSV injection protection and strict validation.
    
    Security requirements:
    - Length: 16-128 characters
    - Allowed characters: A-Z, a-z, 0-9, hyphen (-), underscore (_)
    - CSV formula injection protection: blocks '=', '+', '-', '@' as first character
    - Neutral error messages that don't expose input values
    """
    value: str
    _pattern: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9\-_]{16,128}$")
    
    def __post_init__(self) -> None:
        # Import here to avoid circular dependency
        from src.domain.events import (
            ValueObjectValidationEvent,
            SecurityThreatDetectedEvent,
            DomainEventCollector
        )
        
        if not isinstance(self.value, str):
            # Emit validation failed event
            event = ValueObjectValidationEvent.create_validation_failed(
                value_object_type="IdempotencyKey",
                error_type="invalid_type",
                error_reason="Invalid idempotency key format",
                value_type=type(self.value).__name__
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid idempotency key format")
        
        # CSV Injection Protection: block formula characters at start
        # This prevents CSV formula injection when keys are exported
        if self.value and self.value[0] in ('=', '+', '-', '@'):
            # Emit security threat event
            event = SecurityThreatDetectedEvent.create(
                threat_type="csv_formula",
                field_name="idempotency_key",
                severity="ERROR",
                injection_type="csv_formula",
                # Note: We log the first character for security monitoring but never in error messages
                first_char=self.value[0]
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid idempotency key format")
        
        # Pattern and length validation (16-128 chars, alphanumeric + hyphen + underscore only)
        if not self._pattern.match(self.value):
            # Emit validation failed event
            event = ValueObjectValidationEvent.create_validation_failed(
                value_object_type="IdempotencyKey",
                error_type="pattern_mismatch",
                error_reason="Invalid idempotency key format",
                # Log length for monitoring but not the actual value
                key_length=len(self.value) if self.value else 0
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid idempotency key format")
        
        # Emit successful validation event
        event = ValueObjectValidationEvent.create_validation_success(
            value_object_type="IdempotencyKey",
            # Only log non-sensitive metadata
            key_length=len(self.value)
        )
        DomainEventCollector.collect_event(event)
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"IdempotencyKey('{self.value}')"


# Deny list for dangerous file extensions
_DENY_EXT = {".exe", ".zip", ".bat", ".cmd", ".sh", ".dll", ".com", ".scr"}
# Allow list for expected text formats
_ALLOW_EXT = {".csv", ".tsv", ".txt"}

_S3_BUCKET_RE = re.compile(r"^(?!\.)[a-z0-9][a-z0-9.-]{1,61}[a-z0-9](?<!\.)$")


@dataclass(frozen=True)
class FileReference:
    """File reference with path traversal and extension validation."""
    value: str
    
    def __post_init__(self) -> None:
        # Import here to avoid circular dependency
        from src.domain.events import (
            ValueObjectValidationEvent,
            SecurityThreatDetectedEvent,
            DomainEventCollector
        )
        
        if not isinstance(self.value, str):
            # Emit validation failed event
            event = ValueObjectValidationEvent.create_validation_failed(
                value_object_type="FileReference",
                error_type="invalid_type",
                error_reason="Invalid file reference",
                value_type=type(self.value).__name__
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid file reference")
        
        v = (self.value or "").strip()
        if not v:
            raise ValueError("Invalid file reference")
        
        # Normalize backslashes to forward slashes and collapse duplicate slashes in path part
        v_norm = v.replace("\\", "/")
        # Quick traversal detection
        if "../" in v_norm:
            # Emit security threat event
            event = SecurityThreatDetectedEvent.create(
                threat_type="path_traversal",
                field_name="file_reference",
                severity="ERROR",
                injection_type="path_traversal"
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid file reference")
        
        # Identify scheme
        parsed = urlparse(v_norm)
        scheme = parsed.scheme
        path = parsed.path
        netloc = parsed.netloc
        
        # Normalize multiple slashes in path
        while '//' in path:
            path = path.replace('//', '/')
        
        # Apply validations by scheme
        if scheme in ("http", "https"):
            if not netloc:
                raise ValueError("Invalid file reference")
            if not path or path == "/":
                raise ValueError("Invalid file reference")
            key = path.lstrip('/')
        elif scheme == "s3":
            # s3://bucket/key
            remainder = v_norm[5:] if v_norm.startswith('s3://') else v_norm
            parts = remainder.split('/', 1)
            bucket = parts[0] if parts and parts[0] else ""
            key = parts[1] if len(parts) > 1 else ""
            # Validate bucket per AWS S3 naming
            if not bucket or not _S3_BUCKET_RE.match(bucket) or bucket.isnumeric() or ".." in bucket or bucket.lower() != bucket:
                raise ValueError("Invalid file reference")
            if not key:
                raise ValueError("Invalid file reference")
            # Normalize key slashes
            while '//' in key:
                key = key.replace('//', '/')
        else:
            # Plain bucket/key format
            parts = v_norm.split('/', 1)
            bucket = parts[0] if parts and parts[0] else ""
            key = parts[1] if len(parts) > 1 else ""
            if not bucket or not key:
                raise ValueError("Invalid file reference")
            # Normalize key slashes
            while '//' in key:
                key = key.replace('//', '/')
        
        low_key = key.lower()
        # Extension checks: deny dangerous and allow only csv/tsv/txt
        for bad_ext in _DENY_EXT:
            if low_key.endswith(bad_ext):
                # Emit security threat event
                event = SecurityThreatDetectedEvent.create(
                    threat_type="dangerous_file",
                    field_name="file_reference",
                    severity="ERROR",
                    extension=bad_ext,
                    file_ref=self.value
                )
                DomainEventCollector.collect_event(event)
                raise ValueError("Invalid file reference")
        
        if not any(low_key.endswith(ext) for ext in _ALLOW_EXT):
            raise ValueError("Invalid file reference")
        
        # Emit successful validation event
        event = ValueObjectValidationEvent.create_validation_success(
            value_object_type="FileReference",
            file_ref=self.value,
            scheme=self.get_scheme()
        )
        DomainEventCollector.collect_event(event)
    
    def get_scheme(self) -> str | None:
        """Extract URL scheme (e.g., 's3', 'https')."""
        p = urlparse(self.value)
        return p.scheme or None
    
    def get_host(self) -> str | None:
        """Extract hostname from URL."""
        p = urlparse(self.value)
        return p.hostname or None
    
    def get_bucket(self) -> str:
        """Extract S3 bucket name from S3 URLs."""
        if self.value.startswith('s3://'):
            parts = self.value[5:].split('/', 1)
            return parts[0] if parts else ''
        # For plain bucket/key format
        parts = self.value.split('/', 1)
        return parts[0] if parts else ''
    
    def get_key(self) -> str:
        """Extract object key from S3 URLs or file path."""
        if self.value.startswith('s3://'):
            parts = self.value[5:].split('/', 1)
            key = parts[1] if len(parts) > 1 else ''
            while '//' in key:
                key = key.replace('//', '/')
            return key
        if self.value.startswith(('http://', 'https://')):
            p = urlparse(self.value)
            # Remove leading slash from path
            key = p.path.lstrip('/')
            while '//' in key:
                key = key.replace('//', '/')
            return key
        # For plain bucket/key format
        parts = self.value.split('/', 1)
        key = parts[1] if len(parts) > 1 else self.value
        while '//' in key:
            key = key.replace('//', '/')
        return key
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"FileReference('{self.value}')"


@dataclass(frozen=True)
class RulesProfileId:
    """Rules profile with channel and semantic versioning."""
    channel: str
    major: int
    minor: int
    patch: int
    
    @classmethod
    def from_string(cls, value: str) -> 'RulesProfileId':
        """Parse from 'channel@major.minor.patch' format."""
        if not value or '@' not in value:
            raise ValueError("Invalid rules profile format")
        
        try:
            channel_part, version_part = value.strip().split('@')
            channel = channel_part.strip().lower()
            
            if not channel:
                raise ValueError("Invalid rules profile format")
            
            version_parts = version_part.strip().split('.')
            if len(version_parts) != 3:
                raise ValueError("Invalid rules profile format")
            
            major = int(version_parts[0])
            minor = int(version_parts[1])
            patch = int(version_parts[2])
            
            if major < 0 or minor < 0 or patch < 0:
                raise ValueError("Invalid rules profile format")
            
            return cls(channel, major, minor, patch)
        except (ValueError, IndexError):
            raise ValueError("Invalid rules profile format")
    
    @property
    def version(self) -> str:
        """Get version string."""
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def __str__(self) -> str:
        return f"{self.channel}@{self.version}"
    
    def __repr__(self) -> str:
        return f"RulesProfileId('{self}')"


@dataclass(frozen=True)
class Channel:
    """Channel (marketplace) identifier with validation."""
    value: str
    _valid_channels: ClassVar[set[str]] = {
        "mercado_livre", "magalu", "americanas", "shopee", "amazon"
    }
    
    def __post_init__(self) -> None:
        # Import here to avoid circular dependency
        from src.domain.events import (
            ValueObjectValidationEvent,
            DomainEventCollector
        )
        
        if not isinstance(self.value, str):
            # Emit validation failed event
            event = ValueObjectValidationEvent.create_validation_failed(
                value_object_type="Channel",
                error_type="invalid_type",
                error_reason="Invalid channel format",
                value_type=type(self.value).__name__
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid channel format")
        
        # Normalize
        normalized = self.value.strip().lower()
        
        # Length validation
        if not normalized or len(normalized) < 2 or len(normalized) > 50:
            # Emit validation failed event
            event = ValueObjectValidationEvent.create_validation_failed(
                value_object_type="Channel",
                error_type="invalid_length",
                error_reason="Invalid channel format",
                length=len(normalized) if normalized else 0
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid channel format")
        
        # Set normalized value
        object.__setattr__(self, 'value', normalized)
        
        # Emit successful validation event
        event = ValueObjectValidationEvent.create_validation_success(
            value_object_type="Channel",
            channel=normalized,
            is_known_channel=normalized in self._valid_channels
        )
        DomainEventCollector.collect_event(event)
    
    def is_known_channel(self) -> bool:
        """Check if this is a known/supported channel."""
        return self.value in self._valid_channels
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"Channel('{self.value}')"


@dataclass(frozen=True)
class ProcessingCounters:
    """Processing counters with invariant validation."""
    total: int
    processed: int
    errors: int
    warnings: int
    
    def __post_init__(self) -> None:
        # Import here to avoid circular dependency
        from src.domain.events import (
            ValueObjectValidationEvent,
            DomainEventCollector
        )
        
        # All values must be non-negative
        if any(v < 0 for v in [self.total, self.processed, self.errors, self.warnings]):
            # Emit validation failed event
            event = ValueObjectValidationEvent.create_validation_failed(
                value_object_type="ProcessingCounters",
                error_type="negative_values",
                error_reason="Invalid processing counters",
                total=self.total,
                processed=self.processed,
                errors=self.errors,
                warnings=self.warnings
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid processing counters")
        
        # Processed cannot exceed total
        if self.processed > self.total:
            # Emit validation failed event
            event = ValueObjectValidationEvent.create_validation_failed(
                value_object_type="ProcessingCounters",
                error_type="processed_exceeds_total",
                error_reason="Invalid processing counters",
                total=self.total,
                processed=self.processed
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid processing counters")
        
        # Errors + warnings cannot exceed processed
        if self.errors + self.warnings > self.processed:
            # Emit validation failed event
            event = ValueObjectValidationEvent.create_validation_failed(
                value_object_type="ProcessingCounters",
                error_type="issues_exceed_processed",
                error_reason="Invalid processing counters",
                processed=self.processed,
                errors=self.errors,
                warnings=self.warnings
            )
            DomainEventCollector.collect_event(event)
            raise ValueError("Invalid processing counters")
        
        # Emit successful validation event
        event = ValueObjectValidationEvent.create_validation_success(
            value_object_type="ProcessingCounters",
            total=self.total,
            processed=self.processed,
            errors=self.errors,
            warnings=self.warnings,
            success_rate=self.get_success_rate()
        )
        DomainEventCollector.collect_event(event)
    
    def get_success_count(self) -> int:
        """Calculate number of successful items."""
        return self.processed - self.errors - self.warnings
    
    def get_success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        if self.processed == 0:
            return 0.0
        return self.get_success_count() / self.processed
    
    def get_error_rate(self) -> float:
        """Calculate error rate (0.0 to 1.0)."""
        if self.processed == 0:
            return 0.0
        return self.errors / self.processed
    
    def get_warning_rate(self) -> float:
        """Calculate warning rate (0.0 to 1.0)."""
        if self.processed == 0:
            return 0.0
        return self.warnings / self.processed
    
    def is_complete(self) -> bool:
        """Check if processing is complete."""
        return self.processed == self.total
    
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return self.errors > 0
    
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return self.warnings > 0
    
    def is_perfect(self) -> bool:
        """Check if processing was perfect (complete with no issues)."""
        return self.is_complete() and not self.has_errors() and not self.has_warnings()
    
    def __str__(self) -> str:
        return f"ProcessingCounters(total={self.total}, processed={self.processed}, errors={self.errors}, warnings={self.warnings})"
    
    def __repr__(self) -> str:
        return self.__str__()