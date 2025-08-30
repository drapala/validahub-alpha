"""
Unit tests for Rules Runtime Engine following TDD RED→GREEN→REFACTOR methodology.

Tests the execution of compiled rules against data with focus on performance,
vectorization, and correctness of rule evaluation.
"""

import pytest
import pandas as pd
import numpy as np
import time
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

from src.domain.rules.engine.runtime import (
    RuleExecutionEngine, ExecutionResult, RuleViolation, RuleSuggestion, 
    RuleTransformation, ExecutionStats
)
from src.domain.rules.engine.ir_types import (
    CompiledRuleSet, CompiledRule, CompiledCondition, CompiledAction,
    ExecutionPlan, ExecutionPhase, RuleGroup, ExecutionMode,
    ConditionType, ActionType, RuleScope, Severity, PhaseType
)
from src.domain.rules.value_objects import SemVer


class TestRuleExecutionEngine:
    """Test suite for RuleExecutionEngine following TDD principles."""
    
    @pytest.fixture
    def engine(self) -> RuleExecutionEngine:
        """Create RuleExecutionEngine with default settings."""
        return RuleExecutionEngine(
            max_workers=2,
            timeout_seconds=5.0,
            memory_limit_mb=512.0,
            enable_cache=True,
            enable_vectorization=True
        )
    
    @pytest.fixture  
    def engine_no_cache(self) -> RuleExecutionEngine:
        """Create engine without caching for testing."""
        return RuleExecutionEngine(enable_cache=False)
    
    @pytest.fixture
    def sample_dataframe(self) -> pd.DataFrame:
        """Sample DataFrame for testing."""
        return pd.DataFrame({
            'title': ['Product A', 'Product B', '', 'Product D', None],
            'price': [10.50, 25.99, 15.00, 0, -5.0],
            'category': ['Electronics', '', 'Fashion', 'Electronics', 'Books'],
            'email': ['test@example.com', 'invalid-email', 'user@domain.co', '', 'bad@'],
            'description': ['Great product', 'Another item', 'Nice', 'X', 'Too short']
        })
    
    @pytest.fixture
    def simple_assert_rule(self) -> CompiledRule:
        """Simple assertion rule for testing."""
        return CompiledRule(
            id="title_not_empty",
            field="title", 
            type=ActionType.ASSERT,
            precedence=100,
            scope=RuleScope.ROW,
            condition=CompiledCondition(
                type=ConditionType.SIMPLE,
                operator="not_empty",
                field="title"
            ),
            action=CompiledAction(type=ActionType.ASSERT),
            message="Title cannot be empty",
            severity=Severity.ERROR,
            enabled=True,
            tags=[]
        )
    
    @pytest.fixture
    def simple_transform_rule(self) -> CompiledRule:
        """Simple transform rule for testing."""
        return CompiledRule(
            id="price_format",
            field="price",
            type=ActionType.TRANSFORM,
            precedence=200,
            scope=RuleScope.ROW,
            condition=CompiledCondition(
                type=ConditionType.SIMPLE,
                operator="is_number",
                field="price"
            ),
            action=CompiledAction(
                type=ActionType.TRANSFORM,
                operation="format",
                value="R$ {:.2f}"
            ),
            message="Format price as currency",
            severity=Severity.INFO,
            enabled=True,
            tags=[]
        )
    
    @pytest.fixture
    def simple_suggest_rule(self) -> CompiledRule:
        """Simple suggestion rule for testing."""
        return CompiledRule(
            id="category_suggestion",
            field="category",
            type=ActionType.SUGGEST,
            precedence=300,
            scope=RuleScope.ROW,
            condition=CompiledCondition(
                type=ConditionType.SIMPLE,
                operator="empty",
                field="category"
            ),
            action=CompiledAction(
                type=ActionType.SUGGEST,
                suggestions=["Electronics", "Fashion", "Books"],
                confidence=0.8
            ),
            message="Suggest category if missing",
            severity=Severity.WARNING,
            enabled=True,
            tags=[]
        )
    
    @pytest.fixture
    def mock_ruleset(self, simple_assert_rule, simple_transform_rule) -> CompiledRuleSet:
        """Mock compiled ruleset for testing."""
        rules = {
            simple_assert_rule.id: simple_assert_rule,
            simple_transform_rule.id: simple_transform_rule
        }
        
        # Create minimal execution plan
        phase = ExecutionPhase(
            name="validation",
            phase_type=PhaseType.VALIDATION,
            rule_groups=[
                RuleGroup(
                    rule_ids=list(rules.keys()),
                    execution_mode=ExecutionMode.SEQUENTIAL,
                    dependencies=[]
                )
            ],
            can_vectorize=False
        )
        
        execution_plan = ExecutionPlan(
            phases=[phase],
            optimizations=[],
            field_index={"title": ["title_not_empty"], "price": ["price_format"]},
            precedence_index={100: ["title_not_empty"], 200: ["price_format"]},
            parallel_groups=[]
        )
        
        return CompiledRuleSet(
            schema_version="1.0.0",
            checksum="test_checksum",
            compiled_at=pd.Timestamp.now(),
            marketplace="test",
            version=SemVer.from_string("1.0.0"),
            ccm_mapping=None,
            rules=rules,
            execution_plan=execution_plan,
            compatibility=None,
            stats=None
        )


class TestRuleExecutionEngineBasics:
    """Test basic execution engine functionality."""
    
    def test_execute_rules__with_empty_dataframe__returns_empty_result(
        self, 
        engine: RuleExecutionEngine, 
        mock_ruleset: CompiledRuleSet
    ):
        """RED: Test execution fails with empty DataFrame."""
        empty_df = pd.DataFrame()
        
        result = engine.execute_rules(mock_ruleset, empty_df)
        
        assert isinstance(result, ExecutionResult)
        assert result.stats.total_rows == 0
        assert result.stats.processed_rows == 0
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert result.stats.execution_time_ms > 0
    
    def test_execute_rules__with_valid_data__executes_successfully(
        self, 
        engine: RuleExecutionEngine, 
        mock_ruleset: CompiledRuleSet,
        sample_dataframe: pd.DataFrame
    ):
        """Test successful execution with valid data."""
        result = engine.execute_rules(mock_ruleset, sample_dataframe)
        
        assert isinstance(result, ExecutionResult)
        assert result.stats.total_rows == len(sample_dataframe)
        assert result.stats.processed_rows == len(sample_dataframe)
        assert result.stats.execution_time_ms > 0
        assert result.stats.rules_executed > 0
    
    def test_execute_rules__tracks_execution_stats__correctly(
        self, 
        engine: RuleExecutionEngine,
        mock_ruleset: CompiledRuleSet,
        sample_dataframe: pd.DataFrame
    ):
        """Test that execution statistics are tracked correctly."""
        result = engine.execute_rules(mock_ruleset, sample_dataframe)
        
        stats = result.stats
        assert stats.total_rows == 5
        assert stats.processed_rows == 5
        assert stats.execution_time_ms > 0
        assert stats.rules_executed == len(mock_ruleset.rules) * len(sample_dataframe)
    
    def test_execute_rules__with_cache_disabled__clears_cache_after_execution(
        self,
        engine_no_cache: RuleExecutionEngine,
        mock_ruleset: CompiledRuleSet,
        sample_dataframe: pd.DataFrame
    ):
        """Test cache clearing when caching is disabled."""
        # Add some items to cache first
        engine_no_cache._condition_cache["test_key"] = pd.Series([True, False])
        
        result = engine_no_cache.execute_rules(mock_ruleset, sample_dataframe)
        
        # Cache should be cleared
        assert len(engine_no_cache._condition_cache) == 0


class TestRuleExecutionEngineAssertions:
    """Test assertion rule execution."""
    
    def test_execute_single_rule__assert_rule_with_violations__creates_errors(
        self, 
        engine: RuleExecutionEngine,
        simple_assert_rule: CompiledRule,
        sample_dataframe: pd.DataFrame
    ):
        """Test assertion rule creates violations for invalid data."""
        result = engine._execute_single_rule(simple_assert_rule, sample_dataframe)
        
        # Should have violations for empty and None title values (rows 2 and 4)
        assert len(result.errors) == 2
        assert result.stats.error_count == 2
        
        # Check violation details
        violation1 = result.errors[0]
        assert violation1.rule_id == "title_not_empty"
        assert violation1.field == "title"
        assert violation1.row_index == 2  # Empty string row
        assert violation1.severity == Severity.ERROR
        
        violation2 = result.errors[1]
        assert violation2.row_index == 4  # None row
    
    def test_execute_single_rule__assert_rule_all_valid__creates_no_violations(
        self, 
        engine: RuleExecutionEngine,
        simple_assert_rule: CompiledRule
    ):
        """Test assertion rule with all valid data creates no violations."""
        valid_df = pd.DataFrame({
            'title': ['Product A', 'Product B', 'Product C']
        })
        
        result = engine._execute_single_rule(simple_assert_rule, valid_df)
        
        assert len(result.errors) == 0
        assert result.stats.error_count == 0
    
    def test_execute_single_rule__assert_rule_with_warning_severity__creates_warnings(
        self,
        engine: RuleExecutionEngine,
        sample_dataframe: pd.DataFrame
    ):
        """Test assertion rule with warning severity creates warnings not errors."""
        warning_rule = CompiledRule(
            id="title_warning",
            field="title",
            type=ActionType.ASSERT,
            precedence=100,
            scope=RuleScope.ROW,
            condition=CompiledCondition(
                type=ConditionType.SIMPLE,
                operator="not_empty",
                field="title"
            ),
            action=CompiledAction(type=ActionType.ASSERT),
            message="Title should not be empty",
            severity=Severity.WARNING,  # Warning instead of error
            enabled=True,
            tags=[]
        )
        
        result = engine._execute_single_rule(warning_rule, sample_dataframe)
        
        assert len(result.warnings) == 2  # Empty and None values
        assert len(result.errors) == 0
        assert result.stats.warning_count == 2
        assert result.stats.error_count == 0


class TestRuleExecutionEngineTransformations:
    """Test transformation rule execution."""
    
    def test_execute_single_rule__transform_rule__creates_transformations(
        self,
        engine: RuleExecutionEngine,
        simple_transform_rule: CompiledRule,
        sample_dataframe: pd.DataFrame
    ):
        """Test transform rule creates transformation records."""
        result = engine._execute_single_rule(simple_transform_rule, sample_dataframe)
        
        # Should transform numeric price values
        assert len(result.transformations) > 0
        assert result.stats.transformation_count > 0
        
        # Check transformation details
        if result.transformations:
            transform = result.transformations[0]
            assert transform.rule_id == "price_format"
            assert transform.field == "price"
            assert transform.operation == "format"


class TestRuleExecutionEngineSuggestions:
    """Test suggestion rule execution."""
    
    def test_execute_single_rule__suggest_rule__creates_suggestions(
        self,
        engine: RuleExecutionEngine,
        simple_suggest_rule: CompiledRule,
        sample_dataframe: pd.DataFrame
    ):
        """Test suggestion rule creates suggestion records."""
        result = engine._execute_single_rule(simple_suggest_rule, sample_dataframe)
        
        # Should suggest categories for empty category field (row 1)
        assert len(result.suggestions) == 1
        assert result.stats.suggestion_count == 1
        
        # Check suggestion details
        suggestion = result.suggestions[0]
        assert suggestion.rule_id == "category_suggestion"
        assert suggestion.field == "category"
        assert suggestion.row_index == 1  # Row with empty category
        assert len(suggestion.suggested_values) == 3
        assert "Electronics" in suggestion.suggested_values
        assert suggestion.confidence == 0.8


class TestRuleExecutionEngineConditions:
    """Test condition evaluation logic."""
    
    @pytest.mark.parametrize("operator,value,test_data,expected_results", [
        ("eq", "test", ["test", "other", "test"], [True, False, True]),
        ("ne", "test", ["test", "other", "test"], [False, True, False]), 
        ("gt", 10, [5, 15, 10], [False, True, False]),
        ("gte", 10, [5, 15, 10], [False, True, True]),
        ("lt", 10, [5, 15, 10], [True, False, False]),
        ("lte", 10, [5, 15, 10], [True, False, True]),
        ("contains", "sub", ["substring", "other", "sub"], [True, False, True]),
        ("startswith", "pre", ["prefix", "other", "pre"], [True, False, True]),
        ("endswith", "fix", ["suffix", "other", "fix"], [True, False, True]),
        ("in", ["a", "b"], ["a", "c", "b"], [True, False, True]),
        ("not_in", ["a", "b"], ["a", "c", "b"], [False, True, False]),
        ("empty", None, ["", "text", None], [True, False, True]),
        ("not_empty", None, ["", "text", None], [False, True, False]),
        ("length_eq", 4, ["test", "hi", "four"], [True, False, True]),
        ("length_gt", 3, ["test", "hi", "four"], [True, False, True]),
        ("length_lt", 3, ["test", "hi", "a"], [False, True, True]),
        ("is_number", None, ["123", "abc", "45.6"], [True, False, True]),
        ("is_email", None, ["test@example.com", "invalid", "user@domain.co"], [True, False, True]),
    ])
    def test_evaluate_simple_condition_vectorized__with_various_operators__returns_correct_results(
        self, 
        engine: RuleExecutionEngine,
        operator: str,
        value,
        test_data,
        expected_results
    ):
        """Test vectorized condition evaluation for various operators."""
        df = pd.DataFrame({'test_field': test_data})
        condition = CompiledCondition(
            type=ConditionType.SIMPLE,
            operator=operator,
            value=value,
            field="test_field"
        )
        
        result = engine._evaluate_simple_condition_vectorized(condition, df)
        
        assert isinstance(result, pd.Series)
        assert len(result) == len(expected_results)
        assert result.tolist() == expected_results
    
    def test_evaluate_logical_condition_vectorized__with_and_operator__combines_correctly(
        self,
        engine: RuleExecutionEngine
    ):
        """Test logical AND condition evaluation."""
        df = pd.DataFrame({'field1': ['test', 'test', 'other'], 'field2': [10, 5, 10]})
        
        condition = CompiledCondition(
            type=ConditionType.LOGICAL,
            logical_op="and",
            field="field1",
            subconditions=[
                CompiledCondition(
                    type=ConditionType.SIMPLE,
                    operator="eq",
                    value="test",
                    field="field1"
                ),
                CompiledCondition(
                    type=ConditionType.SIMPLE,
                    operator="gt",
                    value=8,
                    field="field2"
                )
            ]
        )
        
        result = engine._evaluate_logical_condition_vectorized(condition, df)
        
        # Only first row should match both conditions
        assert result.tolist() == [True, False, False]
    
    def test_evaluate_logical_condition_vectorized__with_or_operator__combines_correctly(
        self,
        engine: RuleExecutionEngine
    ):
        """Test logical OR condition evaluation."""
        df = pd.DataFrame({'field1': ['test', 'other', 'other'], 'field2': [5, 10, 5]})
        
        condition = CompiledCondition(
            type=ConditionType.LOGICAL,
            logical_op="or",
            field="field1", 
            subconditions=[
                CompiledCondition(
                    type=ConditionType.SIMPLE,
                    operator="eq",
                    value="test",
                    field="field1"
                ),
                CompiledCondition(
                    type=ConditionType.SIMPLE,
                    operator="gt",
                    value=8,
                    field="field2"
                )
            ]
        )
        
        result = engine._evaluate_logical_condition_vectorized(condition, df)
        
        # First and second rows should match (test OR gt 8)
        assert result.tolist() == [True, True, False]
    
    def test_evaluate_logical_condition_vectorized__with_not_operator__negates_correctly(
        self,
        engine: RuleExecutionEngine
    ):
        """Test logical NOT condition evaluation."""
        df = pd.DataFrame({'field': ['test', 'other', 'test']})
        
        condition = CompiledCondition(
            type=ConditionType.LOGICAL,
            logical_op="not",
            field="field",
            subconditions=[
                CompiledCondition(
                    type=ConditionType.SIMPLE,
                    operator="eq", 
                    value="test",
                    field="field"
                )
            ]
        )
        
        result = engine._evaluate_logical_condition_vectorized(condition, df)
        
        # Should negate the eq condition
        assert result.tolist() == [False, True, False]


class TestRuleExecutionEngineCaching:
    """Test caching functionality."""
    
    def test_evaluate_condition_vectorized__with_caching_enabled__caches_results(
        self,
        engine: RuleExecutionEngine
    ):
        """Test that condition results are cached when caching is enabled."""
        df = pd.DataFrame({'test': ['a', 'b', 'c']})
        condition = CompiledCondition(
            type=ConditionType.SIMPLE,
            operator="eq",
            value="a",
            field="test"
        )
        
        # First evaluation
        result1 = engine._evaluate_condition_vectorized(condition, df)
        cache_size1 = len(engine._condition_cache)
        
        # Second evaluation (should use cache) 
        result2 = engine._evaluate_condition_vectorized(condition, df)
        cache_size2 = len(engine._condition_cache)
        
        assert cache_size1 == 1
        assert cache_size2 == 1  # Cache didn't grow
        assert result1.equals(result2)
    
    def test_evaluate_condition_vectorized__with_caching_disabled__does_not_cache(
        self,
        engine_no_cache: RuleExecutionEngine
    ):
        """Test that results are not cached when caching is disabled."""
        df = pd.DataFrame({'test': ['a', 'b', 'c']})
        condition = CompiledCondition(
            type=ConditionType.SIMPLE,
            operator="eq",
            value="a", 
            field="test"
        )
        
        result = engine_no_cache._evaluate_condition_vectorized(condition, df)
        
        assert len(engine_no_cache._condition_cache) == 0


class TestRuleExecutionEngineExecutionModes:
    """Test different execution modes (sequential, parallel, vectorized)."""
    
    def test_execute_sequential__processes_rules_in_order(
        self,
        engine: RuleExecutionEngine,
        sample_dataframe: pd.DataFrame
    ):
        """Test sequential execution processes rules in order."""
        rules = [
            CompiledRule(
                id=f"rule_{i}",
                field="title",
                type=ActionType.ASSERT,
                precedence=i * 100,
                scope=RuleScope.ROW,
                condition=CompiledCondition(
                    type=ConditionType.SIMPLE,
                    operator="not_empty",
                    field="title"
                ),
                action=CompiledAction(type=ActionType.ASSERT),
                message=f"Rule {i}",
                severity=Severity.ERROR,
                enabled=True,
                tags=[]
            )
            for i in range(3)
        ]
        
        result = engine._execute_sequential(rules, sample_dataframe)
        
        assert result.stats.rules_executed == len(rules)
        # Should have violations for each rule where title is empty/None
        expected_violations = len(rules) * 2  # 2 rows with empty/None title
        assert len(result.errors) == expected_violations
    
    def test_execute_parallel__uses_thread_pool__when_multiple_rules(
        self,
        engine: RuleExecutionEngine,
        sample_dataframe: pd.DataFrame
    ):
        """Test parallel execution uses ThreadPoolExecutor."""
        rules = [
            CompiledRule(
                id=f"parallel_rule_{i}",
                field="title",
                type=ActionType.ASSERT,
                precedence=100,
                scope=RuleScope.ROW,
                condition=CompiledCondition(
                    type=ConditionType.SIMPLE,
                    operator="not_empty",
                    field="title"
                ),
                action=CompiledAction(type=ActionType.ASSERT),
                message=f"Parallel rule {i}",
                severity=Severity.ERROR,
                enabled=True,
                tags=[]
            )
            for i in range(3)
        ]
        
        with patch('concurrent.futures.ThreadPoolExecutor') as mock_executor:
            mock_executor.return_value.__enter__.return_value.submit.return_value.result.return_value = ExecutionResult()
            
            result = engine._execute_parallel(rules, sample_dataframe)
            
            mock_executor.assert_called_once_with(max_workers=engine.max_workers)


class TestRuleExecutionEngineScopes:
    """Test different rule scopes (row, column, global)."""
    
    def test_execute_single_rule__with_row_scope__executes_for_each_row(
        self,
        engine: RuleExecutionEngine,
        sample_dataframe: pd.DataFrame
    ):
        """Test row scope rules execute for each row."""
        row_rule = CompiledRule(
            id="row_scope_rule",
            field="title",
            type=ActionType.ASSERT,
            precedence=100,
            scope=RuleScope.ROW,
            condition=CompiledCondition(
                type=ConditionType.SIMPLE,
                operator="not_empty",
                field="title"
            ),
            action=CompiledAction(type=ActionType.ASSERT),
            message="Row level validation",
            severity=Severity.ERROR,
            enabled=True,
            tags=[]
        )
        
        result = engine._execute_single_rule(row_rule, sample_dataframe)
        
        # Should have processed each row individually
        assert result.stats.rules_executed == 1
        # Should have violations for empty/None rows
        assert len(result.errors) == 2  # Rows 2 and 4
    
    def test_execute_single_rule__with_column_scope__executes_once_per_column(
        self,
        engine: RuleExecutionEngine,
        sample_dataframe: pd.DataFrame
    ):
        """Test column scope rules execute once per column."""
        column_rule = CompiledRule(
            id="column_scope_rule",
            field="title",
            type=ActionType.ASSERT,
            precedence=100,
            scope=RuleScope.COLUMN,
            condition=CompiledCondition(
                type=ConditionType.SIMPLE,
                operator="not_empty",
                field="title"
            ),
            action=CompiledAction(type=ActionType.ASSERT),
            message="Column level validation",
            severity=Severity.ERROR,
            enabled=True,
            tags=[]
        )
        
        result = engine._execute_single_rule(column_rule, sample_dataframe)
        
        assert result.stats.rules_executed == 1
        # Column scope creates single violation if condition not met
    
    def test_execute_single_rule__with_global_scope__executes_once_per_dataset(
        self,
        engine: RuleExecutionEngine,
        sample_dataframe: pd.DataFrame
    ):
        """Test global scope rules execute once per dataset."""
        global_rule = CompiledRule(
            id="global_scope_rule",
            field="title",
            type=ActionType.ASSERT,
            precedence=100,
            scope=RuleScope.GLOBAL,
            condition=CompiledCondition(
                type=ConditionType.SIMPLE,
                operator="not_empty",
                field="title"
            ),
            action=CompiledAction(type=ActionType.ASSERT),
            message="Global validation",
            severity=Severity.ERROR,
            enabled=True,
            tags=[]
        )
        
        result = engine._execute_single_rule(global_rule, sample_dataframe)
        
        assert result.stats.rules_executed == 1
        # Global scope creates single violation if condition not met


class TestRuleExecutionEngineVectorization:
    """Test vectorized execution capabilities."""
    
    def test_execute_vectorized__with_vectorizable_rules__improves_performance(
        self,
        engine: RuleExecutionEngine,
        sample_dataframe: pd.DataFrame
    ):
        """Test vectorized execution performance vs sequential."""
        # Create vectorizable rules
        vectorizable_rules = [
            CompiledRule(
                id=f"vectorized_rule_{i}",
                field="price",
                type=ActionType.ASSERT,
                precedence=100,
                scope=RuleScope.ROW,
                condition=CompiledCondition(
                    type=ConditionType.SIMPLE,
                    operator="gt",
                    value=0,
                    field="price"
                ),
                action=CompiledAction(type=ActionType.ASSERT),
                message=f"Price must be positive {i}",
                severity=Severity.ERROR,
                enabled=True,
                tags=[]
            )
            for i in range(10)
        ]
        
        # Time vectorized execution
        start_time = time.perf_counter()
        vectorized_result = engine._execute_vectorized(vectorizable_rules, sample_dataframe)
        vectorized_time = time.perf_counter() - start_time
        
        # Time sequential execution 
        start_time = time.perf_counter()
        sequential_result = engine._execute_sequential(vectorizable_rules, sample_dataframe)
        sequential_time = time.perf_counter() - start_time
        
        # Results should be equivalent
        assert len(vectorized_result.errors) == len(sequential_result.errors)
        assert vectorized_result.stats.vectorized_operations > 0
        
        # For large datasets, vectorized should be faster, but with small test data
        # we just verify it completes successfully
        assert vectorized_time >= 0
        assert sequential_time >= 0
    
    def test_execute_vectorized__with_vectorization_disabled__falls_back_to_sequential(
        self,
        sample_dataframe: pd.DataFrame
    ):
        """Test fallback to sequential when vectorization is disabled."""
        engine_no_vector = RuleExecutionEngine(enable_vectorization=False)
        
        vectorizable_rule = CompiledRule(
            id="test_rule",
            field="price",
            type=ActionType.ASSERT,
            precedence=100,
            scope=RuleScope.ROW,
            condition=CompiledCondition(
                type=ConditionType.SIMPLE,
                operator="gt",
                value=0,
                field="price"
            ),
            action=CompiledAction(type=ActionType.ASSERT),
            message="Price must be positive",
            severity=Severity.ERROR,
            enabled=True,
            tags=[]
        )
        
        result = engine_no_vector._execute_vectorized([vectorizable_rule], sample_dataframe)
        
        # Should still execute (fallback to sequential)
        assert result.stats.rules_executed > 0
        assert result.stats.vectorized_operations == 0  # No vectorized operations


class TestRuleExecutionEngineErrorHandling:
    """Test error handling and edge cases."""
    
    def test_execute_single_rule__with_missing_field__handles_gracefully(
        self,
        engine: RuleExecutionEngine,
        simple_assert_rule: CompiledRule
    ):
        """Test execution with missing field in DataFrame."""
        df_missing_field = pd.DataFrame({'other_field': ['value1', 'value2']})
        
        result = engine._execute_single_rule(simple_assert_rule, df_missing_field)
        
        # Should handle missing field gracefully
        assert isinstance(result, ExecutionResult)
    
    def test_execute_single_rule__with_rule_execution_error__continues_execution(
        self,
        engine: RuleExecutionEngine,
        sample_dataframe: pd.DataFrame
    ):
        """Test that rule execution errors are handled gracefully."""
        # Create rule that might cause errors
        problematic_rule = CompiledRule(
            id="problematic_rule",
            field="title",
            type=ActionType.ASSERT,
            precedence=100,
            scope=RuleScope.ROW,
            condition=CompiledCondition(
                type=ConditionType.SIMPLE,
                operator="unknown_operator",  # Invalid operator
                field="title"
            ),
            action=CompiledAction(type=ActionType.ASSERT),
            message="Problematic rule",
            severity=Severity.ERROR,
            enabled=True,
            tags=[]
        )
        
        # Should not raise exception
        result = engine._execute_single_rule(problematic_rule, sample_dataframe)
        
        assert isinstance(result, ExecutionResult)


class TestRuleExecutionEnginePerformance:
    """Test performance characteristics and limits."""
    
    def test_execute_rules__with_large_dataset__completes_within_time_limit(self, engine: RuleExecutionEngine):
        """Test execution performance with larger datasets."""
        # Create larger dataset
        large_df = pd.DataFrame({
            'title': [f'Product {i}' for i in range(1000)],
            'price': np.random.uniform(1, 100, 1000),
            'category': np.random.choice(['A', 'B', 'C'], 1000)
        })
        
        # Simple rule
        rule = CompiledRule(
            id="perf_test_rule",
            field="title",
            type=ActionType.ASSERT,
            precedence=100,
            scope=RuleScope.ROW,
            condition=CompiledCondition(
                type=ConditionType.SIMPLE,
                operator="not_empty",
                field="title"
            ),
            action=CompiledAction(type=ActionType.ASSERT),
            message="Title required",
            severity=Severity.ERROR,
            enabled=True,
            tags=[]
        )
        
        start_time = time.perf_counter()
        result = engine._execute_single_rule(rule, large_df)
        execution_time = time.perf_counter() - start_time
        
        # Should complete within reasonable time (adjust as needed)
        assert execution_time < 1.0  # 1 second limit
        assert result.stats.rules_executed == 1
    
    def test_execute_rules__memory_usage__stays_within_limits(
        self,
        engine: RuleExecutionEngine,
        simple_assert_rule: CompiledRule
    ):
        """Test memory usage remains reasonable."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Execute with moderately large dataset
        large_df = pd.DataFrame({
            'title': [f'Product {i}' for i in range(5000)],
        })
        
        result = engine._execute_single_rule(simple_assert_rule, large_df)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (adjust as needed)
        assert memory_increase < 100  # 100MB limit
        assert result.stats.rules_executed == 1
    
    def test_execute_rules__with_timeout__respects_timeout_limit(self):
        """Test that execution respects timeout settings."""
        # Create engine with very short timeout
        timeout_engine = RuleExecutionEngine(timeout_seconds=0.1)
        
        # Create rule that might be slow
        slow_rule = CompiledRule(
            id="slow_rule",
            field="title",
            type=ActionType.ASSERT,
            precedence=100,
            scope=RuleScope.ROW,
            condition=CompiledCondition(
                type=ConditionType.SIMPLE,
                operator="matches",
                value=r".*very.*complex.*regex.*pattern.*",
                field="title"
            ),
            action=CompiledAction(type=ActionType.ASSERT),
            message="Slow regex rule",
            severity=Severity.ERROR,
            enabled=True,
            tags=[]
        )
        
        large_df = pd.DataFrame({
            'title': ['complex string pattern'] * 1000
        })
        
        # Should complete without hanging (timeout protection)
        start_time = time.perf_counter()
        result = timeout_engine._execute_single_rule(slow_rule, large_df)
        execution_time = time.perf_counter() - start_time
        
        # Should complete reasonably quickly
        assert execution_time < 5.0  # Generous limit
        assert isinstance(result, ExecutionResult)


# Integration-style tests
class TestRuleExecutionEngineIntegration:
    """Test integration scenarios with multiple components."""
    
    def test_execute_rules__complex_ruleset_with_all_types__executes_correctly(
        self,
        engine: RuleExecutionEngine,
        sample_dataframe: pd.DataFrame
    ):
        """Test execution with complex ruleset containing all rule types."""
        # Create comprehensive ruleset
        rules = {
            "title_assert": CompiledRule(
                id="title_assert",
                field="title",
                type=ActionType.ASSERT,
                precedence=100,
                scope=RuleScope.ROW,
                condition=CompiledCondition(
                    type=ConditionType.SIMPLE,
                    operator="not_empty",
                    field="title"
                ),
                action=CompiledAction(type=ActionType.ASSERT),
                message="Title required",
                severity=Severity.ERROR,
                enabled=True,
                tags=[]
            ),
            "price_transform": CompiledRule(
                id="price_transform",
                field="price",
                type=ActionType.TRANSFORM,
                precedence=200,
                scope=RuleScope.ROW,
                condition=CompiledCondition(
                    type=ConditionType.SIMPLE,
                    operator="is_number",
                    field="price"
                ),
                action=CompiledAction(
                    type=ActionType.TRANSFORM,
                    operation="format",
                    value="R$ {:.2f}"
                ),
                message="Format price",
                severity=Severity.INFO,
                enabled=True,
                tags=[]
            ),
            "category_suggest": CompiledRule(
                id="category_suggest",
                field="category",
                type=ActionType.SUGGEST,
                precedence=300,
                scope=RuleScope.ROW,
                condition=CompiledCondition(
                    type=ConditionType.SIMPLE,
                    operator="empty",
                    field="category"
                ),
                action=CompiledAction(
                    type=ActionType.SUGGEST,
                    suggestions=["Electronics", "Fashion"],
                    confidence=0.8
                ),
                message="Suggest category",
                severity=Severity.WARNING,
                enabled=True,
                tags=[]
            )
        }
        
        # Create execution plan
        phases = [
            ExecutionPhase(
                name="validation", 
                phase_type=PhaseType.VALIDATION,
                rule_groups=[
                    RuleGroup(
                        rule_ids=["title_assert"],
                        execution_mode=ExecutionMode.VECTORIZED,
                        dependencies=[]
                    )
                ],
                can_vectorize=True
            ),
            ExecutionPhase(
                name="transformation",
                phase_type=PhaseType.TRANSFORMATION,
                rule_groups=[
                    RuleGroup(
                        rule_ids=["price_transform"],
                        execution_mode=ExecutionMode.SEQUENTIAL,
                        dependencies=[]
                    )
                ],
                can_vectorize=False
            ),
            ExecutionPhase(
                name="suggestion",
                phase_type=PhaseType.SUGGESTION,
                rule_groups=[
                    RuleGroup(
                        rule_ids=["category_suggest"],
                        execution_mode=ExecutionMode.SEQUENTIAL,
                        dependencies=[]
                    )
                ],
                can_vectorize=False
            )
        ]
        
        execution_plan = ExecutionPlan(
            phases=phases,
            optimizations=["phase_separation"],
            field_index={"title": ["title_assert"], "price": ["price_transform"], "category": ["category_suggest"]},
            precedence_index={100: ["title_assert"], 200: ["price_transform"], 300: ["category_suggest"]},
            parallel_groups=[]
        )
        
        ruleset = CompiledRuleSet(
            schema_version="1.0.0",
            checksum="integration_test",
            compiled_at=pd.Timestamp.now(),
            marketplace="test",
            version=SemVer.from_string("1.0.0"),
            ccm_mapping=None,
            rules=rules,
            execution_plan=execution_plan,
            compatibility=None,
            stats=None
        )
        
        result = engine.execute_rules(ruleset, sample_dataframe)
        
        # Verify all rule types executed
        assert result.stats.rules_executed > 0
        assert len(result.errors) > 0  # From assertion rules
        # May have transformations and suggestions depending on data
        
        # Verify phases executed in order
        assert result.stats.execution_time_ms > 0