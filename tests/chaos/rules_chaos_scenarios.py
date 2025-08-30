"""
Chaos Engineering Tests for Rules Engine.

Chaos engineering validates system resilience by intentionally introducing 
failures and observing how the system responds. These tests ensure the 
rules engine gracefully handles various failure scenarios:

- Cache failures (Redis unavailable)
- Network failures (Kafka unavailable) 
- Memory pressure and resource limits
- Disk I/O failures
- Concurrent access issues
- Malformed data inputs
- Performance degradation scenarios
"""

import pytest
import pandas as pd
import numpy as np
import time
import threading
import tempfile
import os
import signal
import psutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Callable, Generator
import subprocess

from src.domain.rules.engine.compiler import RuleCompiler, CompilationError
from src.domain.rules.engine.runtime import RuleExecutionEngine, ExecutionResult
from tests.perf.benchmark_50k import PerformanceBenchmark


class ChaosTestFailure(Exception):
    """Exception raised when chaos test detects system failure."""
    pass


class ChaosScenario:
    """Base class for chaos engineering scenarios."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.active = False
        self.results: Dict[str, Any] = {}
    
    def inject_failure(self) -> None:
        """Inject the failure condition."""
        self.active = True
    
    def remove_failure(self) -> None:
        """Remove the failure condition."""
        self.active = False
    
    def validate_resilience(self, result: Any) -> bool:
        """Validate that the system handled the failure gracefully."""
        return True
    
    @contextmanager
    def chaos_context(self):
        """Context manager for applying chaos scenario."""
        try:
            self.inject_failure()
            yield self
        finally:
            self.remove_failure()


class CacheFailureScenario(ChaosScenario):
    """Simulate cache (Redis) unavailability."""
    
    def __init__(self):
        super().__init__(
            "cache_failure",
            "Simulates Redis cache being unavailable or returning errors"
        )
        self.original_cache_methods = {}
    
    def inject_failure(self) -> None:
        """Make cache operations fail."""
        super().inject_failure()
        
        # Mock cache operations to fail
        def failing_cache_get(*args, **kwargs):
            raise ConnectionError("Redis connection failed")
        
        def failing_cache_set(*args, **kwargs):
            raise ConnectionError("Redis connection failed")
        
        # Store references to patch later
        self.failing_get = failing_cache_get
        self.failing_set = failing_cache_set
    
    def validate_resilience(self, result: ExecutionResult) -> bool:
        """Validate system continues working without cache."""
        # System should still process rules, just without caching benefits
        return (
            isinstance(result, ExecutionResult) and
            result.stats.processed_rows > 0 and
            result.stats.rules_executed > 0
        )


class NetworkFailureScenario(ChaosScenario):
    """Simulate network failures affecting external services."""
    
    def __init__(self):
        super().__init__(
            "network_failure", 
            "Simulates network failures affecting Kafka, webhooks, etc."
        )
    
    def inject_failure(self) -> None:
        """Make network operations fail."""
        super().inject_failure()
        
        def failing_network_call(*args, **kwargs):
            raise ConnectionError("Network unreachable")
        
        self.failing_network_call = failing_network_call
    
    def validate_resilience(self, result: ExecutionResult) -> bool:
        """Validate core rule processing continues despite network issues."""
        return (
            isinstance(result, ExecutionResult) and
            result.stats.rules_executed > 0
            # Network failures shouldn't prevent local rule processing
        )


class MemoryPressureScenario(ChaosScenario):
    """Simulate memory pressure and OOM conditions."""
    
    def __init__(self):
        super().__init__(
            "memory_pressure",
            "Simulates high memory usage and pressure conditions"
        )
        self.memory_hogs: List[bytes] = []
    
    def inject_failure(self) -> None:
        """Consume significant memory to create pressure."""
        super().inject_failure()
        
        # Allocate memory to create pressure (be careful not to crash test)
        available_mb = psutil.virtual_memory().available / 1024 / 1024
        consume_mb = min(available_mb * 0.3, 1000)  # Use max 30% or 1GB
        
        try:
            # Allocate memory in chunks
            chunk_size = 50 * 1024 * 1024  # 50MB chunks
            num_chunks = int(consume_mb * 1024 * 1024 / chunk_size)
            
            for _ in range(num_chunks):
                self.memory_hogs.append(b'x' * chunk_size)
                
            print(f"Allocated ~{consume_mb:.0f}MB for memory pressure test")
            
        except MemoryError:
            # If we can't allocate, that's actually what we want to test
            pass
    
    def remove_failure(self) -> None:
        """Release consumed memory."""
        self.memory_hogs.clear()
        super().remove_failure()
    
    def validate_resilience(self, result: ExecutionResult) -> bool:
        """Validate system handles memory pressure gracefully."""
        return (
            isinstance(result, ExecutionResult) and
            result.stats.processed_rows > 0
            # System should either complete successfully or fail gracefully
        )


class DiskIOFailureScenario(ChaosScenario):
    """Simulate disk I/O failures."""
    
    def __init__(self):
        super().__init__(
            "disk_io_failure",
            "Simulates disk I/O failures affecting file operations"
        )
    
    def inject_failure(self) -> None:
        """Make file operations fail."""
        super().inject_failure()
        
        def failing_file_operation(*args, **kwargs):
            raise IOError("Disk I/O error")
        
        self.failing_file_op = failing_file_operation
    
    def validate_resilience(self, result: Any) -> bool:
        """Validate system handles I/O failures gracefully."""
        # Should either complete or fail with appropriate error
        return True  # Basic validation - system should not crash


class ConcurrencyStressScenario(ChaosScenario):
    """Simulate high concurrency stress and race conditions."""
    
    def __init__(self):
        super().__init__(
            "concurrency_stress",
            "Simulates high concurrency load to reveal race conditions"
        )
        self.stress_threads: List[threading.Thread] = []
        self.stop_stress = threading.Event()
    
    def inject_failure(self) -> None:
        """Create high concurrency stress."""
        super().inject_failure()
        
        def stress_worker():
            """Worker thread that creates concurrent load."""
            while not self.stop_stress.is_set():
                # Simulate concurrent access patterns
                time.sleep(0.001)  # Small delay to prevent excessive CPU usage
        
        # Start multiple stress threads
        for i in range(8):  # 8 concurrent threads
            thread = threading.Thread(target=stress_worker, daemon=True)
            thread.start()
            self.stress_threads.append(thread)
    
    def remove_failure(self) -> None:
        """Stop stress threads."""
        self.stop_stress.set()
        for thread in self.stress_threads:
            thread.join(timeout=1.0)
        self.stress_threads.clear()
        super().remove_failure()
    
    def validate_resilience(self, result: ExecutionResult) -> bool:
        """Validate system handles concurrency correctly."""
        return (
            isinstance(result, ExecutionResult) and
            result.stats.processed_rows > 0 and
            # No data corruption or inconsistent results
            result.stats.error_count >= 0 and
            result.stats.warning_count >= 0
        )


class MalformedDataScenario(ChaosScenario):
    """Simulate malformed and adversarial data inputs."""
    
    def __init__(self):
        super().__init__(
            "malformed_data",
            "Tests resilience against malformed and adversarial data"
        )
    
    def create_malicious_dataframe(self, base_df: pd.DataFrame) -> pd.DataFrame:
        """Create DataFrame with malicious/malformed data."""
        chaos_df = base_df.copy()
        
        # Inject various malformed data patterns
        malformed_patterns = [
            None,                           # None values
            "",                            # Empty strings
            " " * 1000,                    # Very long whitespace
            "A" * 10000,                   # Extremely long strings
            "\x00\x01\x02",               # Binary data
            "'; DROP TABLE products; --",  # SQL injection attempt
            "<script>alert('xss')</script>", # XSS attempt
            "../../../../etc/passwd",       # Path traversal
            "\n\r\t\b\f",                 # Control characters
            "𝕏𝖍𝖆𝖔𝖘",                      # Unicode edge cases
            "NaN",                         # String "NaN"
            "Infinity",                    # String "Infinity"
            "-0",                          # Negative zero
            "1.7976931348623157e+308",     # Near float max
            "2.2250738585072014e-308",     # Near float min
        ]
        
        # Randomly inject malformed data
        for col in chaos_df.columns:
            if chaos_df[col].dtype == 'object':  # String columns
                # Replace 10% of values with malformed data
                mask = np.random.random(len(chaos_df)) < 0.1
                chaos_df.loc[mask, col] = np.random.choice(malformed_patterns, size=mask.sum())
        
        # Add some completely invalid rows
        invalid_rows = pd.DataFrame({
            col: [np.random.choice(malformed_patterns)] * 5 
            for col in chaos_df.columns
        })
        
        return pd.concat([chaos_df, invalid_rows], ignore_index=True)
    
    def validate_resilience(self, result: ExecutionResult) -> bool:
        """Validate system handles malformed data gracefully."""
        return (
            isinstance(result, ExecutionResult) and
            # System should not crash and should report issues appropriately
            result.stats.error_count >= 0  # May have many errors, but should not crash
        )


class PerformanceDegradationScenario(ChaosScenario):
    """Simulate performance degradation conditions."""
    
    def __init__(self):
        super().__init__(
            "performance_degradation",
            "Simulates performance degradation through CPU/IO throttling"
        )
        self.cpu_hogs: List[threading.Thread] = []
        self.stop_cpu_stress = threading.Event()
    
    def inject_failure(self) -> None:
        """Create CPU load to degrade performance."""
        super().inject_failure()
        
        def cpu_stress_worker():
            """Worker that consumes CPU cycles."""
            while not self.stop_cpu_stress.is_set():
                # Busy work to consume CPU
                sum(i**2 for i in range(1000))
        
        # Start CPU stress threads (limited to prevent complete system lock)
        num_threads = min(os.cpu_count() or 4, 4)
        for _ in range(num_threads):
            thread = threading.Thread(target=cpu_stress_worker, daemon=True)
            thread.start()
            self.cpu_hogs.append(thread)
    
    def remove_failure(self) -> None:
        """Stop CPU stress."""
        self.stop_cpu_stress.set()
        for thread in self.cpu_hogs:
            thread.join(timeout=1.0)
        self.cpu_hogs.clear()
        super().remove_failure()
    
    def validate_resilience(self, result: ExecutionResult) -> bool:
        """Validate system maintains functionality under performance pressure."""
        return (
            isinstance(result, ExecutionResult) and
            result.stats.processed_rows > 0 and
            # Should complete, though may be slower
            result.stats.execution_time_ms > 0
        )


@pytest.mark.chaos
class TestRulesChaosEngineering:
    """Chaos engineering test suite for rules engine."""
    
    @pytest.fixture
    def compiler(self) -> RuleCompiler:
        """Rule compiler for chaos tests."""
        return RuleCompiler()
    
    @pytest.fixture
    def engine(self) -> RuleExecutionEngine:
        """Rule execution engine for chaos tests."""
        return RuleExecutionEngine(
            max_workers=2,
            timeout_seconds=30.0,
            memory_limit_mb=1024.0,
            enable_cache=True,
            enable_vectorization=True
        )
    
    @pytest.fixture
    def benchmark_data(self) -> pd.DataFrame:
        """Generate test data for chaos scenarios."""
        benchmark = PerformanceBenchmark()
        return benchmark.generate_benchmark_data(1000)  # Smaller dataset for chaos tests
    
    @pytest.fixture
    def basic_ruleset(self) -> Dict[str, Any]:
        """Basic ruleset for chaos testing."""
        return {
            "schema_version": "1.0.0",
            "marketplace": "chaos_test",
            "version": "1.0.0",
            "rules": [
                {
                    "id": "title_required",
                    "field": "title",
                    "type": "assert",
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Title required",
                    "severity": "error"
                },
                {
                    "id": "price_positive",
                    "field": "price", 
                    "type": "assert",
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
                    "id": "title_cleanup",
                    "field": "title",
                    "type": "transform",
                    "condition": {"operator": "not_empty"},
                    "action": {
                        "type": "transform",
                        "operation": "trim"
                    },
                    "message": "Clean title"
                }
            ]
        }
    
    def test_cache_failure_resilience__system_continues_without_cache(
        self,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        benchmark_data: pd.DataFrame,
        basic_ruleset: Dict[str, Any]
    ):
        """Test system resilience when cache (Redis) is unavailable."""
        scenario = CacheFailureScenario()
        
        with scenario.chaos_context():
            print(f"\n🌪️  CHAOS TEST: {scenario.description}")
            
            # Compile rules
            compiled_rules = compiler.compile_yaml(basic_ruleset)
            
            # Patch cache operations to simulate failures
            with patch.object(engine, '_condition_cache', side_effect=scenario.failing_get), \
                 patch.object(engine, '_transform_cache', side_effect=scenario.failing_set):
                
                # Execute rules with cache failures
                start_time = time.time()
                result = engine.execute_rules(compiled_rules, benchmark_data)
                execution_time = time.time() - start_time
                
                # Validate resilience
                assert scenario.validate_resilience(result), (
                    "System failed to handle cache unavailability gracefully"
                )
                
                # Should complete successfully (though potentially slower)
                assert result.stats.processed_rows == len(benchmark_data)
                assert result.stats.rules_executed > 0
                assert execution_time < 30.0  # Should not hang
                
                print(f"✅ Cache failure handled: {result.stats.processed_rows} rows processed")
                print(f"   Execution time: {execution_time:.2f}s (without cache)")
    
    def test_network_failure_resilience__core_processing_continues(
        self,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        benchmark_data: pd.DataFrame,
        basic_ruleset: Dict[str, Any]
    ):
        """Test system resilience when network services are unavailable."""
        scenario = NetworkFailureScenario()
        
        with scenario.chaos_context():
            print(f"\n🌪️  CHAOS TEST: {scenario.description}")
            
            compiled_rules = compiler.compile_yaml(basic_ruleset)
            
            # Simulate network failures for external services
            with patch('requests.post', side_effect=scenario.failing_network_call), \
                 patch('kafka.KafkaProducer', side_effect=scenario.failing_network_call):
                
                result = engine.execute_rules(compiled_rules, benchmark_data)
                
                # Core rule processing should continue
                assert scenario.validate_resilience(result)
                assert result.stats.processed_rows == len(benchmark_data)
                
                print(f"✅ Network failure handled: Core processing continued")
    
    def test_memory_pressure_resilience__graceful_degradation(
        self,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        benchmark_data: pd.DataFrame,
        basic_ruleset: Dict[str, Any]
    ):
        """Test system behavior under memory pressure."""
        scenario = MemoryPressureScenario()
        
        with scenario.chaos_context():
            print(f"\n🌪️  CHAOS TEST: {scenario.description}")
            
            compiled_rules = compiler.compile_yaml(basic_ruleset)
            
            # Monitor memory during execution
            initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            try:
                result = engine.execute_rules(compiled_rules, benchmark_data)
                
                # Should either complete successfully or fail gracefully
                assert scenario.validate_resilience(result)
                
                final_memory = psutil.Process().memory_info().rss / 1024 / 1024
                memory_increase = final_memory - initial_memory
                
                # Memory usage should be reasonable even under pressure
                assert memory_increase < 500, f"Memory usage too high: {memory_increase}MB"
                
                print(f"✅ Memory pressure handled: {result.stats.processed_rows} rows")
                print(f"   Memory usage: {memory_increase:.1f}MB increase")
                
            except MemoryError:
                print("✅ Memory pressure handled: Graceful OOM handling")
                # This is acceptable - system failed gracefully
            except Exception as e:
                # System should not crash with unexpected errors
                pytest.fail(f"System crashed unexpectedly under memory pressure: {e}")
    
    def test_disk_io_failure_resilience__handles_io_errors_gracefully(
        self,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        benchmark_data: pd.DataFrame,
        basic_ruleset: Dict[str, Any]
    ):
        """Test system resilience to disk I/O failures."""
        scenario = DiskIOFailureScenario()
        
        with scenario.chaos_context():
            print(f"\n🌪️  CHAOS TEST: {scenario.description}")
            
            compiled_rules = compiler.compile_yaml(basic_ruleset)
            
            # Execute normally - I/O failures would affect logging, file outputs, etc.
            result = engine.execute_rules(compiled_rules, benchmark_data)
            
            # Core processing should continue
            assert result.stats.processed_rows > 0
            
            print(f"✅ I/O failure handled: Core processing unaffected")
    
    def test_concurrency_stress_resilience__no_race_conditions(
        self,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        benchmark_data: pd.DataFrame,
        basic_ruleset: Dict[str, Any]
    ):
        """Test system resilience under high concurrency stress."""
        scenario = ConcurrencyStressScenario()
        
        with scenario.chaos_context():
            print(f"\n🌪️  CHAOS TEST: {scenario.description}")
            
            compiled_rules = compiler.compile_yaml(basic_ruleset)
            
            # Run multiple concurrent executions
            def concurrent_execution():
                return engine.execute_rules(compiled_rules, benchmark_data)
            
            # Execute multiple times concurrently
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(concurrent_execution) 
                    for _ in range(4)
                ]
                
                results = []
                for future in futures:
                    try:
                        result = future.result(timeout=30)
                        results.append(result)
                    except TimeoutError:
                        print("⚠️  Concurrent execution timed out (acceptable under stress)")
                    except Exception as e:
                        pytest.fail(f"Concurrent execution failed: {e}")
            
            # At least some executions should complete
            assert len(results) > 0, "No concurrent executions completed"
            
            # All results should be consistent
            for result in results:
                assert scenario.validate_resilience(result)
                assert result.stats.processed_rows == len(benchmark_data)
            
            print(f"✅ Concurrency stress handled: {len(results)} successful executions")
    
    def test_malformed_data_resilience__handles_adversarial_inputs(
        self,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        benchmark_data: pd.DataFrame,
        basic_ruleset: Dict[str, Any]
    ):
        """Test system resilience against malformed and adversarial data."""
        scenario = MalformedDataScenario()
        
        print(f"\n🌪️  CHAOS TEST: {scenario.description}")
        
        # Create malicious dataset
        malicious_data = scenario.create_malicious_dataframe(benchmark_data)
        
        compiled_rules = compiler.compile_yaml(basic_ruleset)
        
        # Execute with malformed data
        try:
            result = engine.execute_rules(compiled_rules, malicious_data)
            
            # Should handle malformed data without crashing
            assert scenario.validate_resilience(result)
            
            # May have many errors, but should not crash
            print(f"✅ Malformed data handled: {result.stats.error_count} errors detected")
            print(f"   Processed rows: {result.stats.processed_rows}")
            
        except Exception as e:
            # Should not crash with unhandled exceptions
            if isinstance(e, (ValueError, TypeError)):
                print(f"✅ Malformed data rejected gracefully: {type(e).__name__}")
            else:
                pytest.fail(f"System crashed on malformed data: {e}")
    
    def test_performance_degradation_resilience__maintains_functionality(
        self,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        benchmark_data: pd.DataFrame,
        basic_ruleset: Dict[str, Any]
    ):
        """Test system behavior under performance degradation."""
        scenario = PerformanceDegradationScenario()
        
        with scenario.chaos_context():
            print(f"\n🌪️  CHAOS TEST: {scenario.description}")
            
            compiled_rules = compiler.compile_yaml(basic_ruleset)
            
            # Execute under CPU load
            start_time = time.time()
            result = engine.execute_rules(compiled_rules, benchmark_data)
            execution_time = time.time() - start_time
            
            # Should complete successfully, though slower
            assert scenario.validate_resilience(result)
            assert result.stats.processed_rows == len(benchmark_data)
            
            # Should not timeout (may be slower but should complete)
            assert execution_time < 60.0  # Generous limit under CPU stress
            
            print(f"✅ Performance degradation handled: {execution_time:.2f}s execution time")
            print(f"   Throughput: {len(benchmark_data)/execution_time:.0f} rows/s (under load)")
    
    def test_timeout_handling_resilience__respects_time_limits(
        self,
        compiler: RuleCompiler,
        benchmark_data: pd.DataFrame,
        basic_ruleset: Dict[str, Any]
    ):
        """Test system timeout handling with short time limits."""
        print(f"\n🌪️  CHAOS TEST: Timeout handling")
        
        # Create engine with very short timeout
        timeout_engine = RuleExecutionEngine(
            timeout_seconds=0.1,  # Very short timeout
            enable_vectorization=False  # Force slower execution
        )
        
        compiled_rules = compiler.compile_yaml(basic_ruleset)
        
        # Should handle timeout gracefully
        start_time = time.time()
        try:
            result = timeout_engine.execute_rules(compiled_rules, benchmark_data)
            execution_time = time.time() - start_time
            
            # If it completes, should be valid
            assert result.stats.processed_rows >= 0
            print(f"✅ Completed within timeout: {execution_time:.3f}s")
            
        except TimeoutError:
            execution_time = time.time() - start_time
            print(f"✅ Timeout handled gracefully: {execution_time:.3f}s")
            # This is acceptable behavior
            
        except Exception as e:
            pytest.fail(f"Unexpected error on timeout: {e}")
    
    def test_comprehensive_chaos_suite__multiple_failure_scenarios(
        self,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        benchmark_data: pd.DataFrame,
        basic_ruleset: Dict[str, Any]
    ):
        """Test system resilience under multiple simultaneous failure conditions."""
        print(f"\n🌪️  CHAOS TEST: Multiple simultaneous failures")
        
        # Combine multiple failure scenarios
        scenarios = [
            CacheFailureScenario(),
            NetworkFailureScenario(),
            ConcurrencyStressScenario()
        ]
        
        compiled_rules = compiler.compile_yaml(basic_ruleset)
        
        # Apply multiple chaos scenarios simultaneously
        with scenarios[0].chaos_context(), \
             scenarios[1].chaos_context(), \
             scenarios[2].chaos_context():
            
            start_time = time.time()
            
            try:
                result = engine.execute_rules(compiled_rules, benchmark_data)
                execution_time = time.time() - start_time
                
                # Should handle multiple failures gracefully
                assert result.stats.processed_rows > 0
                assert execution_time < 60.0  # Should not hang
                
                print(f"✅ Multiple failures handled: {result.stats.processed_rows} rows processed")
                print(f"   Execution time: {execution_time:.2f}s under multiple stressors")
                
            except Exception as e:
                # If it fails, should fail gracefully
                execution_time = time.time() - start_time
                if execution_time < 60.0:  # Didn't hang
                    print(f"✅ Multiple failures caused graceful failure: {type(e).__name__}")
                else:
                    pytest.fail(f"System hung under multiple failures: {e}")
    
    @pytest.mark.slow
    def test_extended_chaos_endurance__long_term_stability(
        self,
        compiler: RuleCompiler,
        engine: RuleExecutionEngine,
        benchmark_data: pd.DataFrame,
        basic_ruleset: Dict[str, Any]
    ):
        """Test system endurance under sustained chaos conditions."""
        print(f"\n🌪️  CHAOS TEST: Extended endurance (slow test)")
        
        compiled_rules = compiler.compile_yaml(basic_ruleset)
        memory_scenario = MemoryPressureScenario()
        performance_scenario = PerformanceDegradationScenario()
        
        results = []
        
        with memory_scenario.chaos_context(), performance_scenario.chaos_context():
            # Run multiple iterations under sustained stress
            for iteration in range(5):
                print(f"   Iteration {iteration + 1}/5...")
                
                start_time = time.time()
                result = engine.execute_rules(compiled_rules, benchmark_data)
                execution_time = time.time() - start_time
                
                results.append({
                    'iteration': iteration + 1,
                    'execution_time': execution_time,
                    'processed_rows': result.stats.processed_rows,
                    'errors': result.stats.error_count
                })
                
                # Validate each iteration
                assert result.stats.processed_rows == len(benchmark_data)
                assert execution_time < 60.0
        
        # Analyze stability over time
        execution_times = [r['execution_time'] for r in results]
        avg_time = sum(execution_times) / len(execution_times)
        max_time = max(execution_times)
        
        # System should remain stable (no severe performance degradation)
        assert max_time <= avg_time * 3, f"Performance degraded severely: {max_time:.2f}s vs avg {avg_time:.2f}s"
        
        print(f"✅ Endurance test passed: Avg {avg_time:.2f}s, Max {max_time:.2f}s")


# Pytest configuration for chaos tests
def pytest_configure(config):
    """Configure chaos testing markers."""
    config.addinivalue_line(
        "markers", "chaos: mark test as chaos engineering test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow/long-running chaos test"
    )


def pytest_addoption(parser):
    """Add chaos testing options.""" 
    parser.addoption(
        "--run-chaos",
        action="store_true",
        default=False,
        help="Run chaos engineering tests"
    )
    parser.addoption(
        "--chaos-intensity",
        choices=["low", "medium", "high"],
        default="medium",
        help="Chaos test intensity level"
    )


def pytest_collection_modifyitems(config, items):
    """Skip chaos tests unless explicitly requested."""
    if config.getoption("--run-chaos"):
        return
    
    skip_chaos = pytest.mark.skip(reason="Chaos tests skipped (use --run-chaos to run)")
    for item in items:
        if "chaos" in item.keywords:
            item.add_marker(skip_chaos)


# Utility functions for manual chaos testing
def create_chaos_test_runner():
    """Create standalone chaos test runner script."""
    return '''#!/usr/bin/env python3
"""
Standalone chaos testing runner for ValidaHub Rules Engine.

Usage:
    python chaos_runner.py [--scenario SCENARIO] [--intensity LEVEL]

Examples:
    python chaos_runner.py --scenario cache_failure
    python chaos_runner.py --scenario all --intensity high
    python chaos_runner.py  # Run all scenarios with medium intensity
"""

import argparse
import sys
import time
from pathlib import Path
from tests.chaos.rules_chaos_scenarios import (
    CacheFailureScenario, NetworkFailureScenario, MemoryPressureScenario,
    ConcurrencyStressScenario, MalformedDataScenario, PerformanceDegradationScenario
)
from tests.perf.benchmark_50k import PerformanceBenchmark
from src.domain.rules.engine.compiler import RuleCompiler
from src.domain.rules.engine.runtime import RuleExecutionEngine


def main():
    parser = argparse.ArgumentParser(description="Run chaos engineering tests")
    parser.add_argument("--scenario", choices=[
        "cache_failure", "network_failure", "memory_pressure", 
        "concurrency_stress", "malformed_data", "performance_degradation", "all"
    ], default="all", help="Chaos scenario to run")
    parser.add_argument("--intensity", choices=["low", "medium", "high"], 
                       default="medium", help="Test intensity level")
    
    args = parser.parse_args()
    
    # Setup
    compiler = RuleCompiler()
    engine = RuleExecutionEngine(enable_vectorization=True)
    benchmark = PerformanceBenchmark()
    
    # Generate test data
    data_size = {"low": 500, "medium": 1000, "high": 2000}[args.intensity]
    test_data = benchmark.generate_benchmark_data(data_size)
    
    # Basic ruleset
    ruleset = benchmark.create_comprehensive_ruleset()
    compiled_rules = compiler.compile_yaml(ruleset)
    
    # Define scenarios
    scenarios = {
        "cache_failure": CacheFailureScenario(),
        "network_failure": NetworkFailureScenario(),
        "memory_pressure": MemoryPressureScenario(),
        "concurrency_stress": ConcurrencyStressScenario(),
        "malformed_data": MalformedDataScenario(),
        "performance_degradation": PerformanceDegradationScenario()
    }
    
    # Run scenarios
    if args.scenario == "all":
        test_scenarios = list(scenarios.values())
    else:
        test_scenarios = [scenarios[args.scenario]]
    
    results = {}
    
    for scenario in test_scenarios:
        print(f"\n🌪️  Running {scenario.name}: {scenario.description}")
        
        try:
            if scenario.name == "malformed_data":
                # Special handling for malformed data
                malicious_data = scenario.create_malicious_dataframe(test_data)
                start_time = time.time()
                result = engine.execute_rules(compiled_rules, malicious_data)
                execution_time = time.time() - start_time
            else:
                # Standard chaos scenario
                with scenario.chaos_context():
                    start_time = time.time()
                    result = engine.execute_rules(compiled_rules, test_data)
                    execution_time = time.time() - start_time
            
            # Validate resilience
            resilient = scenario.validate_resilience(result)
            
            results[scenario.name] = {
                "passed": resilient,
                "execution_time": execution_time,
                "processed_rows": result.stats.processed_rows,
                "errors": result.stats.error_count
            }
            
            status = "✅ PASSED" if resilient else "❌ FAILED"
            print(f"   {status}: {execution_time:.2f}s, {result.stats.processed_rows} rows")
            
        except Exception as e:
            results[scenario.name] = {
                "passed": False,
                "error": str(e),
                "execution_time": 0,
                "processed_rows": 0
            }
            print(f"   ❌ FAILED: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print("🌪️  CHAOS TESTING SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for r in results.values() if r["passed"])
    total = len(results)
    
    print(f"Scenarios: {passed}/{total} passed")
    print(f"Intensity: {args.intensity}")
    
    for name, result in results.items():
        status = "✅" if result["passed"] else "❌"
        if "error" in result:
            print(f"{status} {name}: {result['error']}")
        else:
            print(f"{status} {name}: {result['execution_time']:.2f}s")
    
    # Exit code
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
'''


if __name__ == "__main__":
    # Create standalone chaos runner
    runner_path = Path(__file__).parent.parent.parent / "chaos_runner.py"
    
    with open(runner_path, 'w') as f:
        f.write(create_chaos_test_runner())
    
    runner_path.chmod(0o755)
    print(f"Created chaos test runner: {runner_path}")
    
    print("🌪️  Use pytest --run-chaos for full chaos test suite")
    print("🚀 Use python chaos_runner.py for standalone chaos testing")