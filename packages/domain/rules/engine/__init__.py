"""
ValidaHub Rules Engine.

Sistema de regras agnostic para marketplaces com compilação YAML → IR → Runtime.
"""

from .ccm import CCM, CanonicalCSVModel
from .compiler import CompilationError, RuleCompiler
from .ir_types import (
    ActionType,
    CCMMapping,
    CompiledAction,
    CompiledCondition,
    CompiledRule,
    CompiledRuleSet,
    ConditionType,
    ExecutionMode,
    FieldMapping,
    RuleScope,
    Severity,
    Transform,
)
from .runtime import ExecutionResult, RuleExecutionEngine

__version__ = "1.0.0"

__all__ = [
    # Core classes
    "RuleCompiler",
    "RuleExecutionEngine",
    "CCM",
    "CanonicalCSVModel",
    # Data structures
    "CompiledRuleSet",
    "CompiledRule",
    "CompiledCondition",
    "CompiledAction",
    "CCMMapping",
    "FieldMapping",
    "Transform",
    "ExecutionResult",
    # Enums
    "ActionType",
    "ConditionType",
    "RuleScope",
    "Severity",
    "ExecutionMode",
    # Exceptions
    "CompilationError",
]
