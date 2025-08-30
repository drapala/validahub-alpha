"""Test LGPD Article 12 - Data Anonymization compliance.

LGPD Article 12 defines anonymization requirements:
- Anonymous data is not considered personal data under LGPD
- Anonymization must be irreversible (data cannot be re-identified)
- Anonymization techniques must prevent re-identification even with additional data
- K-anonymity, L-diversity, and T-closeness principles should be applied
- Common techniques: hashing, masking, generalization, suppression, noise addition

These tests ensure ValidaHub's anonymization techniques comply with LGPD standards
and provide irreversible anonymization that maintains data utility for analytics.
"""

import hashlib
import re
from enum import Enum
from typing import Any
from unittest.mock import Mock

import pytest

# Note: These imports will fail initially (RED phase) - that's expected in TDD
try:
    from application.compliance import (
        ApplyAnonymizationTechniqueUseCase,
        GeneralizeDataUseCase,
        HashPersonalDataUseCase,
        MaskSensitiveDataUseCase,
        SuppressUniqueAttributesUseCase,
        ValidateKAnonymityUseCase,
    )
    # from application.ports import # AnonymizationPort,  # TODO: Implement when needed # AuditLogPort,  # TODO: Implement when needed DataAnalysisPort
    # from domain.compliance import (
    # # AnonymizationResult,  # TODO: Implement when needed
    # # AnonymizationTechnique,  # TODO: Implement when needed
    # # AnonymizedDataset,  # TODO: Implement when needed
    # # KAnonymityLevel,  # TODO: Implement when needed
    # # PersonalDataField,  # TODO: Implement when needed
    # )
except ImportError:
    # Expected during RED phase
    pass


class AnonymizationTechniqueEnum(Enum):
    """Anonymization techniques supported by the system."""

    HASHING = "hashing"  # SHA-256 with salt for deterministic but irreversible anonymization
    MASKING = "masking"  # Replace sensitive parts with X or * characters
    GENERALIZATION = "generalization"  # Replace specific values with broader categories
    SUPPRESSION = "suppression"  # Remove unique identifying attributes entirely
    NOISE_ADDITION = "noise_addition"  # Add statistical noise to numerical data
    PSEUDONYMIZATION = "pseudonymization"  # Replace with consistent pseudonyms


class PersonalDataFieldEnum(Enum):
    """Types of personal data fields requiring anonymization."""

    NAME = "name"
    EMAIL = "email"
    CPF = "cpf"
    PHONE = "phone"
    BIRTH_DATE = "birth_date"
    ADDRESS = "address"
    IP_ADDRESS = "ip_address"
    USER_ID = "user_id"
    FILE_NAME = "file_name"


@pytest.mark.skip(reason="LGPD compliance functionality not yet implemented. TODO: Implement after core features")
class TestLGPDAnonymization:
    """Test LGPD Article 12 - Data Anonymization implementation."""

    @pytest.fixture
    def mock_anonymization_port(self) -> Mock:
        """Mock port for anonymization operations."""
        return Mock(
            spec=[
                "hash_field",
                "mask_field",
                "generalize_field",
                "suppress_field",
                "add_noise",
                "validate_anonymization",
                "check_re_identification_risk",
            ]
        )

    @pytest.fixture
    def mock_data_analysis_port(self) -> Mock:
        """Mock port for data analysis and validation."""
        return Mock(spec=["calculate_k_anonymity", "check_l_diversity", "validate_t_closeness"])

    @pytest.fixture
    def mock_audit_log_port(self) -> Mock:
        """Mock port for anonymization audit logging."""
        return Mock(spec=["log_anonymization_event"])

    @pytest.fixture
    def sample_personal_data(self) -> list[dict[str, Any]]:
        """Sample personal data for anonymization testing."""
        return [
            {
                "user_id": "user_001",
                "name": "João Silva",
                "email": "joao.silva@email.com",
                "cpf": "123.456.789-00",
                "birth_date": "1985-06-15",
                "phone": "+55 11 99999-9999",
                "address": "Rua A, 123, São Paulo, SP",
                "ip_address": "192.168.1.100",
            },
            {
                "user_id": "user_002",
                "name": "Maria Santos",
                "email": "maria.santos@email.com",
                "cpf": "987.654.321-00",
                "birth_date": "1990-12-20",
                "phone": "+55 11 88888-8888",
                "address": "Rua B, 456, São Paulo, SP",
                "ip_address": "192.168.1.101",
            },
            {
                "user_id": "user_003",
                "name": "Pedro Costa",
                "email": "pedro.costa@email.com",
                "cpf": "555.666.777-88",
                "birth_date": "1975-03-10",
                "phone": "+55 11 77777-7777",
                "address": "Rua C, 789, Rio de Janeiro, RJ",
                "ip_address": "10.0.0.50",
            },
        ]

    @pytest.fixture
    def anonymization_salt(self) -> str:
        """Salt for deterministic hashing."""
        return "validahub_salt_2024_lgpd_compliance"


@pytest.mark.skip(reason="LGPD compliance functionality not yet implemented. TODO: Implement after core features")
class TestHashEmailConsistently:
    """Test deterministic but irreversible email hashing."""

    def test_hash_email_consistently__when_same_email_provided__returns_same_hash(
        self, mock_anonymization_port: Mock, mock_audit_log_port: Mock, anonymization_salt: str
    ):
        """
        LGPD Article 12: Anonymization must be consistent for analytical purposes.

        When hashing emails, same email must always produce same hash
        but must be irreversible (cannot recover original email).
        """
        # Arrange
        email = "joao.silva@email.com"
        expected_hash = hashlib.sha256(f"{email}{anonymization_salt}".encode()).hexdigest()

        mock_anonymization_port.hash_field.return_value = {
            "original_value": email,
            "anonymized_value": f"hash_{expected_hash[:16]}",  # Truncated hash for readability
            "technique": AnonymizationTechniqueEnum.HASHING.value,
            "irreversible": True,
            "deterministic": True,
        }

        use_case = HashPersonalDataUseCase(
            anonymization_port=mock_anonymization_port, audit_log_port=mock_audit_log_port
        )

        # Act - Hash same email multiple times
        result1 = use_case.execute(
            field_type=PersonalDataFieldEnum.EMAIL.value, value=email, salt=anonymization_salt
        )

        result2 = use_case.execute(
            field_type=PersonalDataFieldEnum.EMAIL.value, value=email, salt=anonymization_salt
        )

        # Assert
        assert result1.anonymized_value == result2.anonymized_value  # Consistency
        assert result1.irreversible is True  # Cannot recover original
        assert result1.deterministic is True  # Same input = same output
        assert result1.anonymized_value != email  # Actually anonymized
        assert result1.anonymized_value.startswith("hash_")  # Proper format

        # Verify hashing was applied correctly
        mock_anonymization_port.hash_field.assert_called()
        hash_calls = mock_anonymization_port.hash_field.call_args_list
        assert len(hash_calls) == 2  # Called twice
        assert hash_calls[0] == hash_calls[1]  # Same parameters

        # Verify hashing was audited
        assert mock_audit_log_port.log_anonymization_event.call_count == 2
        audit_call = mock_audit_log_port.log_anonymization_event.call_args[1]
        assert audit_call["technique"] == AnonymizationTechniqueEnum.HASHING.value
        assert audit_call["field_type"] == PersonalDataFieldEnum.EMAIL.value
        assert audit_call["irreversible"] is True

    def test_hash_different_emails__when_different_inputs__returns_different_hashes(
        self, mock_anonymization_port: Mock, mock_audit_log_port: Mock, anonymization_salt: str
    ):
        """
        Different emails must produce different hashes to maintain data utility.
        """
        # Arrange
        email1 = "joao@email.com"
        email2 = "maria@email.com"

        hash1 = hashlib.sha256(f"{email1}{anonymization_salt}".encode()).hexdigest()
        hash2 = hashlib.sha256(f"{email2}{anonymization_salt}".encode()).hexdigest()

        mock_anonymization_port.hash_field.side_effect = [
            {"anonymized_value": f"hash_{hash1[:16]}", "irreversible": True, "deterministic": True},
            {"anonymized_value": f"hash_{hash2[:16]}", "irreversible": True, "deterministic": True},
        ]

        use_case = HashPersonalDataUseCase(
            anonymization_port=mock_anonymization_port, audit_log_port=mock_audit_log_port
        )

        # Act
        result1 = use_case.execute(PersonalDataFieldEnum.EMAIL.value, email1, anonymization_salt)
        result2 = use_case.execute(PersonalDataFieldEnum.EMAIL.value, email2, anonymization_salt)

        # Assert
        assert result1.anonymized_value != result2.anonymized_value  # Different outputs
        assert result1.anonymized_value != email1  # Anonymized
        assert result2.anonymized_value != email2  # Anonymized
        assert both_results_irreversible(result1, result2)

    def test_hash_email__when_salt_missing__raises_anonymization_error(
        self, mock_anonymization_port: Mock, mock_audit_log_port: Mock
    ):
        """
        Hashing without salt creates security vulnerability and must be rejected.
        """
        # Arrange
        use_case = HashPersonalDataUseCase(
            anonymization_port=mock_anonymization_port, audit_log_port=mock_audit_log_port
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Salt required for secure hashing"):
            use_case.execute(
                field_type=PersonalDataFieldEnum.EMAIL.value,
                value="test@email.com",
                salt="",  # Empty salt not allowed
            )


@pytest.mark.skip(reason="LGPD compliance functionality not yet implemented. TODO: Implement after core features")
class TestMaskCPFFormatPreserved:
    """Test CPF masking while preserving format."""

    def test_mask_cpf_format_preserved__when_cpf_provided__returns_masked_cpf_with_format(
        self, mock_anonymization_port: Mock, mock_audit_log_port: Mock
    ):
        """
        LGPD Article 12: Masking must preserve data utility while anonymizing.

        When masking CPF, format must be preserved (XXX.XXX.XXX-XX)
        to maintain data type and validation logic.
        """
        # Arrange
        cpf = "123.456.789-00"
        masked_cpf = "XXX.XXX.XXX-XX"

        mock_anonymization_port.mask_field.return_value = {
            "original_value": cpf,
            "anonymized_value": masked_cpf,
            "technique": AnonymizationTechniqueEnum.MASKING.value,
            "format_preserved": True,
            "data_type_preserved": True,
        }

        use_case = MaskSensitiveDataUseCase(
            anonymization_port=mock_anonymization_port, audit_log_port=mock_audit_log_port
        )

        # Act
        result = use_case.execute(
            field_type=PersonalDataFieldEnum.CPF.value, value=cpf, mask_pattern="XXX.XXX.XXX-XX"
        )

        # Assert
        assert result.anonymized_value == "XXX.XXX.XXX-XX"
        assert result.format_preserved is True
        assert result.data_type_preserved is True
        assert len(result.anonymized_value) == len(cpf)  # Same length
        assert result.anonymized_value.count(".") == cpf.count(".")  # Same dots
        assert result.anonymized_value.count("-") == cpf.count("-")  # Same dash

        # Verify CPF pattern is maintained
        cpf_pattern = r"^XXX\.XXX\.XXX-XX$"
        assert re.match(cpf_pattern, result.anonymized_value)

        # Verify masking was applied correctly
        mock_anonymization_port.mask_field.assert_called_once_with(
            field_type=PersonalDataFieldEnum.CPF.value, value=cpf, mask_pattern="XXX.XXX.XXX-XX"
        )

        # Verify masking was audited
        mock_audit_log_port.log_anonymization_event.assert_called_once()
        audit_call = mock_audit_log_port.log_anonymization_event.call_args[1]
        assert audit_call["technique"] == AnonymizationTechniqueEnum.MASKING.value
        assert audit_call["format_preserved"] is True

    def test_mask_phone_format_preserved__when_phone_provided__returns_masked_phone_with_format(
        self, mock_anonymization_port: Mock, mock_audit_log_port: Mock
    ):
        """
        Phone numbers must be masked while preserving Brazilian phone format.
        """
        # Arrange
        phone = "+55 11 99999-9999"
        masked_phone = "+55 XX XXXXX-XXXX"

        mock_anonymization_port.mask_field.return_value = {
            "original_value": phone,
            "anonymized_value": masked_phone,
            "technique": AnonymizationTechniqueEnum.MASKING.value,
            "format_preserved": True,
            "country_code_preserved": True,
        }

        use_case = MaskSensitiveDataUseCase(
            anonymization_port=mock_anonymization_port, audit_log_port=mock_audit_log_port
        )

        # Act
        result = use_case.execute(
            field_type=PersonalDataFieldEnum.PHONE.value,
            value=phone,
            mask_pattern="+55 XX XXXXX-XXXX",
        )

        # Assert
        assert result.anonymized_value == "+55 XX XXXXX-XXXX"
        assert result.anonymized_value.startswith("+55")  # Country code preserved
        assert len(result.anonymized_value) == len(phone)  # Same length


@pytest.mark.skip(reason="LGPD compliance functionality not yet implemented. TODO: Implement after core features")
class TestPseudonymizeUserId:
    """Test user ID pseudonymization with random UUIDs."""

    def test_pseudonymize_user_id__when_user_id_provided__returns_consistent_pseudonym(
        self, mock_anonymization_port: Mock, mock_audit_log_port: Mock, anonymization_salt: str
    ):
        """
        LGPD Article 12: Pseudonymization creates consistent identifiers.

        User IDs must be replaced with pseudonyms that are:
        - Consistent (same user = same pseudonym)
        - Non-reversible (cannot recover original ID)
        - Valid UUIDs for system compatibility
        """
        # Arrange
        user_id = "user_123"
        # Generate deterministic pseudonym based on original ID + salt
        pseudonym_source = f"{user_id}_{anonymization_salt}"
        pseudonym_hash = hashlib.sha256(pseudonym_source.encode()).hexdigest()
        # Create UUID-like pseudonym from hash
        pseudonym = f"pseudo-{pseudonym_hash[:8]}-{pseudonym_hash[8:12]}-{pseudonym_hash[12:16]}-{pseudonym_hash[16:20]}"

        mock_anonymization_port.pseudonymize_field.return_value = {
            "original_value": user_id,
            "anonymized_value": pseudonym,
            "technique": AnonymizationTechniqueEnum.PSEUDONYMIZATION.value,
            "consistent": True,
            "reversible": False,
            "format_valid": True,
        }

        use_case = ApplyAnonymizationTechniqueUseCase(
            anonymization_port=mock_anonymization_port, audit_log_port=mock_audit_log_port
        )

        # Act
        result = use_case.execute(
            field_type=PersonalDataFieldEnum.USER_ID.value,
            value=user_id,
            technique=AnonymizationTechniqueEnum.PSEUDONYMIZATION.value,
            parameters={"salt": anonymization_salt},
        )

        # Assert
        assert result.anonymized_value != user_id  # Actually pseudonymized
        assert result.anonymized_value.startswith("pseudo-")  # Proper format
        assert result.consistent is True  # Same user = same pseudonym
        assert result.reversible is False  # Cannot recover original
        assert (
            len(result.anonymized_value.replace("-", "").replace("pseudo", "")) == 32
        )  # Hash length

        # Verify pseudonymization was applied
        mock_anonymization_port.pseudonymize_field.assert_called_once()

        # Verify pseudonymization was audited
        mock_audit_log_port.log_anonymization_event.assert_called_once()
        audit_call = mock_audit_log_port.log_anonymization_event.call_args[1]
        assert audit_call["technique"] == AnonymizationTechniqueEnum.PSEUDONYMIZATION.value
        assert audit_call["consistent"] is True
        assert audit_call["reversible"] is False


@pytest.mark.skip(reason="LGPD compliance functionality not yet implemented. TODO: Implement after core features")
class TestGeneralizeBirthDateToYear:
    """Test birth date generalization for privacy protection."""

    def test_generalize_birth_date_to_year__when_birth_date_provided__returns_year_only(
        self, mock_anonymization_port: Mock, mock_audit_log_port: Mock
    ):
        """
        LGPD Article 12: Generalization reduces granularity while preserving utility.

        Birth dates must be generalized to year only to:
        - Prevent precise age identification
        - Maintain age group analysis capability
        - Comply with anonymization requirements
        """
        # Arrange
        birth_date = "1985-06-15"
        generalized_year = "1985"

        mock_anonymization_port.generalize_field.return_value = {
            "original_value": birth_date,
            "anonymized_value": generalized_year,
            "technique": AnonymizationTechniqueEnum.GENERALIZATION.value,
            "granularity_reduced": True,
            "utility_preserved": True,
            "precision_loss": "day_and_month_removed",
        }

        use_case = GeneralizeDataUseCase(
            anonymization_port=mock_anonymization_port, audit_log_port=mock_audit_log_port
        )

        # Act
        result = use_case.execute(
            field_type=PersonalDataFieldEnum.BIRTH_DATE.value,
            value=birth_date,
            generalization_level="year_only",
        )

        # Assert
        assert result.anonymized_value == "1985"
        assert result.granularity_reduced is True
        assert result.utility_preserved is True  # Can still do age group analysis
        assert len(result.anonymized_value) == 4  # Year format
        assert result.anonymized_value.isdigit()  # Valid year

        # Verify generalization preserves analytical value
        original_year = int(birth_date.split("-")[0])
        anonymized_year = int(result.anonymized_value)
        assert original_year == anonymized_year  # Year preserved

        # Verify generalization was applied
        mock_anonymization_port.generalize_field.assert_called_once_with(
            field_type=PersonalDataFieldEnum.BIRTH_DATE.value,
            value=birth_date,
            generalization_level="year_only",
        )

        # Verify generalization was audited
        mock_audit_log_port.log_anonymization_event.assert_called_once()
        audit_call = mock_audit_log_port.log_anonymization_event.call_args[1]
        assert audit_call["technique"] == AnonymizationTechniqueEnum.GENERALIZATION.value
        assert audit_call["granularity_reduced"] is True

    def test_generalize_address_to_city__when_full_address_provided__returns_city_only(
        self, mock_anonymization_port: Mock, mock_audit_log_port: Mock
    ):
        """
        Full addresses must be generalized to city level for location analysis.
        """
        # Arrange
        full_address = "Rua das Flores, 123, Apt 45, Vila Madalena, São Paulo, SP, 01234-567"
        generalized_city = "São Paulo, SP"

        mock_anonymization_port.generalize_field.return_value = {
            "original_value": full_address,
            "anonymized_value": generalized_city,
            "technique": AnonymizationTechniqueEnum.GENERALIZATION.value,
            "granularity_reduced": True,
            "utility_preserved": True,
            "precision_loss": "street_and_number_removed",
        }

        use_case = GeneralizeDataUseCase(
            anonymization_port=mock_anonymization_port, audit_log_port=mock_audit_log_port
        )

        # Act
        result = use_case.execute(
            field_type=PersonalDataFieldEnum.ADDRESS.value,
            value=full_address,
            generalization_level="city_state",
        )

        # Assert
        assert result.anonymized_value == "São Paulo, SP"
        assert result.granularity_reduced is True
        assert "São Paulo" in result.anonymized_value  # City preserved
        assert "SP" in result.anonymized_value  # State preserved
        assert "Rua das Flores" not in result.anonymized_value  # Street removed
        assert "123" not in result.anonymized_value  # Number removed


@pytest.mark.skip(reason="LGPD compliance functionality not yet implemented. TODO: Implement after core features")
class TestSuppressRareAttributes:
    """Test suppression of unique identifying attributes."""

    def test_suppress_rare_attributes__when_unique_identifiers_found__removes_identifying_fields(
        self,
        mock_anonymization_port: Mock,
        mock_data_analysis_port: Mock,
        mock_audit_log_port: Mock,
        sample_personal_data: list[dict[str, Any]],
    ):
        """
        LGPD Article 12: Unique attributes that could re-identify individuals must be suppressed.

        When data contains rare or unique combinations that could identify individuals,
        those attributes must be removed entirely (not just masked).
        """
        # Arrange
        # Analysis finds that specific file names are unique identifiers
        rare_attributes_analysis = {
            "unique_attributes": ["ip_address", "file_name"],
            "quasi_identifiers": ["birth_date", "address"],
            "k_anonymity_violations": [
                {
                    "attribute": "ip_address",
                    "unique_values": 3,  # Each person has unique IP
                    "re_identification_risk": 0.95,
                }
            ],
        }

        mock_data_analysis_port.analyze_uniqueness.return_value = rare_attributes_analysis

        suppressed_data = [
            {
                "user_id": "pseudo-abc123-def4-5678-9012",
                "name": "hash_a1b2c3d4",
                "email": "hash_e5f6g7h8",
                "cpf": "XXX.XXX.XXX-XX",
                "birth_date": "1985",  # Generalized
                "phone": "+55 XX XXXXX-XXXX",
                "address": "São Paulo, SP",  # Generalized
                # ip_address: SUPPRESSED (unique identifier)
                # file_name: SUPPRESSED (unique identifier)
            },
            # Similar for other records...
        ]

        mock_anonymization_port.suppress_field.return_value = {
            "suppressed_fields": ["ip_address", "file_name"],
            "records_affected": 3,
            "re_identification_risk_after": 0.05,  # Significantly reduced
            "anonymized_dataset": suppressed_data,
        }

        use_case = SuppressUniqueAttributesUseCase(
            anonymization_port=mock_anonymization_port,
            data_analysis_port=mock_data_analysis_port,
            audit_log_port=mock_audit_log_port,
        )

        # Act
        result = use_case.execute(
            dataset=sample_personal_data,
            uniqueness_threshold=0.9,  # Suppress if >90% unique
            re_identification_risk_threshold=0.1,  # Target <10% risk
        )

        # Assert
        assert result.suppression_applied is True
        assert result.suppressed_fields == ["ip_address", "file_name"]
        assert result.re_identification_risk_after < 0.1  # Below threshold
        assert len(result.anonymized_dataset) == len(sample_personal_data)  # Same record count

        # Verify suppressed fields are removed
        for record in result.anonymized_dataset:
            assert "ip_address" not in record  # Completely removed
            assert "file_name" not in record  # Completely removed
            assert "user_id" in record  # Pseudonymized but kept
            assert "birth_date" in record  # Generalized but kept

        # Verify uniqueness analysis was performed
        mock_data_analysis_port.analyze_uniqueness.assert_called_once_with(
            dataset=sample_personal_data, uniqueness_threshold=0.9
        )

        # Verify suppression was applied
        mock_anonymization_port.suppress_field.assert_called_once()

        # Verify suppression was audited
        mock_audit_log_port.log_anonymization_event.assert_called_once()
        audit_call = mock_audit_log_port.log_anonymization_event.call_args[1]
        assert audit_call["technique"] == AnonymizationTechniqueEnum.SUPPRESSION.value
        assert audit_call["suppressed_fields"] == ["ip_address", "file_name"]
        assert audit_call["re_identification_risk_reduced"] is True


@pytest.mark.skip(reason="LGPD compliance functionality not yet implemented. TODO: Implement after core features")
class TestKAnonymityValidation:
    """Test k-anonymity validation for datasets."""

    def test_validate_k_anonymity__when_dataset_provided__ensures_minimum_k_level(
        self,
        mock_anonymization_port: Mock,
        mock_data_analysis_port: Mock,
        mock_audit_log_port: Mock,
        sample_personal_data: list[dict[str, Any]],
    ):
        """
        LGPD Article 12: Anonymization must prevent re-identification.

        K-anonymity ensures each record is indistinguishable from at least k-1 other records
        based on quasi-identifying attributes. Minimum k=5 is recommended for LGPD compliance.
        """
        # Arrange
        quasi_identifiers = [
            "birth_date",
            "address",
            "phone",
        ]  # Attributes that could identify someone
        target_k = 5  # Each record must be identical to at least 4 others on these attributes

        # Initial analysis shows k-anonymity violations
        initial_k_analysis = {
            "current_k_level": 1,  # Each record is unique - violates k-anonymity
            "violations": [
                {
                    "record_group": ["user_001"],
                    "quasi_identifier_values": {
                        "birth_date": "1985-06-15",
                        "address": "São Paulo",
                        "phone": "+55 11 99999-9999",
                    },
                    "group_size": 1,  # Only 1 record with these values = k=1
                },
                {
                    "record_group": ["user_002"],
                    "quasi_identifier_values": {
                        "birth_date": "1990-12-20",
                        "address": "São Paulo",
                        "phone": "+55 11 88888-8888",
                    },
                    "group_size": 1,
                },
            ],
        }

        # After anonymization, k-anonymity is satisfied
        final_k_analysis = {
            "current_k_level": 5,  # Meets minimum requirement
            "violations": [],  # No violations
            "anonymization_successful": True,
            "techniques_applied": [
                AnonymizationTechniqueEnum.GENERALIZATION.value,  # Birth dates generalized to year
                AnonymizationTechniqueEnum.SUPPRESSION.value,  # Unique phone numbers suppressed
            ],
        }

        mock_data_analysis_port.calculate_k_anonymity.side_effect = [
            initial_k_analysis,  # Before anonymization
            final_k_analysis,  # After anonymization
        ]

        # Mock anonymization to achieve k-anonymity
        anonymized_dataset = [
            {
                "user_id": "pseudo-abc123",
                "name": "hash_a1b2",
                "email": "hash_e5f6",
                "cpf": "XXX.XXX.XXX-XX",
                "birth_date": "1985",
                "address": "São Paulo, SP",
                # phone suppressed to achieve k-anonymity
            },
            {
                "user_id": "pseudo-def456",
                "name": "hash_c3d4",
                "email": "hash_g7h8",
                "cpf": "XXX.XXX.XXX-XX",
                "birth_date": "1990",
                "address": "São Paulo, SP",
                # phone suppressed, birth_date generalized
            },
            # Additional records with same generalized values to achieve k=5...
        ]

        mock_anonymization_port.apply_k_anonymity.return_value = {
            "anonymized_dataset": anonymized_dataset,
            "k_level_achieved": 5,
            "techniques_used": [
                AnonymizationTechniqueEnum.GENERALIZATION.value,
                AnonymizationTechniqueEnum.SUPPRESSION.value,
            ],
        }

        use_case = ValidateKAnonymityUseCase(
            anonymization_port=mock_anonymization_port,
            data_analysis_port=mock_data_analysis_port,
            audit_log_port=mock_audit_log_port,
        )

        # Act
        result = use_case.execute(
            dataset=sample_personal_data,
            quasi_identifiers=quasi_identifiers,
            target_k_level=target_k,
        )

        # Assert
        assert result.k_anonymity_satisfied is True
        assert result.achieved_k_level >= target_k
        assert result.k_anonymity_violations == 0
        assert len(result.anonymized_dataset) == len(sample_personal_data)  # No records lost

        # Verify k-anonymity was calculated before and after
        assert mock_data_analysis_port.calculate_k_anonymity.call_count == 2

        # Verify anonymization was applied to achieve k-anonymity
        mock_anonymization_port.apply_k_anonymity.assert_called_once_with(
            dataset=sample_personal_data,
            quasi_identifiers=quasi_identifiers,
            target_k_level=target_k,
        )

        # Verify k-anonymity validation was audited
        mock_audit_log_port.log_anonymization_event.assert_called_once()
        audit_call = mock_audit_log_port.log_anonymization_event.call_args[1]
        assert audit_call["technique"] == "k_anonymity_validation"
        assert audit_call["target_k_level"] == target_k
        assert audit_call["achieved_k_level"] == 5
        assert audit_call["k_anonymity_satisfied"] is True

    def test_validate_k_anonymity__when_k_cannot_be_achieved__raises_anonymization_error(
        self,
        mock_anonymization_port: Mock,
        mock_data_analysis_port: Mock,
        mock_audit_log_port: Mock,
    ):
        """
        If k-anonymity cannot be achieved, anonymization must fail rather than provide false security.
        """
        # Arrange
        dataset_too_small = [{"user_id": "user_001", "name": "João"}]  # Only 1 record
        target_k = 5  # Impossible with 1 record

        mock_data_analysis_port.calculate_k_anonymity.return_value = {
            "current_k_level": 1,
            "max_possible_k": 1,  # Dataset too small
            "violations": [{"group_size": 1}],
        }

        use_case = ValidateKAnonymityUseCase(
            anonymization_port=mock_anonymization_port,
            data_analysis_port=mock_data_analysis_port,
            audit_log_port=mock_audit_log_port,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="K-anonymity cannot be achieved"):
            use_case.execute(
                dataset=dataset_too_small, quasi_identifiers=["name"], target_k_level=target_k
            )

        # Verify failure was audited
        mock_audit_log_port.log_anonymization_event.assert_called_once()
        audit_call = mock_audit_log_port.log_anonymization_event.call_args[1]
        assert audit_call["technique"] == "k_anonymity_validation"
        assert audit_call["k_anonymity_satisfied"] is False
        assert audit_call["failure_reason"] == "dataset_too_small"


# Helper functions
def both_results_irreversible(result1, result2) -> bool:
    """Helper to check if both results are irreversible."""
    return result1.irreversible is True and result2.irreversible is True
