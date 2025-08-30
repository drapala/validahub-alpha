"""
Unit tests for Rules Compiler following TDD RED→GREEN→REFACTOR methodology.

Tests the compilation of YAML rule definitions into optimized intermediate representation (IR).
Validates schema compliance, rule optimization, and compilation performance.
"""

import pytest
import yaml
import json
import hashlib
import re
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timezone
from pathlib import Path

from src.domain.rules.engine.compiler import RuleCompiler, CompilationError
from src.domain.rules.engine.ir_types import (
    CompiledRuleSet, CompiledRule, CompiledCondition, CompiledAction,
    CCMMapping, FieldMapping, Transform, TransformType,
    ExecutionPlan, RuleGroup, ExecutionMode, ConditionType, ActionType,
    RuleScope, Severity, PhaseType
)
from src.domain.rules.value_objects import SemVer


class TestRuleCompiler:
    """Test suite for RuleCompiler following TDD principles."""
    
    @pytest.fixture
    def compiler(self) -> RuleCompiler:
        """Create RuleCompiler instance without schema validation."""
        return RuleCompiler()
    
    @pytest.fixture
    def compiler_with_schema(self, tmp_path) -> RuleCompiler:
        """Create RuleCompiler with mock schema."""
        schema_path = tmp_path / "test_schema.json"
        mock_schema = {
            "type": "object",
            "required": ["schema_version", "marketplace", "rules"],
            "properties": {
                "schema_version": {"type": "string"},
                "marketplace": {"type": "string"},
                "rules": {"type": "array"}
            }
        }
        schema_path.write_text(json.dumps(mock_schema))
        return RuleCompiler(str(schema_path))
    
    @pytest.fixture
    def minimal_yaml_content(self) -> dict:
        """Minimal valid YAML content for testing."""
        return {
            "schema_version": "1.0.0",
            "marketplace": "test_marketplace",
            "version": "1.0.0",
            "rules": [
                {
                    "id": "test_rule_1",
                    "field": "title",
                    "type": "assert",
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Title cannot be empty"
                }
            ]
        }
    
    @pytest.fixture
    def complex_yaml_content(self) -> dict:
        """Complex YAML content with multiple rule types."""
        return {
            "schema_version": "1.0.0",
            "marketplace": "mercado_livre",
            "version": "2.1.0",
            "ccm_mapping": {
                "title": {
                    "source": "product_title",
                    "transform": {
                        "type": "upper",
                        "expression": "str.upper()"
                    },
                    "required": True
                },
                "price": "product_price"
            },
            "rules": [
                {
                    "id": "title_validation",
                    "field": "title",
                    "type": "assert",
                    "precedence": 100,
                    "scope": "row",
                    "condition": {
                        "and": [
                            {"operator": "not_empty"},
                            {"operator": "length_gt", "value": 5}
                        ]
                    },
                    "action": {"type": "assert", "stop_on_error": True},
                    "message": "Title must be non-empty and longer than 5 characters",
                    "severity": "error",
                    "tags": ["required", "validation"]
                },
                {
                    "id": "price_transform",
                    "field": "price", 
                    "type": "transform",
                    "precedence": 200,
                    "condition": {"operator": "is_number"},
                    "action": {
                        "type": "transform",
                        "operation": "format",
                        "value": "R$ {:.2f}",
                        "params": {"decimal_places": 2}
                    },
                    "message": "Format price as currency"
                },
                {
                    "id": "category_suggestion",
                    "field": "category",
                    "type": "suggest",
                    "condition": {"operator": "empty"},
                    "action": {
                        "type": "suggest",
                        "suggestions": ["Electronics", "Fashion", "Home"],
                        "confidence": 0.75
                    },
                    "message": "Suggest category if missing"
                }
            ],
            "compatibility": {
                "auto_apply_patch": True,
                "shadow_period_days": 30,
                "require_major_opt_in": True
            }
        }


class TestRuleCompilerBasics:
    """Test basic compiler functionality."""
    
    def test_compile_yaml__with_string_input__compiles_successfully(self, compiler: RuleCompiler):
        """RED: Test compilation fails without implementation."""
        yaml_string = """
        schema_version: "1.0.0"
        marketplace: "test"
        version: "1.0.0" 
        rules:
          - id: "simple_rule"
            field: "title"
            type: "assert"
            condition:
              operator: "not_empty"
            action:
              type: "assert"
            message: "Title required"
        """
        
        result = compiler.compile_yaml(yaml_string)
        
        assert isinstance(result, CompiledRuleSet)
        assert result.marketplace == "test"
        assert len(result.rules) == 1
        assert "simple_rule" in result.rules
    
    def test_compile_yaml__with_dict_input__compiles_successfully(self, compiler: RuleCompiler, minimal_yaml_content: dict):
        """Test compilation with dictionary input."""
        result = compiler.compile_yaml(minimal_yaml_content)
        
        assert isinstance(result, CompiledRuleSet)
        assert result.marketplace == "test_marketplace"
        assert len(result.rules) == 1
        assert "test_rule_1" in result.rules
    
    def test_compile_yaml__generates_consistent_checksum__for_same_content(self, compiler: RuleCompiler):
        """Test that same content generates same checksum."""
        yaml_content = {"schema_version": "1.0.0", "marketplace": "test", "rules": []}
        
        result1 = compiler.compile_yaml(yaml_content.copy())
        result2 = compiler.compile_yaml(yaml_content.copy())
        
        assert result1.checksum == result2.checksum
        assert result1.checksum is not None
        assert len(result1.checksum) == 64  # SHA-256 hex length
    
    def test_compile_yaml__generates_different_checksum__for_different_content(self, compiler: RuleCompiler):
        """Test that different content generates different checksums."""
        content1 = {"schema_version": "1.0.0", "marketplace": "test1", "rules": []}
        content2 = {"schema_version": "1.0.0", "marketplace": "test2", "rules": []}
        
        result1 = compiler.compile_yaml(content1)
        result2 = compiler.compile_yaml(content2)
        
        assert result1.checksum != result2.checksum
    
    def test_compile_yaml__with_invalid_yaml__raises_compilation_error(self, compiler: RuleCompiler):
        """Test that invalid YAML raises CompilationError."""
        invalid_yaml = "invalid: yaml: content: [unclosed bracket"
        
        with pytest.raises(CompilationError) as exc_info:
            compiler.compile_yaml(invalid_yaml)
        
        assert "Erro de compilação" in str(exc_info.value)


class TestRuleCompilerSchemaValidation:
    """Test schema validation during compilation."""
    
    def test_compile_yaml__with_valid_schema__validates_successfully(
        self, 
        compiler_with_schema: RuleCompiler, 
        minimal_yaml_content: dict
    ):
        """Test successful schema validation."""
        result = compiler_with_schema.compile_yaml(minimal_yaml_content)
        
        assert isinstance(result, CompiledRuleSet)
        assert result.schema_version == "1.0.0"
    
    def test_compile_yaml__with_invalid_schema__raises_compilation_error(
        self, 
        compiler_with_schema: RuleCompiler
    ):
        """Test that schema violations raise CompilationError."""
        invalid_content = {"schema_version": "1.0.0"}  # Missing required fields
        
        with pytest.raises(CompilationError) as exc_info:
            compiler_with_schema.compile_yaml(invalid_content)
        
        assert "Erro de validação de schema" in str(exc_info.value)
    
    def test_compile_yaml__with_missing_schema_file__continues_without_validation(self, tmp_path):
        """Test graceful handling of missing schema file."""
        nonexistent_schema = tmp_path / "nonexistent.json"
        compiler = RuleCompiler(str(nonexistent_schema))
        
        minimal_content = {"schema_version": "1.0.0", "marketplace": "test", "rules": []}
        result = compiler.compile_yaml(minimal_content)
        
        assert isinstance(result, CompiledRuleSet)  # Should compile without schema validation


class TestRuleCompilerCCMMapping:
    """Test CCM (Common Commerce Model) mapping compilation."""
    
    def test_compile_ccm_mapping__with_simple_mapping__creates_field_mappings(self, compiler: RuleCompiler):
        """Test simple string field mappings."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": [],
            "ccm_mapping": {
                "title": "product_title",
                "price": "product_price"
            }
        }
        
        result = compiler.compile_yaml(yaml_content)
        
        assert result.ccm_mapping is not None
        assert "title" in result.ccm_mapping.field_mappings
        assert "price" in result.ccm_mapping.field_mappings
        assert result.ccm_mapping.field_mappings["title"].source_field == "product_title"
        assert result.ccm_mapping.field_mappings["price"].source_field == "product_price"
    
    def test_compile_ccm_mapping__with_complex_mapping__creates_field_mappings_with_transforms(
        self, 
        compiler: RuleCompiler, 
        complex_yaml_content: dict
    ):
        """Test complex field mappings with transforms."""
        result = compiler.compile_yaml(complex_yaml_content)
        
        ccm = result.ccm_mapping
        assert ccm is not None
        
        # Check title mapping with transform
        title_mapping = ccm.field_mappings["title"]
        assert title_mapping.source_field == "product_title"
        assert title_mapping.transform is not None
        assert title_mapping.transform.type == TransformType.UPPER
        assert title_mapping.required is True
        
        # Check simple price mapping
        price_mapping = ccm.field_mappings["price"]
        assert price_mapping.source_field == "product_price"
        assert price_mapping.transform is None
        assert price_mapping.required is False


class TestRuleCompilerRules:
    """Test rule compilation logic."""
    
    def test_compile_single_rule__with_assert_type__creates_compiled_rule(self, compiler: RuleCompiler):
        """Test compilation of assertion rules."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": [
                {
                    "id": "title_required",
                    "field": "title",
                    "type": "assert",
                    "precedence": 100,
                    "scope": "row",
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert", "stop_on_error": True},
                    "message": "Title is required",
                    "severity": "error",
                    "enabled": True,
                    "tags": ["required"]
                }
            ]
        }
        
        result = compiler.compile_yaml(yaml_content)
        
        rule = result.rules["title_required"]
        assert rule.id == "title_required"
        assert rule.field == "title"
        assert rule.type == ActionType.ASSERT
        assert rule.precedence == 100
        assert rule.scope == RuleScope.ROW
        assert rule.condition.operator == "not_empty"
        assert rule.action.type == ActionType.ASSERT
        assert rule.action.stop_on_error is True
        assert rule.message == "Title is required"
        assert rule.severity == Severity.ERROR
        assert rule.enabled is True
        assert "required" in rule.tags
    
    def test_compile_single_rule__with_transform_type__creates_compiled_rule(self, compiler: RuleCompiler):
        """Test compilation of transformation rules."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": [
                {
                    "id": "price_format",
                    "field": "price",
                    "type": "transform",
                    "action": {
                        "type": "transform",
                        "operation": "format",
                        "value": "R$ {:.2f}",
                        "params": {"currency": "BRL"}
                    },
                    "message": "Format price"
                }
            ]
        }
        
        result = compiler.compile_yaml(yaml_content)
        
        rule = result.rules["price_format"]
        assert rule.type == ActionType.TRANSFORM
        assert rule.action.operation == "format"
        assert rule.action.value == "R$ {:.2f}"
        assert rule.action.params == {"currency": "BRL"}
    
    def test_compile_single_rule__with_suggest_type__creates_compiled_rule(self, compiler: RuleCompiler):
        """Test compilation of suggestion rules."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": [
                {
                    "id": "category_suggest",
                    "field": "category",
                    "type": "suggest",
                    "action": {
                        "type": "suggest",
                        "suggestions": ["Electronics", "Fashion"],
                        "confidence": 0.8
                    },
                    "message": "Suggest category"
                }
            ]
        }
        
        result = compiler.compile_yaml(yaml_content)
        
        rule = result.rules["category_suggest"]
        assert rule.type == ActionType.SUGGEST
        assert rule.action.suggestions == ["Electronics", "Fashion"]
        assert rule.action.confidence == 0.8
    
    def test_compile_single_rule__with_logical_condition__creates_compiled_condition(self, compiler: RuleCompiler):
        """Test compilation of complex logical conditions."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": [
                {
                    "id": "complex_condition",
                    "field": "title",
                    "type": "assert",
                    "condition": {
                        "and": [
                            {"operator": "not_empty"},
                            {
                                "or": [
                                    {"operator": "length_gt", "value": 10},
                                    {"operator": "contains", "value": "Premium"}
                                ]
                            }
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "Complex validation"
                }
            ]
        }
        
        result = compiler.compile_yaml(yaml_content)
        
        rule = result.rules["complex_condition"]
        condition = rule.condition
        assert condition.type == ConditionType.LOGICAL
        assert condition.logical_op == "and"
        assert len(condition.subconditions) == 2
        
        # Check nested OR condition
        or_condition = condition.subconditions[1]
        assert or_condition.logical_op == "or"
        assert len(or_condition.subconditions) == 2
    
    def test_compile_single_rule__with_regex_condition__compiles_regex_pattern(self, compiler: RuleCompiler):
        """Test that regex patterns are compiled and cached."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": [
                {
                    "id": "email_validation",
                    "field": "email",
                    "type": "assert",
                    "condition": {
                        "operator": "matches",
                        "value": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                    },
                    "action": {"type": "assert"},
                    "message": "Invalid email format"
                }
            ]
        }
        
        result = compiler.compile_yaml(yaml_content)
        
        rule = result.rules["email_validation"]
        assert rule.condition.operator == "matches"
        assert rule.condition.compiled_value is not None
        assert isinstance(rule.condition.compiled_value, re.Pattern)
    
    def test_compile_single_rule__with_invalid_regex__raises_compilation_error(self, compiler: RuleCompiler):
        """Test that invalid regex patterns raise CompilationError."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": [
                {
                    "id": "invalid_regex",
                    "field": "test",
                    "type": "assert",
                    "condition": {
                        "operator": "matches",
                        "value": "[unclosed bracket"  # Invalid regex
                    },
                    "action": {"type": "assert"},
                    "message": "Test"
                }
            ]
        }
        
        with pytest.raises(CompilationError) as exc_info:
            compiler.compile_yaml(yaml_content)
        
        assert "Regex inválido" in str(exc_info.value)
        assert exc_info.value.rule_id == "invalid_regex"


class TestRuleCompilerExecutionPlan:
    """Test execution plan generation and optimization."""
    
    def test_create_execution_plan__with_mixed_rules__creates_optimized_plan(
        self, 
        compiler: RuleCompiler, 
        complex_yaml_content: dict
    ):
        """Test that execution plan is created with proper phases."""
        result = compiler.compile_yaml(complex_yaml_content)
        
        plan = result.execution_plan
        assert plan is not None
        assert len(plan.phases) > 0
        
        # Check that optimizations are applied
        assert "precedence_ordering" in plan.optimizations
        assert "dependency_resolution" in plan.optimizations
        
        # Check field index is created
        assert plan.field_index is not None
        assert "title" in plan.field_index
        assert "price" in plan.field_index
        
        # Check precedence index is created
        assert plan.precedence_index is not None
        assert 100 in plan.precedence_index
        assert 200 in plan.precedence_index
    
    def test_create_execution_plan__identifies_vectorizable_rules__correctly(self, compiler: RuleCompiler):
        """Test identification of rules suitable for vectorization."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": [
                {
                    "id": "vectorizable_rule",
                    "field": "price",
                    "type": "assert",
                    "scope": "row",
                    "condition": {"operator": "gt", "value": 0},
                    "action": {"type": "assert"},
                    "message": "Price must be positive"
                },
                {
                    "id": "complex_rule",
                    "field": "title",
                    "type": "transform",
                    "scope": "global",
                    "condition": {
                        "and": [
                            {"operator": "not_empty"},
                            {"operator": "matches", "value": "complex_pattern"}
                        ]
                    },
                    "action": {"type": "transform", "operation": "custom", "expression": "complex_transform()"},
                    "message": "Complex transformation"
                }
            ]
        }
        
        result = compiler.compile_yaml(yaml_content)
        
        # Check that vectorizable rule is identified
        plan = result.execution_plan
        vectorizable_found = False
        sequential_found = False
        
        for phase in plan.phases:
            if phase.can_vectorize:
                vectorizable_found = True
            for group in phase.rule_groups:
                if group.execution_mode == ExecutionMode.VECTORIZED:
                    vectorizable_found = True
                elif group.execution_mode == ExecutionMode.SEQUENTIAL:
                    sequential_found = True
        
        # Complex rules should use sequential execution
        assert sequential_found


class TestRuleCompilerStatistics:
    """Test compilation statistics and metrics."""
    
    def test_compile_yaml__tracks_compilation_stats__correctly(
        self, 
        compiler: RuleCompiler, 
        complex_yaml_content: dict
    ):
        """Test that compilation statistics are tracked correctly."""
        result = compiler.compile_yaml(complex_yaml_content)
        
        stats = result.stats
        assert stats is not None
        assert stats.total_rules == 3
        assert stats.compilation_time_ms > 0
        
        # Check rule type counts
        assert stats.rules_by_type["assert"] == 1
        assert stats.rules_by_type["transform"] == 1
        assert stats.rules_by_type["suggest"] == 1
        
        # Check field counts
        assert stats.rules_by_field["title"] == 1
        assert stats.rules_by_field["price"] == 1
        assert stats.rules_by_field["category"] == 1


class TestRuleCompilerCaching:
    """Test regex and expression caching."""
    
    def test_compile_regex__caches_patterns__for_reuse(self, compiler: RuleCompiler):
        """Test that regex patterns are cached for performance."""
        pattern = r"test_pattern_\d+"
        
        # First compilation
        compiled1 = compiler._compile_regex(pattern)
        cache_size1 = len(compiler._regex_cache)
        
        # Second compilation (should use cache)
        compiled2 = compiler._compile_regex(pattern)
        cache_size2 = len(compiler._regex_cache)
        
        assert compiled1 is compiled2  # Same object reference
        assert cache_size1 == cache_size2  # Cache didn't grow
        assert pattern in compiler._regex_cache


class TestRuleCompilerErrorHandling:
    """Test error handling and validation."""
    
    def test_compile_yaml__with_missing_required_field__raises_compilation_error(self, compiler: RuleCompiler):
        """Test that missing required rule fields raise CompilationError."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": [
                {
                    "id": "incomplete_rule",
                    # Missing required 'field' and 'type'
                    "action": {"type": "assert"},
                    "message": "Incomplete rule"
                }
            ]
        }
        
        with pytest.raises(CompilationError) as exc_info:
            compiler.compile_yaml(yaml_content)
        
        assert exc_info.value.rule_id == "incomplete_rule"
    
    def test_compile_yaml__with_unknown_action_type__raises_compilation_error(self, compiler: RuleCompiler):
        """Test that unknown action types raise CompilationError."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": [
                {
                    "id": "unknown_action",
                    "field": "test",
                    "type": "assert",
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "unknown_action_type"},  # Invalid action type
                    "message": "Unknown action"
                }
            ]
        }
        
        with pytest.raises(CompilationError) as exc_info:
            compiler.compile_yaml(yaml_content)
        
        assert "Tipo de ação desconhecido" in str(exc_info.value)
    
    def test_compile_yaml__with_invalid_logical_condition__raises_compilation_error(self, compiler: RuleCompiler):
        """Test that invalid logical conditions raise CompilationError."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": [
                {
                    "id": "invalid_logic",
                    "field": "test",
                    "type": "assert",
                    "condition": {"invalid_logic": []},  # Invalid logical operator
                    "action": {"type": "assert"},
                    "message": "Invalid logic"
                }
            ]
        }
        
        with pytest.raises(CompilationError) as exc_info:
            compiler.compile_yaml(yaml_content)
        
        assert "Condição lógica inválida" in str(exc_info.value)


class TestRuleCompilerCompatibilityConfig:
    """Test compatibility configuration compilation."""
    
    def test_create_compatibility_config__with_full_config__creates_complete_config(
        self, 
        compiler: RuleCompiler
    ):
        """Test creation of complete compatibility configuration."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": [],
            "compatibility": {
                "auto_apply_patch": False,
                "shadow_period_days": 60,
                "require_major_opt_in": True,
                "validate_field_removals": True,
                "validate_type_changes": False,
                "validate_constraint_tightening": True,
                "fallback_on_error": False,
                "max_fallback_versions": 5
            }
        }
        
        result = compiler.compile_yaml(yaml_content)
        
        config = result.compatibility
        assert config.auto_apply_patch is False
        assert config.shadow_period_days == 60
        assert config.require_major_opt_in is True
        assert config.validate_field_removals is True
        assert config.validate_type_changes is False
        assert config.validate_constraint_tightening is True
        assert config.fallback_on_error is False
        assert config.max_fallback_versions == 5
    
    def test_create_compatibility_config__with_default_values__uses_defaults(self, compiler: RuleCompiler):
        """Test that missing compatibility config uses default values."""
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": []
        }
        
        result = compiler.compile_yaml(yaml_content)
        
        config = result.compatibility
        assert config.auto_apply_patch is True  # Default
        assert config.shadow_period_days == 30  # Default
        assert config.require_major_opt_in is True  # Default


# Performance tests
class TestRuleCompilerPerformance:
    """Test compilation performance characteristics."""
    
    def test_compile_yaml__with_large_ruleset__completes_within_time_limit(self, compiler: RuleCompiler):
        """Test that large rulesets compile within reasonable time."""
        import time
        
        # Generate large ruleset
        rules = []
        for i in range(100):
            rules.append({
                "id": f"rule_{i}",
                "field": f"field_{i % 10}",
                "type": "assert",
                "condition": {"operator": "not_empty"},
                "action": {"type": "assert"},
                "message": f"Rule {i} validation"
            })
        
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": rules
        }
        
        start_time = time.perf_counter()
        result = compiler.compile_yaml(yaml_content)
        compilation_time = (time.perf_counter() - start_time) * 1000
        
        assert compilation_time < 1000  # Should compile in under 1 second
        assert len(result.rules) == 100
        assert result.stats.compilation_time_ms > 0
    
    def test_compile_yaml__regex_caching__improves_performance_on_repeated_patterns(self, compiler: RuleCompiler):
        """Test that regex caching improves performance for repeated patterns."""
        pattern = r"^[A-Z]{2,3}-\d{4,6}$"
        
        # Create multiple rules with same regex pattern
        rules = []
        for i in range(20):
            rules.append({
                "id": f"regex_rule_{i}",
                "field": f"field_{i}",
                "type": "assert", 
                "condition": {"operator": "matches", "value": pattern},
                "action": {"type": "assert"},
                "message": f"Regex rule {i}"
            })
        
        yaml_content = {
            "schema_version": "1.0.0",
            "marketplace": "test",
            "rules": rules
        }
        
        result = compiler.compile_yaml(yaml_content)
        
        # Should have only compiled regex once
        assert len(compiler._regex_cache) == 1
        assert pattern in compiler._regex_cache
        
        # All rules should reference the same compiled pattern
        compiled_patterns = [
            rule.condition.compiled_value 
            for rule in result.rules.values() 
            if rule.condition.compiled_value
        ]
        assert len(set(id(pattern) for pattern in compiled_patterns)) == 1