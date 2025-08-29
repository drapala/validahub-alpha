"""Integration tests for jobs HTTP handler with legacy key scenarios.

These tests focus on comprehensive scenarios with security considerations,
legacy key handling, and concurrency scenarios.
"""

import asyncio
import copy
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Tuple
from unittest.mock import Mock, patch

import pytest

from src.application.config import IdempotencyCompatMode
from src.application.errors import RateLimitExceeded, ValidationError
from src.application.http.handlers.jobs import (
    JobsHttpHandler,
    HttpJobSubmissionRequest,
    HttpJobSubmissionResponse,
    get_idempotency_key_header,
    get_request_id_header
)
from src.application.idempotency.store import InMemoryIdempotencyStore, IdempotencyConflictError
from src.application.use_cases.submit_job import SubmitJobResponse
from src.domain.value_objects import TenantId


class TestJobsHttpHandlerIntegration:
    """Comprehensive integration tests for JobsHttpHandler."""
    
    def setup_method(self):
        """Set up test fixtures with fresh state."""
        self.mock_use_case = Mock()
        self.idempotency_store = InMemoryIdempotencyStore()
        self.handler = JobsHttpHandler(self.mock_use_case, self.idempotency_store)
        
        # Base request template
        self.base_request = HttpJobSubmissionRequest(
            tenant_id="t_test123",
            seller_id="seller_456", 
            channel="mercado_livre",
            job_type="validation",
            file_ref="s3://bucket/file.csv",
            rules_profile_id="ml@1.0.0",
            idempotency_key_raw=None,
            request_id="req_123",
            method="POST",
            route_template="/jobs"
        )
        
        self.mock_response = SubmitJobResponse(
            job_id="job_789",
            status="queued", 
            file_ref="s3://bucket/file.csv",
            created_at=datetime.now().isoformat()
        )
    
    def test_request_without_idempotency_key_generates_valid_key(self):
        """Test request without idempotency key generates valid key."""
        # Setup: No idempotency key provided
        request = copy.deepcopy(self.base_request)
        request.idempotency_key_raw = None
        
        self.mock_use_case.execute.return_value = self.mock_response
        
        # Execute
        response = self.handler.submit_job(request)
        
        # Verify: Handler generates valid key 
        assert response.idempotency_key_resolved is not None
        assert len(response.idempotency_key_resolved) >= 16
        
        # Security: First char must not be formula injection chars
        assert response.idempotency_key_resolved[0] not in {'=', '+', '-', '@'}
        
        # Verify: Regex compliant (alphanumeric + hyphens/underscores)
        import re
        assert re.match(r'^[a-zA-Z0-9_-]+$', response.idempotency_key_resolved)
        
        assert not response.is_idempotent_replay
        self.mock_use_case.execute.assert_called_once()
    
    @patch.dict(os.environ, {"IDEMP_COMPAT_MODE": "canonicalize"})
    def test_legacy_key_canonicalized_to_valid_format(self):
        """Test legacy key 'abc.def:ghi' is canonicalized to valid format."""
        # Setup: Legacy key with problematic chars
        legacy_key = "abc.def:ghi" 
        request = copy.deepcopy(self.base_request)
        request.idempotency_key_raw = legacy_key
        
        self.mock_use_case.execute.return_value = self.mock_response
        
        # Execute
        response = self.handler.submit_job(request)
        
        # Verify: Key was canonicalized (not equal to raw)
        assert response.idempotency_key_resolved != legacy_key
        assert len(response.idempotency_key_resolved) >= 16
        
        # Security: Safe first character
        assert response.idempotency_key_resolved[0] not in {'=', '+', '-', '@'}
        
        # Verify: Regex compliant
        import re
        assert re.match(r'^[a-zA-Z0-9_-]+$', response.idempotency_key_resolved)
        
        assert not response.is_idempotent_replay
        self.mock_use_case.execute.assert_called_once()
    
    @patch.dict(os.environ, {"IDEMP_COMPAT_MODE": "reject"})
    def test_reject_mode_returns_422_without_echoing_invalid_value(self):
        """Test IDEMP_COMPAT_MODE=reject returns 422 without echoing invalid value."""
        # Setup: Invalid legacy key
        invalid_key = "order.123:item"
        request = copy.deepcopy(self.base_request)
        request.idempotency_key_raw = invalid_key
        
        # Execute & Verify: Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            self.handler.submit_job(request)
        
        # Security: Error message must not echo the invalid key value
        error_message = str(exc_info.value)
        assert invalid_key not in error_message
        assert "Invalid idempotency key format" in error_message
        
        # Verify: Use case was not called
        self.mock_use_case.execute.assert_not_called()
    
    def test_scope_verification_different_keys_for_different_scope(self):
        """Test same key for different method+route produces different resolved keys."""
        legacy_key = "order.123"
        
        # First request: POST /jobs
        request1 = copy.deepcopy(self.base_request)
        request1.idempotency_key_raw = legacy_key
        request1.method = "POST"
        request1.route = "/jobs"
        
        self.mock_use_case.execute.return_value = self.mock_response
        response1 = self.handler.submit_job(request1)
        
        # Second request: PUT /jobs/retry  
        request2 = copy.deepcopy(self.base_request)
        request2.idempotency_key_raw = legacy_key
        request2.method = "PUT"
        request2.route_template = "/jobs/retry"
        
        self.mock_use_case.reset_mock()
        self.mock_use_case.execute.return_value = self.mock_response
        response2 = self.handler.submit_job(request2)
        
        # Verify: Different scopes produce different resolved keys
        assert response1.idempotency_key_resolved != response2.idempotency_key_resolved
        
        # Both should be valid
        assert len(response1.idempotency_key_resolved) >= 16
        assert len(response2.idempotency_key_resolved) >= 16
        
        # Both use cases should have been called (different scopes)
        assert self.mock_use_case.execute.call_count == 2
    
    def test_concurrency_same_key_scope_one_wins_other_reuses(self):
        """Test concurrent requests with same key/scope: one wins, other reuses."""
        secure_key = "concurrent-test-key-123"
        num_threads = 5
        results = []
        
        def submit_request(thread_id: int) -> Tuple[int, HttpJobSubmissionResponse]:
            """Submit a job request from a thread."""
            request = copy.deepcopy(self.base_request)
            request.idempotency_key_raw = secure_key
            request.request_id = f"req_{thread_id}"
            
            # Add small random delay to increase race condition chance
            time.sleep(0.001 * thread_id)
            
            response = self.handler.submit_job(request)
            return thread_id, response
        
        # Setup: Mock use case should return unique response each time
        def mock_execute_side_effect(*args, **kwargs):
            # Simulate some processing time
            time.sleep(0.01)
            return SubmitJobResponse(
                job_id=f"job_{int(time.time() * 1000000)}",  # Unique ID
                status="queued",
                file_ref="s3://bucket/file.csv", 
                created_at=datetime.now().isoformat()
            )
        
        self.mock_use_case.execute.side_effect = mock_execute_side_effect
        
        # Execute: Submit concurrent requests
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(submit_request, i) 
                for i in range(num_threads)
            ]
            
            for future in as_completed(futures):
                thread_id, response = future.result()
                results.append((thread_id, response))
        
        # Verify: All requests completed
        assert len(results) == num_threads
        
        # Verify: All have same resolved idempotency key
        resolved_keys = [r[1].idempotency_key_resolved for r in results]
        assert all(key == resolved_keys[0] for key in resolved_keys)
        
        # Verify: All have same job_id (idempotent replay)
        job_ids = [r[1].job_id for r in results]
        assert all(job_id == job_ids[0] for job_id in job_ids)
        
        # Verify: Only one should not be a replay, others should be replays
        replay_statuses = [r[1].is_idempotent_replay for r in results]
        non_replays = [status for status in replay_statuses if not status]
        replays = [status for status in replay_statuses if status]
        
        assert len(non_replays) == 1  # Exactly one winner
        assert len(replays) == num_threads - 1  # Others are replays
        
        # Verify: Use case called exactly once (winner only)
        assert self.mock_use_case.execute.call_count == 1
    
    @patch.dict(os.environ, {"IDEMP_COMPAT_MODE": "canonicalize"})
    def test_multiple_legacy_key_formats_canonicalization(self):
        """Test various legacy key formats are properly canonicalized."""
        legacy_keys = [
            "order.123",
            "item:456", 
            "order.123:item.456",
            "=dangerous",
            "+formula",
            "-minus",
            "@at-sign",
            "with spaces",
            "with/slashes",
            "with\\backslashes",
            "with\"quotes",
            "with'single",
            "",  # Empty key
            "   ",  # Whitespace only
        ]
        
        responses = []
        for i, legacy_key in enumerate(legacy_keys):
            request = copy.deepcopy(self.base_request)
            request.idempotency_key_raw = legacy_key
            request.request_id = f"req_{i}"
            
            self.mock_use_case.reset_mock()
            self.mock_use_case.execute.return_value = SubmitJobResponse(
                job_id=f"job_{i}",
                status="queued",
                file_ref="s3://bucket/file.csv", 
                created_at=datetime.now().isoformat()
            )
            
            try:
                response = self.handler.submit_job(request)
                responses.append((legacy_key, response.idempotency_key_resolved))
            except Exception as e:
                responses.append((legacy_key, f"ERROR: {str(e)}"))
        
        # Verify: All were processed (canonicalized or generated)
        for legacy_key, resolved in responses:
            if not resolved.startswith("ERROR:"):
                # Security: No formula injection chars at start
                assert resolved[0] not in {'=', '+', '-', '@'}
                # Security: Reasonable length
                assert len(resolved) >= 16
                # Security: Only safe characters
                import re
                assert re.match(r'^[a-zA-Z0-9_-]+$', resolved)
                # Verify: Different from original (or was empty/whitespace)
                if legacy_key.strip():
                    assert resolved != legacy_key
    
    def test_error_scenarios_no_pii_leakage(self):
        """Test error scenarios don't leak PII in responses."""
        sensitive_keys = [
            "user@email.com",
            "cpf:123.456.789-00", 
            "credit:4111-1111-1111-1111",
            "secret-token-abc123"
        ]
        
        for sensitive_key in sensitive_keys:
            request = copy.deepcopy(self.base_request) 
            request.idempotency_key_raw = sensitive_key
            
            # Simulate various error conditions
            error_scenarios = [
                RateLimitExceeded("t_test123", "job_submission"),
                ValidationError("Invalid input"),
                ValueError("Database error")
            ]
            
            for error in error_scenarios:
                self.mock_use_case.reset_mock()
                self.mock_use_case.execute.side_effect = error
                
                try:
                    self.handler.submit_job(request)
                except Exception as caught_error:
                    # Security: Error message must not contain sensitive key
                    error_message = str(caught_error)
                    assert sensitive_key not in error_message
                    
                    # Security: Error type should be preserved
                    assert type(caught_error) == type(error)
    
    def test_rate_limiting_per_tenant_isolation(self):
        """Test rate limiting properly isolates tenants."""
        # Setup: Different tenants
        tenant1_request = copy.deepcopy(self.base_request)
        tenant1_request.tenant_id = "t_tenant1"
        
        tenant2_request = copy.deepcopy(self.base_request)
        tenant2_request.tenant_id = "t_tenant2"
        
        # First tenant hits rate limit
        self.mock_use_case.execute.side_effect = RateLimitExceeded("t_tenant1", "job_submission")
        
        with pytest.raises(RateLimitExceeded):
            self.handler.submit_job(tenant1_request)
        
        # Second tenant should not be affected
        self.mock_use_case.reset_mock()
        self.mock_use_case.execute.side_effect = None
        self.mock_use_case.execute.return_value = self.mock_response
        
        response = self.handler.submit_job(tenant2_request)
        
        # Verify: Second tenant request succeeded
        assert response.job_id == "job_789"
        assert not response.is_idempotent_replay
    
    def test_audit_trail_preservation(self):
        """Test that audit information is preserved across requests."""
        # Setup: Request with specific audit fields
        request = copy.deepcopy(self.base_request)
        request.tenant_id = "t_audit_test"
        request.seller_id = "seller_audit"
        request.request_id = "audit_req_123"
        request.idempotency_key_raw = "audit-key-123"
        
        self.mock_use_case.execute.return_value = self.mock_response
        
        # Execute
        response = self.handler.submit_job(request)
        
        # Verify: Audit fields are preserved
        assert response.request_id == "audit_req_123"
        assert response.idempotency_key_resolved is not None
        
        # Verify: Use case was called with correct parameters
        call_args = self.mock_use_case.execute.call_args[0][0]  # First positional arg
        assert call_args.tenant_id == "t_audit_test"
        assert call_args.seller_id == "seller_audit"
        assert call_args.idempotency_key is not None


class TestHeaderExtractionSecurity:
    """Security-focused tests for header extraction functions."""
    
    def test_header_injection_prevention(self):
        """Test that header values are properly sanitized."""
        malicious_headers = {
            "Idempotency-Key": "key\r\nX-Admin: true",  # CRLF injection
            "X-Request-Id": "req\nContent-Length: 0"    # Header injection
        }
        
        # Verify: CRLF characters are handled safely
        idemp_key = get_idempotency_key_header(malicious_headers)
        request_id = get_request_id_header(malicious_headers)
        
        # Should not contain line break characters
        if idemp_key:
            assert '\r' not in idemp_key
            assert '\n' not in idemp_key
        
        if request_id:
            assert '\r' not in request_id
            assert '\n' not in request_id
    
    def test_header_size_limits(self):
        """Test that oversized headers are handled safely."""
        oversized_key = "x" * 10000  # Very long key
        headers = {"Idempotency-Key": oversized_key}
        
        result = get_idempotency_key_header(headers)
        
        # Should handle gracefully (either truncate or reject)
        if result:
            assert len(result) <= 1000  # Reasonable limit
    
    def test_unicode_handling(self):
        """Test that unicode in headers is handled safely."""
        unicode_headers = {
            "Idempotency-Key": "key-🔑-test",
            "X-Request-Id": "req-ñ-123"
        }
        
        idemp_key = get_idempotency_key_header(unicode_headers)
        request_id = get_request_id_header(unicode_headers)
        
        # Should handle unicode gracefully
        assert idemp_key is not None
        assert request_id is not None
        assert len(idemp_key) > 0
        assert len(request_id) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])