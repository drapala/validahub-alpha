"""Domain enums for ValidaHub."""

from enum import Enum


class JobStatus(Enum):
    """Job processing status enumeration.
    
    Represents the lifecycle states of a job from submission to completion.
    """
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    RETRYING = "retrying"

    def can_transition_to(self, target: 'JobStatus') -> bool:
        """Check if transition to target status is valid."""
        valid_transitions = {
            JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED, JobStatus.EXPIRED},
            JobStatus.RUNNING: {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED},
            JobStatus.SUCCEEDED: set(),  # Terminal state
            JobStatus.FAILED: {JobStatus.RETRYING},
            JobStatus.CANCELLED: set(),  # Terminal state
            JobStatus.EXPIRED: set(),    # Terminal state
            JobStatus.RETRYING: {JobStatus.QUEUED, JobStatus.FAILED},
        }
        return target in valid_transitions.get(self, set())

    def is_terminal(self) -> bool:
        """Check if this is a terminal status (no further transitions)."""
        return self in {JobStatus.SUCCEEDED, JobStatus.CANCELLED, JobStatus.EXPIRED}

    def is_active(self) -> bool:
        """Check if job is actively being processed."""
        return self in {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.RETRYING}

    def is_completed(self) -> bool:
        """Check if job has completed (successfully or with failure)."""
        return self in {JobStatus.SUCCEEDED, JobStatus.FAILED}


class JobType(Enum):
    """Job processing type enumeration."""
    VALIDATION = "validation"
    CORRECTION = "correction"
    ENRICHMENT = "enrichment"

    def get_description(self) -> str:
        """Get human-readable description of job type."""
        descriptions = {
            JobType.VALIDATION: "Validate data against marketplace rules",
            JobType.CORRECTION: "Fix validation errors automatically",
            JobType.ENRICHMENT: "Enrich data with additional information",
        }
        return descriptions[self]


class EventType(Enum):
    """Domain event types following CloudEvents specification."""
    JOB_SUBMITTED = "job.submitted"
    JOB_STARTED = "job.started"
    JOB_SUCCEEDED = "job.succeeded"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"
    JOB_RETRIED = "job.retried"
    JOB_EXPIRED = "job.expired"

    @classmethod
    def from_status_transition(cls, old_status: JobStatus | None, new_status: JobStatus) -> 'EventType':
        """Get event type for status transition."""
        if old_status is None and new_status == JobStatus.QUEUED:
            return cls.JOB_SUBMITTED
        
        transition_map = {
            JobStatus.RUNNING: cls.JOB_STARTED,
            JobStatus.SUCCEEDED: cls.JOB_SUCCEEDED,
            JobStatus.FAILED: cls.JOB_FAILED,
            JobStatus.CANCELLED: cls.JOB_CANCELLED,
            JobStatus.EXPIRED: cls.JOB_EXPIRED,
            JobStatus.RETRYING: cls.JOB_RETRIED,
        }
        
        event_type = transition_map.get(new_status)
        if not event_type:
            raise ValueError(f"No event type for status transition to {new_status}")
        
        return event_type