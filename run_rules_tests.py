#!/usr/bin/env python3
"""
Comprehensive test runner for ValidaHub Smart Rules Engine.

This script orchestrates all test types and provides a unified interface
for running the complete test strategy with proper quality gates.

Usage:
    python run_rules_tests.py [--suite SUITE] [--coverage] [--report]

Test Suites:
    unit        - Unit tests only
    golden      - Golden tests only  
    performance - Performance benchmarks
    mutation    - Mutation testing
    chaos       - Chaos engineering
    all         - Complete test suite (default)
    ci          - CI-optimized subset

Examples:
    python run_rules_tests.py --suite unit --coverage
    python run_rules_tests.py --suite performance --report
    python run_rules_tests.py --suite all --coverage --report
"""

import argparse
import subprocess
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import tempfile
import shutil


class TestResult:
    """Container for test execution results."""
    
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.duration = 0.0
        self.output = ""
        self.error = ""
        self.metrics: Dict[str, Any] = {}
    
    def __str__(self) -> str:
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        return f"{status} {self.name} ({self.duration:.2f}s)"


class RulesTestRunner:
    """Comprehensive test runner for Rules Engine."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.results: List[TestResult] = []
        self.start_time = time.time()
        
        # Quality gates
        self.quality_gates = {
            "min_coverage_percent": 90,
            "max_performance_seconds": 3.0,
            "max_mutation_survival_percent": 15,
            "required_test_categories": ["unit", "golden"]
        }
        
    def run_command(self, cmd: List[str], description: str, timeout: int = 300) -> TestResult:
        """Run a command and capture results."""
        result = TestResult(description)
        start_time = time.time()
        
        print(f"\n🚀 {description}")
        print(f"   Command: {' '.join(cmd)}")
        
        try:
            process = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            result.duration = time.time() - start_time
            result.output = process.stdout
            result.error = process.stderr
            result.passed = process.returncode == 0
            
            if result.passed:
                print(f"   ✅ Completed in {result.duration:.2f}s")
            else:
                print(f"   ❌ Failed after {result.duration:.2f}s")
                if result.error:
                    print(f"   Error: {result.error[:200]}...")
                    
        except subprocess.TimeoutExpired:
            result.duration = timeout
            result.error = f"Command timed out after {timeout}s"
            print(f"   ⏰ Timed out after {timeout}s")
            
        except Exception as e:
            result.duration = time.time() - start_time
            result.error = str(e)
            print(f"   💥 Exception: {e}")
        
        self.results.append(result)
        return result
    
    def run_unit_tests(self, with_coverage: bool = False) -> TestResult:
        """Run unit tests for rules engine."""
        cmd = [
            "poetry", "run", "pytest", 
            "tests/unit/rules/",
            "-v", "--tb=short"
        ]
        
        if with_coverage:
            cmd.extend([
                "--cov=src/domain/rules",
                "--cov=src/application/ports/rules.py", 
                "--cov-report=term-missing",
                "--cov-report=xml:coverage-unit.xml",
                "--cov-report=html:htmlcov-unit"
            ])
        
        result = self.run_command(cmd, "Unit Tests", timeout=300)
        
        # Extract coverage if available
        if with_coverage and result.passed:
            try:
                coverage_output = subprocess.run(
                    ["poetry", "run", "coverage", "report", "--format=total"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True
                )
                if coverage_output.returncode == 0:
                    coverage = int(coverage_output.stdout.strip())
                    result.metrics["coverage_percent"] = coverage
                    print(f"   📊 Coverage: {coverage}%")
                    
                    if coverage < self.quality_gates["min_coverage_percent"]:
                        print(f"   ⚠️  Coverage below minimum {self.quality_gates['min_coverage_percent']}%")
                        
            except Exception as e:
                print(f"   ⚠️  Could not extract coverage: {e}")
        
        return result
    
    def run_golden_tests(self, update_fixtures: bool = False) -> TestResult:
        """Run golden tests for marketplace compatibility."""
        cmd = [
            "poetry", "run", "pytest",
            "tests/golden/",
            "-v", "--tb=short"
        ]
        
        if update_fixtures:
            cmd.append("--update-golden")
        
        return self.run_command(cmd, "Golden Tests", timeout=180)
    
    def run_performance_tests(self) -> TestResult:
        """Run performance benchmark tests."""
        cmd = [
            "poetry", "run", "pytest",
            "tests/perf/benchmark_50k.py::TestRulesEnginePerformance::test_benchmark_50k_rows_under_3_seconds__primary_performance_requirement",
            "--run-perf",
            "-v", "--tb=short",
            "--durations=0"
        ]
        
        result = self.run_command(cmd, "Performance Benchmarks", timeout=600)
        
        # Extract performance metrics if available
        benchmark_file = self.project_root / "benchmark_results.json"
        if benchmark_file.exists():
            try:
                with open(benchmark_file) as f:
                    data = json.load(f)
                    
                primary = data.get("primary_benchmark", {})
                exec_time = primary.get("execution_time_seconds", 0)
                throughput = primary.get("throughput_rows_per_second", 0)
                
                result.metrics["execution_time_seconds"] = exec_time
                result.metrics["throughput_rows_per_second"] = throughput
                
                print(f"   ⚡ Execution time: {exec_time:.3f}s")
                print(f"   📈 Throughput: {throughput:,.0f} rows/second")
                
                if exec_time > self.quality_gates["max_performance_seconds"]:
                    print(f"   ⚠️  Performance below requirement ({self.quality_gates['max_performance_seconds']}s)")
                    result.passed = False
                    
            except Exception as e:
                print(f"   ⚠️  Could not extract performance metrics: {e}")
        
        return result
    
    def run_mutation_tests(self, limited: bool = True) -> TestResult:
        """Run mutation testing for test quality assessment."""
        cmd = [
            "poetry", "run", "pytest",
            "tests/mutation/",
            "--run-mutation"
        ]
        
        if limited:
            cmd.extend(["-k", "test_compiler_mutation_testing"])  # Run limited subset
        
        cmd.extend(["-v", "--tb=short"])
        
        result = self.run_command(cmd, "Mutation Testing", timeout=900)
        
        # Extract mutation metrics if available
        mutation_file = self.project_root / "mutation_report.json"
        if mutation_file.exists():
            try:
                with open(mutation_file) as f:
                    data = json.load(f)
                    
                report = data.get("mutation_testing_report", {})
                summary = report.get("summary", {})
                survival_rate = summary.get("survival_rate_percent", 100)
                
                result.metrics["mutation_survival_percent"] = survival_rate
                
                print(f"   🧬 Mutation survival rate: {survival_rate:.1f}%")
                
                if survival_rate > self.quality_gates["max_mutation_survival_percent"]:
                    print(f"   ⚠️  Mutation survival above threshold ({self.quality_gates['max_mutation_survival_percent']}%)")
                    
            except Exception as e:
                print(f"   ⚠️  Could not extract mutation metrics: {e}")
        
        return result
    
    def run_chaos_tests(self, intensity: str = "low") -> TestResult:
        """Run chaos engineering tests."""
        cmd = [
            "poetry", "run", "pytest",
            "tests/chaos/",
            "--run-chaos",
            f"--chaos-intensity={intensity}",
            "-v", "--tb=short"
        ]
        
        return self.run_command(cmd, "Chaos Engineering", timeout=600)
    
    def run_architecture_tests(self) -> TestResult:
        """Run architecture validation tests."""
        cmd = [
            "poetry", "run", "pytest",
            "tests/architecture/",
            "-v", "--tb=short"
        ]
        
        return self.run_command(cmd, "Architecture Validation", timeout=120)
    
    def run_lint_and_format(self) -> TestResult:
        """Run code quality checks."""
        # Run multiple quality checks in sequence
        checks = [
            (["poetry", "run", "black", "--check", "src/", "tests/"], "Code formatting"),
            (["poetry", "run", "isort", "--check-only", "src/", "tests/"], "Import sorting"),
            (["poetry", "run", "ruff", "check", "src/", "tests/"], "Linting"),
            (["poetry", "run", "mypy", "src/domain/rules/", "--strict"], "Type checking")
        ]
        
        overall_result = TestResult("Code Quality Checks")
        overall_start = time.time()
        
        all_passed = True
        outputs = []
        
        for cmd, description in checks:
            print(f"\n   🔍 {description}")
            result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"      ✅ Passed")
            else:
                print(f"      ❌ Failed")
                all_passed = False
                outputs.append(f"{description}: {result.stderr[:100]}")
        
        overall_result.passed = all_passed
        overall_result.duration = time.time() - overall_start
        overall_result.output = "\n".join(outputs)
        
        self.results.append(overall_result)
        return overall_result
    
    def generate_report(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        total_duration = time.time() - self.start_time
        
        # Calculate statistics
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        
        # Collect metrics
        all_metrics = {}
        for result in self.results:
            all_metrics.update(result.metrics)
        
        # Quality gate evaluation
        quality_gates_passed = 0
        quality_gates_total = 0
        quality_issues = []
        
        # Coverage gate
        if "coverage_percent" in all_metrics:
            quality_gates_total += 1
            coverage = all_metrics["coverage_percent"]
            if coverage >= self.quality_gates["min_coverage_percent"]:
                quality_gates_passed += 1
            else:
                quality_issues.append(f"Coverage {coverage}% < {self.quality_gates['min_coverage_percent']}%")
        
        # Performance gate
        if "execution_time_seconds" in all_metrics:
            quality_gates_total += 1
            exec_time = all_metrics["execution_time_seconds"]
            if exec_time <= self.quality_gates["max_performance_seconds"]:
                quality_gates_passed += 1
            else:
                quality_issues.append(f"Performance {exec_time:.3f}s > {self.quality_gates['max_performance_seconds']}s")
        
        # Mutation testing gate
        if "mutation_survival_percent" in all_metrics:
            quality_gates_total += 1
            survival = all_metrics["mutation_survival_percent"]
            if survival <= self.quality_gates["max_mutation_survival_percent"]:
                quality_gates_passed += 1
            else:
                quality_issues.append(f"Mutation survival {survival:.1f}% > {self.quality_gates['max_mutation_survival_percent']}%")
        
        # Create report
        report = {
            "summary": {
                "total_duration_seconds": total_duration,
                "tests_run": total_tests,
                "tests_passed": passed_tests,
                "tests_failed": failed_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "quality_gates_passed": quality_gates_passed,
                "quality_gates_total": quality_gates_total,
                "overall_status": "PASSED" if failed_tests == 0 and len(quality_issues) == 0 else "FAILED"
            },
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "duration": r.duration,
                    "metrics": r.metrics
                }
                for r in self.results
            ],
            "metrics": all_metrics,
            "quality_issues": quality_issues,
            "timestamp": time.time()
        }
        
        # Save report if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Report saved to: {output_path}")
        
        return report
    
    def print_summary(self, report: Dict[str, Any]) -> None:
        """Print test execution summary."""
        summary = report["summary"]
        
        print(f"\n{'='*80}")
        print("🎯 VALIDAHUB RULES ENGINE TEST SUMMARY")
        print(f"{'='*80}")
        
        print(f"⏱️  Total Duration: {summary['total_duration_seconds']:.1f}s")
        print(f"🧪 Tests Run: {summary['tests_run']}")
        print(f"✅ Passed: {summary['tests_passed']}")
        print(f"❌ Failed: {summary['tests_failed']}")
        print(f"📊 Success Rate: {summary['success_rate']:.1%}")
        
        # Quality gates
        print(f"\n🎯 Quality Gates: {summary['quality_gates_passed']}/{summary['quality_gates_total']} passed")
        
        if report["quality_issues"]:
            print(f"\n⚠️  Quality Issues:")
            for issue in report["quality_issues"]:
                print(f"   • {issue}")
        
        # Individual results
        print(f"\n📋 Test Results:")
        for result in self.results:
            print(f"   {result}")
        
        # Metrics
        metrics = report["metrics"]
        if metrics:
            print(f"\n📈 Key Metrics:")
            
            if "coverage_percent" in metrics:
                print(f"   • Coverage: {metrics['coverage_percent']}%")
            
            if "execution_time_seconds" in metrics:
                print(f"   • Performance: {metrics['execution_time_seconds']:.3f}s")
                
            if "throughput_rows_per_second" in metrics:
                print(f"   • Throughput: {metrics['throughput_rows_per_second']:,.0f} rows/s")
            
            if "mutation_survival_percent" in metrics:
                print(f"   • Mutation survival: {metrics['mutation_survival_percent']:.1f}%")
        
        # Final status
        status = summary['overall_status']
        if status == "PASSED":
            print(f"\n🎉 OVERALL STATUS: ✅ {status}")
            print("🚀 Rules Engine is ready for deployment!")
        else:
            print(f"\n🚨 OVERALL STATUS: ❌ {status}")
            print("🔧 Address issues before deployment.")


def main():
    parser = argparse.ArgumentParser(description="Run ValidaHub Rules Engine tests")
    
    parser.add_argument(
        "--suite",
        choices=["unit", "golden", "performance", "mutation", "chaos", "all", "ci"],
        default="all",
        help="Test suite to run"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Include coverage analysis"
    )
    
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate detailed report"
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for report"
    )
    
    parser.add_argument(
        "--update-fixtures",
        action="store_true",
        help="Update golden test fixtures"
    )
    
    args = parser.parse_args()
    
    # Initialize runner
    runner = RulesTestRunner()
    
    print(f"🚀 ValidaHub Rules Engine Test Suite")
    print(f"   Suite: {args.suite}")
    print(f"   Coverage: {args.coverage}")
    print(f"   Report: {args.report}")
    
    # Run code quality first (always)
    runner.run_lint_and_format()
    runner.run_architecture_tests()
    
    # Run selected test suite
    if args.suite in ["unit", "all", "ci"]:
        runner.run_unit_tests(with_coverage=args.coverage)
    
    if args.suite in ["golden", "all", "ci"]:
        runner.run_golden_tests(update_fixtures=args.update_fixtures)
    
    if args.suite in ["performance", "all"]:
        runner.run_performance_tests()
    
    if args.suite in ["mutation", "all"] and args.suite != "ci":
        # Skip mutation tests in CI mode (too slow)
        runner.run_mutation_tests(limited=True)
    
    if args.suite in ["chaos", "all"] and args.suite != "ci":
        # Skip chaos tests in CI mode (resource intensive)
        runner.run_chaos_tests(intensity="low")
    
    # Generate report
    output_path = args.output or (Path("test_report.json") if args.report else None)
    report = runner.generate_report(output_path)
    
    # Print summary
    runner.print_summary(report)
    
    # Exit with appropriate code
    exit_code = 0 if report["summary"]["overall_status"] == "PASSED" else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()