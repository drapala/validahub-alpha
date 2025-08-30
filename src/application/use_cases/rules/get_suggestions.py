"""Get suggestions use case for ValidaHub Smart Rules Engine."""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from src.application.errors import ValidationError
from src.application.ports.rules import SuggestionEngine, RuleRepository
from src.domain.value_objects import TenantId


@dataclass(frozen=True)
class GetSuggestionsRequest:
    """Request DTO for getting rule suggestions."""
    tenant_id: str
    field: str
    channel: Optional[str] = None
    current_rules: Optional[List[str]] = None  # List of existing rule IDs
    context: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class RuleSuggestion:
    """Individual rule suggestion."""
    rule_id: str
    rule_type: str
    field: str
    condition: Dict[str, Any]
    message: str
    severity: str
    confidence_score: float
    reason: str
    examples: Optional[List[str]] = None


@dataclass(frozen=True)
class GetSuggestionsResponse:
    """Response DTO for rule suggestions."""
    tenant_id: str
    field: str
    suggestions: List[RuleSuggestion]
    total_suggestions: int
    
    @classmethod
    def create(
        cls,
        request: GetSuggestionsRequest,
        suggestions_data: List[Dict[str, Any]]
    ) -> "GetSuggestionsResponse":
        """Create response from request and suggestions data."""
        suggestions = []
        
        for suggestion_data in suggestions_data:
            suggestion = RuleSuggestion(
                rule_id=suggestion_data.get("rule_id", ""),
                rule_type=suggestion_data.get("rule_type", ""),
                field=suggestion_data.get("field", request.field),
                condition=suggestion_data.get("condition", {}),
                message=suggestion_data.get("message", ""),
                severity=suggestion_data.get("severity", "warning"),
                confidence_score=suggestion_data.get("confidence_score", 0.0),
                reason=suggestion_data.get("reason", ""),
                examples=suggestion_data.get("examples")
            )
            suggestions.append(suggestion)
        
        return cls(
            tenant_id=request.tenant_id,
            field=request.field,
            suggestions=suggestions,
            total_suggestions=len(suggestions)
        )


class GetSuggestionsUseCase:
    """Use case for getting intelligent rule suggestions based on field and context."""
    
    def __init__(
        self,
        suggestion_engine: SuggestionEngine,
        rule_repository: RuleRepository
    ) -> None:
        """
        Initialize use case with dependencies.
        
        Args:
            suggestion_engine: Engine for generating rule suggestions
            rule_repository: Repository for accessing existing rules
        """
        self._suggestion_engine = suggestion_engine
        self._rule_repository = rule_repository
    
    def execute(self, request: GetSuggestionsRequest) -> GetSuggestionsResponse:
        """
        Execute get suggestions use case.
        
        Args:
            request: Suggestions request
            
        Returns:
            Suggestions response
            
        Raises:
            ValidationError: If input validation fails
        """
        # Validate request
        self._validate_request(request)
        
        # Convert to value objects
        tenant_id = TenantId(request.tenant_id)
        
        # Build context for suggestions
        context = self._build_suggestion_context(request)
        
        # Get suggestions from engine
        suggestions_data = self._suggestion_engine.get_rule_suggestions(
            tenant_id=tenant_id,
            field=request.field,
            context=context
        )
        
        # Filter out suggestions for rules that already exist
        filtered_suggestions = self._filter_existing_rules(
            suggestions_data,
            request.current_rules or []
        )
        
        # Sort by confidence score (highest first)
        sorted_suggestions = sorted(
            filtered_suggestions,
            key=lambda x: x.get("confidence_score", 0.0),
            reverse=True
        )
        
        return GetSuggestionsResponse.create(request, sorted_suggestions)
    
    def _validate_request(self, request: GetSuggestionsRequest) -> None:
        """Validate suggestions request."""
        validation_errors = []
        
        # Validate required fields
        if not request.tenant_id or not request.tenant_id.strip():
            validation_errors.append("tenant_id is required")
        
        if not request.field or not request.field.strip():
            validation_errors.append("field is required")
        
        if validation_errors:
            raise ValidationError("; ".join(validation_errors))
        
        # Validate field name length and format
        if len(request.field) > 100:
            raise ValidationError("field name must be 100 characters or less")
        
        # Validate value objects
        try:
            TenantId(request.tenant_id)
        except ValueError as e:
            raise ValidationError(f"invalid tenant_id: {e}")
        
        # Validate current_rules if provided
        if request.current_rules:
            if len(request.current_rules) > 50:  # Reasonable limit
                raise ValidationError("too many current rules (max 50)")
            
            for rule_id in request.current_rules:
                if not rule_id or not rule_id.strip():
                    raise ValidationError("current_rules cannot contain empty rule IDs")
    
    def _build_suggestion_context(self, request: GetSuggestionsRequest) -> Dict[str, Any]:
        """Build context dictionary for suggestions."""
        context = {
            "field": request.field,
            "tenant_id": request.tenant_id
        }
        
        if request.channel:
            context["channel"] = request.channel
        
        if request.current_rules:
            context["existing_rule_ids"] = request.current_rules
            context["existing_rule_count"] = len(request.current_rules)
        
        if request.context:
            # Merge additional context, avoiding key conflicts
            for key, value in request.context.items():
                if key not in context:
                    context[key] = value
        
        # Add field analysis
        context.update(self._analyze_field(request.field))
        
        return context
    
    def _analyze_field(self, field: str) -> Dict[str, Any]:
        """Analyze field to provide better context for suggestions."""
        field_lower = field.lower()
        analysis = {}
        
        # Infer field type
        if any(keyword in field_lower for keyword in ["price", "valor", "preco"]):
            analysis["field_type"] = "price"
            analysis["expected_rules"] = ["range", "format", "required"]
        elif any(keyword in field_lower for keyword in ["title", "titulo", "name", "nome"]):
            analysis["field_type"] = "text"
            analysis["expected_rules"] = ["length", "pattern", "required"]
        elif any(keyword in field_lower for keyword in ["category", "categoria"]):
            analysis["field_type"] = "category"
            analysis["expected_rules"] = ["enum", "required"]
        elif any(keyword in field_lower for keyword in ["brand", "marca"]):
            analysis["field_type"] = "brand"
            analysis["expected_rules"] = ["enum", "length", "required"]
        elif any(keyword in field_lower for keyword in ["description", "descricao"]):
            analysis["field_type"] = "description"
            analysis["expected_rules"] = ["length", "pattern"]
        elif any(keyword in field_lower for keyword in ["sku", "codigo"]):
            analysis["field_type"] = "sku"
            analysis["expected_rules"] = ["pattern", "length", "required"]
        elif any(keyword in field_lower for keyword in ["email"]):
            analysis["field_type"] = "email"
            analysis["expected_rules"] = ["format", "required"]
        elif any(keyword in field_lower for keyword in ["phone", "telefone"]):
            analysis["field_type"] = "phone"
            analysis["expected_rules"] = ["pattern", "format"]
        elif any(keyword in field_lower for keyword in ["url", "link"]):
            analysis["field_type"] = "url"
            analysis["expected_rules"] = ["format", "pattern"]
        else:
            analysis["field_type"] = "generic"
            analysis["expected_rules"] = ["required", "length"]
        
        # Add priority suggestions based on field type
        analysis["priority_suggestion_types"] = analysis.get("expected_rules", [])
        
        return analysis
    
    def _filter_existing_rules(
        self,
        suggestions: List[Dict[str, Any]],
        current_rules: List[str]
    ) -> List[Dict[str, Any]]:
        """Filter out suggestions that match existing rules."""
        if not current_rules:
            return suggestions
        
        filtered = []
        current_rules_set = set(current_rules)
        
        for suggestion in suggestions:
            suggestion_id = suggestion.get("rule_id", "")
            
            # Skip if exact rule ID already exists
            if suggestion_id in current_rules_set:
                continue
            
            # Skip if same rule type for same field already exists
            rule_type = suggestion.get("rule_type", "")
            field = suggestion.get("field", "")
            
            # Create a composite key for rule type + field
            rule_key = f"{rule_type}:{field}"
            
            # Check if similar rule already exists (simplified check)
            similar_exists = any(
                rule_id.startswith(rule_key) or rule_id.endswith(f"_{rule_type}")
                for rule_id in current_rules
            )
            
            if not similar_exists:
                filtered.append(suggestion)
        
        return filtered