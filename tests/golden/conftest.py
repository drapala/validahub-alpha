"""
Golden test fixtures and utilities.

Golden tests compare actual rule engine output against expected fixtures,
ensuring consistent behavior across marketplace rule implementations.
"""

import pytest
import pandas as pd
import json
from pathlib import Path
from typing import Dict, Any, List

from src.domain.rules.engine.compiler import RuleCompiler
from src.domain.rules.engine.runtime import RuleExecutionEngine


@pytest.fixture
def golden_fixtures_path() -> Path:
    """Path to golden test fixtures."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def input_fixtures_path(golden_fixtures_path: Path) -> Path:
    """Path to input CSV fixtures."""
    return golden_fixtures_path / "input"


@pytest.fixture
def expected_fixtures_path(golden_fixtures_path: Path) -> Path:
    """Path to expected output fixtures."""
    return golden_fixtures_path / "expected"


@pytest.fixture
def rules_fixtures_path(golden_fixtures_path: Path) -> Path:
    """Path to rules YAML fixtures."""
    return golden_fixtures_path / "rules"


@pytest.fixture
def compiler() -> RuleCompiler:
    """Rule compiler for golden tests."""
    return RuleCompiler()


@pytest.fixture
def engine() -> RuleExecutionEngine:
    """Rule execution engine for golden tests."""
    return RuleExecutionEngine(
        enable_vectorization=True,
        enable_cache=False  # Disable cache for consistent golden tests
    )


@pytest.fixture
def marketplace_configs() -> Dict[str, Dict[str, Any]]:
    """Configuration for different marketplace golden tests."""
    return {
        "mercado_livre": {
            "name": "Mercado Livre",
            "version": "2.1.0",
            "required_fields": ["title", "price", "category", "brand"],
            "optional_fields": ["description", "condition", "shipping_weight"],
            "validation_rules": 15,
            "transformation_rules": 8,
            "suggestion_rules": 5
        },
        "amazon": {
            "name": "Amazon",
            "version": "3.0.0",
            "required_fields": ["title", "price", "category", "brand", "upc"],
            "optional_fields": ["description", "features", "dimensions"],
            "validation_rules": 20,
            "transformation_rules": 12,
            "suggestion_rules": 7
        },
        "magazine_luiza": {
            "name": "Magazine Luiza",
            "version": "1.5.2",
            "required_fields": ["title", "price", "category"],
            "optional_fields": ["description", "brand", "model"],
            "validation_rules": 12,
            "transformation_rules": 6,
            "suggestion_rules": 4
        },
        "shopify": {
            "name": "Shopify",
            "version": "4.1.1",
            "required_fields": ["title", "price", "inventory"],
            "optional_fields": ["description", "tags", "vendor"],
            "validation_rules": 10,
            "transformation_rules": 5,
            "suggestion_rules": 3
        }
    }


class GoldenTestHelper:
    """Helper class for golden test operations."""
    
    @staticmethod
    def load_csv_fixture(fixture_path: Path) -> pd.DataFrame:
        """Load CSV fixture with consistent formatting."""
        return pd.read_csv(fixture_path, dtype=str, keep_default_na=False)
    
    @staticmethod
    def load_rules_fixture(fixture_path: Path) -> Dict[str, Any]:
        """Load YAML rules fixture."""
        import yaml
        with open(fixture_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    @staticmethod
    def load_expected_results(fixture_path: Path) -> Dict[str, Any]:
        """Load expected results JSON fixture."""
        with open(fixture_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def save_results_as_fixture(results: Dict[str, Any], fixture_path: Path) -> None:
        """Save results as JSON fixture for updating golden files."""
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        with open(fixture_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    @staticmethod
    def normalize_execution_result(result) -> Dict[str, Any]:
        """Normalize execution result for comparison."""
        return {
            "errors": [
                {
                    "rule_id": error.rule_id,
                    "field": error.field,
                    "row_index": error.row_index,
                    "message": error.message,
                    "severity": error.severity.value,
                    "actual_value": str(error.actual_value) if error.actual_value is not None else None
                }
                for error in result.errors
            ],
            "warnings": [
                {
                    "rule_id": warning.rule_id,
                    "field": warning.field,
                    "row_index": warning.row_index,
                    "message": warning.message,
                    "severity": warning.severity.value,
                    "actual_value": str(warning.actual_value) if warning.actual_value is not None else None
                }
                for warning in result.warnings
            ],
            "suggestions": [
                {
                    "rule_id": suggestion.rule_id,
                    "field": suggestion.field,
                    "row_index": suggestion.row_index,
                    "current_value": str(suggestion.current_value) if suggestion.current_value is not None else None,
                    "suggested_values": suggestion.suggested_values,
                    "confidence": suggestion.confidence,
                    "reason": suggestion.reason
                }
                for suggestion in result.suggestions
            ],
            "transformations": [
                {
                    "rule_id": transform.rule_id,
                    "field": transform.field,
                    "row_index": transform.row_index,
                    "original_value": str(transform.original_value) if transform.original_value is not None else None,
                    "transformed_value": str(transform.transformed_value) if transform.transformed_value is not None else None,
                    "operation": transform.operation
                }
                for transform in result.transformations
            ],
            "stats": {
                "total_rows": result.stats.total_rows,
                "processed_rows": result.stats.processed_rows,
                "error_count": result.stats.error_count,
                "warning_count": result.stats.warning_count,
                "suggestion_count": result.stats.suggestion_count,
                "transformation_count": result.stats.transformation_count,
                "rules_executed": result.stats.rules_executed,
                "vectorized_operations": result.stats.vectorized_operations
            }
        }
    
    @staticmethod
    def compare_results(actual: Dict[str, Any], expected: Dict[str, Any], tolerance: float = 0.01) -> List[str]:
        """
        Compare actual vs expected results with detailed diff.
        
        Args:
            actual: Actual test results
            expected: Expected golden results
            tolerance: Tolerance for floating point comparisons
            
        Returns:
            List of difference descriptions (empty if identical)
        """
        differences = []
        
        # Compare stats
        for stat_key in ["total_rows", "processed_rows", "error_count", "warning_count", 
                        "suggestion_count", "transformation_count", "rules_executed"]:
            actual_val = actual["stats"].get(stat_key, 0)
            expected_val = expected["stats"].get(stat_key, 0)
            if actual_val != expected_val:
                differences.append(f"Stats {stat_key}: actual={actual_val}, expected={expected_val}")
        
        # Compare errors
        if len(actual["errors"]) != len(expected["errors"]):
            differences.append(f"Error count: actual={len(actual['errors'])}, expected={len(expected['errors'])}")
        else:
            for i, (actual_err, expected_err) in enumerate(zip(actual["errors"], expected["errors"])):
                if actual_err != expected_err:
                    differences.append(f"Error {i} differs: actual={actual_err}, expected={expected_err}")
        
        # Compare warnings
        if len(actual["warnings"]) != len(expected["warnings"]):
            differences.append(f"Warning count: actual={len(actual['warnings'])}, expected={len(expected['warnings'])}")
        else:
            for i, (actual_warn, expected_warn) in enumerate(zip(actual["warnings"], expected["warnings"])):
                if actual_warn != expected_warn:
                    differences.append(f"Warning {i} differs: actual={actual_warn}, expected={expected_warn}")
        
        # Compare suggestions
        if len(actual["suggestions"]) != len(expected["suggestions"]):
            differences.append(f"Suggestion count: actual={len(actual['suggestions'])}, expected={len(expected['suggestions'])}")
        else:
            for i, (actual_sugg, expected_sugg) in enumerate(zip(actual["suggestions"], expected["suggestions"])):
                # Compare with tolerance for confidence scores
                actual_conf = actual_sugg.get("confidence", 0.0)
                expected_conf = expected_sugg.get("confidence", 0.0)
                if abs(actual_conf - expected_conf) > tolerance:
                    differences.append(f"Suggestion {i} confidence differs: actual={actual_conf}, expected={expected_conf}")
                
                # Compare other fields exactly
                for key in ["rule_id", "field", "row_index", "current_value", "suggested_values", "reason"]:
                    if actual_sugg.get(key) != expected_sugg.get(key):
                        differences.append(f"Suggestion {i} {key} differs: actual={actual_sugg.get(key)}, expected={expected_sugg.get(key)}")
        
        # Compare transformations
        if len(actual["transformations"]) != len(expected["transformations"]):
            differences.append(f"Transformation count: actual={len(actual['transformations'])}, expected={len(expected['transformations'])}")
        else:
            for i, (actual_trans, expected_trans) in enumerate(zip(actual["transformations"], expected["transformations"])):
                if actual_trans != expected_trans:
                    differences.append(f"Transformation {i} differs: actual={actual_trans}, expected={expected_trans}")
        
        return differences


@pytest.fixture
def golden_helper() -> GoldenTestHelper:
    """Golden test helper instance."""
    return GoldenTestHelper()


def pytest_configure(config):
    """Configure pytest for golden tests."""
    config.addinivalue_line(
        "markers", "golden: mark test as a golden test that compares against fixtures"
    )
    config.addinivalue_line(
        "markers", "update_golden: mark test to update golden fixtures instead of comparing"
    )


def pytest_addoption(parser):
    """Add command line options for golden tests."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Update golden test fixtures instead of comparing"
    )
    parser.addoption(
        "--marketplace",
        action="store",
        default=None,
        help="Run golden tests for specific marketplace only"
    )