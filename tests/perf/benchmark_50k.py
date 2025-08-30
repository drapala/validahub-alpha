"""
Performance benchmark tests for Rules Engine.

Validates that the smart rules engine can process 50,000 CSV lines
in under 3 seconds, meeting ValidaHub's performance requirements.

This test uses realistic marketplace rules and data patterns to ensure
benchmarks represent real-world performance characteristics.
"""

import pytest
import pandas as pd
import numpy as np
import time
import psutil
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple
from concurrent.futures import ProcessPoolExecutor
import json

from src.domain.rules.engine.compiler import RuleCompiler
from src.domain.rules.engine.runtime import RuleExecutionEngine
from src.domain.rules.value_objects import SemVer


class PerformanceBenchmark:
    """Performance benchmark test suite for rules engine."""
    
    def __init__(self):
        self.results: Dict[str, Any] = {}
        self.process = psutil.Process(os.getpid())
        
    def generate_benchmark_data(self, num_rows: int = 50000) -> pd.DataFrame:
        """
        Generate realistic benchmark data with various patterns.
        
        Simulates real marketplace product data with:
        - Various title lengths and patterns
        - Price distributions (normal, edge cases)
        - Category distributions 
        - Missing/invalid data patterns
        - Special characters and edge cases
        """
        np.random.seed(42)  # Consistent data for reproducible benchmarks
        
        # Title generation with realistic patterns
        title_templates = [
            "Product {id} - {brand} {model}",
            "{brand} {category} {color} {size}",
            "Premium {adjective} {product_type}",
            "{brand} {product_type} {features} {color}",
            "Professional {category} with {features}"
        ]
        
        brands = ["Samsung", "Apple", "Nike", "Sony", "Dell", "HP", "Lenovo", "Adidas", "Canon", "LG"]
        categories = ["Electronics", "Clothing", "Sports", "Home", "Books", "Health", "Automotive", "Beauty"]
        colors = ["Black", "White", "Red", "Blue", "Green", "Silver", "Gold", "Gray"]
        sizes = ["Small", "Medium", "Large", "XL", "XXL", "32GB", "64GB", "128GB", "256GB", "512GB"]
        adjectives = ["Premium", "Professional", "Advanced", "Ultimate", "Essential", "Deluxe", "Standard"]
        features = ["Wireless", "Bluetooth", "HD", "4K", "Waterproof", "Portable", "Rechargeable"]
        
        data = {
            'id': range(1, num_rows + 1),
            'title': [],
            'price': [],
            'category': [],
            'brand': [],
            'description': [],
            'upc': [],
            'condition': [],
            'shipping_weight': [],
            'dimensions': []
        }
        
        for i in range(num_rows):
            # Generate titles with various lengths and complexity
            template = np.random.choice(title_templates)
            title = template.format(
                id=i+1,
                brand=np.random.choice(brands),
                model=f"Model {np.random.randint(100, 9999)}",
                category=np.random.choice(categories),
                color=np.random.choice(colors),
                size=np.random.choice(sizes),
                adjective=np.random.choice(adjectives),
                product_type=np.random.choice(["Phone", "Laptop", "Shirt", "Shoes", "Camera", "TV"]),
                features=" ".join(np.random.choice(features, size=np.random.randint(1, 3), replace=False))
            )
            
            # Add realistic data quality issues (5% of records)
            if np.random.random() < 0.05:
                if np.random.random() < 0.3:
                    title = ""  # Empty title
                elif np.random.random() < 0.3:
                    title = title.upper()  # All caps
                elif np.random.random() < 0.3:
                    title = "   " + title + "   "  # Extra spaces
                else:
                    title = title[:5]  # Too short
            
            data['title'].append(title)
            
            # Generate prices with realistic distribution
            base_price = np.random.lognormal(mean=4, sigma=1)  # Lognormal distribution for realistic pricing
            if np.random.random() < 0.02:  # 2% edge cases
                if np.random.random() < 0.5:
                    base_price = 0  # Zero price (error)
                else:
                    base_price = -np.random.uniform(1, 100)  # Negative price (error)
            elif np.random.random() < 0.03:  # 3% very high prices
                base_price = np.random.uniform(10000, 50000)
            
            data['price'].append(round(base_price, 2))
            
            # Categories with some missing data
            if np.random.random() < 0.08:  # 8% missing categories
                data['category'].append("")
            else:
                data['category'].append(np.random.choice(categories))
            
            # Brands with some missing data  
            if np.random.random() < 0.03:  # 3% missing brands
                data['brand'].append("")
            else:
                data['brand'].append(np.random.choice(brands))
            
            # Generate descriptions
            desc_length = np.random.choice([0, 50, 100, 200, 500], p=[0.1, 0.2, 0.3, 0.3, 0.1])
            if desc_length == 0:
                data['description'].append("")
            else:
                words = ["quality", "premium", "professional", "durable", "reliable", "innovative", 
                        "modern", "stylish", "comfortable", "efficient", "powerful", "lightweight"]
                description = " ".join(np.random.choice(words, size=desc_length//8, replace=True))
                data['description'].append(description.capitalize() + ".")
            
            # UPC codes with realistic patterns
            if np.random.random() < 0.05:  # 5% missing/invalid UPC
                if np.random.random() < 0.5:
                    data['upc'].append("")
                else:
                    data['upc'].append("INVALID")
            else:
                upc = ''.join([str(np.random.randint(0, 10)) for _ in range(12)])
                data['upc'].append(upc)
            
            # Condition
            data['condition'].append(np.random.choice(["New", "Used", "Refurbished"], p=[0.8, 0.15, 0.05]))
            
            # Shipping weight (in kg)
            weight = np.random.lognormal(mean=0, sigma=1)  # Most products are light, some heavy
            data['shipping_weight'].append(round(weight, 2))
            
            # Dimensions (LxWxH in cm)
            dims = [round(np.random.uniform(1, 50), 1) for _ in range(3)]
            data['dimensions'].append(f"{dims[0]}x{dims[1]}x{dims[2]}")
        
        return pd.DataFrame(data)
    
    def create_comprehensive_ruleset(self) -> Dict[str, Any]:
        """
        Create comprehensive ruleset covering all major validation scenarios.
        
        Includes:
        - Field presence validation
        - Format validation (email, URL, numeric)
        - Business logic validation
        - Data transformation rules
        - Suggestion rules
        - Cross-field validation
        """
        return {
            "schema_version": "1.0.0",
            "marketplace": "performance_test",
            "version": "1.0.0",
            "ccm_mapping": {
                "title": {
                    "source": "title",
                    "transform": {"type": "trim"},
                    "required": True
                },
                "price": {
                    "source": "price",
                    "transform": {"type": "clean_price"},
                    "required": True
                }
            },
            "rules": [
                # Field presence validations (fast operations)
                {
                    "id": "title_required",
                    "field": "title",
                    "type": "assert",
                    "precedence": 100,
                    "scope": "row",
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Title is required",
                    "severity": "error"
                },
                {
                    "id": "price_required",
                    "field": "price",
                    "type": "assert",
                    "precedence": 100,
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Price is required",
                    "severity": "error"
                },
                {
                    "id": "category_required",
                    "field": "category",
                    "type": "assert",
                    "precedence": 100,
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Category is required",
                    "severity": "error"
                },
                
                # Length validations (vectorizable)
                {
                    "id": "title_min_length",
                    "field": "title",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {"operator": "length_gt", "value": 5},
                    "action": {"type": "assert"},
                    "message": "Title must be longer than 5 characters",
                    "severity": "error"
                },
                {
                    "id": "title_max_length",
                    "field": "title",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {"operator": "length_lt", "value": 200},
                    "action": {"type": "assert"},
                    "message": "Title must be shorter than 200 characters",
                    "severity": "error"
                },
                
                # Numeric validations (vectorizable)
                {
                    "id": "price_is_number",
                    "field": "price",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {"operator": "is_number"},
                    "action": {"type": "assert"},
                    "message": "Price must be a valid number",
                    "severity": "error"
                },
                {
                    "id": "price_positive",
                    "field": "price",
                    "type": "assert",
                    "precedence": 300,
                    "condition": {
                        "and": [
                            {"operator": "is_number"},
                            {"operator": "gt", "value": 0}
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "Price must be positive",
                    "severity": "error"
                },
                {
                    "id": "price_reasonable",
                    "field": "price",
                    "type": "assert",
                    "precedence": 400,
                    "condition": {
                        "and": [
                            {"operator": "is_number"},
                            {"operator": "lte", "value": 100000}
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "Price seems unusually high - please verify",
                    "severity": "warning"
                },
                
                # Text pattern validations (regex operations)
                {
                    "id": "upc_format",
                    "field": "upc",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {
                        "or": [
                            {"operator": "empty"},
                            {"operator": "eq", "value": "EXEMPT"},
                            {"operator": "matches", "value": r"^\d{12}$"}
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "UPC must be 12 digits, EXEMPT, or empty",
                    "severity": "error"
                },
                {
                    "id": "no_promotional_language",
                    "field": "title",
                    "type": "assert",
                    "precedence": 300,
                    "condition": {
                        "not": {
                            "operator": "matches",
                            "value": r"(?i)(best|amazing|deal|sale|cheap|discount|free shipping|limited time)"
                        }
                    },
                    "action": {"type": "assert"},
                    "message": "Promotional language not allowed in title",
                    "severity": "error"
                },
                
                # List/choice validations
                {
                    "id": "valid_condition",
                    "field": "condition",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {
                        "operator": "in",
                        "value": ["New", "Used", "Refurbished"]
                    },
                    "action": {"type": "assert"},
                    "message": "Condition must be New, Used, or Refurbished",
                    "severity": "error"
                },
                {
                    "id": "valid_category",
                    "field": "category",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {
                        "operator": "in",
                        "value": ["Electronics", "Clothing", "Sports", "Home", "Books", "Health", "Automotive", "Beauty"]
                    },
                    "action": {"type": "assert"},
                    "message": "Invalid category",
                    "severity": "error"
                },
                
                # Transformation rules
                {
                    "id": "title_trim",
                    "field": "title",
                    "type": "transform",
                    "precedence": 150,
                    "condition": {"operator": "not_empty"},
                    "action": {
                        "type": "transform",
                        "operation": "trim"
                    },
                    "message": "Remove leading/trailing spaces from title"
                },
                {
                    "id": "title_case_fix",
                    "field": "title", 
                    "type": "transform",
                    "precedence": 350,
                    "condition": {
                        "and": [
                            {"operator": "not_empty"},
                            {"operator": "matches", "value": r"^[A-Z\s\d\-,]+$"}  # All caps
                        ]
                    },
                    "action": {
                        "type": "transform",
                        "operation": "title_case",
                        "params": {"preserve_acronyms": True}
                    },
                    "message": "Convert all caps title to proper case"
                },
                {
                    "id": "price_format",
                    "field": "price",
                    "type": "transform",
                    "precedence": 450,
                    "condition": {"operator": "is_number"},
                    "action": {
                        "type": "transform",
                        "operation": "format",
                        "value": "{:.2f}",
                        "params": {"decimal_places": 2}
                    },
                    "message": "Format price with 2 decimal places"
                },
                
                # Suggestion rules (more complex logic)
                {
                    "id": "brand_suggestion",
                    "field": "brand",
                    "type": "suggest",
                    "precedence": 500,
                    "condition": {
                        "and": [
                            {"operator": "empty"},
                            {
                                "field": "title",
                                "operator": "matches",
                                "value": r"(?i)(samsung|apple|nike|sony|dell)"
                            }
                        ]
                    },
                    "action": {
                        "type": "suggest",
                        "suggestions": ["Samsung", "Apple", "Nike", "Sony", "Dell"],
                        "confidence": 0.8
                    },
                    "message": "Brand detected in title - consider adding to brand field"
                },
                {
                    "id": "category_electronics_suggestion",
                    "field": "category",
                    "type": "suggest",
                    "precedence": 500,
                    "condition": {
                        "and": [
                            {"operator": "empty"},
                            {
                                "field": "title",
                                "operator": "matches",
                                "value": r"(?i)(phone|laptop|tv|camera|headphones|tablet)"
                            }
                        ]
                    },
                    "action": {
                        "type": "suggest",
                        "suggestions": ["Electronics"],
                        "confidence": 0.9
                    },
                    "message": "Electronics category suggested based on title"
                },
                
                # Cross-field validations (more complex)
                {
                    "id": "electronics_brand_consistency",
                    "field": "brand",
                    "type": "assert",
                    "precedence": 600,
                    "condition": {
                        "or": [
                            {"field": "category", "operator": "ne", "value": "Electronics"},
                            {"operator": "not_empty"}
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "Electronics products should specify a brand",
                    "severity": "warning"
                },
                {
                    "id": "high_price_description",
                    "field": "description",
                    "type": "assert",
                    "precedence": 600,
                    "condition": {
                        "or": [
                            {
                                "field": "price",
                                "operator": "lte",
                                "value": 1000
                            },
                            {"operator": "length_gt", "value": 50}
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "High-priced items should have detailed descriptions",
                    "severity": "warning"
                }
            ],
            "compatibility": {
                "auto_apply_patch": True,
                "shadow_period_days": 7
            }
        }
    
    def measure_performance_metrics(self, func, *args, **kwargs) -> Tuple[Any, Dict[str, float]]:
        """Measure detailed performance metrics for a function call."""
        # Initial memory measurement
        initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        # CPU measurement
        cpu_percent_start = self.process.cpu_percent()
        
        # Time measurement
        start_time = time.perf_counter()
        wall_start = time.time()
        
        try:
            result = func(*args, **kwargs)
        finally:
            # Final measurements
            end_time = time.perf_counter()
            wall_end = time.time()
            final_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            cpu_percent_end = self.process.cpu_percent()
        
        metrics = {
            "execution_time_seconds": end_time - start_time,
            "wall_time_seconds": wall_end - wall_start,
            "memory_used_mb": final_memory - initial_memory,
            "peak_memory_mb": final_memory,
            "cpu_percent": cpu_percent_end - cpu_percent_start
        }
        
        return result, metrics


@pytest.mark.performance
class TestRulesEnginePerformance:
    """Performance benchmark tests for rules engine."""
    
    @pytest.fixture
    def benchmark(self) -> PerformanceBenchmark:
        """Create performance benchmark instance."""
        return PerformanceBenchmark()
    
    @pytest.fixture
    def compiler(self) -> RuleCompiler:
        """Rule compiler optimized for performance."""
        return RuleCompiler()
    
    @pytest.fixture
    def engine(self) -> RuleExecutionEngine:
        """Rule execution engine optimized for performance."""
        return RuleExecutionEngine(
            max_workers=4,
            timeout_seconds=10.0,
            memory_limit_mb=2048.0,
            enable_cache=True,
            enable_vectorization=True
        )
    
    @pytest.fixture
    def benchmark_data_50k(self, benchmark: PerformanceBenchmark) -> pd.DataFrame:
        """Generate 50k rows of benchmark data."""
        return benchmark.generate_benchmark_data(50000)
    
    @pytest.fixture
    def comprehensive_rules(self, benchmark: PerformanceBenchmark) -> Dict[str, Any]:
        """Comprehensive ruleset for benchmarking."""
        return benchmark.create_comprehensive_ruleset()
    
    def test_benchmark_50k_rows_under_3_seconds__primary_performance_requirement(
        self,
        benchmark: PerformanceBenchmark,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        benchmark_data_50k: pd.DataFrame,
        comprehensive_rules: Dict[str, Any]
    ):
        """
        PRIMARY BENCHMARK: 50k rows processed in under 3 seconds.
        
        This is the core ValidaHub performance requirement that must pass
        for the rules engine to be considered production-ready.
        """
        print(f"\n🚀 PERFORMANCE BENCHMARK: Processing {len(benchmark_data_50k)} rows")
        
        # Compile rules (this time doesn't count toward the 3-second limit)
        print("Compiling rules...")
        compiled_rules, compile_metrics = benchmark.measure_performance_metrics(
            compiler.compile_yaml, comprehensive_rules
        )
        
        print(f"Rules compiled in {compile_metrics['execution_time_seconds']:.3f}s")
        print(f"Total rules: {len(compiled_rules.rules)}")
        print(f"Execution plan phases: {len(compiled_rules.execution_plan.phases)}")
        
        # Execute rules (this is the critical 3-second measurement)
        print("\n⏱️  Starting 50k row execution benchmark...")
        execution_result, exec_metrics = benchmark.measure_performance_metrics(
            engine.execute_rules, compiled_rules, benchmark_data_50k
        )
        
        # Performance requirements
        execution_time = exec_metrics['execution_time_seconds']
        memory_used = exec_metrics['memory_used_mb']
        
        print(f"\n📊 BENCHMARK RESULTS:")
        print(f"Execution time: {execution_time:.3f}s")
        print(f"Memory used: {memory_used:.1f}MB")
        print(f"Rows processed: {execution_result.stats.processed_rows:,}")
        print(f"Rules executed: {execution_result.stats.rules_executed:,}")
        print(f"Errors found: {execution_result.stats.error_count:,}")
        print(f"Warnings: {execution_result.stats.warning_count:,}")
        print(f"Suggestions: {execution_result.stats.suggestion_count:,}")
        print(f"Transformations: {execution_result.stats.transformation_count:,}")
        print(f"Vectorized operations: {execution_result.stats.vectorized_operations:,}")
        
        # Performance metrics
        rows_per_second = len(benchmark_data_50k) / execution_time
        rules_per_second = execution_result.stats.rules_executed / execution_time
        
        print(f"\n📈 PERFORMANCE METRICS:")
        print(f"Throughput: {rows_per_second:,.0f} rows/second")
        print(f"Rule execution rate: {rules_per_second:,.0f} rules/second")
        print(f"Memory efficiency: {memory_used/len(benchmark_data_50k)*1000:.2f} MB/1k rows")
        
        # Store results for CI reporting
        benchmark.results['primary_benchmark'] = {
            'execution_time_seconds': execution_time,
            'memory_used_mb': memory_used,
            'rows_processed': execution_result.stats.processed_rows,
            'rules_executed': execution_result.stats.rules_executed,
            'throughput_rows_per_second': rows_per_second,
            'rule_execution_rate': rules_per_second,
            'vectorized_operations': execution_result.stats.vectorized_operations,
            'errors_found': execution_result.stats.error_count,
            'warnings_found': execution_result.stats.warning_count,
            'pass_criteria': execution_time < 3.0
        }
        
        # CRITICAL ASSERTION: Must complete in under 3 seconds
        assert execution_time < 3.0, (
            f"Performance requirement FAILED: 50k rows processed in {execution_time:.3f}s "
            f"(requirement: <3.0s). Throughput: {rows_per_second:,.0f} rows/s"
        )
        
        # Additional performance checks
        assert memory_used < 1000, f"Memory usage too high: {memory_used:.1f}MB (limit: 1000MB)"
        assert execution_result.stats.processed_rows == len(benchmark_data_50k), "Not all rows processed"
        assert execution_result.stats.vectorized_operations > 0, "Vectorization not working"
        
        print("✅ PRIMARY BENCHMARK PASSED: 50k rows in <3 seconds")
    
    def test_benchmark_scalability__with_various_dataset_sizes__scales_linearly(
        self,
        benchmark: PerformanceBenchmark,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        comprehensive_rules: Dict[str, Any]
    ):
        """Test scalability across different dataset sizes."""
        test_sizes = [1000, 5000, 10000, 25000, 50000]
        scalability_results = []
        
        # Compile rules once
        compiled_rules = compiler.compile_yaml(comprehensive_rules)
        
        print(f"\n📈 SCALABILITY BENCHMARK:")
        
        for size in test_sizes:
            print(f"\nTesting {size:,} rows...")
            
            # Generate data
            test_data = benchmark.generate_benchmark_data(size)
            
            # Execute and measure
            result, metrics = benchmark.measure_performance_metrics(
                engine.execute_rules, compiled_rules, test_data
            )
            
            # Calculate performance metrics
            throughput = size / metrics['execution_time_seconds']
            memory_per_row = metrics['memory_used_mb'] / size * 1000  # MB per 1k rows
            
            scalability_results.append({
                'rows': size,
                'execution_time': metrics['execution_time_seconds'],
                'memory_used': metrics['memory_used_mb'],
                'throughput': throughput,
                'memory_per_1k_rows': memory_per_row
            })
            
            print(f"  Time: {metrics['execution_time_seconds']:.3f}s")
            print(f"  Throughput: {throughput:,.0f} rows/s")
            print(f"  Memory: {memory_per_row:.2f} MB/1k rows")
        
        # Analyze scalability
        baseline_throughput = scalability_results[0]['throughput']
        for result in scalability_results[1:]:
            throughput_ratio = result['throughput'] / baseline_throughput
            # Throughput should remain relatively consistent (within 50% of baseline)
            assert throughput_ratio > 0.5, (
                f"Performance degradation detected at {result['rows']:,} rows: "
                f"throughput dropped to {throughput_ratio:.1%} of baseline"
            )
        
        # Store scalability results
        benchmark.results['scalability'] = scalability_results
        
        print("✅ SCALABILITY TEST PASSED: Linear scaling maintained")
    
    def test_benchmark_rule_complexity__with_various_rule_patterns__maintains_performance(
        self,
        benchmark: PerformanceBenchmark,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine
    ):
        """Test performance impact of different rule complexity patterns."""
        test_data = benchmark.generate_benchmark_data(10000)  # Fixed dataset size
        
        rule_patterns = {
            "simple_validations": {
                "description": "Simple field presence and type checks",
                "rules": [
                    {
                        "id": f"simple_rule_{i}",
                        "field": "title",
                        "type": "assert",
                        "condition": {"operator": "not_empty"},
                        "action": {"type": "assert"},
                        "message": f"Simple validation {i}",
                        "severity": "error"
                    }
                    for i in range(20)  # 20 simple rules
                ]
            },
            "regex_heavy": {
                "description": "Complex regex pattern matching",
                "rules": [
                    {
                        "id": f"regex_rule_{i}",
                        "field": "title",
                        "type": "assert", 
                        "condition": {
                            "operator": "matches",
                            "value": rf"^(?=.*\b{word}\b).*$"
                        },
                        "action": {"type": "assert"},
                        "message": f"Regex validation {i}",
                        "severity": "error"
                    }
                    for i, word in enumerate(["product", "premium", "professional", "quality", "durable"])
                ]
            },
            "cross_field_complex": {
                "description": "Complex cross-field validations",
                "rules": [
                    {
                        "id": "cross_field_price_category",
                        "field": "price",
                        "type": "assert",
                        "condition": {
                            "or": [
                                {
                                    "and": [
                                        {"field": "category", "operator": "eq", "value": "Electronics"},
                                        {"operator": "gte", "value": 10}
                                    ]
                                },
                                {
                                    "and": [
                                        {"field": "category", "operator": "eq", "value": "Books"},
                                        {"operator": "gte", "value": 5}
                                    ]
                                },
                                {"field": "category", "operator": "not_in", "value": ["Electronics", "Books"]}
                            ]
                        },
                        "action": {"type": "assert"},
                        "message": "Price too low for category",
                        "severity": "warning"
                    }
                ]
            },
            "transformation_heavy": {
                "description": "Multiple transformation rules",
                "rules": [
                    {
                        "id": f"transform_rule_{i}",
                        "field": "title",
                        "type": "transform",
                        "condition": {"operator": "not_empty"},
                        "action": {
                            "type": "transform",
                            "operation": "title_case" if i % 2 == 0 else "trim",
                            "params": {"preserve_acronyms": True} if i % 2 == 0 else {}
                        },
                        "message": f"Transform {i}",
                    }
                    for i in range(10)  # 10 transform rules
                ]
            }
        }
        
        complexity_results = {}
        
        print(f"\n🔬 RULE COMPLEXITY BENCHMARK:")
        
        for pattern_name, pattern_config in rule_patterns.items():
            print(f"\nTesting {pattern_name}: {pattern_config['description']}")
            
            # Create ruleset with this pattern
            rules_yaml = {
                "schema_version": "1.0.0",
                "marketplace": "complexity_test",
                "version": "1.0.0",
                "rules": pattern_config['rules']
            }
            
            # Compile and execute
            compiled_rules, compile_metrics = benchmark.measure_performance_metrics(
                compiler.compile_yaml, rules_yaml
            )
            
            result, exec_metrics = benchmark.measure_performance_metrics(
                engine.execute_rules, compiled_rules, test_data
            )
            
            # Calculate metrics
            throughput = len(test_data) / exec_metrics['execution_time_seconds']
            
            complexity_results[pattern_name] = {
                'description': pattern_config['description'],
                'rule_count': len(pattern_config['rules']),
                'compile_time': compile_metrics['execution_time_seconds'],
                'execution_time': exec_metrics['execution_time_seconds'],
                'memory_used': exec_metrics['memory_used_mb'],
                'throughput': throughput,
                'vectorized_operations': result.stats.vectorized_operations
            }
            
            print(f"  Rules: {len(pattern_config['rules'])}")
            print(f"  Compile time: {compile_metrics['execution_time_seconds']:.3f}s")
            print(f"  Execution time: {exec_metrics['execution_time_seconds']:.3f}s")
            print(f"  Throughput: {throughput:,.0f} rows/s")
            print(f"  Vectorized ops: {result.stats.vectorized_operations}")
        
        # Store complexity results
        benchmark.results['complexity'] = complexity_results
        
        # Performance requirements for each pattern
        for pattern_name, result in complexity_results.items():
            # All patterns should maintain reasonable throughput (>1000 rows/s)
            assert result['throughput'] > 1000, (
                f"Performance too slow for {pattern_name}: {result['throughput']:.0f} rows/s"
            )
            
            # Complex patterns should still compile quickly (<2s)
            assert result['compile_time'] < 2.0, (
                f"Compilation too slow for {pattern_name}: {result['compile_time']:.3f}s"
            )
        
        print("✅ COMPLEXITY TEST PASSED: All rule patterns maintain performance")
    
    def test_benchmark_concurrent_execution__with_multiple_processors__scales_with_cores(
        self,
        benchmark: PerformanceBenchmark,
        compiler: RuleCompiler,
        comprehensive_rules: Dict[str, Any]
    ):
        """Test concurrent execution performance scaling."""
        test_data = benchmark.generate_benchmark_data(20000)  # Medium dataset
        compiled_rules = compiler.compile_yaml(comprehensive_rules)
        
        # Test with different worker counts
        worker_counts = [1, 2, 4, 8]
        concurrency_results = []
        
        print(f"\n⚡ CONCURRENCY BENCHMARK:")
        
        for workers in worker_counts:
            print(f"\nTesting with {workers} workers...")
            
            # Create engine with specific worker count
            concurrent_engine = RuleExecutionEngine(
                max_workers=workers,
                enable_vectorization=True,
                enable_cache=True
            )
            
            # Execute and measure
            result, metrics = benchmark.measure_performance_metrics(
                concurrent_engine.execute_rules, compiled_rules, test_data
            )
            
            throughput = len(test_data) / metrics['execution_time_seconds']
            
            concurrency_results.append({
                'workers': workers,
                'execution_time': metrics['execution_time_seconds'],
                'throughput': throughput,
                'memory_used': metrics['memory_used_mb'],
                'cpu_usage': metrics['cpu_percent']
            })
            
            print(f"  Time: {metrics['execution_time_seconds']:.3f}s")
            print(f"  Throughput: {throughput:,.0f} rows/s")
            print(f"  Memory: {metrics['memory_used_mb']:.1f}MB")
        
        # Analyze scaling efficiency
        baseline = concurrency_results[0]['throughput']  # 1 worker baseline
        
        for result in concurrency_results[1:]:
            scaling_factor = result['throughput'] / baseline
            theoretical_max = result['workers']  # Perfect scaling would be linear
            efficiency = scaling_factor / theoretical_max
            
            print(f"\n{result['workers']} workers: {scaling_factor:.1f}x speedup ({efficiency:.1%} efficiency)")
            
            # Expect at least 50% scaling efficiency for 2-4 workers
            if result['workers'] <= 4:
                assert efficiency > 0.5, (
                    f"Poor scaling efficiency with {result['workers']} workers: {efficiency:.1%}"
                )
        
        benchmark.results['concurrency'] = concurrency_results
        print("✅ CONCURRENCY TEST PASSED: Reasonable scaling achieved")
    
    def test_benchmark_memory_efficiency__with_large_datasets__stays_within_limits(
        self,
        benchmark: PerformanceBenchmark,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        comprehensive_rules: Dict[str, Any]
    ):
        """Test memory efficiency with progressively larger datasets."""
        compiled_rules = compiler.compile_yaml(comprehensive_rules)
        
        # Test different dataset sizes for memory usage
        memory_test_sizes = [10000, 25000, 50000, 75000, 100000]
        memory_results = []
        
        print(f"\n💾 MEMORY EFFICIENCY BENCHMARK:")
        
        for size in memory_test_sizes:
            if size > 50000:
                print(f"\nOptional memory test with {size:,} rows (may skip on constrained systems)...")
            else:
                print(f"\nTesting memory usage with {size:,} rows...")
            
            try:
                # Generate data
                test_data = benchmark.generate_benchmark_data(size)
                
                # Measure peak memory usage
                initial_memory = benchmark.process.memory_info().rss / 1024 / 1024
                
                result, metrics = benchmark.measure_performance_metrics(
                    engine.execute_rules, compiled_rules, test_data
                )
                
                memory_per_row = metrics['memory_used_mb'] / size * 1000  # MB per 1k rows
                
                memory_results.append({
                    'rows': size,
                    'memory_used_mb': metrics['memory_used_mb'],
                    'peak_memory_mb': metrics['peak_memory_mb'],
                    'memory_per_1k_rows': memory_per_row,
                    'execution_time': metrics['execution_time_seconds']
                })
                
                print(f"  Memory used: {metrics['memory_used_mb']:.1f}MB")
                print(f"  Memory per 1k rows: {memory_per_row:.2f}MB")
                print(f"  Peak memory: {metrics['peak_memory_mb']:.1f}MB")
                
                # Memory efficiency requirements
                if size <= 50000:  # Critical requirement
                    assert metrics['memory_used_mb'] < 2000, (
                        f"Memory usage too high for {size:,} rows: {metrics['memory_used_mb']:.1f}MB"
                    )
                    assert memory_per_row < 20, (
                        f"Memory per row too high: {memory_per_row:.2f}MB/1k rows"
                    )
                
            except MemoryError:
                print(f"  Memory limit reached at {size:,} rows - this is acceptable for optional tests")
                break
            except Exception as e:
                if size > 50000:
                    print(f"  Optional test failed at {size:,} rows: {e}")
                    break
                else:
                    raise  # Critical sizes must pass
        
        benchmark.results['memory_efficiency'] = memory_results
        print("✅ MEMORY EFFICIENCY TEST PASSED: Within acceptable limits")
    
    def save_benchmark_results(self, benchmark: PerformanceBenchmark, output_path: Path):
        """Save benchmark results for CI reporting and analysis."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add system information
        benchmark.results['system_info'] = {
            'cpu_count': os.cpu_count(),
            'memory_total_gb': psutil.virtual_memory().total / 1024**3,
            'python_version': psutil.__version__,
            'timestamp': time.time()
        }
        
        # Add summary
        benchmark.results['summary'] = {
            'primary_benchmark_passed': benchmark.results.get('primary_benchmark', {}).get('pass_criteria', False),
            'max_throughput_rows_per_second': max(
                [r.get('throughput', 0) for r in benchmark.results.get('scalability', [])] + 
                [benchmark.results.get('primary_benchmark', {}).get('throughput_rows_per_second', 0)]
            ),
            'total_rules_tested': len(benchmark.create_comprehensive_ruleset().get('rules', [])),
            'peak_memory_usage_mb': max([
                result.get('peak_memory_mb', 0) 
                for results in benchmark.results.values() 
                if isinstance(results, list)
                for result in results
                if isinstance(result, dict)
            ] + [benchmark.results.get('primary_benchmark', {}).get('memory_used_mb', 0)])
        }
        
        with open(output_path, 'w') as f:
            json.dump(benchmark.results, f, indent=2, default=str)
        
        print(f"\n📁 Benchmark results saved to: {output_path}")
    
    def test_full_benchmark_suite__comprehensive_performance_validation(
        self,
        benchmark: PerformanceBenchmark,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        benchmark_data_50k: pd.DataFrame,
        comprehensive_rules: Dict[str, Any],
        tmp_path: Path
    ):
        """
        Comprehensive benchmark suite that runs all performance tests.
        
        This test aggregates results from all individual benchmarks and
        provides a comprehensive performance report.
        """
        print("\n🎯 COMPREHENSIVE BENCHMARK SUITE")
        print("=" * 60)
        
        # Run primary benchmark (this will be called by other tests too)
        compiled_rules = compiler.compile_yaml(comprehensive_rules)
        result, metrics = benchmark.measure_performance_metrics(
            engine.execute_rules, compiled_rules, benchmark_data_50k
        )
        
        # Store primary results
        execution_time = metrics['execution_time_seconds']
        benchmark.results['comprehensive_summary'] = {
            'primary_execution_time': execution_time,
            'primary_throughput': len(benchmark_data_50k) / execution_time,
            'primary_memory_used': metrics['memory_used_mb'],
            'rules_in_test_set': len(compiled_rules.rules),
            'total_validations': result.stats.rules_executed,
            'performance_requirement_met': execution_time < 3.0,
            'vectorization_utilized': result.stats.vectorized_operations > 0
        }
        
        # Save comprehensive results
        output_file = tmp_path / "benchmark_results.json"
        self.save_benchmark_results(benchmark, output_file)
        
        # Final validation
        assert execution_time < 3.0, f"Primary performance requirement failed: {execution_time:.3f}s"
        
        print(f"\n✅ COMPREHENSIVE BENCHMARK COMPLETED")
        print(f"⚡ 50k rows processed in {execution_time:.3f}s")
        print(f"📊 Throughput: {len(benchmark_data_50k) / execution_time:,.0f} rows/second")
        print(f"🎯 Performance requirement: {'PASSED' if execution_time < 3.0 else 'FAILED'}")


# Pytest configuration for performance tests
def pytest_addoption(parser):
    """Add performance test options."""
    parser.addoption(
        "--run-perf",
        action="store_true", 
        default=False,
        help="Run performance benchmark tests"
    )
    parser.addoption(
        "--perf-size",
        type=int,
        default=50000,
        help="Dataset size for performance tests (default: 50000)"
    )


def pytest_configure(config):
    """Configure performance test markers."""
    config.addinivalue_line(
        "markers", "performance: mark test as a performance benchmark"
    )


def pytest_collection_modifyitems(config, items):
    """Skip performance tests unless explicitly requested."""
    if config.getoption("--run-perf"):
        return
    
    skip_perf = pytest.mark.skip(reason="Performance tests skipped (use --run-perf to run)")
    for item in items:
        if "performance" in item.keywords:
            item.add_marker(skip_perf)


if __name__ == "__main__":
    # Allow running benchmark directly for development
    benchmark = PerformanceBenchmark()
    compiler = RuleCompiler()
    engine = RuleExecutionEngine(enable_vectorization=True)
    
    print("🚀 Running standalone performance benchmark...")
    
    # Generate test data
    data = benchmark.generate_benchmark_data(50000)
    rules = benchmark.create_comprehensive_ruleset()
    
    # Compile and execute
    compiled = compiler.compile_yaml(rules)
    result, metrics = benchmark.measure_performance_metrics(
        engine.execute_rules, compiled, data
    )
    
    print(f"✅ Completed: {metrics['execution_time_seconds']:.3f}s")
    print(f"🎯 Requirement: {'PASSED' if metrics['execution_time_seconds'] < 3.0 else 'FAILED'}")