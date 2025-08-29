# 🔒 LGPD Implementation Plan - ValidaHub

## Executive Summary
This document provides a concrete implementation roadmap for achieving full LGPD compliance in ValidaHub, with code examples and architectural decisions aligned with the existing DDD structure.

## Phase 1: Critical Implementations (Week 1)

### 1.1 Create Privacy Domain Module

```python
# src/domain/privacy/__init__.py
"""Privacy and LGPD compliance domain module."""

from .consent import ConsentRecord, LegalBasis, ConsentStatus
from .personal_data import PersonalDataCategory, DataSubjectRequest
from .retention import RetentionPolicy, DataLifecycle
from .anonymization import AnonymizationStrategy, PIIType

__all__ = [
    'ConsentRecord', 'LegalBasis', 'ConsentStatus',
    'PersonalDataCategory', 'DataSubjectRequest',
    'RetentionPolicy', 'DataLifecycle',
    'AnonymizationStrategy', 'PIIType'
]
```

### 1.2 Implement Consent Management

```python
# src/domain/privacy/consent.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4

class LegalBasis(Enum):
    """LGPD Article 7 - Legal bases for data processing."""
    CONSENT = "consent"                          # Art. 7, I
    CONTRACT = "contract"                        # Art. 7, V
    LEGAL_OBLIGATION = "legal_obligation"        # Art. 7, II
    VITAL_INTERESTS = "vital_interests"          # Art. 7, VII
    PUBLIC_POLICY = "public_policy"              # Art. 7, III
    LEGITIMATE_INTERESTS = "legitimate_interests" # Art. 7, IX
    CREDIT_PROTECTION = "credit_protection"      # Art. 7, X
    HEALTH_PROTECTION = "health_protection"      # Art. 7, VIII
    RESEARCH = "research"                        # Art. 7, IV
    RIGHTS_EXERCISE = "rights_exercise"          # Art. 7, VI

class ConsentStatus(Enum):
    """Consent lifecycle status."""
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    PENDING = "pending"

class ProcessingPurpose(Enum):
    """Specific purposes for data processing."""
    CSV_VALIDATION = "csv_validation"
    MARKETPLACE_ANALYTICS = "marketplace_analytics"
    QUALITY_IMPROVEMENT = "quality_improvement"
    CUSTOMER_SUPPORT = "customer_support"
    BILLING = "billing"
    SECURITY_MONITORING = "security_monitoring"
    LEGAL_COMPLIANCE = "legal_compliance"

@dataclass(frozen=True)
class ConsentRecord:
    """
    Immutable consent record for LGPD compliance.
    Tracks user consent for specific data processing purposes.
    """
    id: UUID = field(default_factory=uuid4)
    tenant_id: str = field()
    user_id: str = field()
    seller_id: Optional[str] = None
    
    # Consent details
    purpose: ProcessingPurpose = field()
    legal_basis: LegalBasis = field()
    status: ConsentStatus = field(default=ConsentStatus.GRANTED)
    
    # Temporal data
    granted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    
    # Metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    consent_text_version: str = "1.0"
    parent_consent_id: Optional[UUID] = None  # For minors
    
    # Granular permissions
    data_categories: List[str] = field(default_factory=list)
    processing_activities: List[str] = field(default_factory=list)
    third_party_sharing: bool = False
    international_transfer: bool = False
    automated_decisions: bool = False
    
    def __post_init__(self):
        """Validate consent invariants."""
        if self.legal_basis == LegalBasis.CONSENT and self.status == ConsentStatus.GRANTED:
            if not self.data_categories:
                raise ValueError("Consent must specify data categories")
            if not self.processing_activities:
                raise ValueError("Consent must specify processing activities")
        
        if self.withdrawn_at and self.status != ConsentStatus.WITHDRAWN:
            raise ValueError("Withdrawn consent must have WITHDRAWN status")
        
        if self.expires_at and self.expires_at <= self.granted_at:
            raise ValueError("Expiration must be after grant date")
    
    def is_valid(self) -> bool:
        """Check if consent is currently valid for processing."""
        if self.status != ConsentStatus.GRANTED:
            return False
        
        if self.withdrawn_at:
            return False
        
        if self.expires_at:
            return datetime.now(timezone.utc) < self.expires_at
        
        return True
    
    def withdraw(self) -> 'ConsentRecord':
        """Create new record with consent withdrawn."""
        from dataclasses import replace
        return replace(
            self,
            status=ConsentStatus.WITHDRAWN,
            withdrawn_at=datetime.now(timezone.utc)
        )
    
    def covers_purpose(self, purpose: ProcessingPurpose) -> bool:
        """Check if this consent covers a specific purpose."""
        return self.is_valid() and self.purpose == purpose
    
    def covers_data_category(self, category: str) -> bool:
        """Check if this consent covers a specific data category."""
        return self.is_valid() and category in self.data_categories
```

### 1.3 Implement Personal Data Rights

```python
# src/application/privacy/use_cases/data_subject_rights.py
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID
import json
import csv
from io import StringIO

from src.domain.privacy import DataSubjectRequest, RequestType
from src.application.ports import (
    PersonalDataRepository,
    ConsentRepository,
    AuditLogPort,
    NotificationPort,
    StoragePort
)

@dataclass
class ExportPersonalDataRequest:
    tenant_id: str
    user_id: str
    format: str = "json"  # json, csv, xml
    include_metadata: bool = True

@dataclass
class ExportPersonalDataResponse:
    export_id: UUID
    user_id: str
    format: str
    download_url: str
    expires_at: datetime
    size_bytes: int

class ExportPersonalDataUseCase:
    """LGPD Art. 18, II - Export personal data in portable format."""
    
    def __init__(
        self,
        personal_data_repo: PersonalDataRepository,
        consent_repo: ConsentRepository,
        storage_port: StoragePort,
        audit_log: AuditLogPort
    ):
        self.personal_data_repo = personal_data_repo
        self.consent_repo = consent_repo
        self.storage = storage_port
        self.audit = audit_log
    
    async def execute(self, request: ExportPersonalDataRequest) -> ExportPersonalDataResponse:
        """Export all personal data for a user."""
        
        # Collect all personal data
        user_data = await self._collect_user_data(request.tenant_id, request.user_id)
        
        # Format data based on request
        if request.format == "json":
            formatted_data = self._format_as_json(user_data, request.include_metadata)
        elif request.format == "csv":
            formatted_data = self._format_as_csv(user_data)
        else:
            raise ValueError(f"Unsupported format: {request.format}")
        
        # Store in secure location with expiration
        export_id = UUID()
        file_key = f"exports/{request.tenant_id}/{request.user_id}/{export_id}.{request.format}"
        
        download_url = await self.storage.upload_with_expiration(
            key=file_key,
            content=formatted_data,
            expires_in_hours=24,
            content_type=f"application/{request.format}"
        )
        
        # Audit the export
        await self.audit.log_data_subject_request(
            request_type="DATA_EXPORT",
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            export_id=str(export_id),
            format=request.format
        )
        
        return ExportPersonalDataResponse(
            export_id=export_id,
            user_id=request.user_id,
            format=request.format,
            download_url=download_url,
            expires_at=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0),
            size_bytes=len(formatted_data.encode('utf-8'))
        )
    
    async def _collect_user_data(self, tenant_id: str, user_id: str) -> Dict[str, Any]:
        """Collect all personal data from various sources."""
        data = {
            "export_metadata": {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "tenant_id": tenant_id,
                "user_id": user_id,
                "lgpd_article": "18_II",
                "data_sources": []
            },
            "user_profile": {},
            "job_history": [],
            "consent_records": [],
            "audit_logs": [],
            "processed_files": []
        }
        
        # Get user profile
        profile = await self.personal_data_repo.get_user_profile(tenant_id, user_id)
        if profile:
            data["user_profile"] = profile
            data["export_metadata"]["data_sources"].append("user_profile")
        
        # Get job history
        jobs = await self.personal_data_repo.get_user_jobs(tenant_id, user_id)
        data["job_history"] = jobs
        if jobs:
            data["export_metadata"]["data_sources"].append("job_history")
        
        # Get consent records
        consents = await self.consent_repo.get_user_consents(tenant_id, user_id)
        data["consent_records"] = [self._serialize_consent(c) for c in consents]
        if consents:
            data["export_metadata"]["data_sources"].append("consent_records")
        
        # Get relevant audit logs (last 90 days)
        audit_logs = await self.personal_data_repo.get_user_audit_logs(
            tenant_id, user_id, days=90
        )
        data["audit_logs"] = audit_logs
        if audit_logs:
            data["export_metadata"]["data_sources"].append("audit_logs")
        
        return data
    
    def _format_as_json(self, data: Dict[str, Any], include_metadata: bool) -> str:
        """Format data as JSON with optional metadata."""
        if not include_metadata:
            data.pop("export_metadata", None)
        
        return json.dumps(data, indent=2, default=str, ensure_ascii=False)
    
    def _format_as_csv(self, data: Dict[str, Any]) -> str:
        """Format data as CSV files (returns a ZIP with multiple CSVs)."""
        output = StringIO()
        writer = csv.writer(output)
        
        # User profile CSV
        writer.writerow(["Category", "Field", "Value"])
        for key, value in data.get("user_profile", {}).items():
            writer.writerow(["user_profile", key, value])
        
        # Job history CSV
        writer.writerow([])
        writer.writerow(["Job ID", "Status", "Created At", "File", "Errors", "Warnings"])
        for job in data.get("job_history", []):
            writer.writerow([
                job.get("id"),
                job.get("status"),
                job.get("created_at"),
                job.get("file_ref"),
                job.get("errors", 0),
                job.get("warnings", 0)
            ])
        
        return output.getvalue()
    
    def _serialize_consent(self, consent: ConsentRecord) -> Dict[str, Any]:
        """Serialize consent record for export."""
        return {
            "id": str(consent.id),
            "purpose": consent.purpose.value,
            "legal_basis": consent.legal_basis.value,
            "status": consent.status.value,
            "granted_at": consent.granted_at.isoformat(),
            "expires_at": consent.expires_at.isoformat() if consent.expires_at else None,
            "withdrawn_at": consent.withdrawn_at.isoformat() if consent.withdrawn_at else None,
            "data_categories": consent.data_categories,
            "processing_activities": consent.processing_activities
        }
```

### 1.4 Implement Data Deletion

```python
# src/application/privacy/use_cases/delete_personal_data.py
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any
from uuid import UUID

from src.application.ports import (
    PersonalDataRepository,
    JobRepository,
    StoragePort,
    AuditLogPort,
    NotificationPort,
    BackupPort
)

@dataclass
class DeletePersonalDataRequest:
    tenant_id: str
    user_id: str
    reason: str = "user_request"
    cascade_to_backups: bool = True
    notify_user: bool = True

@dataclass
class DeletionResult:
    deletion_id: UUID
    user_id: str
    deleted_at: datetime
    data_categories_deleted: List[str]
    systems_affected: List[str]
    backup_deletion_scheduled: bool
    notification_sent: bool

class DeletePersonalDataUseCase:
    """LGPD Art. 18, VI - Delete all personal data."""
    
    def __init__(
        self,
        personal_data_repo: PersonalDataRepository,
        job_repo: JobRepository,
        storage: StoragePort,
        backup: BackupPort,
        audit_log: AuditLogPort,
        notification: NotificationPort
    ):
        self.personal_data_repo = personal_data_repo
        self.job_repo = job_repo
        self.storage = storage
        self.backup = backup
        self.audit = audit_log
        self.notification = notification
    
    async def execute(self, request: DeletePersonalDataRequest) -> DeletionResult:
        """Delete all personal data for a user across all systems."""
        
        deletion_id = UUID()
        deleted_categories = []
        affected_systems = []
        
        # 1. Delete from primary database
        await self.personal_data_repo.delete_user_data(
            request.tenant_id, 
            request.user_id
        )
        deleted_categories.append("user_profile")
        affected_systems.append("primary_database")
        
        # 2. Delete/anonymize job history
        jobs = await self.job_repo.find_by_user(
            request.tenant_id,
            request.user_id
        )
        
        for job in jobs:
            # Anonymize job records (keep for analytics but remove PII)
            await self.job_repo.anonymize_job(
                job.id,
                anonymized_user_id=f"deleted_user_{hash(request.user_id) % 1000000}"
            )
        
        if jobs:
            deleted_categories.append("job_history")
            affected_systems.append("job_processing")
        
        # 3. Delete uploaded files from storage
        file_keys = await self.storage.list_user_files(
            request.tenant_id,
            request.user_id
        )
        
        for key in file_keys:
            await self.storage.delete(key)
        
        if file_keys:
            deleted_categories.append("uploaded_files")
            affected_systems.append("object_storage")
        
        # 4. Schedule backup deletion (if requested)
        backup_scheduled = False
        if request.cascade_to_backups:
            await self.backup.schedule_user_data_deletion(
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                deletion_id=deletion_id
            )
            backup_scheduled = True
            affected_systems.append("backup_systems")
        
        # 5. Delete from cache systems
        await self._clear_user_cache(request.tenant_id, request.user_id)
        affected_systems.append("cache_layer")
        
        # 6. Audit the deletion
        await self.audit.log_data_deletion(
            deletion_id=str(deletion_id),
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            reason=request.reason,
            categories_deleted=deleted_categories,
            systems_affected=affected_systems,
            backup_deletion_scheduled=backup_scheduled
        )
        
        # 7. Notify user (if requested)
        notification_sent = False
        if request.notify_user:
            try:
                await self.notification.send_deletion_confirmation(
                    tenant_id=request.tenant_id,
                    user_id=request.user_id,
                    deletion_id=deletion_id,
                    deleted_at=datetime.now(timezone.utc)
                )
                notification_sent = True
            except Exception as e:
                # Log but don't fail the deletion
                await self.audit.log_error(
                    "deletion_notification_failed",
                    error=str(e),
                    deletion_id=str(deletion_id)
                )
        
        return DeletionResult(
            deletion_id=deletion_id,
            user_id=request.user_id,
            deleted_at=datetime.now(timezone.utc),
            data_categories_deleted=deleted_categories,
            systems_affected=affected_systems,
            backup_deletion_scheduled=backup_scheduled,
            notification_sent=notification_sent
        )
    
    async def _clear_user_cache(self, tenant_id: str, user_id: str):
        """Clear all cached data for a user."""
        # Implementation would clear Redis, Memcached, etc.
        pass
```

### 1.5 PII Detection System

```python
# src/domain/privacy/pii_detector.py
import re
from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass
from enum import Enum

class PIIType(Enum):
    """Types of personally identifiable information."""
    CPF = "cpf"
    CNPJ = "cnpj"
    EMAIL = "email"
    PHONE = "phone"
    NAME = "name"
    ADDRESS = "address"
    CREDIT_CARD = "credit_card"
    BANK_ACCOUNT = "bank_account"
    IP_ADDRESS = "ip_address"
    BIRTH_DATE = "birth_date"
    RG = "rg"
    PASSPORT = "passport"

@dataclass
class PIIMatch:
    """Represents a PII match found in content."""
    pii_type: PIIType
    value: str
    position: Tuple[int, int]  # start, end
    confidence: float  # 0.0 to 1.0
    context: str  # Surrounding text for context

class PIIDetector:
    """
    Detects personally identifiable information in text content.
    Optimized for Brazilian data formats.
    """
    
    def __init__(self):
        self.patterns = {
            PIIType.CPF: (
                r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b',
                self._validate_cpf
            ),
            PIIType.CNPJ: (
                r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b',
                self._validate_cnpj
            ),
            PIIType.EMAIL: (
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                None
            ),
            PIIType.PHONE: (
                r'(\+55\s?)?(\(?\d{2}\)?\s?)?(\d{4,5}[-.\s]?\d{4})',
                None
            ),
            PIIType.CREDIT_CARD: (
                r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
                self._validate_credit_card
            ),
            PIIType.IP_ADDRESS: (
                r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
                None
            ),
            PIIType.BIRTH_DATE: (
                r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b',
                None
            ),
            PIIType.RG: (
                r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[0-9X]\b',
                None
            )
        }
        
        # Common Brazilian names for name detection
        self.common_names = self._load_common_names()
    
    def scan_text(self, text: str, pii_types: List[PIIType] = None) -> List[PIIMatch]:
        """
        Scan text for PII.
        
        Args:
            text: Text to scan
            pii_types: Specific PII types to look for (None = all)
            
        Returns:
            List of PII matches found
        """
        matches = []
        
        types_to_scan = pii_types or list(PIIType)
        
        for pii_type in types_to_scan:
            if pii_type not in self.patterns:
                continue
            
            pattern, validator = self.patterns[pii_type]
            
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group()
                
                # Validate if validator exists
                confidence = 1.0
                if validator:
                    is_valid, confidence = validator(value)
                    if not is_valid:
                        continue
                
                # Extract context (50 chars before and after)
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end]
                
                matches.append(PIIMatch(
                    pii_type=pii_type,
                    value=value,
                    position=(match.start(), match.end()),
                    confidence=confidence,
                    context=context
                ))
        
        # Detect names using NLP-like approach
        if PIIType.NAME in types_to_scan:
            matches.extend(self._detect_names(text))
        
        return matches
    
    def scan_csv_headers(self, headers: List[str]) -> Dict[str, PIIType]:
        """
        Detect potential PII columns based on header names.
        
        Args:
            headers: CSV column headers
            
        Returns:
            Mapping of column name to likely PII type
        """
        pii_indicators = {
            PIIType.CPF: ['cpf', 'documento', 'doc'],
            PIIType.EMAIL: ['email', 'e-mail', 'correio'],
            PIIType.PHONE: ['telefone', 'celular', 'fone', 'tel', 'phone'],
            PIIType.NAME: ['nome', 'name', 'cliente', 'usuario', 'vendedor'],
            PIIType.ADDRESS: ['endereco', 'rua', 'logradouro', 'cep', 'cidade'],
            PIIType.BIRTH_DATE: ['nascimento', 'aniversario', 'data_nasc', 'birth'],
            PIIType.RG: ['rg', 'identidade'],
            PIIType.CREDIT_CARD: ['cartao', 'card', 'pagamento']
        }
        
        detected = {}
        
        for header in headers:
            header_lower = header.lower().strip()
            
            for pii_type, indicators in pii_indicators.items():
                for indicator in indicators:
                    if indicator in header_lower:
                        detected[header] = pii_type
                        break
        
        return detected
    
    def _validate_cpf(self, cpf: str) -> Tuple[bool, float]:
        """Validate CPF using check digits."""
        # Remove non-digits
        cpf_digits = re.sub(r'\D', '', cpf)
        
        if len(cpf_digits) != 11:
            return False, 0.0
        
        # Check for known invalid patterns
        if cpf_digits in ['00000000000', '11111111111', '22222222222']:
            return False, 0.0
        
        # Validate check digits
        def calculate_digit(digits, weights):
            total = sum(int(d) * w for d, w in zip(digits, weights))
            remainder = total % 11
            return 0 if remainder < 2 else 11 - remainder
        
        # First check digit
        first_check = calculate_digit(cpf_digits[:9], range(10, 1, -1))
        if first_check != int(cpf_digits[9]):
            return False, 0.0
        
        # Second check digit
        second_check = calculate_digit(cpf_digits[:10], range(11, 1, -1))
        if second_check != int(cpf_digits[10]):
            return False, 0.0
        
        return True, 1.0
    
    def _validate_cnpj(self, cnpj: str) -> Tuple[bool, float]:
        """Validate CNPJ using check digits."""
        # Similar to CPF validation but for CNPJ
        cnpj_digits = re.sub(r'\D', '', cnpj)
        
        if len(cnpj_digits) != 14:
            return False, 0.0
        
        # Simplified validation - would implement full algorithm
        return True, 0.9
    
    def _validate_credit_card(self, card: str) -> Tuple[bool, float]:
        """Validate credit card using Luhn algorithm."""
        digits = re.sub(r'\D', '', card)
        
        if len(digits) < 13 or len(digits) > 19:
            return False, 0.0
        
        # Luhn algorithm
        total = 0
        for i, digit in enumerate(reversed(digits[:-1])):
            n = int(digit)
            if i % 2 == 0:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        
        check_digit = (10 - (total % 10)) % 10
        if check_digit == int(digits[-1]):
            return True, 1.0
        
        return False, 0.0
    
    def _detect_names(self, text: str) -> List[PIIMatch]:
        """Detect potential person names in text."""
        matches = []
        
        # Simple pattern for Brazilian names
        name_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b'
        
        for match in re.finditer(name_pattern, text):
            potential_name = match.group()
            
            # Check if it matches common name patterns
            confidence = self._calculate_name_confidence(potential_name)
            
            if confidence > 0.5:
                matches.append(PIIMatch(
                    pii_type=PIIType.NAME,
                    value=potential_name,
                    position=(match.start(), match.end()),
                    confidence=confidence,
                    context=text[max(0, match.start()-30):min(len(text), match.end()+30)]
                ))
        
        return matches
    
    def _calculate_name_confidence(self, text: str) -> float:
        """Calculate confidence that text is a person's name."""
        # Simplified - would use more sophisticated NLP
        words = text.split()
        
        # Check word count (names usually 2-4 words)
        if len(words) < 2 or len(words) > 4:
            return 0.3
        
        # Check if words are in common names list
        matches = sum(1 for word in words if word.lower() in self.common_names)
        
        return min(1.0, matches / len(words) + 0.3)
    
    def _load_common_names(self) -> Set[str]:
        """Load common Brazilian first and last names."""
        # In production, load from a comprehensive database
        return {
            'silva', 'santos', 'oliveira', 'souza', 'costa',
            'joão', 'maria', 'josé', 'ana', 'pedro',
            'paulo', 'carlos', 'lucas', 'gabriel', 'rafael'
        }

    def suggest_anonymization(self, pii_type: PIIType) -> str:
        """Suggest anonymization strategy for PII type."""
        strategies = {
            PIIType.CPF: "Hash with salt or replace with XXX.XXX.XXX-XX",
            PIIType.EMAIL: "Replace domain with @example.com or hash",
            PIIType.PHONE: "Keep area code, mask rest: (11) XXXX-XXXX",
            PIIType.NAME: "Replace with 'User_[ID]' or use initials",
            PIIType.ADDRESS: "Keep only city/state or first 3 digits of ZIP",
            PIIType.CREDIT_CARD: "Keep first 4 and last 4 digits only",
            PIIType.BIRTH_DATE: "Keep only year or age range",
            PIIType.IP_ADDRESS: "Mask last octet: 192.168.1.XXX"
        }
        return strategies.get(pii_type, "Remove or hash with salt")
```

## Phase 2: API Integration (Week 2)

### 2.1 Privacy API Router

```python
# apps/api/routers/privacy.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.application.privacy.use_cases import (
    ExportPersonalDataUseCase,
    DeletePersonalDataUseCase,
    RecordConsentUseCase,
    WithdrawConsentUseCase,
    GetConsentStatusUseCase
)
from src.domain.privacy import LegalBasis, ProcessingPurpose
from apps.api.dependencies import get_request_context, get_use_case

router = APIRouter(prefix="/privacy", tags=["privacy", "lgpd"])

# Data Subject Rights Endpoints

@router.get("/my-data")
async def get_my_data(
    format: str = "json",
    context: Dict = Depends(get_request_context),
    use_case: ExportPersonalDataUseCase = Depends(get_use_case(ExportPersonalDataUseCase))
):
    """
    LGPD Art. 18, II - Access personal data.
    
    Returns all personal data associated with the authenticated user
    in the requested format (json, csv, xml).
    """
    try:
        result = await use_case.execute(
            tenant_id=context["tenant_id"],
            user_id=context["user_id"],
            format=format
        )
        
        return {
            "export_id": str(result.export_id),
            "download_url": result.download_url,
            "expires_at": result.expires_at.isoformat(),
            "format": result.format,
            "size_bytes": result.size_bytes
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export data: {str(e)}"
        )

@router.delete("/my-data")
async def delete_my_data(
    background_tasks: BackgroundTasks,
    reason: str = "user_request",
    cascade_to_backups: bool = True,
    context: Dict = Depends(get_request_context),
    use_case: DeletePersonalDataUseCase = Depends(get_use_case(DeletePersonalDataUseCase))
):
    """
    LGPD Art. 18, VI - Delete personal data.
    
    Schedules deletion of all personal data across all systems.
    This action is irreversible.
    """
    # Schedule deletion in background to avoid timeout
    background_tasks.add_task(
        use_case.execute,
        tenant_id=context["tenant_id"],
        user_id=context["user_id"],
        reason=reason,
        cascade_to_backups=cascade_to_backups
    )
    
    return {
        "message": "Data deletion has been scheduled",
        "estimated_completion": "24 hours",
        "note": "You will receive confirmation when deletion is complete"
    }

@router.post("/my-data/portability")
async def request_data_portability(
    target_service: str,
    context: Dict = Depends(get_request_context),
    use_case: ExportPersonalDataUseCase = Depends(get_use_case(ExportPersonalDataUseCase))
):
    """
    LGPD Art. 18, V - Data portability to another service provider.
    
    Exports data in a format suitable for import into another service.
    """
    # Implementation would handle specific service formats
    result = await use_case.execute_portability(
        tenant_id=context["tenant_id"],
        user_id=context["user_id"],
        target_service=target_service
    )
    
    return {
        "transfer_id": str(result.transfer_id),
        "target_service": target_service,
        "status": "pending",
        "estimated_completion": result.estimated_completion
    }

# Consent Management Endpoints

@router.post("/consent")
async def grant_consent(
    purpose: ProcessingPurpose,
    legal_basis: LegalBasis = LegalBasis.CONSENT,
    data_categories: List[str] = [],
    expires_in_days: Optional[int] = None,
    context: Dict = Depends(get_request_context),
    use_case: RecordConsentUseCase = Depends(get_use_case(RecordConsentUseCase))
):
    """
    LGPD Art. 8 - Record user consent for data processing.
    
    Records explicit, informed consent for specific processing purposes.
    """
    result = await use_case.execute(
        tenant_id=context["tenant_id"],
        user_id=context["user_id"],
        purpose=purpose,
        legal_basis=legal_basis,
        data_categories=data_categories,
        expires_in_days=expires_in_days,
        ip_address=context.get("ip_address"),
        user_agent=context.get("user_agent")
    )
    
    return {
        "consent_id": str(result.consent_id),
        "purpose": purpose.value,
        "legal_basis": legal_basis.value,
        "status": "granted",
        "expires_at": result.expires_at.isoformat() if result.expires_at else None
    }

@router.delete("/consent/{consent_id}")
async def withdraw_consent(
    consent_id: str,
    context: Dict = Depends(get_request_context),
    use_case: WithdrawConsentUseCase = Depends(get_use_case(WithdrawConsentUseCase))
):
    """
    LGPD Art. 8, §5 - Withdraw consent.
    
    User can withdraw consent at any time. Processing based on this
    consent must stop immediately.
    """
    await use_case.execute(
        tenant_id=context["tenant_id"],
        user_id=context["user_id"],
        consent_id=consent_id
    )
    
    return {
        "consent_id": consent_id,
        "status": "withdrawn",
        "withdrawn_at": datetime.now().isoformat(),
        "message": "Consent has been withdrawn. Related processing will stop."
    }

@router.get("/consent")
async def list_my_consents(
    include_withdrawn: bool = False,
    context: Dict = Depends(get_request_context),
    use_case: GetConsentStatusUseCase = Depends(get_use_case(GetConsentStatusUseCase))
):
    """
    Get all consent records for the authenticated user.
    """
    consents = await use_case.execute(
        tenant_id=context["tenant_id"],
        user_id=context["user_id"],
        include_withdrawn=include_withdrawn
    )
    
    return {
        "consents": [
            {
                "consent_id": str(c.id),
                "purpose": c.purpose.value,
                "legal_basis": c.legal_basis.value,
                "status": c.status.value,
                "granted_at": c.granted_at.isoformat(),
                "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                "data_categories": c.data_categories
            }
            for c in consents
        ]
    }

# Privacy Information Endpoints

@router.get("/policy")
async def get_privacy_policy(
    version: Optional[str] = None,
    language: str = "pt-BR"
):
    """
    LGPD Art. 9 - Provide clear information about data processing.
    
    Returns the privacy policy in the requested language and version.
    """
    # In production, load from database or CMS
    return {
        "version": version or "2.0",
        "language": language,
        "last_updated": "2025-01-01",
        "sections": [
            {
                "title": "Dados Coletados",
                "content": "Coletamos apenas dados necessários para validação de CSV..."
            },
            {
                "title": "Finalidade do Tratamento",
                "content": "Utilizamos seus dados para fornecer serviços de validação..."
            },
            {
                "title": "Seus Direitos",
                "content": "Você tem direito a acessar, corrigir e excluir seus dados..."
            }
        ],
        "contact": {
            "dpo_email": "privacidade@validahub.com",
            "dpo_name": "Data Protection Officer"
        }
    }

@router.get("/data-mapping")
async def get_data_mapping(
    context: Dict = Depends(get_request_context)
):
    """
    LGPD Art. 37 - Record of processing activities.
    
    Returns information about what data is collected and how it's processed.
    """
    return {
        "data_categories": [
            {
                "category": "identification",
                "fields": ["seller_id", "tenant_id"],
                "purpose": "User identification and multi-tenancy",
                "retention": "Until account deletion",
                "legal_basis": "Contract execution"
            },
            {
                "category": "job_data",
                "fields": ["file_name", "processing_results"],
                "purpose": "CSV validation service",
                "retention": "90 days",
                "legal_basis": "Contract execution"
            },
            {
                "category": "audit_logs",
                "fields": ["ip_address", "user_agent", "actions"],
                "purpose": "Security and compliance",
                "retention": "365 days",
                "legal_basis": "Legitimate interest"
            }
        ],
        "third_party_sharing": [],
        "international_transfers": [],
        "automated_decisions": []
    }

# Anonymization Endpoints

@router.post("/anonymize/{job_id}")
async def anonymize_job_data(
    job_id: str,
    context: Dict = Depends(get_request_context)
):
    """
    LGPD Art. 12 - Anonymize specific job data.
    
    Irreversibly anonymizes data while preserving statistical value.
    """
    # Implementation would anonymize specific job data
    return {
        "job_id": job_id,
        "status": "anonymized",
        "anonymized_at": datetime.now().isoformat(),
        "techniques_applied": ["k-anonymity", "pseudonymization", "generalization"]
    }
```

## Phase 3: Database and Infrastructure (Week 3)

### 3.1 Database Migrations

```sql
-- migrations/002_lgpd_compliance.sql

-- Consent management table
CREATE TABLE consent_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    seller_id VARCHAR(100),
    
    -- Consent details
    purpose VARCHAR(50) NOT NULL,
    legal_basis VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'granted',
    
    -- Temporal data
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    withdrawn_at TIMESTAMPTZ,
    
    -- Metadata
    ip_address INET,
    user_agent TEXT,
    consent_text_version VARCHAR(10) NOT NULL DEFAULT '1.0',
    parent_consent_id UUID REFERENCES consent_records(id),
    
    -- Granular permissions (JSONB for flexibility)
    data_categories JSONB NOT NULL DEFAULT '[]',
    processing_activities JSONB NOT NULL DEFAULT '[]',
    third_party_sharing BOOLEAN DEFAULT FALSE,
    international_transfer BOOLEAN DEFAULT FALSE,
    automated_decisions BOOLEAN DEFAULT FALSE,
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT consent_tenant_user_purpose_unique 
        UNIQUE(tenant_id, user_id, purpose, granted_at)
);

CREATE INDEX idx_consent_tenant_user ON consent_records(tenant_id, user_id);
CREATE INDEX idx_consent_status ON consent_records(status) WHERE status = 'granted';
CREATE INDEX idx_consent_expires ON consent_records(expires_at) 
    WHERE expires_at IS NOT NULL;

-- Data retention policies table
CREATE TABLE retention_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_category VARCHAR(50) NOT NULL UNIQUE,
    retention_days INTEGER NOT NULL,
    description TEXT,
    legal_requirement BOOLEAN DEFAULT FALSE,
    auto_delete BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default retention policies
INSERT INTO retention_policies (data_category, retention_days, description, legal_requirement) VALUES
    ('job_data', 90, 'CSV processing job data', false),
    ('audit_logs', 365, 'Security audit logs', true),
    ('consent_records', 1825, 'Consent records (5 years)', true),
    ('deleted_user_logs', 2555, 'Logs of deleted user data (7 years)', true);

-- Data subject requests table
CREATE TABLE data_subject_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    request_type VARCHAR(30) NOT NULL, -- export, delete, rectify, etc.
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    
    -- Request details
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    
    -- Response data
    response_url TEXT,
    response_format VARCHAR(10),
    
    -- Metadata
    ip_address INET,
    user_agent TEXT,
    notes TEXT,
    
    -- Audit
    created_by VARCHAR(100),
    completed_by VARCHAR(100),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dsr_tenant_user ON data_subject_requests(tenant_id, user_id);
CREATE INDEX idx_dsr_status ON data_subject_requests(status);
CREATE INDEX idx_dsr_type ON data_subject_requests(request_type);

-- Anonymization log table
CREATE TABLE anonymization_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(50) NOT NULL,
    original_id VARCHAR(100) NOT NULL,
    anonymized_id VARCHAR(100) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    
    -- Anonymization details
    technique VARCHAR(30) NOT NULL, -- hash, generalization, suppression, etc.
    parameters JSONB,
    reversible BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    anonymized_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    anonymized_by VARCHAR(100),
    reason VARCHAR(100),
    
    -- Prevent re-identification
    CONSTRAINT anonymization_unique UNIQUE(tenant_id, original_id, data_type)
);

CREATE INDEX idx_anon_tenant ON anonymization_log(tenant_id);
CREATE INDEX idx_anon_original ON anonymization_log(original_id);

-- Add LGPD fields to existing jobs table
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS contains_pii BOOLEAN DEFAULT FALSE;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS pii_types JSONB;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS consent_id UUID REFERENCES consent_records(id);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS retention_until TIMESTAMPTZ;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS anonymized_at TIMESTAMPTZ;

-- Add soft delete support to users table (if exists)
ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deletion_reason VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS deletion_request_id UUID REFERENCES data_subject_requests(id);

-- Function to automatically update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to tables
CREATE TRIGGER update_consent_records_updated_at 
    BEFORE UPDATE ON consent_records 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_retention_policies_updated_at 
    BEFORE UPDATE ON retention_policies 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_data_subject_requests_updated_at 
    BEFORE UPDATE ON data_subject_requests 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Row-level security for multi-tenant isolation
ALTER TABLE consent_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_subject_requests ENABLE ROW LEVEL SECURITY;

-- Create policies for tenant isolation
CREATE POLICY tenant_isolation_consent ON consent_records
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_dsr ON data_subject_requests
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant', true));
```

## Phase 4: Monitoring and Compliance Dashboard (Week 4)

### 4.1 Compliance Metrics

```python
# src/application/privacy/metrics.py
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List
from prometheus_client import Counter, Histogram, Gauge

# Prometheus metrics for LGPD compliance
lgpd_consent_total = Counter(
    'lgpd_consent_total',
    'Total consent records created',
    ['tenant_id', 'purpose', 'legal_basis']
)

lgpd_consent_withdrawn = Counter(
    'lgpd_consent_withdrawn_total',
    'Total consent withdrawals',
    ['tenant_id', 'purpose']
)

lgpd_data_requests = Counter(
    'lgpd_data_subject_requests_total',
    'Total data subject requests',
    ['tenant_id', 'request_type', 'status']
)

lgpd_request_duration = Histogram(
    'lgpd_request_duration_seconds',
    'Time to complete data subject requests',
    ['request_type'],
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600]
)

lgpd_pii_detected = Counter(
    'lgpd_pii_detected_total',
    'PII detected in processed files',
    ['tenant_id', 'pii_type']
)

lgpd_data_retention_violations = Gauge(
    'lgpd_data_retention_violations',
    'Number of data items exceeding retention policy',
    ['data_category']
)

@dataclass
class ComplianceMetrics:
    """LGPD compliance metrics for reporting."""
    tenant_id: str
    period_start: datetime
    period_end: datetime
    
    # Consent metrics
    consents_granted: int
    consents_withdrawn: int
    active_consents: int
    
    # Data subject requests
    access_requests: int
    deletion_requests: int
    rectification_requests: int
    portability_requests: int
    average_response_time_hours: float
    
    # Data protection
    pii_incidents: int
    anonymization_operations: int
    retention_violations: int
    
    # Compliance score (0-100)
    compliance_score: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'tenant_id': self.tenant_id,
            'period': {
                'start': self.period_start.isoformat(),
                'end': self.period_end.isoformat()
            },
            'consent': {
                'granted': self.consents_granted,
                'withdrawn': self.consents_withdrawn,
                'active': self.active_consents
            },
            'requests': {
                'access': self.access_requests,
                'deletion': self.deletion_requests,
                'rectification': self.rectification_requests,
                'portability': self.portability_requests,
                'avg_response_hours': self.average_response_time_hours
            },
            'protection': {
                'pii_incidents': self.pii_incidents,
                'anonymizations': self.anonymization_operations,
                'retention_violations': self.retention_violations
            },
            'compliance_score': self.compliance_score
        }
```

## Conclusion

This implementation plan provides:

1. **Complete LGPD compliance framework** aligned with ValidaHub's DDD architecture
2. **Practical code examples** that can be directly implemented
3. **Database schema** for privacy management
4. **API endpoints** for all LGPD data subject rights
5. **PII detection system** for automatic identification of personal data
6. **Consent management** with granular control
7. **Data deletion pipeline** with cascade to all systems
8. **Monitoring and metrics** for compliance tracking

The plan follows a phased approach that prioritizes critical LGPD requirements while building on ValidaHub's existing architecture. Each phase delivers working functionality that moves the system closer to full compliance.

Key success factors:
- Leverage existing DDD structure for clean implementation
- Use TDD approach with existing test suite
- Implement incrementally with clear milestones
- Monitor compliance metrics from day one
- Document all privacy-related decisions

This implementation ensures ValidaHub can:
- Respond to data subject requests within legal timeframes
- Demonstrate compliance to ANPD if audited
- Build trust with customers through transparent privacy practices
- Scale privacy controls as the platform grows