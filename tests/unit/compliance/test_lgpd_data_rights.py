"""Test LGPD Article 18 - Data Subject Rights compliance.

LGPD Article 18 establishes the rights of data subjects regarding their personal data.
These tests ensure ValidaHub complies with user rights to:
- Access their data in a portable format
- Request deletion of all personal data
- Have data anonymized irreversibly
- Correct inaccurate personal data
- Request human review of automated decisions
- Object to automated processing

RED phase: These tests will initially fail as the functionality doesn't exist yet.
This is expected in TDD - we define the behavior first, then implement it.
"""

from datetime import datetime
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest

# Note: These imports will fail initially (RED phase) - that's expected in TDD
try:
    from application.compliance import (
        AnonymizeDataUseCase,
        CorrectPersonalDataUseCase,
        DeletePersonalDataUseCase,
        ExportPersonalDataUseCase,
        ObjectToAutomationUseCase,
        RequestHumanReviewUseCase,
    )
    # from application.ports import (
    # # AnonymizationPort,  # TODO: Implement when needed
    # # AuditLogPort,  # TODO: Implement when needed
    # # DataExportPort,  # TODO: Implement when needed
    # # PersonalDataRepository,  # TODO: Implement when needed
    # )
    # from domain.compliance import # AnonymizationResult,  # TODO: Implement when needed # DataSubjectRights,  # TODO: Implement when needed PersonalDataExport
except ImportError:
    # Expected during RED phase - we'll create these classes as we implement
    pass


class TestLGPDDataSubjectRights:
    """Test LGPD Article 18 - Data Subject Rights implementation."""

    @pytest.fixture
    def mock_personal_data_repo(self) -> Mock:
        """Mock repository for personal data operations."""
        return Mock(
            spec=["find_by_tenant_and_user", "delete_all_data", "update_data", "anonymize_data"]
        )

    @pytest.fixture
    def mock_data_export_port(self) -> Mock:
        """Mock port for data export operations."""
        return Mock(spec=["export_to_json", "export_to_csv", "generate_presigned_url"])

    @pytest.fixture
    def mock_anonymization_port(self) -> Mock:
        """Mock port for anonymization operations."""
        return Mock(spec=["anonymize_user_data", "validate_anonymization"])

    @pytest.fixture
    def mock_audit_log_port(self) -> Mock:
        """Mock port for audit logging."""
        return Mock(spec=["log_data_subject_request"])

    @pytest.fixture
    def user_id(self) -> str:
        """Valid user ID for testing."""
        return "user_123"

    @pytest.fixture
    def sample_personal_data(self) -> dict[str, Any]:
        """Sample personal data for testing."""
        return {
            "user_profile": {
                "name": "João Silva",
                "email": "joao.silva@example.com",
                "cpf": "123.456.789-00",
                "birth_date": "1985-06-15",
                "phone": "+55 11 99999-9999",
            },
            "job_history": [
                {
                    "job_id": str(uuid4()),
                    "file_name": "produtos_joao.csv",
                    "processed_at": "2024-01-15T10:30:00Z",
                    "results": {"total": 100, "errors": 2},
                }
            ],
            "audit_trail": [
                {
                    "action": "login",
                    "timestamp": "2024-01-15T09:00:00Z",
                    "ip_address": "192.168.1.100",
                }
            ],
        }


class TestExportPersonalDataInPortableFormat:
    """Test data export in JSON/CSV portable formats per LGPD Article 18."""

    def test_export_personal_data_in_json_format__when_requested_by_user__returns_complete_structured_data(
        self,
        mock_personal_data_repo: Mock,
        mock_data_export_port: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str,
        user_id: str,
        sample_personal_data: dict[str, Any],
    ):
        """
        LGPD Article 18, VI: Right to data portability in structured format.

        When user requests data export in JSON format,
        system must return all personal data in structured, machine-readable format.
        """
        # Arrange
        mock_personal_data_repo.find_by_tenant_and_user.return_value = sample_personal_data
        expected_export = {
            "export_id": str(uuid4()),
            "user_id": user_id,
            "tenant_id": tenant_id,
            "exported_at": datetime.now().isoformat(),
            "data": sample_personal_data,
            "format": "json",
            "schema_version": "1.0",
        }
        mock_data_export_port.export_to_json.return_value = expected_export

        use_case = ExportPersonalDataUseCase(
            personal_data_repo=mock_personal_data_repo,
            data_export_port=mock_data_export_port,
            audit_log_port=mock_audit_log_port,
        )

        # Act
        result = use_case.execute(tenant_id=tenant_id, user_id=user_id, format="json")

        # Assert
        assert result.format == "json"
        assert result.user_id == user_id
        assert result.tenant_id == tenant_id
        assert "data" in result.export_data
        assert result.export_data["data"] == sample_personal_data

        # Verify repository was called correctly
        mock_personal_data_repo.find_by_tenant_and_user.assert_called_once_with(tenant_id, user_id)

        # Verify export port was called correctly
        mock_data_export_port.export_to_json.assert_called_once()

        # Verify audit log was created
        mock_audit_log_port.log_data_subject_request.assert_called_once()
        audit_call = mock_audit_log_port.log_data_subject_request.call_args[1]
        assert audit_call["action"] == "data_export"
        assert audit_call["user_id"] == user_id
        assert audit_call["format"] == "json"

    def test_export_personal_data_in_csv_format__when_requested_by_user__returns_tabular_data(
        self,
        mock_personal_data_repo: Mock,
        mock_data_export_port: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str,
        user_id: str,
        sample_personal_data: dict[str, Any],
    ):
        """
        LGPD Article 18, VI: Right to data portability in CSV format.

        When user requests data export in CSV format,
        system must flatten hierarchical data into tabular format.
        """
        # Arrange
        mock_personal_data_repo.find_by_tenant_and_user.return_value = sample_personal_data
        expected_csv_data = (
            "category,field,value\n"
            "user_profile,name,João Silva\n"
            "user_profile,email,joao.silva@example.com\n"
            "user_profile,cpf,123.456.789-00\n"
            "job_history,total_jobs,1\n"
        )
        mock_data_export_port.export_to_csv.return_value = {
            "export_id": str(uuid4()),
            "format": "csv",
            "data": expected_csv_data,
        }

        use_case = ExportPersonalDataUseCase(
            personal_data_repo=mock_personal_data_repo,
            data_export_port=mock_data_export_port,
            audit_log_port=mock_audit_log_port,
        )

        # Act
        result = use_case.execute(tenant_id=tenant_id, user_id=user_id, format="csv")

        # Assert
        assert result.format == "csv"
        assert "name,João Silva" in result.export_data["data"]
        assert "email,joao.silva@example.com" in result.export_data["data"]

        # Verify CSV format is properly structured
        lines = result.export_data["data"].strip().split("\n")
        assert lines[0] == "category,field,value"  # Header row
        assert len(lines) > 1  # Has data rows

    def test_export_personal_data__when_no_data_exists__returns_empty_export_with_audit_log(
        self,
        mock_personal_data_repo: Mock,
        mock_data_export_port: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str,
        user_id: str,
    ):
        """
        When user has no personal data, export should still succeed with empty structure.
        """
        # Arrange
        mock_personal_data_repo.find_by_tenant_and_user.return_value = {}
        mock_data_export_port.export_to_json.return_value = {
            "export_id": str(uuid4()),
            "user_id": user_id,
            "data": {},
            "format": "json",
        }

        use_case = ExportPersonalDataUseCase(
            personal_data_repo=mock_personal_data_repo,
            data_export_port=mock_data_export_port,
            audit_log_port=mock_audit_log_port,
        )

        # Act
        result = use_case.execute(tenant_id=tenant_id, user_id=user_id, format="json")

        # Assert
        assert result.export_data["data"] == {}
        mock_audit_log_port.log_data_subject_request.assert_called_once()

    def test_export_personal_data__when_invalid_format_requested__raises_validation_error(
        self,
        mock_personal_data_repo: Mock,
        mock_data_export_port: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str,
        user_id: str,
    ):
        """
        Invalid export formats should be rejected with clear error message.
        """
        # Arrange
        use_case = ExportPersonalDataUseCase(
            personal_data_repo=mock_personal_data_repo,
            data_export_port=mock_data_export_port,
            audit_log_port=mock_audit_log_port,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported export format"):
            use_case.execute(tenant_id=tenant_id, user_id=user_id, format="xml")


class TestDeleteAllPersonalDataOnRequest:
    """Test complete data deletion including backups per LGPD Article 18."""

    def test_delete_all_personal_data__when_requested_by_user__removes_data_from_all_systems(
        self, mock_personal_data_repo: Mock, mock_audit_log_port: Mock, tenant_id: str, user_id: str
    ):
        """
        LGPD Article 18, II: Right to deletion (right to be forgotten).

        When user requests data deletion, system must remove ALL personal data
        from all systems including primary storage, caches, backups, and logs.
        """
        # Arrange
        mock_personal_data_repo.delete_all_data.return_value = {
            "deleted_records": 156,
            "affected_tables": ["users", "job_history", "audit_logs", "file_metadata"],
            "backup_purged": True,
            "cache_cleared": True,
            "anonymization_applied": False,  # True deletion, not anonymization
        }

        use_case = DeletePersonalDataUseCase(
            personal_data_repo=mock_personal_data_repo, audit_log_port=mock_audit_log_port
        )

        # Act
        result = use_case.execute(
            tenant_id=tenant_id, user_id=user_id, deletion_reason="user_request"
        )

        # Assert
        assert result.deletion_completed is True
        assert result.deleted_records > 0
        assert "users" in result.affected_systems
        assert result.backup_purged is True
        assert result.cache_cleared is True

        # Verify complete deletion was called
        mock_personal_data_repo.delete_all_data.assert_called_once_with(
            tenant_id=tenant_id, user_id=user_id, include_backups=True, clear_caches=True
        )

        # Verify deletion audit log (this log entry itself should not contain personal data)
        mock_audit_log_port.log_data_subject_request.assert_called_once()
        audit_call = mock_audit_log_port.log_data_subject_request.call_args[1]
        assert audit_call["action"] == "data_deletion"
        assert audit_call["user_id"] == user_id  # Hash or pseudonym, not actual ID
        assert audit_call["deletion_reason"] == "user_request"

    def test_delete_all_personal_data__when_cascading_fails__raises_deletion_error(
        self, mock_personal_data_repo: Mock, mock_audit_log_port: Mock, tenant_id: str, user_id: str
    ):
        """
        If cascading deletion fails, system must not complete partial deletion.
        """
        # Arrange
        mock_personal_data_repo.delete_all_data.side_effect = Exception("Backup deletion failed")

        use_case = DeletePersonalDataUseCase(
            personal_data_repo=mock_personal_data_repo, audit_log_port=mock_audit_log_port
        )

        # Act & Assert
        with pytest.raises(Exception, match="Data deletion failed"):
            use_case.execute(tenant_id=tenant_id, user_id=user_id, deletion_reason="user_request")

        # Verify failure is logged
        mock_audit_log_port.log_data_subject_request.assert_called_once()
        audit_call = mock_audit_log_port.log_data_subject_request.call_args[1]
        assert audit_call["action"] == "data_deletion_failed"


class TestAnonymizeDataIrreversibly:
    """Test irreversible data anonymization per LGPD Article 18."""

    def test_anonymize_data_irreversibly__when_requested__makes_data_non_identifiable(
        self,
        mock_personal_data_repo: Mock,
        mock_anonymization_port: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str,
        user_id: str,
        sample_personal_data: dict[str, Any],
    ):
        """
        LGPD Article 18, III & Article 12: Right to anonymization.

        When user requests anonymization, personal data must be transformed
        so that it cannot be re-identified, even with additional data.
        """
        # Arrange
        anonymized_data = {
            "user_profile": {
                "name": "ANONYMIZED_USER_HASH_ABC123",
                "email": "user.hash.abc123@anonymized.local",
                "cpf": "XXX.XXX.XXX-XX",
                "birth_date": "1985",  # Only year kept for age analysis
                "phone": "ANONYMIZED",
            },
            "job_history": [
                {
                    "job_id": "ANONYMOUS_JOB_001",
                    "file_name": "anonymized_file.csv",
                    "processed_at": "2024-01-15T10:30:00Z",
                    "results": {"total": 100, "errors": 2},  # Aggregated data preserved
                }
            ],
        }

        mock_personal_data_repo.find_by_tenant_and_user.return_value = sample_personal_data
        
        # Mock the AnonymizationResult
        from unittest.mock import Mock
        mock_result = Mock()
        mock_result.success = True
        mock_result.original_records = 5
        mock_result.anonymized_records = 5
        mock_result.techniques_applied = ["hashing", "masking", "generalization", "suppression"]
        mock_result.anonymized_data = anonymized_data
        mock_result.reversible = False  # Critical: must be irreversible
        
        mock_anonymization_port.anonymize_user_data.return_value = mock_result

        use_case = AnonymizeDataUseCase(
            personal_data_repo=mock_personal_data_repo,
            anonymization_port=mock_anonymization_port,
            audit_log_port=mock_audit_log_port,
        )

        # Act
        result = use_case.execute(tenant_id=tenant_id, user_id=user_id)

        # Assert
        assert result.success is True
        assert result.reversible is False  # Critical LGPD requirement
        assert "hashing" in result.techniques_applied
        assert "masking" in result.techniques_applied

        # Verify data is actually anonymized
        anonymized = result.anonymized_data
        assert anonymized["user_profile"]["cpf"] == "XXX.XXX.XXX-XX"
        assert "ANONYMIZED" in anonymized["user_profile"]["name"]
        assert anonymized["user_profile"]["birth_date"] == "1985"  # Generalized

        # Verify statistical data is preserved for analytics
        assert anonymized["job_history"][0]["results"]["total"] == 100

        mock_anonymization_port.anonymize_user_data.assert_called_once()

        # Verify anonymization audit log
        mock_audit_log_port.log_data_subject_request.assert_called_once()
        audit_call = mock_audit_log_port.log_data_subject_request.call_args[1]
        assert audit_call["action"] == "data_anonymization"
        assert audit_call["techniques"] == ["hashing", "masking", "generalization", "suppression"]

    def test_anonymize_data__when_k_anonymity_violated__applies_additional_techniques(
        self,
        mock_personal_data_repo: Mock,
        mock_anonymization_port: Mock,
        mock_audit_log_port: Mock,
        tenant_id: str,
        user_id: str,
    ):
        """
        Anonymization must ensure k-anonymity (k >= 5) to prevent re-identification.
        """
        # Arrange
        # Mock the AnonymizationResult
        from unittest.mock import Mock
        mock_result = Mock()
        mock_result.success = True
        mock_result.original_records = 1
        mock_result.anonymized_records = 1
        mock_result.techniques_applied = ["suppression", "generalization"]  # Added suppression for k-anonymity
        mock_result.k_anonymity_level = 5  # Meets minimum requirement
        mock_result.reversible = False
        
        mock_anonymization_port.anonymize_user_data.return_value = mock_result

        use_case = AnonymizeDataUseCase(
            personal_data_repo=mock_personal_data_repo,
            anonymization_port=mock_anonymization_port,
            audit_log_port=mock_audit_log_port,
        )

        # Act
        result = use_case.execute(tenant_id=tenant_id, user_id=user_id)

        # Assert
        assert result.k_anonymity_level >= 5  # LGPD best practice
        assert "suppression" in result.techniques_applied


class TestCorrectInaccuratePersonalData:
    """Test data correction per LGPD Article 18."""

    def test_correct_inaccurate_personal_data__when_user_provides_corrections__updates_data_accurately(
        self, mock_personal_data_repo: Mock, mock_audit_log_port: Mock, tenant_id: str, user_id: str
    ):
        """
        LGPD Article 18, III: Right to correction of inaccurate data.

        When user identifies inaccurate personal data,
        system must allow correction and maintain audit trail.
        """
        # Arrange
        corrections = {
            "name": "João Carlos Silva",  # Corrected name
            "email": "joao.carlos@newemail.com",  # Updated email
            "phone": "+55 11 98888-8888",  # New phone number
        }

        mock_personal_data_repo.update_data.return_value = {
            "updated": True,
            "fields_changed": 3,
            "previous_values": {
                "name": "João Silva",
                "email": "joao.silva@example.com",
                "phone": "+55 11 99999-9999",
            },
            "new_values": corrections,
        }

        use_case = CorrectPersonalDataUseCase(
            personal_data_repo=mock_personal_data_repo, audit_log_port=mock_audit_log_port
        )

        # Act
        result = use_case.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            corrections=corrections,
            correction_reason="User reported inaccurate information",
        )

        # Assert
        assert result.correction_applied is True
        assert result.fields_changed == 3
        assert result.new_values == corrections

        # Verify correction was applied
        mock_personal_data_repo.update_data.assert_called_once_with(
            tenant_id=tenant_id, user_id=user_id, updates=corrections
        )

        # Verify correction audit trail (must not include old values for privacy)
        mock_audit_log_port.log_data_subject_request.assert_called_once()
        audit_call = mock_audit_log_port.log_data_subject_request.call_args[1]
        assert audit_call["action"] == "data_correction"
        assert audit_call["fields_corrected"] == ["name", "email", "phone"]
        assert audit_call["correction_reason"] == "User reported inaccurate information"
        assert "previous_values" not in audit_call  # Privacy: don't log old values


class TestRequestDataProcessingReview:
    """Test human review request per LGPD Article 18."""

    def test_request_data_processing_review__when_user_objects_to_automated_decision__creates_review_case(
        self, mock_audit_log_port: Mock, tenant_id: str, user_id: str
    ):
        """
        LGPD Article 18, § 2: Right to human review of automated decisions.

        When user objects to automated processing,
        system must allow human review of the decision.
        """
        # Arrange
        review_request = {
            "decision_id": "auto_reject_001",
            "decision_type": "file_validation_rejection",
            "user_objection": "My CSV file was incorrectly rejected as invalid",
            "requested_outcome": "Manual review and approval",
            "supporting_evidence": "File follows all marketplace requirements",
        }

        use_case = RequestHumanReviewUseCase(audit_log_port=mock_audit_log_port)

        # Act
        result = use_case.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            decision_id=review_request["decision_id"],
            objection_reason=review_request["user_objection"],
            requested_outcome=review_request["requested_outcome"],
        )

        # Assert
        assert result.review_case_created is True
        assert result.review_case_id is not None
        assert result.estimated_resolution_days <= 30  # LGPD compliance timeline

        # Verify review request is logged
        mock_audit_log_port.log_data_subject_request.assert_called_once()
        audit_call = mock_audit_log_port.log_data_subject_request.call_args[1]
        assert audit_call["action"] == "human_review_requested"
        assert audit_call["decision_id"] == "auto_reject_001"
        assert audit_call["objection_reason"] == review_request["user_objection"]


class TestObjectToAutomatedDecisions:
    """Test objection to automated processing per LGPD Article 18."""

    def test_object_to_automated_decisions__when_user_opts_out__disables_automated_processing(
        self, mock_personal_data_repo: Mock, mock_audit_log_port: Mock, tenant_id: str, user_id: str
    ):
        """
        LGPD Article 18, § 2: Right to object to automated decision-making.

        When user objects to automated processing,
        system must provide alternative processing methods.
        """
        # Arrange
        objection_details = {
            "processing_types": ["automated_validation", "risk_scoring", "pricing_suggestions"],
            "objection_reason": "Prefer human review for business-critical decisions",
            "alternative_requested": "manual_review",
        }

        mock_personal_data_repo.update_processing_preferences.return_value = {
            "automated_processing_disabled": True,
            "alternative_processing_enabled": True,
            "affected_features": objection_details["processing_types"],
        }

        use_case = ObjectToAutomationUseCase(
            personal_data_repo=mock_personal_data_repo, audit_log_port=mock_audit_log_port
        )

        # Act
        result = use_case.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            processing_types=objection_details["processing_types"],
            objection_reason=objection_details["objection_reason"],
        )

        # Assert
        assert result.objection_applied is True
        assert result.automated_processing_disabled is True
        assert result.alternative_processing_available is True

        # Verify processing preferences were updated
        mock_personal_data_repo.update_processing_preferences.assert_called_once_with(
            tenant_id=tenant_id,
            user_id=user_id,
            disable_automation=True,
            processing_types=objection_details["processing_types"],
        )

        # Verify objection is audited
        mock_audit_log_port.log_data_subject_request.assert_called_once()
        audit_call = mock_audit_log_port.log_data_subject_request.call_args[1]
        assert audit_call["action"] == "automation_objection"
        assert audit_call["processing_types"] == objection_details["processing_types"]
        assert audit_call["objection_reason"] == objection_details["objection_reason"]
