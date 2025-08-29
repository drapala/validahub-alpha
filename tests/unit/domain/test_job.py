"""Test Job domain entity."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from domain.job import Job, JobStatus, InvalidTransition
from domain.value_objects import TenantId, IdempotencyKey


class TestJobStatus:
    """Test JobStatus enum."""
    
    def test_all_statuses_exist(self):
        """JobStatus should have all expected statuses."""
        expected_statuses = {
            "queued", "running", "succeeded", "failed", 
            "cancelled", "expired", "retrying"
        }
        actual_statuses = {status.value for status in JobStatus}
        assert actual_statuses == expected_statuses


class TestJob:
    """Test Job entity."""
    
    def test_create_job_with_valid_data(self):
        """Should create job with valid data."""
        job_id = str(uuid4())
        tenant_id = TenantId("tenant_123")
        now = datetime.now(timezone.utc)
        
        job = Job(
            id=job_id,
            tenant_id=tenant_id,
            seller_id="seller_456",
            channel="mercado_livre",
            job_type="csv_validation",
            status=JobStatus.QUEUED,
            file_ref="s3://bucket/file.csv",
            rules_profile_id="ml@1.2.3",
            idempotency_key=IdempotencyKey("test-key-123"),
            created_at=now,
            updated_at=now
        )
        
        assert job.id == job_id
        assert job.tenant_id == tenant_id
        assert job.seller_id == "seller_456"
        assert job.channel == "mercado_livre"
        assert job.job_type == "csv_validation"
        assert job.status == JobStatus.QUEUED
        assert job.file_ref == "s3://bucket/file.csv"
        assert job.rules_profile_id == "ml@1.2.3"
        assert job.idempotency_key.value == "test-key-123"
        assert job.created_at == now
        assert job.updated_at == now
        assert job.counters.errors == 0
        assert job.counters.warnings == 0
        assert job.counters.total == 0


class TestJobTransitions:
    """Test job status transitions."""
    
    @pytest.fixture
    def base_job(self):
        """Create base job for transition tests."""
        return Job(
            id=str(uuid4()),
            tenant_id=TenantId("tenant_123"),
            seller_id="seller_456",
            channel="mercado_livre",
            job_type="csv_validation",
            status=JobStatus.QUEUED,
            file_ref="s3://bucket/file.csv",
            rules_profile_id="ml@1.2.3",
            idempotency_key=IdempotencyKey("test-key-123"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
    def test_queued_to_running_transition(self, base_job):
        """Should allow transition from queued to running."""
        old_updated_at = base_job.updated_at
        
        base_job.start_processing()
        
        assert base_job.status == JobStatus.RUNNING
        assert base_job.updated_at > old_updated_at
    
    def test_retrying_to_running_transition(self, base_job):
        """Should allow transition from retrying to running."""
        # Set up retrying status
        base_job._status = JobStatus.RETRYING  # Direct assignment for test setup
        old_updated_at = base_job.updated_at
        
        base_job.start_processing()
        
        assert base_job.status == JobStatus.RUNNING
        assert base_job.updated_at > old_updated_at
    
    def test_running_to_succeeded_transition(self, base_job):
        """Should allow transition from running to succeeded."""
        base_job._status = JobStatus.RUNNING  # Direct assignment for test setup
        old_updated_at = base_job.updated_at
        
        counters = {"errors": 2, "warnings": 5, "total": 100}
        base_job.mark_succeeded(counters)
        
        assert base_job.status == JobStatus.SUCCEEDED
        assert base_job.counters.errors == 2
        assert base_job.counters.warnings == 5
        assert base_job.counters.total == 100
        assert base_job.updated_at > old_updated_at
    
    def test_running_to_failed_transition(self, base_job):
        """Should allow transition from running to failed."""
        base_job._status = JobStatus.RUNNING  # Direct assignment for test setup
        old_updated_at = base_job.updated_at
        
        base_job.mark_failed("Processing error occurred")
        
        assert base_job.status == JobStatus.FAILED
        assert base_job.error_message == "Processing error occurred"
        assert base_job.updated_at > old_updated_at
    
    def test_running_to_expired_transition(self, base_job):
        """Should allow transition from running to expired."""
        base_job._status = JobStatus.RUNNING  # Direct assignment for test setup
        old_updated_at = base_job.updated_at
        
        base_job.mark_expired()
        
        assert base_job.status == JobStatus.EXPIRED
        assert base_job.updated_at > old_updated_at
    
    def test_running_to_cancelled_transition(self, base_job):
        """Should allow transition from running to cancelled."""
        base_job._status = JobStatus.RUNNING  # Direct assignment for test setup
        old_updated_at = base_job.updated_at
        
        base_job.cancel("User requested cancellation")
        
        assert base_job.status == JobStatus.CANCELLED
        assert base_job.error_message == "User requested cancellation"
        assert base_job.updated_at > old_updated_at
    
    def test_failed_to_retrying_transition(self, base_job):
        """Should allow transition from failed to retrying."""
        base_job._status = JobStatus.FAILED  # Direct assignment for test setup
        old_updated_at = base_job.updated_at
        
        base_job.retry()
        
        assert base_job.status == JobStatus.RETRYING
        assert base_job.updated_at > old_updated_at
    
    def test_expired_to_retrying_transition(self, base_job):
        """Should allow transition from expired to retrying."""
        base_job._status = JobStatus.EXPIRED  # Direct assignment for test setup
        old_updated_at = base_job.updated_at
        
        base_job.retry()
        
        assert base_job.status == JobStatus.RETRYING
        assert base_job.updated_at > old_updated_at


class TestInvalidTransitions:
    """Test invalid job status transitions."""
    
    @pytest.fixture
    def base_job(self):
        """Create base job for invalid transition tests."""
        return Job(
            id=str(uuid4()),
            tenant_id=TenantId("tenant_123"),
            seller_id="seller_456",
            channel="mercado_livre",
            job_type="csv_validation",
            status=JobStatus.QUEUED,
            file_ref="s3://bucket/file.csv",
            rules_profile_id="ml@1.2.3",
            idempotency_key=IdempotencyKey("test-key-123"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
    def test_succeeded_to_any_status_invalid(self, base_job):
        """Should reject transitions from succeeded status."""
        base_job._status = JobStatus.SUCCEEDED  # Direct assignment for test setup
        
        with pytest.raises(InvalidTransition, match="Cannot transition from succeeded"):
            base_job.start_processing()
        
        with pytest.raises(InvalidTransition, match="Cannot transition from succeeded"):
            base_job.mark_failed("Some error")
        
        with pytest.raises(InvalidTransition, match="Cannot transition from succeeded"):
            base_job.retry()
    
    def test_cancelled_to_any_status_invalid(self, base_job):
        """Should reject transitions from cancelled status."""
        base_job._status = JobStatus.CANCELLED  # Direct assignment for test setup
        
        with pytest.raises(InvalidTransition, match="Cannot transition from cancelled"):
            base_job.start_processing()
        
        with pytest.raises(InvalidTransition, match="Cannot transition from cancelled"):
            base_job.mark_failed("Some error")
        
        with pytest.raises(InvalidTransition, match="Cannot transition from cancelled"):
            base_job.retry()
    
    def test_queued_to_succeeded_invalid(self, base_job):
        """Should reject direct transition from queued to succeeded."""
        with pytest.raises(InvalidTransition, match="Cannot transition from queued to succeeded"):
            base_job.mark_succeeded({"errors": 0, "warnings": 0, "total": 100})
    
    def test_queued_to_failed_invalid(self, base_job):
        """Should reject direct transition from queued to failed."""
        with pytest.raises(InvalidTransition, match="Cannot transition from queued to failed"):
            base_job.mark_failed("Some error")
    
    def test_succeeded_to_retrying_invalid(self, base_job):
        """Should reject transition from succeeded to retrying."""
        base_job._status = JobStatus.SUCCEEDED  # Direct assignment for test setup
        
        with pytest.raises(InvalidTransition, match="Cannot retry job in status succeeded"):
            base_job.retry()
    
    def test_queued_to_retrying_invalid(self, base_job):
        """Should reject transition from queued to retrying."""
        with pytest.raises(InvalidTransition, match="Cannot retry job in status queued"):
            base_job.retry()
    
    def test_running_to_retrying_invalid(self, base_job):
        """Should reject direct transition from running to retrying."""
        base_job._status = JobStatus.RUNNING  # Direct assignment for test setup
        
        with pytest.raises(InvalidTransition, match="Cannot retry job in status running"):
            base_job.retry()


class TestJobInvariants:
    """Test job business invariants."""
    
    def test_updated_at_increases_on_valid_transitions(self):
        """updated_at should increase on every valid transition."""
        job = Job(
            id=str(uuid4()),
            tenant_id=TenantId("tenant_123"),
            seller_id="seller_456",
            channel="mercado_livre",
            job_type="csv_validation",
            status=JobStatus.QUEUED,
            file_ref="s3://bucket/file.csv",
            rules_profile_id="ml@1.2.3",
            idempotency_key=IdempotencyKey("test-key-123"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Track timestamps through transitions
        timestamps = [job.updated_at]
        
        # queued -> running
        job.start_processing()
        timestamps.append(job.updated_at)
        
        # running -> failed
        job.mark_failed("Test error")
        timestamps.append(job.updated_at)
        
        # failed -> retrying
        job.retry()
        timestamps.append(job.updated_at)
        
        # Verify timestamps are strictly increasing
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i-1], f"Timestamp {i} should be greater than {i-1}"
    
    def test_counters_only_set_on_success(self):
        """Counters should only be updated on successful completion."""
        job = Job(
            id=str(uuid4()),
            tenant_id=TenantId("tenant_123"),
            seller_id="seller_456",
            channel="mercado_livre",
            job_type="csv_validation",
            status=JobStatus.RUNNING,
            file_ref="s3://bucket/file.csv",
            rules_profile_id="ml@1.2.3",
            idempotency_key=IdempotencyKey("test-key-123"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Initially zero
        assert job.counters.errors == 0
        assert job.counters.warnings == 0
        assert job.counters.total == 0
        
        # Fail the job - counters should remain zero
        job.mark_failed("Some error")
        assert job.counters.errors == 0
        assert job.counters.warnings == 0
        assert job.counters.total == 0
        
        # Retry and succeed - now counters should be set
        job.retry()
        job.start_processing()
        job.mark_succeeded({"errors": 5, "warnings": 10, "total": 200})
        
        assert job.counters.errors == 5
        assert job.counters.warnings == 10
        assert job.counters.total == 200
    
    def test_error_message_set_on_failure_and_cancellation(self):
        """Error message should be set on failure and cancellation."""
        job = Job(
            id=str(uuid4()),
            tenant_id=TenantId("tenant_123"),
            seller_id="seller_456",
            channel="mercado_livre",
            job_type="csv_validation",
            status=JobStatus.RUNNING,
            file_ref="s3://bucket/file.csv",
            rules_profile_id="ml@1.2.3",
            idempotency_key=IdempotencyKey("test-key-123"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Initially no error message
        assert job.error_message is None
        
        # Mark as failed
        job.mark_failed("Processing failed")
        assert job.error_message == "Processing failed"
        
        # Reset for cancellation test
        job.retry()
        job.start_processing()
        
        # Cancel the job
        job.cancel("User cancelled")
        assert job.error_message == "User cancelled"