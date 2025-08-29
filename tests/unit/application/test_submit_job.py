"""Test SubmitJob use case."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.application.use_cases.submit_job import SubmitJobUseCase, SubmitJobRequest
from src.application.errors import RateLimitExceeded
from src.domain.value_objects import TenantId, IdempotencyKey
from src.domain.job import Job, JobStatus
from tests.fakes import FakeJobRepository, FakeEventBus, FakeRateLimiter


class TestSubmitJobUseCase:
    """Test SubmitJob use case."""
    
    @pytest.fixture
    def job_repository(self):
        """Create fake job repository."""
        return FakeJobRepository()
    
    @pytest.fixture
    def event_bus(self):
        """Create fake event bus."""
        return FakeEventBus()
    
    @pytest.fixture
    def rate_limiter(self):
        """Create fake rate limiter."""
        return FakeRateLimiter()
    
    @pytest.fixture
    def use_case(self, job_repository, event_bus, rate_limiter):
        """Create SubmitJob use case with fakes."""
        return SubmitJobUseCase(
            job_repository=job_repository,
            event_bus=event_bus,
            rate_limiter=rate_limiter
        )
    
    @pytest.fixture
    def submit_request(self):
        """Create valid submit job request."""
        return SubmitJobRequest(
            tenant_id="tenant_123",
            seller_id="seller_456",
            channel="mercado_livre",
            job_type="csv_validation",
            file_ref="s3://bucket/test-file.csv",
            rules_profile_id="ml@1.2.3",
            idempotency_key="test-key-123.csv"
        )
    
    def test_submit_new_job_success(self, use_case, submit_request, event_bus):
        """Should create new job and publish event."""
        # Act
        result = use_case.execute(submit_request)
        
        # Assert job created
        assert result.job_id is not None
        assert result.status == JobStatus.QUEUED.value
        assert result.file_ref == "s3://bucket/test-file.csv"
        assert result.created_at is not None
        
        # Assert event published
        events = event_bus.get_events_by_type("valida.job.submitted")
        assert len(events) == 1
        
        event = events[0]
        assert event.type == "valida.job.submitted"
        assert event.data["job_id"] == result.job_id
        assert event.data["tenant_id"] == "tenant_123"
        assert event.data["seller_id"] == "seller_456"
        assert event.data["channel"] == "mercado_livre"
    
    def test_submit_job_with_idempotency_key_first_time(self, use_case, submit_request, job_repository, event_bus):
        """Should create job and publish event on first submission with idempotency key."""
        # Act
        result = use_case.execute(submit_request)
        
        # Assert job persisted
        saved_job = job_repository.get_by_id(result.job_id)
        assert saved_job is not None
        assert saved_job.tenant_id == "tenant_123"
        assert saved_job.idempotency_key == "test-key-123.csv"
        
        # Assert job can be found by idempotency key
        found_job = job_repository.get_by_idempotency_key("tenant_123", "test-key-123.csv")
        assert found_job is not None
        assert found_job.id == result.job_id
        
        # Assert event published
        events = event_bus.get_events_by_type("valida.job.submitted")
        assert len(events) == 1
    
    def test_submit_job_with_same_idempotency_key_returns_existing(self, use_case, submit_request, event_bus):
        """Should return existing job and NOT publish event on duplicate idempotency key."""
        # Arrange - submit first job
        first_result = use_case.execute(submit_request)
        event_bus.clear()  # Clear events from first submission
        
        # Act - submit same request again
        second_result = use_case.execute(submit_request)
        
        # Assert same job returned
        assert second_result.job_id == first_result.job_id
        assert second_result.status == first_result.status
        assert second_result.created_at == first_result.created_at
        
        # Assert NO new event published
        events = event_bus.get_events_by_type("valida.job.submitted")
        assert len(events) == 0  # No new events
    
    def test_submit_job_different_tenants_same_idempotency_key(self, use_case, event_bus):
        """Should create separate jobs for different tenants with same idempotency key."""
        # Arrange
        request1 = SubmitJobRequest(
            tenant_id="tenant_123",
            seller_id="seller_456",
            channel="mercado_livre",
            job_type="csv_validation",
            file_ref="s3://bucket/test-file.csv",
            rules_profile_id="ml@1.2.3",
            idempotency_key="same-key-123"
        )
        
        request2 = SubmitJobRequest(
            tenant_id="tenant_456",  # Different tenant
            seller_id="seller_789",
            channel="mercado_livre",
            job_type="csv_validation",
            file_ref="s3://bucket/test-file.csv",
            rules_profile_id="ml@1.2.3",
            idempotency_key="same-key-123"  # Same idempotency key
        )
        
        # Act
        result1 = use_case.execute(request1)
        result2 = use_case.execute(request2)
        
        # Assert different jobs created
        assert result1.job_id != result2.job_id
        
        # Assert both events published
        events = event_bus.get_events_by_type("valida.job.submitted")
        assert len(events) == 2
        
        # Verify tenant isolation
        tenant_ids = {event.data["tenant_id"] for event in events}
        assert tenant_ids == {"tenant_123", "tenant_456"}
    
    def test_submit_job_rate_limit_exceeded(self, use_case, submit_request, rate_limiter):
        """Should raise RateLimitExceeded when rate limit exceeded."""
        # Arrange
        rate_limiter.set_exceeded(True)
        
        # Act & Assert
        with pytest.raises(RateLimitExceeded, match="Rate limit exceeded for tenant tenant_123"):
            use_case.execute(submit_request)
    
    def test_submit_job_validates_input(self, use_case):
        """Should validate input parameters."""
        # Test empty tenant_id
        with pytest.raises(ValueError, match="tenant_id is required"):
            invalid_request = SubmitJobRequest(
                tenant_id="",
                seller_id="seller_456",
                channel="mercado_livre",
                job_type="csv_validation",
                file_ref="s3://bucket/test-file.csv",
                rules_profile_id="ml@1.2.3",
                idempotency_key="test-key-123"
            )
            use_case.execute(invalid_request)
        
        # Test empty seller_id
        with pytest.raises(ValueError, match="seller_id is required"):
            invalid_request = SubmitJobRequest(
                tenant_id="tenant_123",
                seller_id="",
                channel="mercado_livre",
                job_type="csv_validation",
                file_ref="s3://bucket/test-file.csv",
                rules_profile_id="ml@1.2.3",
                idempotency_key="test-key-123"
            )
            use_case.execute(invalid_request)
        
        # Test empty file_ref
        with pytest.raises(ValueError, match="file_ref is required"):
            invalid_request = SubmitJobRequest(
                tenant_id="tenant_123",
                seller_id="seller_456",
                channel="mercado_livre",
                job_type="csv_validation",
                file_ref="",
                rules_profile_id="ml@1.2.3",
                idempotency_key="test-key-123"
            )
            use_case.execute(invalid_request)
    
    def test_submit_job_without_idempotency_key(self, use_case, event_bus):
        """Should allow submission without idempotency key."""
        # Arrange
        request = SubmitJobRequest(
            tenant_id="tenant_123",
            seller_id="seller_456",
            channel="mercado_livre",
            job_type="csv_validation",
            file_ref="s3://bucket/test-file.csv",
            rules_profile_id="ml@1.2.3",
            idempotency_key=None
        )
        
        # Act
        result = use_case.execute(request)
        
        # Assert job created
        assert result.job_id is not None
        assert result.status == JobStatus.QUEUED.value
        
        # Assert event published
        events = event_bus.get_events_by_type("valida.job.submitted")
        assert len(events) == 1
    
    def test_submit_job_sets_created_and_updated_timestamps(self, use_case, submit_request, job_repository):
        """Should set created_at and updated_at timestamps on job creation."""
        # Act
        result = use_case.execute(submit_request)
        
        # Assert
        saved_job = job_repository.get_by_id(result.job_id)
        assert saved_job.created_at is not None
        assert saved_job.updated_at is not None
        assert saved_job.created_at == saved_job.updated_at  # Should be equal on creation
        assert saved_job.created_at.tzinfo is not None  # Should be timezone-aware
    
    def test_event_contains_required_fields(self, use_case, submit_request, event_bus):
        """Should publish event with all required CloudEvents fields."""
        # Act
        result = use_case.execute(submit_request)
        
        # Assert
        events = event_bus.get_events_by_type("valida.job.submitted")
        assert len(events) == 1
        
        event = events[0]
        # CloudEvents standard fields
        assert event.id is not None
        assert event.specversion == "1.0"
        assert event.source == "application/submit-job"
        assert event.type == "valida.job.submitted"
        assert event.time is not None
        assert event.subject == f"job:{result.job_id}"
        
        # ValidaHub specific fields
        assert event.tenant_id == "tenant_123"
        assert event.actor_id == "seller_456"
        assert event.trace_id is not None
        assert event.schema_version == "1"
        
        # Event data
        assert event.data["job_id"] == result.job_id
        assert event.data["tenant_id"] == "tenant_123"
        assert event.data["seller_id"] == "seller_456"
        assert event.data["channel"] == "mercado_livre"
        assert event.data["job_type"] == "csv_validation"
        assert event.data["file_ref"] == "s3://bucket/test-file.csv"
        assert event.data["rules_profile_id"] == "ml@1.2.3"
    
    def test_multiple_jobs_same_tenant_different_keys(self, use_case, event_bus):
        """Should create multiple jobs for same tenant with different idempotency keys."""
        # Arrange
        request1 = SubmitJobRequest(
            tenant_id="tenant_123",
            seller_id="seller_456",
            channel="mercado_livre",
            job_type="csv_validation",
            file_ref="s3://bucket/file1.csv",
            rules_profile_id="ml@1.2.3",
            idempotency_key="key-1-12345678"
        )
        
        request2 = SubmitJobRequest(
            tenant_id="tenant_123",  # Same tenant
            seller_id="seller_456",
            channel="mercado_livre",
            job_type="csv_validation",
            file_ref="s3://bucket/file2.csv",
            rules_profile_id="ml@1.2.3",
            idempotency_key="key-2-12345678"  # Different key
        )
        
        # Act
        result1 = use_case.execute(request1)
        result2 = use_case.execute(request2)
        
        # Assert
        assert result1.job_id != result2.job_id
        
        # Assert both events published
        events = event_bus.get_events_by_type("valida.job.submitted")
        assert len(events) == 2