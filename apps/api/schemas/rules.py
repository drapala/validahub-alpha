"""Pydantic models for Rules API endpoints.

This module defines request and response models for the Smart Rules Engine API
following OpenAPI 3.1 specifications.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime


# Request Models
class RuleDefinitionModel(BaseModel):
    """Model for rule definition in requests."""
    id: str = Field(..., description="Unique rule identifier", regex=r"^[a-z][a-z0-9_]{2,63}$")
    type: str = Field(..., description="Rule type", regex=r"^(required|format|length|range|enum|pattern|dependency|business|composite)$")
    field: str = Field(..., description="Field name to validate", max_length=100)
    condition: Dict[str, Any] = Field(..., description="Rule condition based on type")
    message: str = Field(..., description="Error message for violations", max_length=500)
    severity: str = Field(..., description="Severity level", regex=r"^(error|warning|info)$")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional rule metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "product_title_required",
                "type": "required",
                "field": "title",
                "condition": {},
                "message": "Product title is required",
                "severity": "error",
                "metadata": {"category": "product_info"}
            }
        }


class CreateRuleRequestModel(BaseModel):
    """Request model for creating rule sets."""
    name: str = Field(..., description="Rule set name", max_length=100)
    channel: str = Field(..., description="Marketplace channel")
    version: str = Field(..., description="Semantic version", regex=r"^\d+\.\d+\.\d+$")
    rules: List[RuleDefinitionModel] = Field(..., description="List of rule definitions", min_items=1)
    description: Optional[str] = Field(None, description="Rule set description", max_length=1000)
    
    @validator('rules')
    def validate_rules_not_empty(cls, v):
        if not v:
            raise ValueError('At least one rule is required')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "name": "mercado_livre_product_rules",
                "channel": "mercado_livre",
                "version": "1.0.0",
                "description": "Product validation rules for Mercado Livre",
                "rules": [
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
                        "message": "Product title must be between 10 and 60 characters",
                        "severity": "warning"
                    }
                ]
            }
        }


class PublishRuleRequestModel(BaseModel):
    """Request model for publishing rule sets."""
    make_current: bool = Field(True, description="Whether to make this version the current active version")
    
    class Config:
        schema_extra = {
            "example": {
                "make_current": True
            }
        }


class LogCorrectionRequestModel(BaseModel):
    """Request model for logging corrections."""
    field: str = Field(..., description="Field that was corrected", max_length=100)
    original_value: str = Field(..., description="Original field value", max_length=1000)
    corrected_value: str = Field(..., description="User-corrected value", max_length=1000)
    rule_set_id: Optional[str] = Field(None, description="Rule set ID that was applied")
    job_id: Optional[str] = Field(None, description="Job ID where correction occurred")
    seller_id: Optional[str] = Field(None, description="Seller identifier")
    channel: Optional[str] = Field(None, description="Marketplace channel")
    
    @validator('corrected_value')
    def validate_values_different(cls, v, values):
        if 'original_value' in values and v == values['original_value']:
            raise ValueError('Corrected value must be different from original value')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "field": "title",
                "original_value": "iPhone 12 64Gb",
                "corrected_value": "iPhone 12 64GB",
                "rule_set_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_id": "j_123456",
                "seller_id": "seller_789",
                "channel": "mercado_livre"
            }
        }


class GetSuggestionsRequestModel(BaseModel):
    """Request model for getting rule suggestions."""
    field: str = Field(..., description="Field name to suggest rules for", max_length=100)
    channel: Optional[str] = Field(None, description="Marketplace channel for context")
    current_rules: Optional[List[str]] = Field(None, description="List of existing rule IDs", max_items=50)
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for suggestions")
    
    class Config:
        schema_extra = {
            "example": {
                "field": "price",
                "channel": "mercado_livre",
                "current_rules": ["price_required", "price_format"],
                "context": {"category": "electronics"}
            }
        }


# Response Models
class RuleSetVersionModel(BaseModel):
    """Model for rule set version information."""
    version: str = Field(..., description="Semantic version")
    status: str = Field(..., description="Version status")
    rules_count: int = Field(..., description="Number of rules in this version")
    checksum: Optional[str] = Field(None, description="Version checksum")
    created_at: str = Field(..., description="Creation timestamp")
    published_at: Optional[str] = Field(None, description="Publication timestamp")


class CreateRuleResponseModel(BaseModel):
    """Response model for rule creation."""
    rule_set_id: str = Field(..., description="Created rule set ID")
    name: str = Field(..., description="Rule set name")
    version: str = Field(..., description="Version created")
    status: str = Field(..., description="Current status")
    rules_count: int = Field(..., description="Number of rules")
    created_at: str = Field(..., description="Creation timestamp")
    validation_errors: List[str] = Field(..., description="Any validation warnings")
    
    class Config:
        schema_extra = {
            "example": {
                "rule_set_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "mercado_livre_product_rules",
                "version": "1.0.0",
                "status": "draft",
                "rules_count": 5,
                "created_at": "2023-12-01T10:00:00Z",
                "validation_errors": []
            }
        }


class PublishRuleResponseModel(BaseModel):
    """Response model for rule publication."""
    rule_set_id: str = Field(..., description="Published rule set ID")
    name: str = Field(..., description="Rule set name")
    version: str = Field(..., description="Published version")
    status: str = Field(..., description="Current status")
    is_current: bool = Field(..., description="Whether this is the current active version")
    checksum: str = Field(..., description="Compiled rule checksum")
    published_at: str = Field(..., description="Publication timestamp")
    compilation_errors: List[str] = Field(..., description="Any compilation errors")
    
    class Config:
        schema_extra = {
            "example": {
                "rule_set_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "mercado_livre_product_rules",
                "version": "1.0.0",
                "status": "published",
                "is_current": True,
                "checksum": "sha256:abc123...",
                "published_at": "2023-12-01T10:05:00Z",
                "compilation_errors": []
            }
        }


class RuleSetResponseModel(BaseModel):
    """Response model for rule set details."""
    rule_set_id: str = Field(..., description="Rule set ID")
    name: str = Field(..., description="Rule set name")
    channel: str = Field(..., description="Marketplace channel")
    description: Optional[str] = Field(None, description="Rule set description")
    current_version: Optional[str] = Field(None, description="Current active version")
    versions: List[RuleSetVersionModel] = Field(..., description="All versions")
    published_versions: List[str] = Field(..., description="Published version numbers")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "rule_set_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "mercado_livre_product_rules",
                "channel": "mercado_livre",
                "description": "Product validation rules for Mercado Livre",
                "current_version": "1.0.0",
                "versions": [
                    {
                        "version": "1.0.0",
                        "status": "published",
                        "rules_count": 5,
                        "created_at": "2023-12-01T10:00:00Z",
                        "published_at": "2023-12-01T10:05:00Z"
                    }
                ],
                "published_versions": ["1.0.0"],
                "created_at": "2023-12-01T10:00:00Z",
                "updated_at": "2023-12-01T10:05:00Z"
            }
        }


class LogCorrectionResponseModel(BaseModel):
    """Response model for correction logging."""
    correction_id: str = Field(..., description="Unique correction ID")
    tenant_id: str = Field(..., description="Tenant identifier")
    field: str = Field(..., description="Field that was corrected")
    original_value: str = Field(..., description="Original field value")
    corrected_value: str = Field(..., description="User-corrected value")
    logged_at: str = Field(..., description="Logging timestamp")
    learning_applied: bool = Field(..., description="Whether machine learning was applied")
    
    class Config:
        schema_extra = {
            "example": {
                "correction_id": "corr_abc123",
                "tenant_id": "t_company_123",
                "field": "title",
                "original_value": "iPhone 12 64Gb",
                "corrected_value": "iPhone 12 64GB",
                "logged_at": "2023-12-01T10:10:00Z",
                "learning_applied": True
            }
        }


class RuleSuggestionModel(BaseModel):
    """Model for individual rule suggestions."""
    rule_id: str = Field(..., description="Suggested rule ID")
    rule_type: str = Field(..., description="Type of rule")
    field: str = Field(..., description="Field name")
    condition: Dict[str, Any] = Field(..., description="Rule condition")
    message: str = Field(..., description="Suggested error message")
    severity: str = Field(..., description="Suggested severity level")
    confidence_score: float = Field(..., description="Confidence score (0-1)", ge=0.0, le=1.0)
    reason: str = Field(..., description="Explanation for suggestion")
    examples: Optional[List[str]] = Field(None, description="Example values that would trigger this rule")


class GetSuggestionsResponseModel(BaseModel):
    """Response model for rule suggestions."""
    tenant_id: str = Field(..., description="Tenant identifier")
    field: str = Field(..., description="Field name")
    suggestions: List[RuleSuggestionModel] = Field(..., description="List of rule suggestions")
    total_suggestions: int = Field(..., description="Total number of suggestions")
    
    class Config:
        schema_extra = {
            "example": {
                "tenant_id": "t_company_123",
                "field": "price",
                "total_suggestions": 2,
                "suggestions": [
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
                    },
                    {
                        "rule_id": "price_decimal_places",
                        "rule_type": "pattern",
                        "field": "price",
                        "condition": {"pattern": "^\\d+\\.\\d{2}$"},
                        "message": "Price must have exactly 2 decimal places",
                        "severity": "warning",
                        "confidence_score": 0.85,
                        "reason": "Currency formatting best practice",
                        "examples": ["10.1", "20", "30.123"]
                    }
                ]
            }
        }


class RuleSetListResponseModel(BaseModel):
    """Response model for rule set listing."""
    data: List[RuleSetResponseModel] = Field(..., description="List of rule sets")
    meta: Dict[str, Any] = Field(..., description="Pagination metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "data": [
                    {
                        "rule_set_id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "mercado_livre_product_rules",
                        "channel": "mercado_livre",
                        "current_version": "1.0.0",
                        "versions": [],
                        "published_versions": ["1.0.0"],
                        "created_at": "2023-12-01T10:00:00Z",
                        "updated_at": "2023-12-01T10:05:00Z"
                    }
                ],
                "meta": {
                    "limit": 20,
                    "offset": 0,
                    "total": 1,
                    "has_more": False
                }
            }
        }


class ErrorResponseModel(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    
    class Config:
        schema_extra = {
            "example": {
                "error": "validation_error",
                "message": "Invalid rule definition",
                "details": {
                    "field": "condition",
                    "reason": "missing required field 'pattern' for pattern rule type"
                },
                "request_id": "req_abc123"
            }
        }