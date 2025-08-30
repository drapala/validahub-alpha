"""Test Job domain entity."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from src.domain.errors import DomainError, InvalidStateTransitionError
from src.domain.job import Job, JobStatus
from src.domain.value_objects import JobId, TenantId


class TestJobStatus:
    """Test JobStatus enum."""

    def test_all_statuses_exist(self):
        """JobStatus should have all expected statuses."""
        expected_statuses = {"submitted", "running", "completed", "failed", "retrying"}
        actual_statuses = {status.value for status in JobStatus}
        assert actual_statuses == expected_statuses


class TestJobCreation:
    """Test Job creation and initialization."""

    def test_create_job_with_factory_method(self):
        """Should create job with factory method."""
        tenant_id = TenantId("t_tenant123")

        job = Job.create(tenant_id)

        assert isinstance(job.id, JobId)
        assert job.tenant_id == tenant_id
        assert job.status == JobStatus.SUBMITTED
        assert job.created_at.tzinfo is not None
        assert job.created_at.tzinfo == UTC

    def test_create_job_with_constructor(self):
        """Should create job with direct constructor."""
        job_id = JobId(uuid4())
        tenant_id = TenantId("t_tenant123")
        created_at = datetime.now(UTC)

        job = Job(id=job_id, tenant_id=tenant_id, status=JobStatus.SUBMITTED, created_at=created_at)

        assert job.id == job_id
        assert job.tenant_id == tenant_id
        assert job.status == JobStatus.SUBMITTED
        assert job.created_at == created_at

    def test_job_requires_timezone_aware_datetime(self):
        """Should raise error if created_at is not timezone-aware."""
        job_id = JobId(uuid4())
        tenant_id = TenantId("t_tenant123")
        naive_datetime = datetime.now()  # No timezone

        with pytest.raises(DomainError, match="created_at must be timezone-aware"):
            Job(
                id=job_id,
                tenant_id=tenant_id,
                status=JobStatus.SUBMITTED,
                created_at=naive_datetime,
            )

    def test_job_is_immutable(self):
        """Should ensure Job instances are immutable."""
        job = Job.create(TenantId("t_tenant123"))

        # Attempt to modify should raise error
        with pytest.raises((AttributeError, TypeError)):
            job.status = JobStatus.RUNNING


class TestValidTransitions:
    """Test valid job status transitions."""

    @pytest.fixture
    def submitted_job(self):
        """Create a job in SUBMITTED status."""
        return Job.create(TenantId("t_tenant123"))

    def test_submitted_to_running_transition(self, submitted_job):
        """Should allow transition from SUBMITTED to RUNNING."""
        running_job = submitted_job.start()

        assert running_job.status == JobStatus.RUNNING
        assert running_job.id == submitted_job.id
        assert running_job.tenant_id == submitted_job.tenant_id
        assert running_job.created_at == submitted_job.created_at
        # Original should be unchanged (immutability)
        assert submitted_job.status == JobStatus.SUBMITTED

    def test_running_to_completed_transition(self, submitted_job):
        """Should allow transition from RUNNING to COMPLETED."""
        running_job = submitted_job.start()
        completed_job = running_job.complete()

        assert completed_job.status == JobStatus.COMPLETED
        assert completed_job.id == submitted_job.id
        # Original instances unchanged
        assert running_job.status == JobStatus.RUNNING
        assert submitted_job.status == JobStatus.SUBMITTED

    def test_running_to_failed_transition(self, submitted_job):
        """Should allow transition from RUNNING to FAILED."""
        running_job = submitted_job.start()
        failed_job = running_job.fail()

        assert failed_job.status == JobStatus.FAILED
        assert failed_job.id == submitted_job.id
        # Original instances unchanged
        assert running_job.status == JobStatus.RUNNING

    def test_failed_to_retrying_transition(self, submitted_job):
        """Should allow transition from FAILED to RETRYING."""
        running_job = submitted_job.start()
        failed_job = running_job.fail()
        retrying_job = failed_job.retry()

        assert retrying_job.status == JobStatus.RETRYING
        assert retrying_job.id == submitted_job.id
        # Original instances unchanged
        assert failed_job.status == JobStatus.FAILED

    def test_retrying_to_running_transition(self, submitted_job):
        """Should allow transition from RETRYING to RUNNING."""
        # Create full cycle: submitted -> running -> failed -> retrying -> running
        running_job = submitted_job.start()
        failed_job = running_job.fail()
        retrying_job = failed_job.retry()
        running_again_job = retrying_job.start()

        assert running_again_job.status == JobStatus.RUNNING
        assert running_again_job.id == submitted_job.id
        # All intermediate instances unchanged
        assert retrying_job.status == JobStatus.RETRYING
        assert failed_job.status == JobStatus.FAILED

    def test_complete_retry_cycle(self, submitted_job):
        """Should support complete retry cycle ending in success."""
        # First attempt fails
        job = submitted_job.start()
        job = job.fail()

        # Retry and succeed
        job = job.retry()
        job = job.start()
        job = job.complete()

        assert job.status == JobStatus.COMPLETED
        assert job.id == submitted_job.id


class TestInvalidTransitions:
    """Test invalid job status transitions."""

    def test_submitted_to_completed_invalid(self):
        """Should reject direct transition from SUBMITTED to COMPLETED."""
        job = Job.create(TenantId("t_tenant123"))

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            job.complete()

        assert exc_info.value.from_state == "submitted"
        assert exc_info.value.to_state == "completed"

    def test_submitted_to_failed_invalid(self):
        """Should reject direct transition from SUBMITTED to FAILED."""
        job = Job.create(TenantId("t_tenant123"))

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            job.fail()

        assert exc_info.value.from_state == "submitted"
        assert exc_info.value.to_state == "failed"

    def test_submitted_to_retrying_invalid(self):
        """Should reject transition from SUBMITTED to RETRYING."""
        job = Job.create(TenantId("t_tenant123"))

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            job.retry()

        assert exc_info.value.from_state == "submitted"
        assert exc_info.value.to_state == "retrying"

    def test_completed_to_any_transition_invalid(self):
        """Should reject any transition from COMPLETED state."""
        job = Job.create(TenantId("t_tenant123"))
        job = job.start()
        completed_job = job.complete()

        # Cannot start
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            completed_job.start()
        assert exc_info.value.from_state == "completed"

        # Cannot complete again
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            completed_job.complete()
        assert exc_info.value.from_state == "completed"

        # Cannot fail
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            completed_job.fail()
        assert exc_info.value.from_state == "completed"

        # Cannot retry
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            completed_job.retry()
        assert exc_info.value.from_state == "completed"

    def test_failed_to_running_invalid(self):
        """Should reject direct transition from FAILED to RUNNING."""
        job = Job.create(TenantId("t_tenant123"))
        job = job.start()
        failed_job = job.fail()

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            failed_job.start()

        assert exc_info.value.from_state == "failed"
        assert exc_info.value.to_state == "running"

    def test_failed_to_completed_invalid(self):
        """Should reject transition from FAILED to COMPLETED."""
        job = Job.create(TenantId("t_tenant123"))
        job = job.start()
        failed_job = job.fail()

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            failed_job.complete()

        assert exc_info.value.from_state == "failed"
        assert exc_info.value.to_state == "completed"

    def test_running_to_retrying_invalid(self):
        """Should reject direct transition from RUNNING to RETRYING."""
        job = Job.create(TenantId("t_tenant123"))
        running_job = job.start()

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            running_job.retry()

        assert exc_info.value.from_state == "running"
        assert exc_info.value.to_state == "retrying"

    def test_retrying_to_completed_invalid(self):
        """Should reject direct transition from RETRYING to COMPLETED."""
        job = Job.create(TenantId("t_tenant123"))
        job = job.start()
        job = job.fail()
        retrying_job = job.retry()

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            retrying_job.complete()

        assert exc_info.value.from_state == "retrying"
        assert exc_info.value.to_state == "completed"

    def test_retrying_to_failed_invalid(self):
        """Should reject direct transition from RETRYING to FAILED."""
        job = Job.create(TenantId("t_tenant123"))
        job = job.start()
        job = job.fail()
        retrying_job = job.retry()

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            retrying_job.fail()

        assert exc_info.value.from_state == "retrying"
        assert exc_info.value.to_state == "failed"


class TestJobHelperMethods:
    """Test Job helper methods."""

    def test_is_terminal_for_completed(self):
        """Should identify COMPLETED as terminal state."""
        job = Job.create(TenantId("t_tenant123"))
        job = job.start()
        completed_job = job.complete()

        assert completed_job.is_terminal() is True

    def test_is_terminal_for_failed(self):
        """Should identify FAILED as terminal state."""
        job = Job.create(TenantId("t_tenant123"))
        job = job.start()
        failed_job = job.fail()

        assert failed_job.is_terminal() is True

    def test_is_terminal_for_non_terminal_states(self):
        """Should identify non-terminal states correctly."""
        job = Job.create(TenantId("t_tenant123"))

        # SUBMITTED
        assert job.is_terminal() is False

        # RUNNING
        running_job = job.start()
        assert running_job.is_terminal() is False

        # RETRYING
        failed_job = running_job.fail()
        retrying_job = failed_job.retry()
        assert retrying_job.is_terminal() is False

    def test_can_retry_for_failed(self):
        """Should allow retry for FAILED state."""
        job = Job.create(TenantId("t_tenant123"))
        job = job.start()
        failed_job = job.fail()

        assert failed_job.can_retry() is True

    def test_can_retry_for_non_failed_states(self):
        """Should not allow retry for non-FAILED states."""
        job = Job.create(TenantId("t_tenant123"))

        # SUBMITTED
        assert job.can_retry() is False

        # RUNNING
        running_job = job.start()
        assert running_job.can_retry() is False

        # COMPLETED
        completed_job = running_job.complete()
        assert completed_job.can_retry() is False

        # RETRYING
        failed_job = running_job.fail()
        retrying_job = failed_job.retry()
        assert retrying_job.can_retry() is False

    def test_string_representation(self):
        """Should have readable string representation."""
        tenant_id = TenantId("t_tenant123")
        job = Job.create(tenant_id)

        str_repr = str(job)
        assert "Job" in str_repr
        assert str(job.id) in str_repr
        assert str(tenant_id) in str_repr
        assert "submitted" in str_repr


class TestJobImmutability:
    """Test that Job maintains immutability."""

    def test_transitions_return_new_instances(self):
        """Should return new instances on state transitions."""
        original = Job.create(TenantId("t_tenant123"))

        # Each transition should return a different instance
        running = original.start()
        assert running is not original
        assert id(running) != id(original)

        completed = running.complete()
        assert completed is not running
        assert completed is not original

        # Create another path
        running2 = original.start()
        failed = running2.fail()
        retrying = failed.retry()

        # All should be different instances
        instances = [original, running, completed, running2, failed, retrying]
        instance_ids = [id(inst) for inst in instances]
        assert len(set(instance_ids)) == len(instance_ids)  # All unique

    def test_original_unchanged_after_transitions(self):
        """Should keep original instance unchanged after transitions."""
        original = Job.create(TenantId("t_tenant123"))
        original_status = original.status
        original_id = original.id
        original_tenant = original.tenant_id
        original_created = original.created_at

        # Perform multiple transitions
        running = original.start()
        _ = running.complete()

        # Original should be completely unchanged
        assert original.status == original_status
        assert original.id == original_id
        assert original.tenant_id == original_tenant
        assert original.created_at == original_created


class TestDomainErrors:
    """Test domain error handling."""

    def test_invalid_state_transition_error_message(self):
        """Should have clear error messages for invalid transitions."""
        job = Job.create(TenantId("t_tenant123"))

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            job.complete()

        error = exc_info.value
        assert "Invalid state transition from submitted to completed" in str(error)
        assert error.from_state == "submitted"
        assert error.to_state == "completed"

    def test_domain_error_for_naive_datetime(self):
        """Should raise DomainError for naive datetime."""
        job_id = JobId(uuid4())
        tenant_id = TenantId("t_tenant123")
        naive_datetime = datetime.now()  # No timezone

        with pytest.raises(DomainError) as exc_info:
            Job(
                id=job_id,
                tenant_id=tenant_id,
                status=JobStatus.SUBMITTED,
                created_at=naive_datetime,
            )

        assert "created_at must be timezone-aware" in str(exc_info.value)
