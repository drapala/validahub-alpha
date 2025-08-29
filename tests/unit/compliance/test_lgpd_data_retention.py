"""Test LGPD Articles 15-16 - Data Retention and Lifecycle compliance.

LGPD Articles 15-16 establish requirements for data retention and lifecycle:
- Article 15: Personal data must be kept only as long as necessary for the purpose
- Article 16: Data must be deleted after the retention period ends
- Retention periods must be defined per data category and purpose
- Deletion must include all systems, backups, caches, and logs
- Automatic deletion mechanisms must be implemented
- Users must be informed about retention periods

These tests ensure ValidaHub's data lifecycle management complies with LGPD requirements.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import uuid4
from typing import Dict, List, Optional, Set
from enum import Enum

# Note: These imports will fail initially (RED phase) - that's expected in TDD
try:
    from domain.compliance import (
        DataCategory,
        RetentionPolicy,
        RetentionPeriod,
        DeletionResult,
        DataLifecycleStatus
    )
    from application.compliance import (
        DefineRetentionPolicyUseCase,
        ScheduleAutomaticDeletionUseCase,
        ExecuteDataDeletionUseCase,
        CheckRetentionComplianceUseCase,
        CascadeDeletionUseCase
    )
    from application.ports import (
        DataRetentionRepository,
        BackupManagementPort,
        CacheManagementPort,
        LogManagementPort,
        NotificationPort,
        AuditLogPort
    )
except ImportError:
    # Expected during RED phase
    pass


# Define RetentionPeriod for TDD RED phase
from dataclasses import dataclass

@dataclass
class RetentionPeriod:
    """Data retention period configuration."""
    duration_months: int
    trigger: str
    description: str


class DataCategoryEnum(Enum):
    """Categories of personal data with different retention requirements."""
    USER_PROFILE = "user_profile"  # Name, email, CPF - 5 years after account closure
    JOB_DATA = "job_data"  # File processing history - 2 years after processing
    AUDIT_LOGS = "audit_logs"  # Access logs - 6 months after creation
    MARKETING_DATA = "marketing_data"  # Preferences, communications - Until consent withdrawn
    FINANCIAL_DATA = "financial_data"  # Payment info - 10 years (legal requirement)
    TEMPORARY_FILES = "temporary_files"  # Upload cache - 24 hours after upload
    ANALYTICS_DATA = "analytics_data"  # Aggregated metrics - 3 years after collection


class TestLGPDDataRetention:
    """Test LGPD Articles 15-16 - Data Retention and Lifecycle implementation."""
    
    @pytest.fixture
    def mock_retention_repo(self) -> Mock:
        """Mock repository for retention policy operations."""
        return Mock(spec=[
            'save_retention_policy', 'get_retention_policy', 'find_expired_data',
            'mark_for_deletion', 'update_retention_status', 'get_retention_audit'
        ])
    
    @pytest.fixture
    def mock_backup_port(self) -> Mock:
        """Mock port for backup management operations."""
        return Mock(spec=['delete_from_backups', 'find_backup_locations', 'verify_deletion'])
    
    @pytest.fixture
    def mock_cache_port(self) -> Mock:
        """Mock port for cache management operations."""
        return Mock(spec=['clear_cache_entries', 'find_cached_data', 'invalidate_cache'])
    
    @pytest.fixture
    def mock_log_port(self) -> Mock:
        """Mock port for log management operations."""
        return Mock(spec=['purge_logs', 'anonymize_log_entries', 'archive_logs'])
    
    @pytest.fixture
    def mock_notification_port(self) -> Mock:
        """Mock port for retention notifications."""
        return Mock(spec=['notify_retention_expiry', 'notify_deletion_completed'])
    
    @pytest.fixture
    def mock_audit_log_port(self) -> Mock:
        """Mock port for retention audit logging."""
        return Mock(spec=['log_retention_event'])
    
    @pytest.fixture
    def retention_policies(self) -> Dict[str, RetentionPeriod]:
        """Standard retention policies for different data categories."""
        return {
            DataCategoryEnum.USER_PROFILE.value: RetentionPeriod(
                duration_months=60,  # 5 years
                trigger="account_closure",
                description="User profile data retained 5 years after account closure"
            ),
            DataCategoryEnum.JOB_DATA.value: RetentionPeriod(
                duration_months=24,  # 2 years
                trigger="job_completion",
                description="Job processing data retained 2 years after completion"
            ),
            DataCategoryEnum.AUDIT_LOGS.value: RetentionPeriod(
                duration_months=6,  # 6 months
                trigger="log_creation",
                description="Audit logs retained 6 months after creation"
            ),
            DataCategoryEnum.TEMPORARY_FILES.value: RetentionPeriod(
                duration_hours=24,  # 24 hours
                trigger="upload_completion",
                description="Temporary files deleted 24 hours after upload"
            )
        }


class TestAutomaticDeletionAfterRetentionPeriod:
    """Test automatic deletion of data after retention period expires."""
    
    def test_schedule_automatic_deletion__when_retention_period_defined__creates_deletion_schedule(
        self,
        mock_retention_repo: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str,
        retention_policies: Dict[str, RetentionPeriod]
    ):
        """
        LGPD Article 15: Data must be deleted automatically after retention period ends.
        
        When retention policies are defined, system must schedule automatic deletion.
        """
        # Arrange
        policy = RetentionPolicy(
            policy_id=str(uuid4()),
            tenant_id=tenant_id,
            data_category=DataCategoryEnum.JOB_DATA.value,
            retention_period=retention_policies[DataCategoryEnum.JOB_DATA.value],
            auto_delete=True,
            created_at=datetime.now(timezone.utc)
        )
        
        mock_retention_repo.save_retention_policy.return_value = policy
        
        # Sample data scheduled for deletion
        deletion_candidates = [
            {
                "data_id": "job_001",
                "created_at": datetime.now(timezone.utc) - timedelta(days=730),  # 2+ years old
                "retention_expires_at": datetime.now(timezone.utc) - timedelta(days=1),  # Expired
                "data_category": DataCategoryEnum.JOB_DATA.value
            },
            {
                "data_id": "job_002", 
                "created_at": datetime.now(timezone.utc) - timedelta(days=750),  # 2+ years old
                "retention_expires_at": datetime.now(timezone.utc) - timedelta(days=20),  # Expired
                "data_category": DataCategoryEnum.JOB_DATA.value
            }
        ]
        mock_retention_repo.find_expired_data.return_value = deletion_candidates
        
        use_case = ScheduleAutomaticDeletionUseCase(
            retention_repo=mock_retention_repo,
            audit_log_port=mock_audit_log_port
        )
        
        # Act
        result = use_case.execute(
            tenant_id=tenant_id,
            data_category=DataCategoryEnum.JOB_DATA.value,
            retention_period=retention_policies[DataCategoryEnum.JOB_DATA.value]
        )
        
        # Assert
        assert result.policy_created is True
        assert result.auto_delete_enabled is True
        assert result.scheduled_deletions == 2  # Two expired jobs found
        
        # Verify retention policy was saved
        mock_retention_repo.save_retention_policy.assert_called_once()
        saved_policy = mock_retention_repo.save_retention_policy.call_args[0][0]
        assert saved_policy.data_category == DataCategoryEnum.JOB_DATA.value
        assert saved_policy.auto_delete is True
        assert saved_policy.retention_period.duration_months == 24
        
        # Verify expired data was identified
        mock_retention_repo.find_expired_data.assert_called_once_with(
            tenant_id=tenant_id,
            data_category=DataCategoryEnum.JOB_DATA.value
        )
        
        # Verify scheduling was audited
        mock_audit_log_port.log_retention_event.assert_called_once()
        audit_call = mock_audit_log_port.log_retention_event.call_args[1]
        assert audit_call["event_type"] == "automatic_deletion_scheduled"
        assert audit_call["data_category"] == DataCategoryEnum.JOB_DATA.value
        assert audit_call["scheduled_count"] == 2
    
    def test_execute_automatic_deletion__when_data_expired__deletes_completely(
        self,
        mock_retention_repo: Mock,
        mock_backup_port: Mock,
        mock_cache_port: Mock,
        mock_log_port: Mock,
        mock_notification_port: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str
    ):
        """
        LGPD Article 16: Deletion must be complete and irreversible.
        
        When automatic deletion executes, data must be removed from all systems.
        """
        # Arrange
        expired_data_items = [
            {
                "data_id": "job_001",
                "data_category": DataCategoryEnum.JOB_DATA.value,
                "retention_expires_at": datetime.now(timezone.utc) - timedelta(days=1),
                "locations": ["primary_db", "backup_db", "cache", "audit_logs"]
            }
        ]
        
        mock_retention_repo.find_expired_data.return_value = expired_data_items
        
        # Mock successful deletion from all systems
        mock_backup_port.delete_from_backups.return_value = {"deleted": True, "backup_locations": 3}
        mock_cache_port.clear_cache_entries.return_value = {"cleared": True, "cache_entries": 5}
        mock_log_port.anonymize_log_entries.return_value = {"anonymized": True, "log_entries": 12}
        
        deletion_result = DeletionResult(
            deletion_id=str(uuid4()),
            data_items_deleted=1,
            locations_cleared=["primary_db", "backup_db", "cache", "audit_logs"],
            deletion_completed_at=datetime.now(timezone.utc),
            irreversible=True
        )
        
        use_case = ExecuteDataDeletionUseCase(
            retention_repo=mock_retention_repo,
            backup_port=mock_backup_port,
            cache_port=mock_cache_port,
            log_port=mock_log_port,
            notification_port=mock_notification_port,
            audit_log_port=mock_audit_log_port
        )
        
        # Act
        result = use_case.execute_scheduled_deletion(tenant_id=tenant_id)
        
        # Assert
        assert result.deletion_completed is True
        assert result.items_deleted == 1
        assert result.irreversible is True
        assert "primary_db" in result.locations_cleared
        assert "backup_db" in result.locations_cleared
        assert "cache" in result.locations_cleared
        
        # Verify deletion from all systems
        mock_backup_port.delete_from_backups.assert_called_once()
        mock_cache_port.clear_cache_entries.assert_called_once()
        mock_log_port.anonymize_log_entries.assert_called_once()  # Logs anonymized, not deleted
        
        # Verify completion notification
        mock_notification_port.notify_deletion_completed.assert_called_once()
        
        # Verify deletion audit (this audit entry itself should be retained)
        mock_audit_log_port.log_retention_event.assert_called_once()
        audit_call = mock_audit_log_port.log_retention_event.call_args[1]
        assert audit_call["event_type"] == "automatic_deletion_executed"
        assert audit_call["items_deleted"] == 1
        assert audit_call["irreversible"] is True


class TestCascadeDeletionInAllSystems:
    """Test cascading deletion across all storage systems."""
    
    def test_cascade_deletion__when_user_data_deleted__removes_from_all_related_systems(
        self,
        mock_retention_repo: Mock,
        mock_backup_port: Mock,
        mock_cache_port: Mock,
        mock_log_port: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str,
        user_id: str
    ):
        """
        LGPD Article 16: Deletion must cascade to all systems containing the data.
        
        When user data is deleted, system must identify and delete from all locations.
        """
        # Arrange
        related_data_locations = {
            "primary_database": [
                "users.user_id", "jobs.user_id", "files.uploaded_by"
            ],
            "backup_database": [
                "backup_users.user_id", "backup_jobs.user_id"
            ],
            "cache_systems": [
                f"user_profile:{user_id}", f"user_jobs:{user_id}", f"user_files:{user_id}"
            ],
            "log_files": [
                "access.log", "audit.log", "job_processing.log"
            ],
            "file_storage": [
                f"uploads/{tenant_id}/{user_id}/", f"processed/{tenant_id}/{user_id}/"
            ]
        }
        
        mock_retention_repo.find_related_data.return_value = related_data_locations
        
        # Mock successful cascading deletion
        mock_backup_port.delete_from_backups.return_value = {
            "deleted": True,
            "backup_tables_affected": ["backup_users", "backup_jobs"],
            "records_deleted": 156
        }
        
        mock_cache_port.clear_cache_entries.return_value = {
            "cleared": True, 
            "cache_keys_deleted": 23
        }
        
        mock_log_port.anonymize_log_entries.return_value = {
            "anonymized": True,
            "log_files_processed": 3,
            "entries_anonymized": 1247
        }
        
        use_case = CascadeDeletionUseCase(
            retention_repo=mock_retention_repo,
            backup_port=mock_backup_port,
            cache_port=mock_cache_port,
            log_port=mock_log_port,
            audit_log_port=mock_audit_log_port
        )
        
        # Act
        result = use_case.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            deletion_reason="retention_period_expired"
        )
        
        # Assert
        assert result.cascade_completed is True
        assert result.systems_affected == 5  # primary, backup, cache, logs, files
        assert result.total_records_deleted == 156 + 23 + 1247  # Sum from all systems
        
        # Verify all related data was identified
        mock_retention_repo.find_related_data.assert_called_once_with(
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        # Verify deletion cascaded to all systems
        mock_backup_port.delete_from_backups.assert_called_once()
        mock_cache_port.clear_cache_entries.assert_called_once()
        mock_log_port.anonymize_log_entries.assert_called_once()
        
        # Verify cascading deletion was audited
        mock_audit_log_port.log_retention_event.assert_called_once()
        audit_call = mock_audit_log_port.log_retention_event.call_args[1]
        assert audit_call["event_type"] == "cascade_deletion_completed"
        assert audit_call["systems_affected"] == 5
        assert audit_call["total_records_deleted"] > 0
    
    def test_cascade_deletion__when_backup_deletion_fails__raises_retention_error(
        self,
        mock_retention_repo: Mock,
        mock_backup_port: Mock,
        mock_cache_port: Mock,
        mock_log_port: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str,
        user_id: str
    ):
        """
        If cascading deletion fails in any system, entire operation must fail.
        """
        # Arrange
        mock_retention_repo.find_related_data.return_value = {"backup_database": ["backup_users"]}
        mock_backup_port.delete_from_backups.side_effect = Exception("Backup deletion failed")
        
        use_case = CascadeDeletionUseCase(
            retention_repo=mock_retention_repo,
            backup_port=mock_backup_port,
            cache_port=mock_cache_port,
            log_port=mock_log_port,
            audit_log_port=mock_audit_log_port
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Cascade deletion failed"):
            use_case.execute(
                tenant_id=tenant_id,
                user_id=user_id,
                deletion_reason="retention_period_expired"
            )
        
        # Verify failure was audited
        mock_audit_log_port.log_retention_event.assert_called_once()
        audit_call = mock_audit_log_port.log_retention_event.call_args[1]
        assert audit_call["event_type"] == "cascade_deletion_failed"


class TestSoftDeleteWithAnonymization:
    """Test soft delete with immediate anonymization."""
    
    def test_soft_delete_with_anonymization__when_data_expired__anonymizes_immediately(
        self,
        mock_retention_repo: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str
    ):
        """
        LGPD Article 12: When deletion is not possible, data must be anonymized.
        
        For data that cannot be immediately deleted (e.g., needed for ongoing transactions),
        system must anonymize personal identifiers while retaining necessary business data.
        """
        # Arrange
        soft_delete_candidates = [
            {
                "data_id": "ongoing_job_001",
                "data_category": DataCategoryEnum.JOB_DATA.value,
                "deletion_blocked_reason": "transaction_in_progress",
                "personal_data_fields": ["user_name", "user_email", "file_name"],
                "business_data_fields": ["job_status", "processing_results", "created_at"]
            }
        ]
        
        mock_retention_repo.find_soft_delete_candidates.return_value = soft_delete_candidates
        mock_retention_repo.anonymize_personal_data.return_value = {
            "anonymized": True,
            "fields_anonymized": ["user_name", "user_email", "file_name"],
            "fields_preserved": ["job_status", "processing_results", "created_at"],
            "anonymization_techniques": ["hashing", "masking"]
        }
        
        use_case = ExecuteDataDeletionUseCase(
            retention_repo=mock_retention_repo,
            backup_port=Mock(),
            cache_port=Mock(),
            log_port=Mock(),
            notification_port=Mock(),
            audit_log_port=mock_audit_log_port
        )
        
        # Act
        result = use_case.execute_soft_deletion(
            tenant_id=tenant_id,
            data_category=DataCategoryEnum.JOB_DATA.value
        )
        
        # Assert
        assert result.soft_deletion_completed is True
        assert result.items_anonymized == 1
        assert result.personal_data_removed is True
        assert result.business_data_preserved is True
        
        # Verify anonymization was applied
        mock_retention_repo.anonymize_personal_data.assert_called_once()
        
        # Verify soft deletion was audited
        mock_audit_log_port.log_retention_event.assert_called_once()
        audit_call = mock_audit_log_port.log_retention_event.call_args[1]
        assert audit_call["event_type"] == "soft_deletion_completed"
        assert audit_call["anonymization_applied"] is True


class TestBackupDataAlsoDeleted:
    """Test that backup data is included in deletion process."""
    
    def test_delete_backup_data__when_retention_expires__removes_from_all_backup_locations(
        self,
        mock_retention_repo: Mock,
        mock_backup_port: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str
    ):
        """
        LGPD Article 16: Deletion must include backup systems.
        
        When data retention expires, system must delete from all backup locations.
        """
        # Arrange
        backup_locations = [
            {
                "backup_id": "daily_backup_2024_01_15",
                "location": "s3://backups/daily/2024-01-15/",
                "contains_data": ["user_profiles", "job_history"],
                "backup_date": datetime(2024, 1, 15, 3, 0, 0, tzinfo=timezone.utc)
            },
            {
                "backup_id": "weekly_backup_2024_w03", 
                "location": "s3://backups/weekly/2024-w03/",
                "contains_data": ["user_profiles", "job_history"],
                "backup_date": datetime(2024, 1, 21, 3, 0, 0, tzinfo=timezone.utc)
            },
            {
                "backup_id": "monthly_backup_2024_01",
                "location": "glacier://backups/monthly/2024-01/",
                "contains_data": ["user_profiles", "job_history"],
                "backup_date": datetime(2024, 1, 31, 3, 0, 0, tzinfo=timezone.utc)
            }
        ]
        
        mock_backup_port.find_backup_locations.return_value = backup_locations
        mock_backup_port.delete_from_backups.return_value = {
            "deleted": True,
            "backup_locations_processed": 3,
            "files_deleted": 47,
            "total_size_deleted": "2.3GB"
        }
        
        # Verify deletion was complete
        mock_backup_port.verify_deletion.return_value = {
            "verification_passed": True,
            "locations_verified": 3,
            "data_completely_removed": True
        }
        
        use_case = ExecuteDataDeletionUseCase(
            retention_repo=mock_retention_repo,
            backup_port=mock_backup_port,
            cache_port=Mock(),
            log_port=Mock(),
            notification_port=Mock(),
            audit_log_port=mock_audit_log_port
        )
        
        # Act
        result = use_case.delete_from_backups(
            tenant_id=tenant_id,
            data_identifiers=["user_001", "job_001", "job_002"]
        )
        
        # Assert
        assert result.backup_deletion_completed is True
        assert result.backup_locations_processed == 3
        assert result.verification_passed is True
        assert result.data_completely_removed is True
        
        # Verify backup locations were identified
        mock_backup_port.find_backup_locations.assert_called_once()
        
        # Verify deletion from all backup types
        mock_backup_port.delete_from_backups.assert_called_once()
        delete_call = mock_backup_port.delete_from_backups.call_args[1]
        assert "daily_backup_2024_01_15" in [loc["backup_id"] for loc in delete_call["backup_locations"]]
        assert "weekly_backup_2024_w03" in [loc["backup_id"] for loc in delete_call["backup_locations"]]
        assert "monthly_backup_2024_01" in [loc["backup_id"] for loc in delete_call["backup_locations"]]
        
        # Verify deletion was verified
        mock_backup_port.verify_deletion.assert_called_once()
        
        # Verify backup deletion was audited
        mock_audit_log_port.log_retention_event.assert_called_once()
        audit_call = mock_audit_log_port.log_retention_event.call_args[1]
        assert audit_call["event_type"] == "backup_deletion_completed"
        assert audit_call["backup_locations_processed"] == 3


class TestRetentionPeriodPerDataCategory:
    """Test different retention periods for different data categories."""
    
    def test_define_retention_policies_per_category__when_system_initialized__applies_appropriate_periods(
        self,
        mock_retention_repo: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str,
        retention_policies: Dict[str, RetentionPeriod]
    ):
        """
        LGPD Article 15: Retention periods must be appropriate for each data category.
        
        Different types of personal data require different retention periods based on purpose.
        """
        # Arrange
        category_policies = [
            RetentionPolicy(
                policy_id=str(uuid4()),
                tenant_id=tenant_id,
                data_category=DataCategoryEnum.USER_PROFILE.value,
                retention_period=retention_policies[DataCategoryEnum.USER_PROFILE.value],
                auto_delete=True,
                legal_basis="user_account_management"
            ),
            RetentionPolicy(
                policy_id=str(uuid4()),
                tenant_id=tenant_id,
                data_category=DataCategoryEnum.TEMPORARY_FILES.value,
                retention_period=retention_policies[DataCategoryEnum.TEMPORARY_FILES.value],
                auto_delete=True,
                legal_basis="service_provision"
            ),
            RetentionPolicy(
                policy_id=str(uuid4()),
                tenant_id=tenant_id,
                data_category=DataCategoryEnum.AUDIT_LOGS.value,
                retention_period=retention_policies[DataCategoryEnum.AUDIT_LOGS.value],
                auto_delete=False,  # Audit logs may be anonymized instead of deleted
                legal_basis="legal_compliance"
            )
        ]
        
        mock_retention_repo.save_retention_policy.side_effect = category_policies
        
        use_case = DefineRetentionPolicyUseCase(
            retention_repo=mock_retention_repo,
            audit_log_port=mock_audit_log_port
        )
        
        # Act
        results = []
        for policy in category_policies:
            result = use_case.execute(
                tenant_id=tenant_id,
                data_category=policy.data_category,
                retention_period=policy.retention_period,
                auto_delete=policy.auto_delete,
                legal_basis=policy.legal_basis
            )
            results.append(result)
        
        # Assert
        assert len(results) == 3
        
        # Verify user profile data has long retention (5 years)
        user_profile_result = next(r for r in results if r.data_category == DataCategoryEnum.USER_PROFILE.value)
        assert user_profile_result.retention_months == 60
        assert user_profile_result.auto_delete is True
        
        # Verify temporary files have short retention (24 hours)
        temp_files_result = next(r for r in results if r.data_category == DataCategoryEnum.TEMPORARY_FILES.value)
        assert temp_files_result.retention_hours == 24
        assert temp_files_result.auto_delete is True
        
        # Verify audit logs have medium retention (6 months) but no auto-delete
        audit_logs_result = next(r for r in results if r.data_category == DataCategoryEnum.AUDIT_LOGS.value)
        assert audit_logs_result.retention_months == 6
        assert audit_logs_result.auto_delete is False  # Special handling for compliance
        
        # Verify all policies were saved
        assert mock_retention_repo.save_retention_policy.call_count == 3
        
        # Verify policy definitions were audited
        assert mock_audit_log_port.log_retention_event.call_count == 3


class TestRetentionComplianceMonitoring:
    """Test monitoring and reporting of retention compliance."""
    
    def test_check_retention_compliance__when_policies_active__reports_compliance_status(
        self,
        mock_retention_repo: Mock,
        mock_notification_port: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str
    ):
        """
        System must continuously monitor retention compliance and report status.
        """
        # Arrange
        compliance_data = [
            {
                "data_category": DataCategoryEnum.JOB_DATA.value,
                "total_records": 1500,
                "expired_records": 23,
                "compliance_rate": 98.5,  # 23/1500 expired but not deleted
                "next_expiry_date": datetime.now(timezone.utc) + timedelta(days=30)
            },
            {
                "data_category": DataCategoryEnum.TEMPORARY_FILES.value,
                "total_records": 450,
                "expired_records": 0,
                "compliance_rate": 100.0,  # All expired files deleted automatically
                "next_expiry_date": datetime.now(timezone.utc) + timedelta(hours=12)
            },
            {
                "data_category": DataCategoryEnum.AUDIT_LOGS.value,
                "total_records": 50000,
                "expired_records": 1200,
                "compliance_rate": 97.6,  # Some expired logs not yet anonymized
                "next_expiry_date": datetime.now(timezone.utc) + timedelta(days=15)
            }
        ]
        
        mock_retention_repo.get_compliance_status.return_value = compliance_data
        
        use_case = CheckRetentionComplianceUseCase(
            retention_repo=mock_retention_repo,
            notification_port=mock_notification_port,
            audit_log_port=mock_audit_log_port
        )
        
        # Act
        result = use_case.execute(tenant_id=tenant_id)
        
        # Assert
        assert result.overall_compliance_rate < 100.0  # Some expired data exists
        assert len(result.category_compliance) == 3
        
        # Verify categories with compliance issues are identified
        job_data_compliance = next(c for c in result.category_compliance 
                                 if c["data_category"] == DataCategoryEnum.JOB_DATA.value)
        assert job_data_compliance["expired_records"] == 23
        assert job_data_compliance["compliance_rate"] == 98.5
        
        # Verify compliant categories
        temp_files_compliance = next(c for c in result.category_compliance 
                                   if c["data_category"] == DataCategoryEnum.TEMPORARY_FILES.value)
        assert temp_files_compliance["compliance_rate"] == 100.0
        
        # Verify notifications for non-compliant categories
        mock_notification_port.notify_retention_expiry.assert_called()
        notification_calls = mock_notification_port.notify_retention_expiry.call_args_list
        assert len(notification_calls) == 2  # Job data and audit logs have expired records
        
        # Verify compliance check was audited
        mock_audit_log_port.log_retention_event.assert_called_once()
        audit_call = mock_audit_log_port.log_retention_event.call_args[1]
        assert audit_call["event_type"] == "retention_compliance_check"
        assert audit_call["overall_compliance_rate"] < 100.0
        assert audit_call["categories_with_expired_data"] == 2