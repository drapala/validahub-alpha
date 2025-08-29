"""Value Objects for ValidaHub domain."""

from dataclasses import dataclass
from typing import ClassVar
import re
import unicodedata
from urllib.parse import urlparse
from uuid import UUID

from src.shared.logging import get_logger
from src.shared.logging.security import SecurityLogger


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
        logger = get_logger("domain.tenant_id")
        security_logger = SecurityLogger("domain.tenant_id")
        
        if not isinstance(self.value, str):
            logger.warning(
                "tenant_id_validation_failed",
                error_type="invalid_type",
                value_type=type(self.value).__name__,
            )
            raise ValueError("Invalid tenant id format")
        
        # Normalize with NFKC Unicode normalization
        normalized = unicodedata.normalize("NFKC", self.value).strip().lower()
        
        # Unicode validation
        if _has_control_or_format(normalized):
            security_logger.injection_attempt(
                injection_type="unicode_control",
                field_name="tenant_id",
            )
            raise ValueError("Invalid tenant id format")
        
        # Regex validation for t_ prefix pattern
        if not self._pattern.match(normalized):
            logger.warning(
                "tenant_id_validation_failed",
                error_type="pattern_mismatch",
                value=normalized,
            )
            raise ValueError("Invalid tenant id format")
        
        # Set normalized value
        object.__setattr__(self, 'value', normalized)
        
        logger.debug(
            "tenant_id_created",
            tenant_id=normalized,
        )
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"TenantId('{self.value}')"


@dataclass(frozen=True)
class IdempotencyKey:
    """Idempotency key with CSV injection protection."""
    value: str
    _pattern: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9\-_.]{8,128}$")
    
    def __post_init__(self) -> None:
        logger = get_logger("domain.idempotency_key")
        security_logger = SecurityLogger("domain.idempotency_key")
        
        if not isinstance(self.value, str):
            logger.warning(
                "idempotency_key_validation_failed",
                error_type="invalid_type",
                value_type=type(self.value).__name__,
            )
            raise ValueError("Invalid idempotency key format")
        
        # CSV Injection: block formulas in exports
        if self.value and self.value[0] in ('=', '+', '-', '@'):
            security_logger.injection_attempt(
                injection_type="csv_formula",
                field_name="idempotency_key",
                first_char=self.value[0],
            )
            raise ValueError("Invalid idempotency key format")
        
        # Pattern validation
        if not self._pattern.match(self.value):
            logger.warning(
                "idempotency_key_validation_failed",
                error_type="pattern_mismatch",
                key_length=len(self.value),
            )
            raise ValueError("Invalid idempotency key format")
        
        logger.debug(
            "idempotency_key_created",
            idempotency_key=self.value,
        )
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"IdempotencyKey('{self.value}')"


# Deny list for dangerous file extensions
_DENY_EXT = {".exe", ".zip", ".bat", ".cmd", ".sh", ".dll", ".com", ".scr"}


@dataclass(frozen=True)
class FileReference:
    """File reference with path traversal and extension validation."""
    value: str
    
    def __post_init__(self) -> None:
        logger = get_logger("domain.file_reference")
        security_logger = SecurityLogger("domain.file_reference")
        
        if not isinstance(self.value, str):
            logger.warning(
                "file_reference_validation_failed",
                error_type="invalid_type",
                value_type=type(self.value).__name__,
            )
            raise ValueError("Invalid file reference")
        
        v = self.value or ""
        
        # Path traversal protection: normalize backslash and check
        v_norm = v.replace("\\", "/")
        if "../" in v_norm:
            security_logger.injection_attempt(
                injection_type="path_traversal",
                field_name="file_reference",
            )
            raise ValueError("Invalid file reference")
        
        # Block dangerous extensions
        low = v.lower()
        for bad_ext in _DENY_EXT:
            if low.endswith(bad_ext):
                security_logger.log_security_event(
                    security_logger.SecurityEventType.DANGEROUS_FILE,
                    "Dangerous file extension blocked",
                    severity="ERROR",
                    extension=bad_ext,
                    file_ref=self.value,
                )
                raise ValueError("Invalid file reference")
        
        logger.debug(
            "file_reference_created",
            file_ref=self.value,
            scheme=self.get_scheme(),
        )
    
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
            return parts[1] if len(parts) > 1 else ''
        if self.value.startswith(('http://', 'https://')):
            p = urlparse(self.value)
            # Remove leading slash from path
            return p.path.lstrip('/')
        # For plain bucket/key format
        parts = self.value.split('/', 1)
        return parts[1] if len(parts) > 1 else self.value
    
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
        logger = get_logger("domain.channel")
        
        if not isinstance(self.value, str):
            logger.warning(
                "channel_validation_failed",
                error_type="invalid_type",
                value_type=type(self.value).__name__,
            )
            raise ValueError("Invalid channel format")
        
        # Normalize
        normalized = self.value.strip().lower()
        
        # Length validation
        if not normalized or len(normalized) < 2 or len(normalized) > 50:
            logger.warning(
                "channel_validation_failed",
                error_type="invalid_length",
                length=len(normalized) if normalized else 0,
            )
            raise ValueError("Invalid channel format")
        
        # Set normalized value
        object.__setattr__(self, 'value', normalized)
        
        logger.debug(
            "channel_created",
            channel=normalized,
            is_known_channel=normalized in self._valid_channels,
        )
    
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
        logger = get_logger("domain.processing_counters")
        
        # All values must be non-negative
        if any(v < 0 for v in [self.total, self.processed, self.errors, self.warnings]):
            logger.warning(
                "processing_counters_validation_failed",
                error_type="negative_values",
                total=self.total,
                processed=self.processed,
                errors=self.errors,
                warnings=self.warnings,
            )
            raise ValueError("Invalid processing counters")
        
        # Processed cannot exceed total
        if self.processed > self.total:
            logger.warning(
                "processing_counters_validation_failed",
                error_type="processed_exceeds_total",
                total=self.total,
                processed=self.processed,
            )
            raise ValueError("Invalid processing counters")
        
        # Errors + warnings cannot exceed processed
        if self.errors + self.warnings > self.processed:
            logger.warning(
                "processing_counters_validation_failed",
                error_type="issues_exceed_processed",
                processed=self.processed,
                errors=self.errors,
                warnings=self.warnings,
            )
            raise ValueError("Invalid processing counters")
        
        logger.debug(
            "processing_counters_created",
            total=self.total,
            processed=self.processed,
            errors=self.errors,
            warnings=self.warnings,
            success_rate=self.get_success_rate(),
        )
    
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