"""Rules management endpoints for ValidaHub Smart Rules Engine API.

This module provides REST endpoints for rule operations:
- POST /rules - Create new rule set
- GET /rules - List rule sets
- GET /rules/{rule_set_id} - Get rule set details
- PUT /rules/{rule_set_id}/publish/{version} - Publish rule version
- POST /corrections/log - Log user corrections
- GET /suggestions - Get rule suggestions

All endpoints follow OpenAPI 3.1 specifications with proper validation,
authorization, idempotency support, and comprehensive error handling.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Request, Depends, HTTPException, status, Header, Query, Path
from pydantic import ValidationError as PydanticValidationError

from src.application.use_cases.rules.create_rule import CreateRuleUseCase, CreateRuleRequest
from src.application.use_cases.rules.publish_rule import PublishRuleUseCase, PublishRuleRequest
from src.application.use_cases.rules.log_correction import LogCorrectionUseCase, LogCorrectionRequest
from src.application.use_cases.rules.get_suggestions import GetSuggestionsUseCase, GetSuggestionsRequest
from src.application.errors import ValidationError
from src.application.ports.rules import RuleRepository

from apps.api.schemas.rules import (
    CreateRuleRequestModel, CreateRuleResponseModel,
    PublishRuleRequestModel, PublishRuleResponseModel,
    RuleSetResponseModel, RuleSetListResponseModel,
    LogCorrectionRequestModel, LogCorrectionResponseModel,
    GetSuggestionsRequestModel, GetSuggestionsResponseModel,
    ErrorResponseModel
)

try:
    from src.shared.logging import get_logger
    from src.shared.logging.context import get_correlation_id
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)
    def get_correlation_id():
        return "no-correlation"


logger = get_logger("apps.api.rules")
router = APIRouter()


# Dependency injection placeholders
def get_create_rule_use_case() -> CreateRuleUseCase:
    """Get CreateRuleUseCase instance with dependencies."""
    raise NotImplementedError("Dependency injection not yet configured")


def get_publish_rule_use_case() -> PublishRuleUseCase:
    """Get PublishRuleUseCase instance with dependencies."""
    raise NotImplementedError("Dependency injection not yet configured")


def get_log_correction_use_case() -> LogCorrectionUseCase:
    """Get LogCorrectionUseCase instance with dependencies."""
    raise NotImplementedError("Dependency injection not yet configured")


def get_suggestions_use_case() -> GetSuggestionsUseCase:
    """Get GetSuggestionsUseCase instance with dependencies."""
    raise NotImplementedError("Dependency injection not yet configured")


def get_rule_repository() -> RuleRepository:
    """Get RuleRepository instance."""
    raise NotImplementedError("Dependency injection not yet configured")


# Header validation functions
def validate_tenant_header(x_tenant_id: str = Header(..., description="Tenant identifier")) -> str:
    """Validate tenant ID header."""
    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Id header is required"
        )
    
    # Basic format validation
    if not x_tenant_id.startswith("t_") or len(x_tenant_id) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant ID format"
        )
    
    return x_tenant_id.strip()


def validate_idempotency_key(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
) -> Optional[str]:
    """Validate idempotency key header for POST operations."""
    if idempotency_key:
        if len(idempotency_key) < 16 or len(idempotency_key) > 128:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Idempotency-Key must be between 16 and 128 characters"
            )
    
    return idempotency_key


def get_request_context(request: Request) -> Dict[str, Any]:
    """Extract request context from FastAPI request."""
    return {
        "request_id": getattr(request.state, 'request_id', None),
        "user_id": getattr(request.state, 'user_id', None),
        "trace_id": request.headers.get("x-trace-id"),
        "correlation_id": get_correlation_id()
    }


# Rules endpoints
@router.post(
    "",
    response_model=CreateRuleResponseModel,
    status_code=status.HTTP_201_CREATED,
    summary="Create new rule set",
    description="Create a new rule set with validation rules for a marketplace channel",
    responses={
        201: {"description": "Rule set created successfully"},
        400: {"model": ErrorResponseModel, "description": "Invalid request"},
        409: {"model": ErrorResponseModel, "description": "Rule set already exists"},
        422: {"model": ErrorResponseModel, "description": "Validation error"},
        429: {"model": ErrorResponseModel, "description": "Rate limit exceeded"},
    }
)
async def create_rule_set(
    request: Request,
    rule_request: CreateRuleRequestModel,
    tenant_id: str = Depends(validate_tenant_header),
    idempotency_key: Optional[str] = Depends(validate_idempotency_key),
    create_rule_use_case: CreateRuleUseCase = Depends(get_create_rule_use_case),
):
    """Create a new rule set with validation rules."""
    try:
        context = get_request_context(request)
        
        # Convert Pydantic models to use case request
        rules_data = []
        for rule_model in rule_request.rules:
            rules_data.append({
                "id": rule_model.id,
                "type": rule_model.type,
                "field": rule_model.field,
                "condition": rule_model.condition,
                "message": rule_model.message,
                "severity": rule_model.severity,
                "metadata": rule_model.metadata
            })
        
        use_case_request = CreateRuleRequest(
            tenant_id=tenant_id,
            channel=rule_request.channel,
            name=rule_request.name,
            version=rule_request.version,
            rules=rules_data,
            description=rule_request.description,
            created_by=context.get("user_id", "api"),
            correlation_id=context.get("correlation_id")
        )
        
        # Execute use case
        response = create_rule_use_case.execute(use_case_request)
        
        logger.info(
            "rule_set_created",
            tenant_id=tenant_id,
            rule_set_id=response.rule_set_id,
            name=response.name,
            version=response.version,
            rules_count=response.rules_count,
            correlation_id=context.get("correlation_id")
        )
        
        return CreateRuleResponseModel(
            rule_set_id=response.rule_set_id,
            name=response.name,
            version=response.version,
            status=response.status,
            rules_count=response.rules_count,
            created_at=response.created_at,
            validation_errors=response.validation_errors
        )
        
    except ValidationError as error:
        logger.warning(
            "rule_creation_validation_error",
            tenant_id=tenant_id,
            error=str(error),
            correlation_id=context.get("correlation_id")
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error)
        )
    
    except PydanticValidationError as error:
        logger.warning(
            "rule_creation_pydantic_error",
            tenant_id=tenant_id,
            error=str(error),
            correlation_id=context.get("correlation_id")
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request format"
        )
    
    except Exception as error:
        logger.error(
            "rule_creation_unexpected_error",
            tenant_id=tenant_id,
            error=str(error),
            error_type=error.__class__.__name__,
            correlation_id=context.get("correlation_id")
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create rule set"
        )


@router.get(
    "",
    response_model=RuleSetListResponseModel,
    summary="List rule sets",
    description="List all rule sets for the tenant with optional filtering",
    responses={
        200: {"description": "Rule sets retrieved successfully"},
        400: {"model": ErrorResponseModel, "description": "Invalid request"},
    }
)
async def list_rule_sets(
    request: Request,
    tenant_id: str = Depends(validate_tenant_header),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    rule_repository: RuleRepository = Depends(get_rule_repository),
):
    """List rule sets for the tenant."""
    try:
        context = get_request_context(request)
        
        # Get rule sets from repository
        from src.domain.value_objects import TenantId
        tenant_id_vo = TenantId(tenant_id)
        rule_sets = rule_repository.find_all_by_tenant(tenant_id_vo)
        
        # Apply channel filter if specified
        if channel:
            rule_sets = [rs for rs in rule_sets if rs.channel.value == channel]
        
        # Apply pagination
        total = len(rule_sets)
        paginated_rule_sets = rule_sets[offset:offset + limit]
        
        # Convert to response models
        data = []
        for rule_set in paginated_rule_sets:
            versions = []
            for version in rule_set.versions:
                versions.append({
                    "version": str(version.version),
                    "status": version.status.value,
                    "rules_count": len(version.rules),
                    "checksum": version.checksum,
                    "created_at": version.created_at.isoformat(),
                    "published_at": version.published_at.isoformat() if version.published_at else None
                })
            
            data.append(RuleSetResponseModel(
                rule_set_id=str(rule_set.id.value),
                name=rule_set.name,
                channel=rule_set.channel.value,
                description=rule_set.description,
                current_version=str(rule_set.current_version) if rule_set.current_version else None,
                versions=versions,
                published_versions=[str(v) for v in rule_set.published_versions],
                created_at=rule_set.created_at.isoformat(),
                updated_at=rule_set.updated_at.isoformat()
            ))
        
        logger.info(
            "rule_sets_listed",
            tenant_id=tenant_id,
            total=total,
            limit=limit,
            offset=offset,
            channel=channel,
            correlation_id=context.get("correlation_id")
        )
        
        return RuleSetListResponseModel(
            data=data,
            meta={
                "limit": limit,
                "offset": offset,
                "total": total,
                "has_more": offset + limit < total
            }
        )
        
    except Exception as error:
        logger.error(
            "list_rule_sets_error",
            tenant_id=tenant_id,
            error=str(error),
            error_type=error.__class__.__name__,
            correlation_id=context.get("correlation_id")
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list rule sets"
        )


@router.get(
    "/{rule_set_id}",
    response_model=RuleSetResponseModel,
    summary="Get rule set details",
    description="Retrieve detailed information about a specific rule set",
    responses={
        200: {"description": "Rule set retrieved successfully"},
        404: {"model": ErrorResponseModel, "description": "Rule set not found"},
    }
)
async def get_rule_set(
    request: Request,
    rule_set_id: UUID = Path(..., description="Rule set identifier"),
    tenant_id: str = Depends(validate_tenant_header),
    rule_repository: RuleRepository = Depends(get_rule_repository),
):
    """Get rule set details by ID."""
    try:
        context = get_request_context(request)
        
        # Find rule set
        from src.domain.value_objects import TenantId
        from src.domain.rules.value_objects import RuleSetId
        
        tenant_id_vo = TenantId(tenant_id)
        rule_set_id_vo = RuleSetId(rule_set_id)
        
        rule_set = rule_repository.find_by_id(tenant_id_vo, rule_set_id_vo)
        
        if not rule_set:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rule set {rule_set_id} not found"
            )
        
        # Convert to response model
        versions = []
        for version in rule_set.versions:
            versions.append({
                "version": str(version.version),
                "status": version.status.value,
                "rules_count": len(version.rules),
                "checksum": version.checksum,
                "created_at": version.created_at.isoformat(),
                "published_at": version.published_at.isoformat() if version.published_at else None
            })
        
        response = RuleSetResponseModel(
            rule_set_id=str(rule_set.id.value),
            name=rule_set.name,
            channel=rule_set.channel.value,
            description=rule_set.description,
            current_version=str(rule_set.current_version) if rule_set.current_version else None,
            versions=versions,
            published_versions=[str(v) for v in rule_set.published_versions],
            created_at=rule_set.created_at.isoformat(),
            updated_at=rule_set.updated_at.isoformat()
        )
        
        logger.info(
            "rule_set_retrieved",
            tenant_id=tenant_id,
            rule_set_id=str(rule_set_id),
            name=rule_set.name,
            correlation_id=context.get("correlation_id")
        )
        
        return response
        
    except HTTPException:
        raise
    
    except Exception as error:
        logger.error(
            "get_rule_set_error",
            tenant_id=tenant_id,
            rule_set_id=str(rule_set_id),
            error=str(error),
            error_type=error.__class__.__name__,
            correlation_id=context.get("correlation_id")
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve rule set"
        )


@router.put(
    "/{rule_set_id}/publish/{version}",
    response_model=PublishRuleResponseModel,
    summary="Publish rule version",
    description="Publish a specific version of a rule set to make it available for use",
    responses={
        200: {"description": "Rule version published successfully"},
        400: {"model": ErrorResponseModel, "description": "Invalid request"},
        404: {"model": ErrorResponseModel, "description": "Rule set or version not found"},
        422: {"model": ErrorResponseModel, "description": "Validation error"},
    }
)
async def publish_rule_version(
    request: Request,
    rule_set_id: UUID = Path(..., description="Rule set identifier"),
    version: str = Path(..., description="Version to publish", regex=r"^\d+\.\d+\.\d+$"),
    publish_request: PublishRuleRequestModel = PublishRuleRequestModel(),
    tenant_id: str = Depends(validate_tenant_header),
    publish_rule_use_case: PublishRuleUseCase = Depends(get_publish_rule_use_case),
):
    """Publish a specific version of a rule set."""
    try:
        context = get_request_context(request)
        
        use_case_request = PublishRuleRequest(
            tenant_id=tenant_id,
            rule_set_id=str(rule_set_id),
            version=version,
            make_current=publish_request.make_current,
            published_by=context.get("user_id", "api"),
            correlation_id=context.get("correlation_id")
        )
        
        # Execute use case
        response = publish_rule_use_case.execute(use_case_request)
        
        logger.info(
            "rule_version_published",
            tenant_id=tenant_id,
            rule_set_id=str(rule_set_id),
            version=version,
            is_current=response.is_current,
            correlation_id=context.get("correlation_id")
        )
        
        return PublishRuleResponseModel(
            rule_set_id=response.rule_set_id,
            name=response.name,
            version=response.version,
            status=response.status,
            is_current=response.is_current,
            checksum=response.checksum,
            published_at=response.published_at,
            compilation_errors=response.compilation_errors
        )
        
    except ValidationError as error:
        logger.warning(
            "rule_publish_validation_error",
            tenant_id=tenant_id,
            rule_set_id=str(rule_set_id),
            version=version,
            error=str(error),
            correlation_id=context.get("correlation_id")
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error)
        )
    
    except Exception as error:
        logger.error(
            "rule_publish_unexpected_error",
            tenant_id=tenant_id,
            rule_set_id=str(rule_set_id),
            version=version,
            error=str(error),
            error_type=error.__class__.__name__,
            correlation_id=context.get("correlation_id")
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish rule version"
        )


@router.post(
    "/corrections/log",
    response_model=LogCorrectionResponseModel,
    status_code=status.HTTP_201_CREATED,
    summary="Log user correction",
    description="Log a user correction for machine learning and analytics",
    responses={
        201: {"description": "Correction logged successfully"},
        400: {"model": ErrorResponseModel, "description": "Invalid request"},
        422: {"model": ErrorResponseModel, "description": "Validation error"},
    }
)
async def log_correction(
    request: Request,
    correction_request: LogCorrectionRequestModel,
    tenant_id: str = Depends(validate_tenant_header),
    idempotency_key: Optional[str] = Depends(validate_idempotency_key),
    log_correction_use_case: LogCorrectionUseCase = Depends(get_log_correction_use_case),
):
    """Log a user correction for machine learning."""
    try:
        context = get_request_context(request)
        
        use_case_request = LogCorrectionRequest(
            tenant_id=tenant_id,
            field=correction_request.field,
            original_value=correction_request.original_value,
            corrected_value=correction_request.corrected_value,
            rule_set_id=correction_request.rule_set_id,
            job_id=correction_request.job_id,
            seller_id=correction_request.seller_id,
            channel=correction_request.channel,
            correlation_id=context.get("correlation_id")
        )
        
        # Execute use case
        response = log_correction_use_case.execute(use_case_request)
        
        logger.info(
            "correction_logged",
            tenant_id=tenant_id,
            correction_id=response.correction_id,
            field=response.field,
            learning_applied=response.learning_applied,
            correlation_id=context.get("correlation_id")
        )
        
        return LogCorrectionResponseModel(
            correction_id=response.correction_id,
            tenant_id=response.tenant_id,
            field=response.field,
            original_value=response.original_value,
            corrected_value=response.corrected_value,
            logged_at=response.logged_at,
            learning_applied=response.learning_applied
        )
        
    except ValidationError as error:
        logger.warning(
            "correction_log_validation_error",
            tenant_id=tenant_id,
            error=str(error),
            correlation_id=context.get("correlation_id")
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error)
        )
    
    except Exception as error:
        logger.error(
            "correction_log_unexpected_error",
            tenant_id=tenant_id,
            error=str(error),
            error_type=error.__class__.__name__,
            correlation_id=context.get("correlation_id")
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log correction"
        )


@router.post(
    "/suggestions",
    response_model=GetSuggestionsResponseModel,
    summary="Get rule suggestions",
    description="Get intelligent rule suggestions based on field and context",
    responses={
        200: {"description": "Suggestions retrieved successfully"},
        400: {"model": ErrorResponseModel, "description": "Invalid request"},
        422: {"model": ErrorResponseModel, "description": "Validation error"},
    }
)
async def get_rule_suggestions(
    request: Request,
    suggestions_request: GetSuggestionsRequestModel,
    tenant_id: str = Depends(validate_tenant_header),
    suggestions_use_case: GetSuggestionsUseCase = Depends(get_suggestions_use_case),
):
    """Get intelligent rule suggestions for a field."""
    try:
        context = get_request_context(request)
        
        use_case_request = GetSuggestionsRequest(
            tenant_id=tenant_id,
            field=suggestions_request.field,
            channel=suggestions_request.channel,
            current_rules=suggestions_request.current_rules,
            context=suggestions_request.context
        )
        
        # Execute use case
        response = suggestions_use_case.execute(use_case_request)
        
        logger.info(
            "rule_suggestions_retrieved",
            tenant_id=tenant_id,
            field=response.field,
            total_suggestions=response.total_suggestions,
            correlation_id=context.get("correlation_id")
        )
        
        return GetSuggestionsResponseModel(
            tenant_id=response.tenant_id,
            field=response.field,
            suggestions=response.suggestions,
            total_suggestions=response.total_suggestions
        )
        
    except ValidationError as error:
        logger.warning(
            "suggestions_validation_error",
            tenant_id=tenant_id,
            error=str(error),
            correlation_id=context.get("correlation_id")
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error)
        )
    
    except Exception as error:
        logger.error(
            "suggestions_unexpected_error",
            tenant_id=tenant_id,
            error=str(error),
            error_type=error.__class__.__name__,
            correlation_id=context.get("correlation_id")
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get suggestions"
        )