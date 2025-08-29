"""Unit tests for jobs HTTP handler with idempotency."""

import os
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

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


class TestJobsHttpHandler:
    """Test cases for JobsHttpHandler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_use_case = Mock()
        self.idempotency_store = InMemoryIdempotencyStore()
        self.handler = JobsHttpHandler(self.mock_use_case, self.idempotency_store)
        
        self.request = HttpJobSubmissionRequest(
            tenant_id="t_test123",
            seller_id="seller_456",
            channel="mercado_livre",
            job_type="validation",
            file_ref="s3://bucket/file.csv",
            rules_profile_id="ml@1.0.0",
            idempotency_key_raw=None,
            request_id="req_123"
        )
        
        self.mock_response = SubmitJobResponse(
            job_id="job_789",
            status="queued",
            file_ref="s3://bucket/file.csv",
            created_at=datetime.now().isoformat()
        )
    
    def test_submit_job_success_new_request(self):
        """Test successful job submission with new request."""
        self.mock_use_case.execute.return_value = self.mock_response
        
        response = self.handler.submit_job(self.request)
        
        assert isinstance(response, HttpJobSubmissionResponse)
        assert response.job_id == "job_789"
        assert response.status == "queued"
        assert response.file_ref == "s3://bucket/file.csv"
        assert response.request_id == "req_123"
        assert not response.is_idempotent_replay
        assert len(response.idempotency_key_resolved) >= 16
        
        # Use case should have been called
        self.mock_use_case.execute.assert_called_once()
    
    def test_submit_job_with_secure_idempotency_key(self):
        """Test job submission with secure idempotency key."""
        secure_key = "secure-key-1234567890"
        self.request.idempotency_key_raw = secure_key
        self.mock_use_case.execute.return_value = self.mock_response
        
        response = self.handler.submit_job(self.request)
        
        assert response.idempotency_key_resolved == secure_key
        assert not response.is_idempotent_replay
    
    @patch.dict(os.environ, {"IDEMP_COMPAT_MODE": "canonicalize"})
    def test_submit_job_with_legacy_key_canonicalized(self):
        """Test job submission with legacy key that gets canonicalized."""
        legacy_key = "order.123:item"
        self.request.idempotency_key_raw = legacy_key
        self.mock_use_case.execute.return_value = self.mock_response
        
        response = self.handler.submit_job(self.request)
        
        # Should be canonicalized
        assert response.idempotency_key_resolved != legacy_key
        assert len(response.idempotency_key_resolved) >= 16
        assert response.idempotency_key_resolved[0] not in {'=', '+', '-', '@'}
        assert not response.is_idempotent_replay
    
    @patch.dict(os.environ, {"IDEMP_COMPAT_MODE": "reject"})
    def test_submit_job_with_legacy_key_rejected(self):
        """Test job submission with legacy key that gets rejected."""
        legacy_key = "order.123"
        self.request.idempotency_key_raw = legacy_key
        
        with pytest.raises(ValidationError, match="Invalid idempotency key format"):
            self.handler.submit_job(self.request)
        
        # Use case should not have been called
        self.mock_use_case.execute.assert_not_called()
    
    def test_submit_job_formula_char_canonicalized(self):
        """Test job submission with key starting with formula character."""
        dangerous_key = "=validkey1234567890"
        self.request.idempotency_key_raw = dangerous_key
        self.mock_use_case.execute.return_value = self.mock_response
        
        response = self.handler.submit_job(self.request)
        
        # Should be canonicalized and safe
        assert response.idempotency_key_resolved != dangerous_key
        assert response.idempotency_key_resolved[0] not in {'=', '+', '-', '@'}
        assert not response.is_idempotent_replay
    
    def test_submit_job_idempotent_replay(self):
        """Test idempotent replay of existing request."""
        # First request
        secure_key = "secure-key-1234567890"
        self.request.idempotency_key_raw = secure_key
        self.mock_use_case.execute.return_value = self.mock_response
        
        response1 = self.handler.submit_job(self.request)
        
        # Second request with same key (should replay)
        self.mock_use_case.reset_mock()
        response2 = self.handler.submit_job(self.request)
        
        # Should be identical responses
        assert response2.job_id == response1.job_id
        assert response2.status == response1.status
        assert response2.idempotency_key_resolved == response1.idempotency_key_resolved
        assert response2.is_idempotent_replay  # This should be True for replay
        
        # Use case should only be called once
        self.mock_use_case.execute.assert_not_called()
    
    def test_submit_job_rate_limit_exceeded(self):
        """Test job submission with rate limit exceeded."""
        self.mock_use_case.execute.side_effect = RateLimitExceeded("t_test123", "job_submission")
        
        with pytest.raises(RateLimitExceeded):
            self.handler.submit_job(self.request)
    
    def test_submit_job_validation_error(self):
        """Test job submission with validation error."""
        self.mock_use_case.execute.side_effect = ValidationError("input", "Invalid input")
        
        with pytest.raises(ValidationError):
            self.handler.submit_job(self.request)
    
    def test_submit_job_invalid_tenant_id(self):
        """Test job submission with invalid tenant ID."""
        self.request.tenant_id = "invalid-tenant"  # Missing t_ prefix
        
        with pytest.raises(ValueError, match="Invalid tenant id format"):
            self.handler.submit_job(self.request)
    
    def test_submit_job_idempotency_race_condition(self):
        """Test handling of idempotency race condition."""
        # Mock the store to raise conflict error
        mock_store = Mock()
        mock_store.get.return_value = None  # No existing record
        mock_store.put.side_effect = IdempotencyConflictError("t_test123", "key123")
        
        handler = JobsHttpHandler(self.mock_use_case, mock_store)
        self.mock_use_case.execute.return_value = self.mock_response
        
        # Should complete successfully despite race condition
        response = self.handler.submit_job(self.request)
        
        assert response.job_id == "job_789"
        assert not response.is_idempotent_replay
    
    def test_submit_job_generates_request_id_if_missing(self):
        """Test that request ID is generated if not provided."""
        self.request.request_id = None
        self.mock_use_case.execute.return_value = self.mock_response
        
        response = self.handler.submit_job(self.request)
        
        assert response.request_id is not None
        assert len(response.request_id) > 0
    
    def test_submit_job_scope_isolation(self):
        """Test that different HTTP scopes produce different keys."""
        legacy_key = "order.123"
        self.request.idempotency_key_raw = legacy_key
        self.mock_use_case.execute.return_value = self.mock_response
        
        # Same key for different methods should resolve differently
        self.request.method = "POST"
        response1 = self.handler.submit_job(self.request)
        
        self.request.method = "PUT"
        response2 = self.handler.submit_job(self.request)
        
        assert response1.idempotency_key_resolved != response2.idempotency_key_resolved
    
    def test_submit_job_no_pii_leakage_in_errors(self):
        """Test that error responses don't leak PII from idempotency keys."""
        sensitive_key = "user@email.com"
        self.request.idempotency_key_raw = sensitive_key
        
        # Simulate validation error
        self.mock_use_case.execute.side_effect = ValidationError("database", "Database connection failed")
        
        with pytest.raises(ValidationError) as exc_info:
            self.handler.submit_job(self.request)
        
        # Error message must not contain the sensitive key
        error_message = str(exc_info.value)
        assert sensitive_key not in error_message
        assert "user@" not in error_message  # Partial check too
    
    def test_submit_job_csv_formula_injection_prevention(self):
        """Test prevention of CSV formula injection through idempotency keys."""
        formula_chars = ['=', '+', '-', '@']
        
        for char in formula_chars:
            # Test each formula character individually
                dangerous_key = f"{char}SUM(A1:A10)"
                self.request.idempotency_key_raw = dangerous_key
                self.mock_use_case.execute.return_value = self.mock_response
                
                response = self.handler.submit_job(self.request)
                
                # Key should be canonicalized to be safe
                assert response.idempotency_key_resolved != dangerous_key
                assert response.idempotency_key_resolved[0] not in formula_chars
                
                self.mock_use_case.reset_mock()
    
    @patch.dict(os.environ, {"IDEMP_COMPAT_MODE": "reject"})
    def test_submit_job_reject_mode_security(self):
        """Test security aspects of reject mode."""
        test_cases = [
            ("order.123:item", "colon character"),
            ("key with spaces", "spaces"),
            ("+formula", "formula character"),
            ("key/with/slashes", "slashes"),
            ("key\\with\\backslashes", "backslashes")
        ]
        
        for invalid_key, description in test_cases:
            with self.subTest(key=description):
                self.request.idempotency_key_raw = invalid_key
                
                with pytest.raises(ValidationError) as exc_info:
                    self.handler.submit_job(self.request)
                
                # Ensure no key value leakage
                error_message = str(exc_info.value)
                assert invalid_key not in error_message
                assert "Invalid idempotency key format" in error_message
    
    def test_submit_job_concurrent_safety(self):
        """Test basic concurrent safety for idempotency."""
        import threading
        import time
        from concurrent.futures import ThreadPoolExecutor
        
        secure_key = "concurrent-test-key"
        num_threads = 3
        results = []
        
        def submit_concurrent_request(thread_id):
            request = HttpJobSubmissionRequest(
                tenant_id="t_test123",
                seller_id="seller_456",
                channel="mercado_livre",
                job_type="validation",
                file_ref="s3://bucket/file.csv",
                rules_profile_id="ml@1.0.0",
                idempotency_key_raw=secure_key,
                request_id=f"req_{thread_id}"
            )
            
            # Small delay to increase race condition likelihood
            time.sleep(0.001 * thread_id)
            return self.handler.submit_job(request)
        
        # Mock use case with processing delay
        def slow_execute(*args, **kwargs):
            time.sleep(0.01)  # Simulate processing
            return self.mock_response
        
        self.mock_use_case.execute.side_effect = slow_execute
        
        # Execute concurrent requests
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(submit_concurrent_request, i) for i in range(num_threads)]
            results = [future.result() for future in futures]
        
        # All should have same resolved key
        resolved_keys = [r.idempotency_key_resolved for r in results]
        assert all(key == resolved_keys[0] for key in resolved_keys)
        
        # All should have same job_id (idempotent)
        job_ids = [r.job_id for r in results]
        assert all(job_id == job_ids[0] for job_id in job_ids)
        
        # Only one should be original, others replays
        replay_count = sum(1 for r in results if r.is_idempotent_replay)
        original_count = sum(1 for r in results if not r.is_idempotent_replay)
        
        assert original_count == 1
        assert replay_count == num_threads - 1


class TestHttpJobSubmissionResponse:
    """Test cases for HttpJobSubmissionResponse."""
    
    def test_to_dict_new_request(self):
        """Test converting new request response to dict."""
        response = HttpJobSubmissionResponse(
            job_id="job_789",
            status="queued",
            file_ref="s3://bucket/file.csv",
            created_at="2023-12-01T10:00:00Z",
            idempotency_key_resolved="key123",
            request_id="req_123",
            is_idempotent_replay=False
        )
        
        result = response.to_dict()
        
        expected = {
            "job_id": "job_789",
            "status": "queued", 
            "file_ref": "s3://bucket/file.csv",
            "created_at": "2023-12-01T10:00:00Z",
            "meta": {
                "idempotency_key": "key123",
                "request_id": "req_123",
                "is_replay": False
            }
        }
        
        assert result == expected
    
    def test_to_dict_replay_request(self):
        """Test converting replay request response to dict."""
        response = HttpJobSubmissionResponse(
            job_id="job_789",
            status="queued",
            file_ref="s3://bucket/file.csv",
            created_at="2023-12-01T10:00:00Z",
            idempotency_key_resolved="key123",
            request_id="req_123",
            is_idempotent_replay=True
        )
        
        result = response.to_dict()
        
        assert result["meta"]["is_replay"] is True


class TestHeaderExtraction:
    """Test cases for header extraction functions."""
    
    def test_get_idempotency_key_header_primary(self):
        """Test extracting idempotency key from primary header."""
        headers = {"Idempotency-Key": "key123"}
        
        result = get_idempotency_key_header(headers)
        
        assert result == "key123"
    
    def test_get_idempotency_key_header_x_prefixed(self):
        """Test extracting idempotency key from X- prefixed header."""
        headers = {"X-Idempotency-Key": "key456"}
        
        result = get_idempotency_key_header(headers)
        
        assert result == "key456"
    
    def test_get_idempotency_key_header_legacy(self):
        """Test extracting idempotency key from legacy header."""
        headers = {"Idempotency-Token": "legacy_key"}
        
        result = get_idempotency_key_header(headers)
        
        assert result == "legacy_key"
    
    def test_get_idempotency_key_header_case_insensitive(self):
        """Test that header extraction is case insensitive."""
        headers = {"idempotency-key": "key123"}
        
        result = get_idempotency_key_header(headers)
        
        assert result == "key123"
    
    def test_get_idempotency_key_header_whitespace_trimmed(self):
        """Test that whitespace is trimmed from header value."""
        headers = {"Idempotency-Key": "  key123  "}
        
        result = get_idempotency_key_header(headers)
        
        assert result == "key123"
    
    def test_get_idempotency_key_header_priority(self):
        """Test header priority when multiple are present."""
        headers = {
            "Idempotency-Token": "legacy",
            "X-Idempotency-Key": "x_prefixed", 
            "Idempotency-Key": "primary"
        }
        
        result = get_idempotency_key_header(headers)
        
        # Should prefer primary header
        assert result == "primary"
    
    def test_get_idempotency_key_header_not_found(self):
        """Test when no idempotency key header is present."""
        headers = {"Content-Type": "application/json"}
        
        result = get_idempotency_key_header(headers)
        
        assert result is None
    
    def test_get_idempotency_key_header_empty_value(self):
        """Test when idempotency key header is empty."""
        headers = {"Idempotency-Key": ""}
        
        result = get_idempotency_key_header(headers)
        
        assert result is None
    
    def test_get_request_id_header(self):
        """Test extracting request ID from header."""
        headers = {"X-Request-Id": "req_123"}
        
        result = get_request_id_header(headers)
        
        assert result == "req_123"
    
    def test_get_request_id_header_alternative(self):
        """Test extracting request ID from alternative header."""
        headers = {"Request-Id": "req_456"}
        
        result = get_request_id_header(headers)
        
        assert result == "req_456"
    
    def test_get_request_id_header_not_found(self):
        """Test when no request ID header is present."""
        headers = {"Content-Type": "application/json"}
        
        result = get_request_id_header(headers)
        
        assert result is None
    
    def test_header_security_crlf_injection_prevention(self):
        """Test prevention of CRLF injection in headers."""
        malicious_headers = {
            "Idempotency-Key": "key\r\nX-Admin: true",  # CRLF injection attempt
            "X-Request-Id": "req\nContent-Length: 0"     # Header injection attempt
        }
        
        idemp_key = get_idempotency_key_header(malicious_headers)
        request_id = get_request_id_header(malicious_headers)
        
        # Should handle CRLF safely - either sanitize or reject
        if idemp_key:
            assert '\r' not in idemp_key
            assert '\n' not in idemp_key
            assert 'X-Admin' not in idemp_key
        
        if request_id:
            assert '\r' not in request_id
            assert '\n' not in request_id
            assert 'Content-Length' not in request_id
    
    def test_header_size_limits(self):
        """Test handling of oversized header values."""
        oversized_key = "x" * 10000  # Very long key
        headers = {"Idempotency-Key": oversized_key}
        
        result = get_idempotency_key_header(headers)
        
        # Should handle gracefully (truncate, reject, or accept with limits)
        if result:
            assert len(result) <= 1000  # Reasonable limit
    
    def test_header_unicode_handling(self):
        """Test safe handling of unicode in header values."""
        unicode_headers = {
            "Idempotency-Key": "key-🔑-test",
            "X-Request-Id": "req-ñ-123"
        }
        
        idemp_key = get_idempotency_key_header(unicode_headers)
        request_id = get_request_id_header(unicode_headers)
        
        # Should handle unicode gracefully
        if idemp_key:
            assert len(idemp_key) > 0
            # Could be sanitized or preserved
        
        if request_id:
            assert len(request_id) > 0
    
    def test_header_null_byte_handling(self):
        """Test handling of null bytes in header values."""
        null_byte_headers = {
            "Idempotency-Key": "key\x00admin",
            "X-Request-Id": "req\x00123"
        }
        
        idemp_key = get_idempotency_key_header(null_byte_headers)
        request_id = get_request_id_header(null_byte_headers)
        
        # Should handle null bytes safely
        if idemp_key:
            assert '\x00' not in idemp_key
            assert 'admin' not in idemp_key or idemp_key == 'key'
        
        if request_id:
            assert '\x00' not in request_id
            assert request_id == 'req' or '123' not in request_id