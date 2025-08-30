"""Integration tests for Rules API endpoints.

These tests cover the Smart Rules Engine API endpoints with comprehensive
scenarios including validation, error handling, security, and multi-tenancy.
"""

import pytest
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, patch
from uuid import uuid4, UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from apps.api.routers.rules import router as rules_router
from src.application.use_cases.rules.create_rule import CreateRuleUseCase, CreateRuleResponse
from src.application.use_cases.rules.publish_rule import PublishRuleUseCase, PublishRuleResponse
from src.application.use_cases.rules.log_correction import LogCorrectionUseCase, LogCorrectionResponse
from src.application.use_cases.rules.get_suggestions import GetSuggestionsUseCase, GetSuggestionsResponse
from src.application.ports.rules import RuleRepository
from src.application.errors import ValidationError
from src.domain.value_objects import TenantId, Channel
from src.domain.rules.value_objects import RuleSetId, SemVer
from src.domain.rules.aggregates import RuleSet
from src.infrastructure.repositories.rules.rule_repository import InMemoryRuleRepository


class TestRulesAPIIntegration:
    """Integration tests for Rules API endpoints."""
    
    def setup_method(self):
        """Set up test fixtures for each test."""
        # Create FastAPI test app
        self.app = FastAPI()
        self.app.include_router(rules_router, prefix="/rules")
        
        # Mock use cases
        self.mock_create_use_case = Mock(spec=CreateRuleUseCase)
        self.mock_publish_use_case = Mock(spec=PublishRuleUseCase)
        self.mock_log_correction_use_case = Mock(spec=LogCorrectionUseCase)
        self.mock_suggestions_use_case = Mock(spec=GetSuggestionsUseCase)
        
        # Real repository for some tests
        self.rule_repository = InMemoryRuleRepository()
        
        # Patch dependency injection
        with patch('apps.api.routers.rules.get_create_rule_use_case', return_value=self.mock_create_use_case):
            with patch('apps.api.routers.rules.get_publish_rule_use_case', return_value=self.mock_publish_use_case):
                with patch('apps.api.routers.rules.get_log_correction_use_case', return_value=self.mock_log_correction_use_case):
                    with patch('apps.api.routers.rules.get_suggestions_use_case', return_value=self.mock_suggestions_use_case):
                        with patch('apps.api.routers.rules.get_rule_repository', return_value=self.rule_repository):
                            self.client = TestClient(self.app)
        
        # Test data
        self.tenant_id = "t_company_123"
        self.headers = {
            "X-Tenant-Id": self.tenant_id,
            "Content-Type": "application/json",
            "X-Request-Id": "req_123"
        }
        
        self.rule_set_id = str(uuid4())
        self.sample_rules = [
            {
                "id": "product_title_required",
                "type": "required",
                "field": "title",
                "condition": {},
                "message": "Product title is required",
                "severity": "error"
            },
            {
                "id": "product_title_length",
                "type": "length",
                "field": "title",
                "condition": {"min": 10, "max": 60},
                "message": "Title must be between 10 and 60 characters",
                "severity": "warning"
            }
        ]
    
    def test_create_rule_set_success(self):
        """Test successful rule set creation."""
        # Setup
        create_request = {
            "name": "mercado_livre_rules",
            "channel": "mercado_livre",
            "version": "1.0.0",
            "description": "Product validation rules",
            "rules": self.sample_rules
        }
        
        mock_response = CreateRuleResponse(
            rule_set_id=self.rule_set_id,
            name="mercado_livre_rules",
            version="1.0.0",
            status="draft",
            rules_count=2,
            created_at=datetime.now(timezone.utc).isoformat(),
            validation_errors=[]
        )
        self.mock_create_use_case.execute.return_value = mock_response
        
        # Execute
        with patch('apps.api.routers.rules.get_create_rule_use_case', return_value=self.mock_create_use_case):
            response = self.client.post(
                "/rules",
                json=create_request,
                headers=self.headers
            )
        
        # Verify
        assert response.status_code == 201
        
        data = response.json()
        assert data["rule_set_id"] == self.rule_set_id
        assert data["name"] == "mercado_livre_rules"
        assert data["version"] == "1.0.0"
        assert data["status"] == "draft"
        assert data["rules_count"] == 2
        assert data["validation_errors"] == []
        
        # Verify use case was called correctly
        self.mock_create_use_case.execute.assert_called_once()
        call_args = self.mock_create_use_case.execute.call_args[0][0]
        assert call_args.tenant_id == self.tenant_id
        assert call_args.name == "mercado_livre_rules"
        assert call_args.channel == "mercado_livre"
        assert call_args.version == "1.0.0"
        assert len(call_args.rules) == 2
    
    def test_create_rule_set_with_idempotency(self):
        """Test rule set creation with idempotency key."""
        headers = {**self.headers, "Idempotency-Key": "create-rule-key-12345"}
        
        create_request = {
            "name": "test_rules",
            "channel": "test_channel",
            "version": "1.0.0",
            "rules": self.sample_rules
        }
        
        mock_response = CreateRuleResponse(
            rule_set_id=self.rule_set_id,
            name="test_rules",
            version="1.0.0",
            status="draft",
            rules_count=2,
            created_at=datetime.now(timezone.utc).isoformat(),
            validation_errors=[]
        )
        self.mock_create_use_case.execute.return_value = mock_response
        
        # Execute
        with patch('apps.api.routers.rules.get_create_rule_use_case', return_value=self.mock_create_use_case):
            response = self.client.post(
                "/rules",
                json=create_request,
                headers=headers
            )
        
        # Verify
        assert response.status_code == 201
        self.mock_create_use_case.execute.assert_called_once()
    
    def test_create_rule_set_validation_error(self):
        """Test rule set creation with validation errors."""
        invalid_request = {
            "name": "",  # Invalid empty name
            "channel": "mercado_livre",
            "version": "invalid",  # Invalid version format
            "rules": []  # No rules provided
        }
        
        self.mock_create_use_case.execute.side_effect = ValidationError("name is required")
        
        # Execute
        with patch('apps.api.routers.rules.get_create_rule_use_case', return_value=self.mock_create_use_case):
            response = self.client.post(
                "/rules",
                json=invalid_request,
                headers=self.headers
            )
        
        # Verify
        assert response.status_code == 422
        assert "name is required" in response.json()["detail"]
    
    def test_create_rule_set_missing_tenant_header(self):
        """Test rule set creation without tenant header."""
        create_request = {
            "name": "test_rules",
            "channel": "test_channel",
            "version": "1.0.0",
            "rules": self.sample_rules
        }
        
        headers = {k: v for k, v in self.headers.items() if k != "X-Tenant-Id"}
        
        # Execute
        response = self.client.post("/rules", json=create_request, headers=headers)
        
        # Verify
        assert response.status_code == 422  # FastAPI validation error
    
    def test_create_rule_set_invalid_idempotency_key(self):
        """Test rule set creation with invalid idempotency key."""
        headers = {**self.headers, "Idempotency-Key": "short"}  # Too short
        
        create_request = {
            "name": "test_rules",
            "channel": "test_channel",
            "version": "1.0.0",
            "rules": self.sample_rules
        }
        
        # Execute
        response = self.client.post("/rules", json=create_request, headers=headers)
        
        # Verify
        assert response.status_code == 400
        assert "Idempotency-Key must be between 16 and 128 characters" in response.json()["detail"]
    
    def test_publish_rule_version_success(self):
        """Test successful rule version publication."""
        publish_request = {"make_current": True}
        
        mock_response = PublishRuleResponse(
            rule_set_id=self.rule_set_id,
            name="test_rules",
            version="1.0.0",
            status="published",
            is_current=True,
            checksum="sha256:abc123",
            published_at=datetime.now(timezone.utc).isoformat(),
            compilation_errors=[]
        )
        self.mock_publish_use_case.execute.return_value = mock_response
        
        # Execute
        with patch('apps.api.routers.rules.get_publish_rule_use_case', return_value=self.mock_publish_use_case):
            response = self.client.put(
                f"/rules/{self.rule_set_id}/publish/1.0.0",
                json=publish_request,
                headers=self.headers
            )
        
        # Verify
        assert response.status_code == 200
        
        data = response.json()
        assert data["rule_set_id"] == self.rule_set_id
        assert data["version"] == "1.0.0"
        assert data["status"] == "published"
        assert data["is_current"] is True
        assert data["checksum"] == "sha256:abc123"
        assert data["compilation_errors"] == []
        
        # Verify use case was called correctly
        self.mock_publish_use_case.execute.assert_called_once()
        call_args = self.mock_publish_use_case.execute.call_args[0][0]
        assert call_args.tenant_id == self.tenant_id
        assert call_args.rule_set_id == self.rule_set_id
        assert call_args.version == "1.0.0"
        assert call_args.make_current is True
    
    def test_publish_rule_version_invalid_uuid(self):
        """Test publishing with invalid rule set ID."""
        publish_request = {"make_current": True}
        
        # Execute
        response = self.client.put(
            "/rules/invalid-uuid/publish/1.0.0",
            json=publish_request,
            headers=self.headers
        )
        
        # Verify
        assert response.status_code == 422  # Validation error for invalid UUID
    
    def test_publish_rule_version_invalid_version_format(self):
        """Test publishing with invalid version format."""
        publish_request = {"make_current": True}
        
        # Execute
        response = self.client.put(
            f"/rules/{self.rule_set_id}/publish/invalid-version",
            json=publish_request,
            headers=self.headers
        )
        
        # Verify
        assert response.status_code == 422  # Validation error for invalid version
    
    def test_log_correction_success(self):
        """Test successful correction logging."""
        correction_request = {
            "field": "title",
            "original_value": "iPhone 12 64Gb",
            "corrected_value": "iPhone 12 64GB",
            "rule_set_id": self.rule_set_id,
            "job_id": "job_123",
            "seller_id": "seller_456",
            "channel": "mercado_livre"
        }
        
        mock_response = LogCorrectionResponse(
            correction_id="corr_abc123",
            tenant_id=self.tenant_id,
            field="title",
            original_value="iPhone 12 64Gb",
            corrected_value="iPhone 12 64GB",
            logged_at=datetime.now(timezone.utc).isoformat(),
            learning_applied=True
        )
        self.mock_log_correction_use_case.execute.return_value = mock_response
        
        # Execute
        with patch('apps.api.routers.rules.get_log_correction_use_case', return_value=self.mock_log_correction_use_case):
            response = self.client.post(
                "/rules/corrections/log",
                json=correction_request,
                headers={**self.headers, "Idempotency-Key": "log-correction-key-123"}
            )
        
        # Verify
        assert response.status_code == 201
        
        data = response.json()
        assert data["correction_id"] == "corr_abc123"
        assert data["field"] == "title"
        assert data["original_value"] == "iPhone 12 64Gb"
        assert data["corrected_value"] == "iPhone 12 64GB"
        assert data["learning_applied"] is True
        
        # Verify use case was called correctly
        self.mock_log_correction_use_case.execute.assert_called_once()
        call_args = self.mock_log_correction_use_case.execute.call_args[0][0]
        assert call_args.tenant_id == self.tenant_id
        assert call_args.field == "title"
        assert call_args.original_value == "iPhone 12 64Gb"
        assert call_args.corrected_value == "iPhone 12 64GB"
    
    def test_log_correction_same_values(self):
        """Test correction logging with same original and corrected values."""
        correction_request = {
            "field": "title",
            "original_value": "iPhone 12 64GB",
            "corrected_value": "iPhone 12 64GB"  # Same as original
        }
        
        # Execute
        response = self.client.post(
            "/rules/corrections/log",
            json=correction_request,
            headers=self.headers
        )
        
        # Verify
        assert response.status_code == 422  # Pydantic validation error
    
    def test_get_suggestions_success(self):
        """Test successful rule suggestions retrieval."""
        suggestions_request = {
            "field": "price",
            "channel": "mercado_livre",
            "current_rules": ["price_required"],
            "context": {"category": "electronics"}
        }
        
        mock_suggestions = [
            {
                "rule_id": "price_range",
                "rule_type": "range",
                "field": "price",
                "condition": {"min": 0.01, "max": 999999.99},
                "message": "Price must be between $0.01 and $999,999.99",
                "severity": "error",
                "confidence_score": 0.92,
                "reason": "Based on similar product categories",
                "examples": ["0", "-10", "1000000"]
            }
        ]
        
        mock_response = GetSuggestionsResponse(
            tenant_id=self.tenant_id,
            field="price",
            suggestions=mock_suggestions,
            total_suggestions=1
        )
        self.mock_suggestions_use_case.execute.return_value = mock_response
        
        # Execute
        with patch('apps.api.routers.rules.get_suggestions_use_case', return_value=self.mock_suggestions_use_case):
            response = self.client.post(
                "/rules/suggestions",
                json=suggestions_request,
                headers=self.headers
            )
        
        # Verify
        assert response.status_code == 200
        
        data = response.json()
        assert data["tenant_id"] == self.tenant_id
        assert data["field"] == "price"
        assert data["total_suggestions"] == 1
        assert len(data["suggestions"]) == 1
        
        suggestion = data["suggestions"][0]
        assert suggestion["rule_id"] == "price_range"
        assert suggestion["rule_type"] == "range"
        assert suggestion["confidence_score"] == 0.92
        
        # Verify use case was called correctly
        self.mock_suggestions_use_case.execute.assert_called_once()
        call_args = self.mock_suggestions_use_case.execute.call_args[0][0]
        assert call_args.tenant_id == self.tenant_id
        assert call_args.field == "price"
        assert call_args.channel == "mercado_livre"
        assert call_args.current_rules == ["price_required"]
    
    def test_list_rule_sets_empty(self):
        """Test listing rule sets when none exist."""
        # Execute
        with patch('apps.api.routers.rules.get_rule_repository', return_value=self.rule_repository):
            response = self.client.get("/rules", headers=self.headers)
        
        # Verify
        assert response.status_code == 200
        
        data = response.json()
        assert data["data"] == []
        assert data["meta"]["total"] == 0
        assert data["meta"]["limit"] == 20
        assert data["meta"]["offset"] == 0
        assert data["meta"]["has_more"] is False
    
    def test_list_rule_sets_with_data(self):
        """Test listing rule sets with existing data."""
        # Setup: Add rule set to repository
        from src.domain.rules.entities import RuleVersion
        from src.domain.rules.value_objects import (
            RuleSetId, RuleVersionId, RuleDefinition, RuleId, RuleType, 
            SemVer, RuleStatus, RuleMetadata
        )
        
        rule_set = RuleSet.create(
            tenant_id=TenantId(self.tenant_id),
            channel=Channel("mercado_livre"),
            name="test_rules",
            description="Test rules",
            created_by="api"
        )
        
        # Add a version
        rule_def = RuleDefinition(
            id=RuleId("test_rule"),
            type=RuleType.REQUIRED,
            field="title",
            condition={},
            message="Title is required",
            severity="error"
        )
        
        metadata = RuleMetadata(
            created_by="api",
            created_at=datetime.now(timezone.utc)
        )
        
        rule_version = RuleVersion.create(
            id=RuleVersionId(uuid4()),
            version=SemVer(1, 0, 0),
            rules=[rule_def],
            metadata=metadata,
            created_by="api"
        )
        
        rule_set_with_version = rule_set.add_version(rule_version, "api")
        self.rule_repository.save(rule_set_with_version)
        
        # Execute
        with patch('apps.api.routers.rules.get_rule_repository', return_value=self.rule_repository):
            response = self.client.get("/rules", headers=self.headers)
        
        # Verify
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["data"]) == 1
        assert data["meta"]["total"] == 1
        
        rule_set_data = data["data"][0]
        assert rule_set_data["name"] == "test_rules"
        assert rule_set_data["channel"] == "mercado_livre"
        assert len(rule_set_data["versions"]) == 1
    
    def test_get_rule_set_not_found(self):
        """Test getting rule set that doesn't exist."""
        non_existent_id = str(uuid4())
        
        # Execute
        with patch('apps.api.routers.rules.get_rule_repository', return_value=self.rule_repository):
            response = self.client.get(f"/rules/{non_existent_id}", headers=self.headers)
        
        # Verify
        assert response.status_code == 404
        assert f"Rule set {non_existent_id} not found" in response.json()["detail"]
    
    def test_tenant_isolation_different_tenants(self):
        """Test that tenant isolation works correctly."""
        tenant1_headers = {**self.headers, "X-Tenant-Id": "t_tenant1"}
        tenant2_headers = {**self.headers, "X-Tenant-Id": "t_tenant2"}
        
        # Create rule set for tenant1
        create_request = {
            "name": "tenant1_rules",
            "channel": "test_channel",
            "version": "1.0.0",
            "rules": self.sample_rules
        }
        
        mock_response = CreateRuleResponse(
            rule_set_id=self.rule_set_id,
            name="tenant1_rules",
            version="1.0.0",
            status="draft",
            rules_count=2,
            created_at=datetime.now(timezone.utc).isoformat(),
            validation_errors=[]
        )
        self.mock_create_use_case.execute.return_value = mock_response
        
        # Create for tenant1
        with patch('apps.api.routers.rules.get_create_rule_use_case', return_value=self.mock_create_use_case):
            response1 = self.client.post("/rules", json=create_request, headers=tenant1_headers)
        
        # Create for tenant2
        self.mock_create_use_case.reset_mock()
        with patch('apps.api.routers.rules.get_create_rule_use_case', return_value=self.mock_create_use_case):
            response2 = self.client.post("/rules", json=create_request, headers=tenant2_headers)
        
        # Verify both requests succeeded
        assert response1.status_code == 201
        assert response2.status_code == 201
        
        # Verify use case was called with different tenant IDs
        assert self.mock_create_use_case.execute.call_count == 2
        call_args_list = [call[0][0] for call in self.mock_create_use_case.execute.call_args_list]
        assert call_args_list[0].tenant_id == "t_tenant1"
        assert call_args_list[1].tenant_id == "t_tenant2"
    
    def test_security_sql_injection_attempts(self):
        """Test API security against SQL injection attempts."""
        malicious_payloads = [
            "'; DROP TABLE rules; --",
            "1' OR '1'='1",
            "admin'/**/OR/**/'1'='1",
            "<script>alert('xss')</script>",
            "../../../etc/passwd"
        ]
        
        for payload in malicious_payloads:
            create_request = {
                "name": payload,  # Malicious name
                "channel": "test_channel",
                "version": "1.0.0",
                "rules": self.sample_rules
            }
            
            # Should either validate/sanitize or return validation error
            with patch('apps.api.routers.rules.get_create_rule_use_case', return_value=self.mock_create_use_case):
                response = self.client.post("/rules", json=create_request, headers=self.headers)
            
            # Should not cause server error
            assert response.status_code in [201, 400, 422]
    
    def test_rate_limiting_headers(self):
        """Test that rate limiting information is available."""
        # This is a placeholder test - actual rate limiting would be implemented
        # at the middleware level and would require additional setup
        
        # Execute a request
        with patch('apps.api.routers.rules.get_rule_repository', return_value=self.rule_repository):
            response = self.client.get("/rules", headers=self.headers)
        
        # Verify basic response
        assert response.status_code == 200
        
        # In a real implementation, you might check for rate limit headers:
        # assert "X-RateLimit-Limit" in response.headers
        # assert "X-RateLimit-Remaining" in response.headers
    
    def test_concurrent_rule_creation_different_names(self):
        """Test concurrent rule creation with different names."""
        import threading
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def create_rule_set(name_suffix: str) -> Response:
            """Create a rule set with a unique name."""
            create_request = {
                "name": f"concurrent_rules_{name_suffix}",
                "channel": "test_channel",
                "version": "1.0.0",
                "rules": self.sample_rules
            }
            
            mock_response = CreateRuleResponse(
                rule_set_id=str(uuid4()),
                name=f"concurrent_rules_{name_suffix}",
                version="1.0.0",
                status="draft",
                rules_count=2,
                created_at=datetime.now(timezone.utc).isoformat(),
                validation_errors=[]
            )
            self.mock_create_use_case.execute.return_value = mock_response
            
            with patch('apps.api.routers.rules.get_create_rule_use_case', return_value=self.mock_create_use_case):
                return self.client.post("/rules", json=create_request, headers=self.headers)
        
        # Execute concurrent requests
        num_requests = 3
        responses = []
        
        with ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [
                executor.submit(create_rule_set, str(i))
                for i in range(num_requests)
            ]
            
            for future in as_completed(futures):
                responses.append(future.result())
        
        # Verify all requests succeeded
        assert len(responses) == num_requests
        for response in responses:
            assert response.status_code == 201
    
    def test_error_response_format_consistency(self):
        """Test that error responses follow consistent format."""
        # Test various error scenarios
        error_scenarios = [
            # Missing tenant header
            (lambda: self.client.get("/rules"), 422),
            # Invalid UUID
            (lambda: self.client.get("/rules/invalid-uuid", headers=self.headers), 422),
            # Invalid version format
            (lambda: self.client.put(f"/rules/{self.rule_set_id}/publish/invalid", headers=self.headers), 422),
        ]
        
        for request_func, expected_status in error_scenarios:
            response = request_func()
            assert response.status_code == expected_status
            
            # Verify error response has consistent structure
            data = response.json()
            assert "detail" in data  # FastAPI standard error format


if __name__ == "__main__":
    pytest.main([__file__, "-v"])