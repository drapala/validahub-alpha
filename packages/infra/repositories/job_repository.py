"""Job repository implementation with comprehensive logging.

This module implements the JobRepository port with full logging
of database operations and performance metrics.
"""

import time
from datetime import UTC, datetime
from typing import Any

from src.application.ports import JobRepository
from src.domain.job import Job, JobStatus
from src.domain.value_objects import IdempotencyKey, JobId, TenantId
from src.infrastructure.logging.utilities import LoggingPort, log_repository_query

from shared.logging.context import get_correlation_id


class InMemoryJobRepository(JobRepository, LoggingPort):
    """
    In-memory implementation of JobRepository for testing.
    Includes comprehensive logging of all operations.
    """

    def __init__(self):
        """Initialize in-memory repository with logging."""
        super().__init__(logger_name="infrastructure.job_repository")
        self._storage: dict[str, dict[str, Any]] = {}
        self._idempotency_index: dict[str, str] = {}  # (tenant_id, idempotency_key) -> job_id

        self._logger.info(
            "job_repository_initialized",
            implementation="in_memory",
            correlation_id=get_correlation_id(),
        )

    def get_component_name(self) -> str:
        """Get component name for logging context."""
        return "JobRepository"

    @log_repository_query(query_type="insert", table_name="jobs")
    def save(self, job: Job) -> Job:
        """
        Save job to in-memory storage with detailed logging.

        Args:
            job: Job instance to save

        Returns:
            Saved job instance
        """
        start_time = time.time()
        job_id = str(job.id.value)
        tenant_id = job.tenant_id.value

        # Check for existing job (for idempotency)
        existing = self._storage.get(job_id)
        if existing:
            self._logger.info(
                "job_repository_save_idempotent",
                job_id=job_id,
                tenant_id=tenant_id,
                status=job.status.value,
                operation="update",
                correlation_id=get_correlation_id(),
            )

        # Store job data
        job_data = {
            "id": job_id,
            "tenant_id": tenant_id,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        # Add any additional fields if job is an extended type
        if hasattr(job, "seller_id"):
            job_data.update(
                {
                    "seller_id": getattr(job, "seller_id", None),
                    "channel": getattr(job, "channel", None),
                    "job_type": getattr(job, "job_type", None),
                    "file_ref": getattr(job, "file_ref", None),
                    "rules_profile_id": getattr(job, "rules_profile_id", None),
                    "idempotency_key": getattr(job, "idempotency_key", None),
                }
            )

            # Update idempotency index if key is present
            if job_data.get("idempotency_key"):
                index_key = f"{tenant_id}:{job_data['idempotency_key']}"
                self._idempotency_index[index_key] = job_id

                self._logger.debug(
                    "idempotency_index_updated",
                    tenant_id=tenant_id,
                    idempotency_key=job_data["idempotency_key"],
                    job_id=job_id,
                    correlation_id=get_correlation_id(),
                )

        self._storage[job_id] = job_data

        # Log successful save with metrics
        duration_ms = (time.time() - start_time) * 1000
        self._logger.info(
            "job_repository_save_completed",
            job_id=job_id,
            tenant_id=tenant_id,
            status=job.status.value,
            operation="insert" if not existing else "update",
            duration_ms=duration_ms,
            storage_size=len(self._storage),
            correlation_id=get_correlation_id(),
        )

        # Return the job (or convert from extended type)
        if hasattr(job, "seller_id"):
            # Return the extended job as-is
            return job
        else:
            # Return the domain job
            return job

    @log_repository_query(query_type="select", table_name="jobs")
    def find_by_idempotency_key(self, tenant_id: TenantId, key: IdempotencyKey) -> Job | None:
        """
        Find job by tenant and idempotency key with detailed logging.

        Args:
            tenant_id: Tenant identifier
            key: Idempotency key

        Returns:
            Job if found, None otherwise
        """
        start_time = time.time()
        tenant_id_value = tenant_id.value

        # Handle both IdempotencyKey objects and opaque keys
        if hasattr(key, "value"):
            key_value = key.value
        else:
            key_value = str(key) if not isinstance(key, str) else key

        index_key = f"{tenant_id_value}:{key_value}"

        self._logger.debug(
            "idempotency_lookup_starting",
            tenant_id=tenant_id_value,
            idempotency_key=key_value,
            index_key=index_key,
            correlation_id=get_correlation_id(),
        )

        # Lookup in idempotency index
        job_id = self._idempotency_index.get(index_key)

        if not job_id:
            duration_ms = (time.time() - start_time) * 1000
            self._logger.info(
                "idempotency_lookup_miss",
                tenant_id=tenant_id_value,
                idempotency_key=key_value,
                duration_ms=duration_ms,
                correlation_id=get_correlation_id(),
            )
            return None

        # Retrieve job data
        job_data = self._storage.get(job_id)

        if not job_data:
            # Index inconsistency - should not happen in production
            self._logger.error(
                "idempotency_index_inconsistency",
                tenant_id=tenant_id_value,
                idempotency_key=key_value,
                job_id=job_id,
                error="Job ID in index but not in storage",
                correlation_id=get_correlation_id(),
            )
            # Clean up inconsistent index
            del self._idempotency_index[index_key]
            return None

        # Verify tenant isolation
        if job_data["tenant_id"] != tenant_id_value:
            self._logger.error(
                "tenant_isolation_violation_attempted",
                requesting_tenant=tenant_id_value,
                job_tenant=job_data["tenant_id"],
                job_id=job_id,
                idempotency_key=key_value,
                correlation_id=get_correlation_id(),
            )
            return None

        duration_ms = (time.time() - start_time) * 1000
        self._logger.info(
            "idempotency_lookup_hit",
            tenant_id=tenant_id_value,
            idempotency_key=key_value,
            job_id=job_id,
            job_status=job_data["status"],
            duration_ms=duration_ms,
            correlation_id=get_correlation_id(),
        )

        # Convert to extended job format for compatibility
        from src.application.use_cases.submit_job import ExtendedJob

        return ExtendedJob(
            id=job_data["id"],
            tenant_id=job_data["tenant_id"],
            seller_id=job_data.get("seller_id", ""),
            channel=job_data.get("channel", ""),
            job_type=job_data.get("job_type", ""),
            file_ref=job_data.get("file_ref", ""),
            rules_profile_id=job_data.get("rules_profile_id", ""),
            status=job_data["status"],
            idempotency_key=job_data.get("idempotency_key"),
            created_at=datetime.fromisoformat(job_data["created_at"]),
            updated_at=datetime.fromisoformat(job_data["updated_at"]),
        )

    @log_repository_query(query_type="select", table_name="jobs")
    def find_by_id(self, job_id: JobId) -> Job | None:
        """
        Find job by ID with logging.

        Args:
            job_id: Job identifier

        Returns:
            Job if found, None otherwise
        """
        start_time = time.time()
        job_id_value = str(job_id.value)

        job_data = self._storage.get(job_id_value)

        duration_ms = (time.time() - start_time) * 1000

        if job_data:
            self._logger.info(
                "job_repository_find_by_id_hit",
                job_id=job_id_value,
                tenant_id=job_data["tenant_id"],
                status=job_data["status"],
                duration_ms=duration_ms,
                correlation_id=get_correlation_id(),
            )

            # Convert to Job domain object
            return Job(
                id=JobId(job_data["id"]),
                tenant_id=TenantId(job_data["tenant_id"]),
                status=JobStatus(job_data["status"]),
                created_at=datetime.fromisoformat(job_data["created_at"]),
            )
        else:
            self._logger.info(
                "job_repository_find_by_id_miss",
                job_id=job_id_value,
                duration_ms=duration_ms,
                correlation_id=get_correlation_id(),
            )
            return None

    @log_repository_query(query_type="select", table_name="jobs")
    def find_by_tenant(self, tenant_id: TenantId, limit: int = 100) -> list[Job]:
        """
        Find all jobs for a tenant with logging.

        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of jobs to return

        Returns:
            List of jobs for the tenant
        """
        start_time = time.time()
        tenant_id_value = tenant_id.value

        self._logger.debug(
            "job_repository_find_by_tenant_starting",
            tenant_id=tenant_id_value,
            limit=limit,
            correlation_id=get_correlation_id(),
        )

        # Filter jobs by tenant
        tenant_jobs = []
        for job_data in self._storage.values():
            if job_data["tenant_id"] == tenant_id_value:
                tenant_jobs.append(job_data)
                if len(tenant_jobs) >= limit:
                    break

        duration_ms = (time.time() - start_time) * 1000

        self._logger.info(
            "job_repository_find_by_tenant_completed",
            tenant_id=tenant_id_value,
            jobs_found=len(tenant_jobs),
            limit=limit,
            duration_ms=duration_ms,
            total_jobs_scanned=len(self._storage),
            correlation_id=get_correlation_id(),
        )

        # Convert to Job domain objects
        jobs = []
        for job_data in tenant_jobs:
            jobs.append(
                Job(
                    id=JobId(job_data["id"]),
                    tenant_id=TenantId(job_data["tenant_id"]),
                    status=JobStatus(job_data["status"]),
                    created_at=datetime.fromisoformat(job_data["created_at"]),
                )
            )

        return jobs

    def get_stats(self) -> dict[str, Any]:
        """
        Get repository statistics for monitoring.

        Returns:
            Dictionary with repository stats
        """
        stats = {
            "total_jobs": len(self._storage),
            "idempotency_keys": len(self._idempotency_index),
            "jobs_by_status": {},
            "jobs_by_tenant": {},
        }

        # Calculate stats
        for job_data in self._storage.values():
            status = job_data["status"]
            tenant = job_data["tenant_id"]

            stats["jobs_by_status"][status] = stats["jobs_by_status"].get(status, 0) + 1
            stats["jobs_by_tenant"][tenant] = stats["jobs_by_tenant"].get(tenant, 0) + 1

        self._logger.info("job_repository_stats", **stats, correlation_id=get_correlation_id())

        return stats
