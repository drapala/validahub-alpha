"""Log correction use case for ValidaHub Smart Rules Engine."""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from uuid import uuid4
from datetime import datetime, timezone

from src.application.errors import ValidationError
from src.application.ports.rules import CorrectionStore, SuggestionEngine, EventBusPort
from src.domain.value_objects import TenantId
from src.domain.rules.value_objects import RuleSetId


@dataclass(frozen=True)
class LogCorrectionRequest:
    """Request DTO for logging corrections."""
    tenant_id: str
    field: str
    original_value: str
    corrected_value: str
    rule_set_id: Optional[str] = None
    job_id: Optional[str] = None
    seller_id: Optional[str] = None
    channel: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass(frozen=True)
class LogCorrectionResponse:
    """Response DTO for correction logging."""
    correction_id: str
    tenant_id: str
    field: str
    original_value: str
    corrected_value: str
    logged_at: str
    learning_applied: bool
    
    @classmethod
    def create(
        cls,
        correction_id: str,
        request: LogCorrectionRequest,
        learning_applied: bool = False
    ) -> "LogCorrectionResponse":
        """Create response from request and results."""
        return cls(
            correction_id=correction_id,
            tenant_id=request.tenant_id,
            field=request.field,
            original_value=request.original_value,
            corrected_value=request.corrected_value,
            logged_at=datetime.now(timezone.utc).isoformat(),
            learning_applied=learning_applied
        )


class LogCorrectionUseCase:
    """Use case for logging user corrections and applying machine learning."""
    
    def __init__(
        self,
        correction_store: CorrectionStore,
        suggestion_engine: SuggestionEngine,
        event_bus: EventBusPort
    ) -> None:
        """
        Initialize use case with dependencies.
        
        Args:
            correction_store: Store for correction data
            suggestion_engine: Engine for learning from corrections
            event_bus: Event bus for publishing correction events
        """
        self._correction_store = correction_store
        self._suggestion_engine = suggestion_engine
        self._event_bus = event_bus
    
    def execute(self, request: LogCorrectionRequest) -> LogCorrectionResponse:
        """
        Execute correction logging use case.
        
        Args:
            request: Correction logging request
            
        Returns:
            Correction logging response
            
        Raises:
            ValidationError: If input validation fails
        """
        # Validate request
        self._validate_request(request)
        
        # Convert to value objects
        tenant_id = TenantId(request.tenant_id)
        rule_set_id = None
        if request.rule_set_id:
            try:
                from uuid import UUID
                rule_set_id = RuleSetId(UUID(request.rule_set_id))
            except ValueError:
                raise ValidationError("Invalid rule_set_id format")
        
        # Prepare context for learning
        context = self._build_correction_context(request)
        
        # Log correction
        correction_id = self._correction_store.log_correction(
            tenant_id=tenant_id,
            field=request.field,
            original_value=request.original_value,
            corrected_value=request.corrected_value,
            rule_set_id=rule_set_id,
            context=context
        )
        
        # Apply machine learning
        learning_applied = False
        try:
            self._suggestion_engine.learn_from_corrections(
                tenant_id=tenant_id,
                field=request.field,
                original_value=request.original_value,
                corrected_value=request.corrected_value,
                context=context
            )
            learning_applied = True
        except Exception:
            # Don't fail correction logging if learning fails
            pass
        
        # Publish correction event
        try:
            correction_event = self._create_correction_event(request, correction_id)
            self._event_bus.publish_rule_events([correction_event])
        except Exception:
            # Don't fail use case if event publishing fails
            pass
        
        return LogCorrectionResponse.create(
            correction_id=correction_id,
            request=request,
            learning_applied=learning_applied
        )
    
    def _validate_request(self, request: LogCorrectionRequest) -> None:
        """Validate correction logging request."""
        validation_errors = []
        
        # Validate required fields
        if not request.tenant_id or not request.tenant_id.strip():
            validation_errors.append("tenant_id is required")
        
        if not request.field or not request.field.strip():
            validation_errors.append("field is required")
        
        if request.original_value is None:
            validation_errors.append("original_value is required")
        
        if request.corrected_value is None:
            validation_errors.append("corrected_value is required")
        
        if validation_errors:
            raise ValidationError("; ".join(validation_errors))
        
        # Validate field name length and format
        if len(request.field) > 100:
            raise ValidationError("field name must be 100 characters or less")
        
        # Validate value lengths
        if len(str(request.original_value)) > 1000:
            raise ValidationError("original_value must be 1000 characters or less")
        
        if len(str(request.corrected_value)) > 1000:
            raise ValidationError("corrected_value must be 1000 characters or less")
        
        # Validate values are different
        if str(request.original_value) == str(request.corrected_value):
            raise ValidationError("original_value and corrected_value must be different")
        
        # Validate value objects
        try:
            TenantId(request.tenant_id)
        except ValueError as e:
            raise ValidationError(f"invalid tenant_id: {e}")
    
    def _build_correction_context(self, request: LogCorrectionRequest) -> Dict[str, Any]:
        """Build context dictionary for machine learning."""
        context = {}
        
        if request.rule_set_id:
            context["rule_set_id"] = request.rule_set_id
        
        if request.job_id:
            context["job_id"] = request.job_id
        
        if request.seller_id:
            context["seller_id"] = request.seller_id
        
        if request.channel:
            context["channel"] = request.channel
        
        if request.correlation_id:
            context["correlation_id"] = request.correlation_id
        
        # Add metadata
        context["logged_at"] = datetime.now(timezone.utc).isoformat()
        context["field_type"] = self._infer_field_type(request.field)
        context["correction_type"] = self._classify_correction_type(
            request.original_value,
            request.corrected_value
        )
        
        return context
    
    def _infer_field_type(self, field: str) -> str:
        """Infer field type from field name."""
        field_lower = field.lower()
        
        if any(keyword in field_lower for keyword in ["price", "valor", "preco"]):
            return "price"
        elif any(keyword in field_lower for keyword in ["title", "titulo", "name", "nome"]):
            return "text"
        elif any(keyword in field_lower for keyword in ["category", "categoria"]):
            return "category"
        elif any(keyword in field_lower for keyword in ["brand", "marca"]):
            return "brand"
        elif any(keyword in field_lower for keyword in ["description", "descricao"]):
            return "description"
        elif any(keyword in field_lower for keyword in ["sku", "codigo"]):
            return "sku"
        else:
            return "other"
    
    def _classify_correction_type(self, original: str, corrected: str) -> str:
        """Classify the type of correction made."""
        original_str = str(original).strip()
        corrected_str = str(corrected).strip()
        
        # Check if it's a formatting correction
        if original_str.replace(" ", "").lower() == corrected_str.replace(" ", "").lower():
            return "formatting"
        
        # Check if it's a case correction
        if original_str.lower() == corrected_str.lower():
            return "case"
        
        # Check if it's a truncation/extension
        if original_str in corrected_str or corrected_str in original_str:
            return "length_adjustment"
        
        # Check if it's a typo correction (simple heuristic)
        if len(original_str) == len(corrected_str):
            differences = sum(1 for a, b in zip(original_str, corrected_str) if a != b)
            if differences <= 2:  # 1-2 character differences
                return "typo"
        
        # Default to content change
        return "content_change"
    
    def _create_correction_event(self, request: LogCorrectionRequest, correction_id: str) -> Dict[str, Any]:
        """Create correction event for publishing."""
        return {
            "id": str(uuid4()),
            "specversion": "1.0",
            "source": "application/log-correction",
            "type": "valida.correction.logged",
            "time": datetime.now(timezone.utc).isoformat(),
            "subject": f"correction:{correction_id}",
            "tenant_id": request.tenant_id,
            "correlation_id": request.correlation_id or str(uuid4()),
            "data": {
                "correction_id": correction_id,
                "field": request.field,
                "original_value": request.original_value,
                "corrected_value": request.corrected_value,
                "rule_set_id": request.rule_set_id,
                "job_id": request.job_id,
                "seller_id": request.seller_id,
                "channel": request.channel
            }
        }