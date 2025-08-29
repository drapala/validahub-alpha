"""Test LGPD Article 37 - Audit Logging compliance.

LGPD Article 37 establishes requirements for demonstrating compliance:
- Data controllers must demonstrate compliance with LGPD requirements
- Complete audit trail of all personal data processing activities
- Logs must include who, when, what, why, and how data was processed
- Audit logs must be immutable and tamper-proof
- Personal data must not be included in audit logs
- Retention period for audit logs must be separate from data retention
- Logs must be available to data protection authorities upon request

These tests ensure ValidaHub's audit logging system complies with LGPD requirements
for accountability and demonstrable compliance.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import uuid4
import json
from typing import Dict, List, Optional, Set, Any
from enum import Enum

# Note: These imports will fail initially (RED phase) - that's expected in TDD
try:
    from domain.compliance import (
        AuditLogEntry,
        AuditEventType, 
        DataProcessingActivity,
        ComplianceReportRequest,
        ImmutableLogRecord
    )
    from application.compliance import (
        LogPersonalDataAccessUseCase,
        CreateImmutableLogUseCase,
        GenerateComplianceReportUseCase,
        ValidateLogIntegrityUseCase,
        QueryAuditTrailUseCase
    )
    from application.ports import (
        AuditLogRepository,
        ImmutableStoragePort,
        EncryptionPort,
        NotificationPort
    )
except ImportError:
    # Expected during RED phase
    pass


class AuditEventTypeEnum(Enum):
    """Types of audit events that must be logged for LGPD compliance."""
    DATA_ACCESS = "data_access"  # Someone accessed personal data
    DATA_PROCESSING = "data_processing"  # Personal data was processed
    DATA_EXPORT = "data_export"  # Data subject requested data export
    DATA_DELETION = "data_deletion"  # Personal data was deleted
    DATA_CORRECTION = "data_correction"  # Personal data was corrected
    CONSENT_GIVEN = "consent_given"  # User provided consent
    CONSENT_WITHDRAWN = "consent_withdrawn"  # User withdrew consent
    ANONYMIZATION_APPLIED = "anonymization_applied"  # Data was anonymized
    RETENTION_POLICY_APPLIED = "retention_policy_applied"  # Retention policy executed
    SECURITY_INCIDENT = "security_incident"  # Security event occurred
    COMPLIANCE_AUDIT = "compliance_audit"  # Compliance audit performed
    DATA_BREACH = "data_breach"  # Personal data breach detected


class TestLGPDAuditLogging:
    """Test LGPD Article 37 - Audit Logging implementation."""
    
    @pytest.fixture
    def mock_audit_log_repo(self) -> Mock:
        """Mock repository for audit log operations."""
        return Mock(spec=[
            'save_log_entry', 'query_logs', 'get_log_by_id', 
            'verify_log_integrity', 'get_logs_by_date_range'
        ])
    
    @pytest.fixture
    def mock_immutable_storage_port(self) -> Mock:
        """Mock port for immutable storage operations."""
        return Mock(spec=['store_immutable_record', 'verify_record_integrity', 'get_record_hash'])
    
    @pytest.fixture
    def mock_encryption_port(self) -> Mock:
        """Mock port for encryption operations."""
        return Mock(spec=['encrypt_sensitive_data', 'hash_personal_identifiers'])
    
    @pytest.fixture 
    def mock_notification_port(self) -> Mock:
        """Mock port for audit-related notifications."""
        return Mock(spec=['notify_audit_anomaly', 'notify_compliance_officer'])
    
    @pytest.fixture
    def request_id(self) -> str:
        """Valid request ID for correlation."""
        return str(uuid4())
    
    @pytest.fixture
    def actor_id(self) -> str:
        """Valid actor ID (anonymized)."""
        return "actor_hash_abc123"


class TestLogAllPersonalDataAccess:
    """Test that all personal data access is logged for accountability."""
    
    def test_log_personal_data_access__when_data_accessed__creates_complete_audit_record(
        self,
        mock_audit_log_repo: Mock,
        mock_immutable_storage_port: Mock,
        mock_encryption_port: Mock,
        tenant_id: str,
        request_id: str,
        actor_id: str
    ):
        """
        LGPD Article 37: All personal data access must be logged for accountability.
        
        When someone accesses personal data, system must create complete audit record
        with who, when, what, why, and how information.
        """
        # Arrange
        access_details = {
            "data_subject_id": "user_hash_def456",  # Anonymized identifier
            "data_categories": ["user_profile", "job_history"],
            "access_reason": "user_requested_data_export",
            "legal_basis": "lgpd_article_18_data_portability",
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0 (compatible; ValidaHub)",
            "accessed_fields": ["name", "email", "job_count"],  # No sensitive values
            "access_method": "api_endpoint",
            "endpoint": "/api/v1/users/export"
        }
        
        expected_log_entry = AuditLogEntry(
            log_id=str(uuid4()),
            tenant_id=tenant_id,
            request_id=request_id,
            event_type=AuditEventTypeEnum.DATA_ACCESS.value,
            actor_id=actor_id,  # Who
            timestamp=datetime.now(timezone.utc),  # When
            data_subject_id=access_details["data_subject_id"],  # Whose data
            activity_description="Personal data accessed for user export request",  # What
            legal_basis=access_details["legal_basis"],  # Why
            technical_details={  # How
                "access_method": access_details["access_method"],
                "endpoint": access_details["endpoint"],
                "data_categories": access_details["data_categories"],
                "ip_address": access_details["ip_address"]
            },
            immutable_hash="sha256_hash_of_log_entry"
        )
        
        mock_audit_log_repo.save_log_entry.return_value = expected_log_entry
        mock_immutable_storage_port.store_immutable_record.return_value = {
            "stored": True,
            "record_hash": "sha256_hash_of_log_entry",
            "storage_location": "immutable://audit_logs/2024/01/15/log_entry.json"
        }
        
        # Hash personal identifiers to prevent personal data in logs
        mock_encryption_port.hash_personal_identifiers.return_value = {
            "data_subject_id": "user_hash_def456",
            "actor_id": actor_id
        }
        
        use_case = LogPersonalDataAccessUseCase(
            audit_log_repo=mock_audit_log_repo,
            immutable_storage_port=mock_immutable_storage_port,
            encryption_port=mock_encryption_port
        )
        
        # Act
        result = use_case.execute(
            tenant_id=tenant_id,
            request_id=request_id,
            actor_id="user_123",  # Original ID, will be hashed
            data_subject_id="user_456",  # Original ID, will be hashed
            data_categories=access_details["data_categories"],
            access_reason=access_details["access_reason"],
            legal_basis=access_details["legal_basis"],
            technical_details={
                "ip_address": access_details["ip_address"],
                "user_agent": access_details["user_agent"],
                "endpoint": access_details["endpoint"]
            }
        )
        
        # Assert
        assert result.audit_logged is True
        assert result.log_id is not None
        assert result.immutable_stored is True
        assert result.record_hash is not None
        
        # Verify complete audit record was created
        mock_audit_log_repo.save_log_entry.assert_called_once()
        saved_entry = mock_audit_log_repo.save_log_entry.call_args[0][0]
        assert saved_entry.event_type == AuditEventTypeEnum.DATA_ACCESS.value
        assert saved_entry.tenant_id == tenant_id
        assert saved_entry.request_id == request_id
        assert saved_entry.legal_basis == access_details["legal_basis"]
        assert saved_entry.data_subject_id == "user_hash_def456"  # Hashed, not original
        
        # Verify technical details include required information
        tech_details = saved_entry.technical_details
        assert tech_details["ip_address"] == access_details["ip_address"]
        assert tech_details["endpoint"] == access_details["endpoint"]
        assert tech_details["data_categories"] == access_details["data_categories"]
        
        # Verify personal identifiers were hashed
        mock_encryption_port.hash_personal_identifiers.assert_called_once()
        
        # Verify immutable storage
        mock_immutable_storage_port.store_immutable_record.assert_called_once()
    
    def test_log_data_processing_activity__when_job_processed__creates_processing_audit_trail(
        self,
        mock_audit_log_repo: Mock,
        mock_immutable_storage_port: Mock,
        mock_encryption_port: Mock,
        tenant_id: str,
        request_id: str,
        job_id: str
    ):
        """
        All personal data processing activities must be logged with complete context.
        """
        # Arrange
        processing_details = {
            "job_id": job_id,
            "processing_purpose": "marketplace_product_validation",
            "data_categories": ["seller_info", "product_data"],
            "processing_operations": ["validation", "enrichment", "format_conversion"],
            "records_processed": 1500,
            "processing_duration_ms": 45000,
            "legal_basis": "legitimate_interest_service_provision"
        }
        
        expected_processing_log = AuditLogEntry(
            log_id=str(uuid4()),
            tenant_id=tenant_id,
            request_id=request_id,
            event_type=AuditEventTypeEnum.DATA_PROCESSING.value,
            actor_id="system_automated_process",
            timestamp=datetime.now(timezone.utc),
            activity_description=f"Personal data processed for {processing_details['processing_purpose']}",
            legal_basis=processing_details["legal_basis"],
            technical_details={
                "job_id": job_id,
                "processing_operations": processing_details["processing_operations"],
                "records_processed": processing_details["records_processed"],
                "duration_ms": processing_details["processing_duration_ms"],
                "data_categories": processing_details["data_categories"]
            }
        )
        
        mock_audit_log_repo.save_log_entry.return_value = expected_processing_log
        mock_immutable_storage_port.store_immutable_record.return_value = {"stored": True}
        
        use_case = LogPersonalDataAccessUseCase(
            audit_log_repo=mock_audit_log_repo,
            immutable_storage_port=mock_immutable_storage_port,
            encryption_port=mock_encryption_port
        )
        
        # Act
        result = use_case.log_processing_activity(
            tenant_id=tenant_id,
            request_id=request_id,
            job_id=job_id,
            processing_purpose=processing_details["processing_purpose"],
            data_categories=processing_details["data_categories"],
            processing_operations=processing_details["processing_operations"],
            legal_basis=processing_details["legal_basis"],
            performance_metrics={
                "records_processed": processing_details["records_processed"],
                "duration_ms": processing_details["processing_duration_ms"]
            }
        )
        
        # Assert
        assert result.audit_logged is True
        
        # Verify processing activity was logged with all required details
        saved_entry = mock_audit_log_repo.save_log_entry.call_args[0][0]
        assert saved_entry.event_type == AuditEventTypeEnum.DATA_PROCESSING.value
        assert saved_entry.technical_details["job_id"] == job_id
        assert saved_entry.technical_details["records_processed"] == 1500
        assert saved_entry.legal_basis == processing_details["legal_basis"]


class TestAuditLogsAreImmutable:
    """Test that audit logs are immutable and tamper-proof."""
    
    def test_create_immutable_log__when_audit_event_occurs__stores_tamper_proof_record(
        self,
        mock_audit_log_repo: Mock,
        mock_immutable_storage_port: Mock,
        mock_encryption_port: Mock,
        tenant_id: str
    ):
        """
        LGPD Article 37: Audit logs must be tamper-proof for regulatory compliance.
        
        When audit events are logged, system must create immutable records
        that cannot be modified or deleted after creation.
        """
        # Arrange
        original_log_data = {
            "event_type": AuditEventTypeEnum.CONSENT_GIVEN.value,
            "tenant_id": tenant_id,
            "timestamp": datetime.now(timezone.utc),
            "actor_id": "user_hash_abc123",
            "activity_description": "User provided consent for data processing",
            "legal_basis": "lgpd_article_8_consent"
        }
        
        # Generate cryptographic hash for tamper detection
        log_content = json.dumps(original_log_data, sort_keys=True, default=str)
        expected_hash = "sha256_" + hashlib.sha256(log_content.encode()).hexdigest()[:32]
        
        mock_immutable_storage_port.store_immutable_record.return_value = {
            "stored": True,
            "record_id": str(uuid4()),
            "content_hash": expected_hash,
            "storage_location": "blockchain://audit_chain/block_12345",
            "immutable": True,
            "tamper_proof": True
        }
        
        mock_immutable_storage_port.verify_record_integrity.return_value = {
            "integrity_verified": True,
            "hash_matches": True,
            "record_unmodified": True
        }
        
        immutable_record = ImmutableLogRecord(
            record_id=str(uuid4()),
            content_hash=expected_hash,
            log_data=original_log_data,
            stored_at=datetime.now(timezone.utc),
            tamper_proof=True
        )
        
        mock_audit_log_repo.save_log_entry.return_value = immutable_record
        
        use_case = CreateImmutableLogUseCase(
            audit_log_repo=mock_audit_log_repo,
            immutable_storage_port=mock_immutable_storage_port,
            encryption_port=mock_encryption_port
        )
        
        # Act
        result = use_case.execute(
            log_data=original_log_data,
            require_immutable_storage=True
        )
        
        # Assert
        assert result.record_created is True
        assert result.tamper_proof is True
        assert result.content_hash == expected_hash
        assert result.immutable_storage_verified is True
        
        # Verify immutable storage was used
        mock_immutable_storage_port.store_immutable_record.assert_called_once()
        store_call = mock_immutable_storage_port.store_immutable_record.call_args[1]
        assert store_call["require_tamper_proof"] is True
        
        # Verify integrity was verified after storage
        mock_immutable_storage_port.verify_record_integrity.assert_called_once()
    
    def test_attempt_to_modify_immutable_log__when_unauthorized_change__detects_tampering(
        self,
        mock_audit_log_repo: Mock,
        mock_immutable_storage_port: Mock,
        mock_encryption_port: Mock,
        mock_notification_port: Mock
    ):
        """
        System must detect any attempts to modify immutable audit logs.
        """
        # Arrange
        log_id = str(uuid4())
        original_hash = "sha256_original_hash_abc123"
        
        # Simulate tampering attempt - hash doesn't match
        mock_immutable_storage_port.verify_record_integrity.return_value = {
            "integrity_verified": False,
            "hash_matches": False,
            "record_unmodified": False,
            "tampering_detected": True,
            "original_hash": original_hash,
            "current_hash": "sha256_modified_hash_def456"  # Different hash = tampering
        }
        
        use_case = ValidateLogIntegrityUseCase(
            audit_log_repo=mock_audit_log_repo,
            immutable_storage_port=mock_immutable_storage_port,
            encryption_port=mock_encryption_port,
            notification_port=mock_notification_port
        )
        
        # Act
        result = use_case.execute(log_id=log_id)
        
        # Assert
        assert result.integrity_verified is False
        assert result.tampering_detected is True
        assert result.original_hash != result.current_hash
        
        # Verify tampering was detected and reported
        mock_notification_port.notify_audit_anomaly.assert_called_once()
        notification_call = mock_notification_port.notify_audit_anomaly.call_args[1]
        assert notification_call["anomaly_type"] == "audit_log_tampering"
        assert notification_call["log_id"] == log_id
        assert notification_call["severity"] == "CRITICAL"


class TestLogsIncludeWhoWhenWhatWhy:
    """Test that audit logs include all required contextual information."""
    
    def test_create_comprehensive_audit_log__when_data_subject_request__includes_all_context(
        self,
        mock_audit_log_repo: Mock,
        mock_immutable_storage_port: Mock,
        mock_encryption_port: Mock,
        tenant_id: str,
        request_id: str
    ):
        """
        LGPD Article 37: Audit logs must include comprehensive context.
        
        Audit logs must answer: WHO did WHAT to WHOSE data, WHEN, WHY, and HOW.
        """
        # Arrange
        comprehensive_context = {
            # WHO
            "actor_id": "user_hash_abc123",
            "actor_role": "data_subject",
            "actor_ip": "192.168.1.100",
            
            # WHAT
            "action": "data_export_requested",
            "data_categories": ["user_profile", "job_history", "consent_records"],
            "operation": "read_personal_data",
            
            # WHOSE data
            "data_subject_id": "user_hash_abc123",  # Same as actor in this case
            
            # WHEN
            "timestamp": datetime.now(timezone.utc),
            "session_id": str(uuid4()),
            
            # WHY 
            "legal_basis": "lgpd_article_18_data_portability",
            "business_purpose": "data_subject_rights_exercise",
            "user_stated_reason": "I want to see all my data for review",
            
            # HOW
            "access_method": "web_interface",
            "endpoint": "/profile/export-data",
            "request_format": "json",
            "authentication_method": "jwt_token",
            "user_agent": "Mozilla/5.0 ValidaHub Web Client"
        }
        
        expected_comprehensive_log = AuditLogEntry(
            log_id=str(uuid4()),
            tenant_id=tenant_id,
            request_id=request_id,
            event_type=AuditEventTypeEnum.DATA_EXPORT.value,
            
            # WHO context
            actor_id=comprehensive_context["actor_id"],
            actor_details={
                "role": comprehensive_context["actor_role"],
                "ip_address": comprehensive_context["actor_ip"],
                "authentication": comprehensive_context["authentication_method"]
            },
            
            # WHAT context
            activity_description="Data subject requested export of all personal data",
            data_categories=comprehensive_context["data_categories"],
            operation_type=comprehensive_context["operation"],
            
            # WHOSE context
            data_subject_id=comprehensive_context["data_subject_id"],
            
            # WHEN context
            timestamp=comprehensive_context["timestamp"],
            session_id=comprehensive_context["session_id"],
            
            # WHY context
            legal_basis=comprehensive_context["legal_basis"],
            business_justification=comprehensive_context["business_purpose"],
            user_intent=comprehensive_context["user_stated_reason"],
            
            # HOW context
            technical_details={
                "access_method": comprehensive_context["access_method"],
                "endpoint": comprehensive_context["endpoint"],
                "request_format": comprehensive_context["request_format"],
                "user_agent": comprehensive_context["user_agent"]
            }
        )
        
        mock_audit_log_repo.save_log_entry.return_value = expected_comprehensive_log
        mock_immutable_storage_port.store_immutable_record.return_value = {"stored": True}
        mock_encryption_port.hash_personal_identifiers.return_value = {
            "actor_id": comprehensive_context["actor_id"],
            "data_subject_id": comprehensive_context["data_subject_id"]
        }
        
        use_case = LogPersonalDataAccessUseCase(
            audit_log_repo=mock_audit_log_repo,
            immutable_storage_port=mock_immutable_storage_port,
            encryption_port=mock_encryption_port
        )
        
        # Act
        result = use_case.execute(
            tenant_id=tenant_id,
            request_id=request_id,
            context=comprehensive_context
        )
        
        # Assert
        assert result.audit_logged is True
        
        # Verify WHO information is logged
        saved_entry = mock_audit_log_repo.save_log_entry.call_args[0][0]
        assert saved_entry.actor_id == comprehensive_context["actor_id"]
        assert saved_entry.actor_details["role"] == comprehensive_context["actor_role"]
        assert saved_entry.actor_details["ip_address"] == comprehensive_context["actor_ip"]
        
        # Verify WHAT information is logged
        assert saved_entry.operation_type == comprehensive_context["operation"]
        assert saved_entry.data_categories == comprehensive_context["data_categories"]
        
        # Verify WHOSE information is logged
        assert saved_entry.data_subject_id == comprehensive_context["data_subject_id"]
        
        # Verify WHEN information is logged
        assert saved_entry.timestamp == comprehensive_context["timestamp"]
        assert saved_entry.session_id == comprehensive_context["session_id"]
        
        # Verify WHY information is logged
        assert saved_entry.legal_basis == comprehensive_context["legal_basis"]
        assert saved_entry.business_justification == comprehensive_context["business_purpose"]
        assert saved_entry.user_intent == comprehensive_context["user_stated_reason"]
        
        # Verify HOW information is logged
        tech_details = saved_entry.technical_details
        assert tech_details["access_method"] == comprehensive_context["access_method"]
        assert tech_details["endpoint"] == comprehensive_context["endpoint"]
        assert tech_details["user_agent"] == comprehensive_context["user_agent"]


class TestNoPersonalDataInLogs:
    """Test that audit logs do not contain personal data."""
    
    def test_sanitize_audit_logs__when_personal_data_present__removes_sensitive_information(
        self,
        mock_audit_log_repo: Mock,
        mock_immutable_storage_port: Mock,
        mock_encryption_port: Mock,
        tenant_id: str
    ):
        """
        LGPD Article 37: Audit logs must not contain personal data themselves.
        
        When logging data processing activities, personal data must be hashed/anonymized
        to prevent the audit logs from becoming another source of personal data exposure.
        """
        # Arrange
        # Unsafe log data containing personal information
        unsafe_log_data = {
            "event_type": AuditEventTypeEnum.DATA_CORRECTION.value,
            "user_name": "João Silva",  # PERSONAL DATA - must be removed
            "user_email": "joao.silva@email.com",  # PERSONAL DATA - must be removed
            "user_cpf": "123.456.789-00",  # PERSONAL DATA - must be removed
            "correction_made": "Changed email from joao.old@email.com to joao.silva@email.com",  # PERSONAL DATA
            "ip_address": "192.168.1.100",  # Could be personal - depends on context
            "request_reason": "User reported email address was incorrect"
        }
        
        # Safe log data after sanitization
        sanitized_log_data = {
            "event_type": AuditEventTypeEnum.DATA_CORRECTION.value,
            "user_id_hash": "user_hash_a1b2c3d4",  # Hash instead of name/email/CPF
            "data_subject_hash": "user_hash_a1b2c3d4",  # Consistent hash
            "correction_type": "email_address_updated",  # Generic description
            "field_changed": "email",  # What field, not the values
            "ip_address_subnet": "192.168.1.0/24",  # Generalized IP
            "request_reason": "user_reported_inaccuracy"  # Generic reason
        }
        
        mock_encryption_port.sanitize_log_data.return_value = {
            "sanitized_data": sanitized_log_data,
            "personal_data_removed": True,
            "hash_replacements": {
                "user_name": "user_hash_a1b2c3d4",
                "user_email": "user_hash_a1b2c3d4", 
                "user_cpf": "user_hash_a1b2c3d4"
            },
            "generalized_fields": ["ip_address", "correction_made"]
        }
        
        sanitized_log_entry = AuditLogEntry(
            log_id=str(uuid4()),
            tenant_id=tenant_id,
            event_type=AuditEventTypeEnum.DATA_CORRECTION.value,
            actor_id=sanitized_log_data["user_id_hash"],
            data_subject_id=sanitized_log_data["data_subject_hash"],
            timestamp=datetime.now(timezone.utc),
            activity_description="User corrected inaccurate personal data",
            technical_details={
                "correction_type": sanitized_log_data["correction_type"],
                "field_changed": sanitized_log_data["field_changed"],
                "ip_subnet": sanitized_log_data["ip_address_subnet"]
            }
        )
        
        mock_audit_log_repo.save_log_entry.return_value = sanitized_log_entry
        mock_immutable_storage_port.store_immutable_record.return_value = {"stored": True}
        
        use_case = LogPersonalDataAccessUseCase(
            audit_log_repo=mock_audit_log_repo,
            immutable_storage_port=mock_immutable_storage_port,
            encryption_port=mock_encryption_port
        )
        
        # Act
        result = use_case.execute(
            tenant_id=tenant_id,
            unsafe_log_data=unsafe_log_data,
            require_sanitization=True
        )
        
        # Assert
        assert result.audit_logged is True
        assert result.personal_data_sanitized is True
        
        # Verify personal data was sanitized
        mock_encryption_port.sanitize_log_data.assert_called_once_with(unsafe_log_data)
        
        # Verify sanitized data was saved (no personal information)
        saved_entry = mock_audit_log_repo.save_log_entry.call_args[0][0]
        saved_dict = saved_entry.__dict__
        
        # Assert no personal data in saved log
        assert "João Silva" not in str(saved_dict)
        assert "joao.silva@email.com" not in str(saved_dict)
        assert "123.456.789-00" not in str(saved_dict)
        assert "192.168.1.100" not in str(saved_dict)  # Should be generalized
        
        # Assert necessary information is preserved in safe form
        assert saved_entry.actor_id == "user_hash_a1b2c3d4"  # Consistent hash
        assert saved_entry.technical_details["field_changed"] == "email"
        assert saved_entry.technical_details["correction_type"] == "email_address_updated"
    
    def test_reject_unsanitized_logs__when_personal_data_detected__prevents_logging(
        self,
        mock_audit_log_repo: Mock,
        mock_immutable_storage_port: Mock,
        mock_encryption_port: Mock,
        tenant_id: str
    ):
        """
        System must reject audit logs containing personal data if sanitization fails.
        """
        # Arrange
        log_with_personal_data = {
            "event_type": "data_access",
            "user_email": "user@email.com",  # Personal data
            "details": "User accessed their profile data"
        }
        
        # Sanitization fails to remove personal data
        mock_encryption_port.sanitize_log_data.return_value = {
            "sanitized_data": log_with_personal_data,  # Still contains personal data
            "personal_data_removed": False,
            "sanitization_failed": True,
            "remaining_personal_data": ["user_email"]
        }
        
        use_case = LogPersonalDataAccessUseCase(
            audit_log_repo=mock_audit_log_repo,
            immutable_storage_port=mock_immutable_storage_port,
            encryption_port=mock_encryption_port
        )
        
        # Act & Assert
        with pytest.raises(ValueError, match="Personal data found in audit log"):
            use_case.execute(
                tenant_id=tenant_id,
                unsafe_log_data=log_with_personal_data,
                require_sanitization=True,
                strict_validation=True
            )
        
        # Verify log was not saved due to personal data
        mock_audit_log_repo.save_log_entry.assert_not_called()


class TestLogRetentionSeparateFromData:
    """Test that audit log retention is separate from personal data retention."""
    
    def test_audit_log_retention_policy__when_personal_data_deleted__preserves_audit_logs(
        self,
        mock_audit_log_repo: Mock,
        tenant_id: str
    ):
        """
        LGPD Article 37: Audit logs must be retained longer than personal data.
        
        When personal data is deleted, audit logs about that data must be preserved
        for regulatory compliance and accountability purposes.
        """
        # Arrange
        personal_data_deletion_date = datetime.now(timezone.utc)
        audit_log_retention_years = 7  # Regulatory requirement
        expected_audit_retention_until = personal_data_deletion_date + timedelta(days=365 * audit_log_retention_years)
        
        # Audit logs related to deleted personal data
        audit_logs_after_deletion = [
            {
                "log_id": str(uuid4()),
                "event_type": AuditEventTypeEnum.DATA_DELETION.value,
                "data_subject_hash": "user_hash_abc123",  # No personal data, just hash
                "timestamp": personal_data_deletion_date,
                "retention_until": expected_audit_retention_until,
                "deletion_reason": "user_request_right_to_erasure",
                "legal_basis": "lgpd_article_18_data_deletion"
            },
            {
                "log_id": str(uuid4()),
                "event_type": AuditEventTypeEnum.DATA_ACCESS.value,
                "data_subject_hash": "user_hash_abc123",
                "timestamp": personal_data_deletion_date - timedelta(days=30),
                "retention_until": expected_audit_retention_until,
                "activity": "data_export_before_deletion"
            }
        ]
        
        mock_audit_log_repo.get_logs_by_data_subject.return_value = audit_logs_after_deletion
        mock_audit_log_repo.update_retention_policy.return_value = {
            "updated": True,
            "logs_affected": 2,
            "retention_period_years": audit_log_retention_years
        }
        
        use_case = QueryAuditTrailUseCase(
            audit_log_repo=mock_audit_log_repo
        )
        
        # Act
        result = use_case.set_audit_log_retention_after_data_deletion(
            tenant_id=tenant_id,
            data_subject_hash="user_hash_abc123",
            personal_data_deletion_date=personal_data_deletion_date,
            audit_retention_years=audit_log_retention_years
        )
        
        # Assert
        assert result.retention_policy_updated is True
        assert result.audit_logs_preserved == 2
        assert result.audit_retention_until == expected_audit_retention_until
        
        # Verify audit logs are retained beyond personal data deletion
        retention_duration = result.audit_retention_until - personal_data_deletion_date
        assert retention_duration.days >= (365 * audit_log_retention_years)
        
        # Verify retention policy was updated
        mock_audit_log_repo.update_retention_policy.assert_called_once_with(
            data_subject_hash="user_hash_abc123",
            retention_until=expected_audit_retention_until
        )


class TestGenerateComplianceReport:
    """Test generation of compliance reports from audit logs."""
    
    def test_generate_compliance_report__when_requested_by_authority__provides_comprehensive_audit_trail(
        self,
        mock_audit_log_repo: Mock,
        mock_immutable_storage_port: Mock,
        tenant_id: str
    ):
        """
        LGPD Article 37: Data controllers must demonstrate compliance to authorities.
        
        System must be able to generate comprehensive compliance reports
        from audit logs for regulatory authorities upon request.
        """
        # Arrange
        report_request = ComplianceReportRequest(
            tenant_id=tenant_id,
            report_period_start=datetime.now(timezone.utc) - timedelta(days=365),
            report_period_end=datetime.now(timezone.utc),
            requested_by="data_protection_authority",
            report_purpose="compliance_audit",
            focus_areas=["data_subject_rights", "consent_management", "data_retention"]
        )
        
        comprehensive_audit_data = [
            # Data subject rights exercises
            {
                "event_category": "data_subject_rights",
                "total_requests": 156,
                "export_requests": 89,
                "deletion_requests": 45,
                "correction_requests": 22,
                "average_response_time_hours": 18.5,
                "legal_compliance_rate": 100.0
            },
            # Consent management
            {
                "event_category": "consent_management", 
                "consents_given": 1247,
                "consents_withdrawn": 89,
                "consent_updates": 203,
                "processing_stopped_on_withdrawal": 89,
                "consent_compliance_rate": 100.0
            },
            # Data retention
            {
                "event_category": "data_retention",
                "retention_policies_applied": 45,
                "automatic_deletions": 234,
                "manual_deletions": 45,
                "retention_compliance_rate": 98.7,
                "overdue_deletions": 3
            }
        ]
        
        mock_audit_log_repo.generate_compliance_report.return_value = {
            "report_id": str(uuid4()),
            "report_generated_at": datetime.now(timezone.utc),
            "report_period": f"{report_request.report_period_start.date()} to {report_request.report_period_end.date()}",
            "total_audit_events": 2847,
            "compliance_summary": comprehensive_audit_data,
            "regulatory_compliance_score": 99.2,
            "identified_issues": [
                {
                    "issue_type": "delayed_deletion",
                    "affected_records": 3,
                    "severity": "low",
                    "remediation_plan": "Scheduled for deletion within 48 hours"
                }
            ]
        }
        
        mock_immutable_storage_port.verify_audit_trail_integrity.return_value = {
            "integrity_verified": True,
            "total_logs_verified": 2847,
            "tampered_logs": 0,
            "verification_timestamp": datetime.now(timezone.utc)
        }
        
        use_case = GenerateComplianceReportUseCase(
            audit_log_repo=mock_audit_log_repo,
            immutable_storage_port=mock_immutable_storage_port
        )
        
        # Act
        result = use_case.execute(report_request=report_request)
        
        # Assert
        assert result.report_generated is True
        assert result.regulatory_compliance_score > 99.0
        assert result.total_audit_events == 2847
        assert result.audit_trail_integrity_verified is True
        
        # Verify comprehensive compliance data
        compliance_data = result.compliance_summary
        assert len(compliance_data) == 3  # Three focus areas
        
        # Verify data subject rights compliance
        dsr_data = next(c for c in compliance_data if c["event_category"] == "data_subject_rights")
        assert dsr_data["total_requests"] == 156
        assert dsr_data["legal_compliance_rate"] == 100.0
        assert dsr_data["average_response_time_hours"] < 24  # Within LGPD timeframe
        
        # Verify consent management compliance  
        consent_data = next(c for c in compliance_data if c["event_category"] == "consent_management")
        assert consent_data["processing_stopped_on_withdrawal"] == consent_data["consents_withdrawn"]
        
        # Verify issues are identified and tracked
        assert len(result.identified_issues) == 1
        assert result.identified_issues[0]["issue_type"] == "delayed_deletion"
        
        # Verify audit trail integrity was checked
        mock_immutable_storage_port.verify_audit_trail_integrity.assert_called_once()
        
        # Verify comprehensive report was generated
        mock_audit_log_repo.generate_compliance_report.assert_called_once_with(
            tenant_id=tenant_id,
            period_start=report_request.report_period_start,
            period_end=report_request.report_period_end,
            focus_areas=report_request.focus_areas
        )