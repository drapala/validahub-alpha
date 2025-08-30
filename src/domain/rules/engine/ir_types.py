"""
Tipos de dados para Intermediate Representation (IR) do sistema de regras.

Este módulo define todas as estruturas de dados usadas pelo compilador
e runtime engine para representar regras compiladas.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.rules.value_objects import SemVer


class ConditionType(Enum):
    """Tipos de condição."""

    SIMPLE = "simple"
    LOGICAL = "logical"


class ActionType(Enum):
    """Tipos de ação."""

    ASSERT = "assert"
    TRANSFORM = "transform"
    SUGGEST = "suggest"


class RuleScope(Enum):
    """Escopo de aplicação da regra."""

    ROW = "row"  # Aplica a cada linha individualmente
    COLUMN = "column"  # Aplica à coluna inteira
    GLOBAL = "global"  # Aplica ao dataset completo


class Severity(Enum):
    """Severidade de violação."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ExecutionMode(Enum):
    """Modo de execução das regras."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    VECTORIZED = "vectorized"


class PhaseType(Enum):
    """Tipo de fase de execução."""

    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    SUGGESTION = "suggestion"


class TransformType(Enum):
    """Tipos de transformação."""

    UPPER = "upper"
    LOWER = "lower"
    TRIM = "trim"
    NORMALIZE = "normalize"
    NUMBER = "number"
    CURRENCY = "currency"
    DATE = "date"
    CUSTOM = "custom"


@dataclass(frozen=True)
class Transform:
    """Transformação de dados."""

    type: TransformType
    expression: str | None = None
    params: dict[str, Any] = dataclass_field(default_factory=dict)
    compiled_expression: Any | None = None


@dataclass(frozen=True)
class FieldMapping:
    """Mapeamento de campo para CCM."""

    source_field: str
    transform: Transform | None = None
    default_value: Any | None = None
    required: bool = False


@dataclass(frozen=True)
class CCMMapping:
    """Mapeamento completo para Canonical CSV Model."""

    field_mappings: dict[str, FieldMapping]
    transforms: dict[str, Transform] = dataclass_field(default_factory=dict)
    validation_order: list[str] = dataclass_field(default_factory=list)


@dataclass(frozen=True)
class CompiledCondition:
    """Condição compilada para execução otimizada."""

    type: ConditionType
    operator: str
    value: Any | None = None
    compiled_value: Any | None = None
    case_sensitive: bool = True
    field: str | None = None  # Campo alvo da condição

    # Para condições lógicas
    subconditions: list["CompiledCondition"] = dataclass_field(default_factory=list)
    logical_op: str | None = None  # "and", "or", "not"


@dataclass(frozen=True)
class CompiledAction:
    """Ação compilada para execução."""

    type: ActionType
    operation: str | None = None
    value: Any | None = None
    compiled_expression: Any | None = None
    params: dict[str, Any] = dataclass_field(default_factory=dict)
    stop_on_error: bool = False

    # Para sugestões
    suggestions: list[str] = dataclass_field(default_factory=list)
    confidence: float = 0.8


@dataclass(frozen=True)
class CompiledRule:
    """Regra compilada completa."""

    id: str
    field: str
    type: ActionType
    precedence: int
    scope: RuleScope

    condition: CompiledCondition
    action: CompiledAction

    message: str
    severity: Severity
    enabled: bool = True
    tags: list[str] = dataclass_field(default_factory=list)


@dataclass(frozen=True)
class RuleGroup:
    """Grupo de regras que executam juntas."""

    rule_ids: list[str]
    execution_mode: ExecutionMode
    dependencies: list[str] = dataclass_field(default_factory=list)


@dataclass(frozen=True)
class ExecutionPhase:
    """Fase de execução do plano."""

    name: str
    phase_type: PhaseType
    rule_groups: list[RuleGroup]
    can_vectorize: bool = False


@dataclass(frozen=True)
class ExecutionPlan:
    """Plano completo de execução otimizado."""

    phases: list[ExecutionPhase]
    optimizations: list[str] = dataclass_field(default_factory=list)
    field_index: dict[str, list[str]] = dataclass_field(default_factory=dict)
    precedence_index: dict[int, list[str]] = dataclass_field(default_factory=dict)
    parallel_groups: list[list[str]] = dataclass_field(default_factory=list)


@dataclass(frozen=True)
class CompatibilityConfig:
    """Configuração de compatibilidade."""

    auto_apply_patch: bool = True
    shadow_period_days: int = 30
    require_major_opt_in: bool = True
    validate_field_removals: bool = True
    validate_type_changes: bool = True
    validate_constraint_tightening: bool = True
    fallback_on_error: bool = True
    max_fallback_versions: int = 3


@dataclass(frozen=True)
class CompilationStats:
    """Estatísticas de compilação."""

    total_rules: int = 0
    rules_by_type: dict[str, int] = dataclass_field(default_factory=dict)
    rules_by_field: dict[str, int] = dataclass_field(default_factory=dict)
    compilation_time_ms: float = 0.0
    optimizations_applied: int = 0
    warnings_count: int = 0
    errors_count: int = 0


@dataclass(frozen=True)
class CompiledRuleSet:
    """Conjunto completo de regras compiladas."""

    # Metadados do IR
    schema_version: str
    checksum: str
    compiled_at: datetime
    marketplace: str
    version: SemVer

    # Conteúdo compilado
    ccm_mapping: CCMMapping
    rules: dict[str, CompiledRule]
    execution_plan: ExecutionPlan

    # Configurações
    compatibility: CompatibilityConfig
    stats: CompilationStats
