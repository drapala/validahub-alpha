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
        self.mock_use_case.execute.side_effect = ValidationError("Invalid input")
        
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