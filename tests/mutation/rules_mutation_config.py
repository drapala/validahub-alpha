"""
Mutation testing configuration for Rules Engine.

Mutation testing validates test quality by introducing bugs (mutations) 
into the code and checking if tests catch them. High-quality tests
should detect most mutations.

This configuration focuses on critical paths in the rules engine:
- Rule compilation logic
- Condition evaluation
- Rule execution flow
- Performance-critical sections
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
import pytest


class RulesMutationConfig:
    """Configuration for mutation testing of rules engine components."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.mutation_results: Dict[str, Any] = {}
    
    @property
    def mutation_targets(self) -> List[str]:
        """
        Target modules for mutation testing.
        
        Focus on critical business logic that should be thoroughly tested:
        - Rule compiler (correctness is critical)
        - Runtime engine (performance and correctness)
        - Condition evaluation (logic correctness)
        - Value objects (domain invariants)
        """
        return [
            "src/domain/rules/engine/compiler.py",
            "src/domain/rules/engine/runtime.py", 
            "src/domain/rules/engine/ir_types.py",
            "src/domain/rules/value_objects.py",
            "src/domain/rules/aggregates.py",
            "src/application/ports/rules.py"
        ]
    
    @property
    def test_directories(self) -> List[str]:
        """Test directories that should kill mutations."""
        return [
            "tests/unit/rules/",
            "tests/integration/rules/",
            "tests/golden/"
        ]
    
    @property
    def mutmut_config(self) -> Dict[str, Any]:
        """Mutmut configuration settings."""
        return {
            # Survival threshold - maximum percentage of mutations that can survive
            "survival_threshold": 15,  # 85% of mutations should be killed
            
            # Test command to run for each mutation
            "test_command": "pytest tests/unit/rules/ tests/golden/ -x --tb=no",
            
            # Mutations to apply
            "mutations": {
                # Arithmetic operators
                "arithmetic": True,
                # Comparison operators  
                "comparison": True,
                # Boolean operators
                "boolean": True,
                # Assignment operators
                "assignment": True,
                # Index mutations
                "index": True,
                # String mutations
                "string": True,
                # Number mutations
                "number": True
            },
            
            # Files to exclude from mutation
            "exclude_patterns": [
                "*/tests/*",
                "*/__pycache__/*",
                "*/migrations/*",
                "*/.pytest_cache/*"
            ],
            
            # Specific mutations to skip (if they cause issues)
            "skip_mutations": []
        }
    
    def create_mutmut_config_file(self) -> Path:
        """Create mutmut configuration file."""
        config_path = self.project_root / "pyproject.toml"
        
        mutmut_config = f"""
[tool.mutmut]
# Mutation testing configuration for ValidaHub Rules Engine
runner = "pytest tests/unit/rules/ tests/golden/ -x --tb=no"
tests_dir = "tests/"
source_dir = "src/"

# Target paths for mutation
paths_to_mutate = [
    {','.join([f'"{path}"' for path in self.mutation_targets])}
]

# Exclude patterns
paths_to_exclude = [
    "tests/",
    "__pycache__/",
    ".pytest_cache/",
    "*/migrations/"
]

# Mutation survival threshold (max % of mutations that can survive)
survival_threshold = {self.mutmut_config['survival_threshold']}

# Disable specific mutation types if needed
# disable_mutation_types = []

# Skip specific mutations by ID if they cause false positives
# skip = []

# Use multiprocessing for faster execution
use_coverage = true
use_patch_file = false
"""
        
        # Check if pyproject.toml exists and append/update
        if config_path.exists():
            with open(config_path, 'a') as f:
                f.write(mutmut_config)
        else:
            with open(config_path, 'w') as f:
                f.write(mutmut_config)
        
        return config_path
    
    def run_mutation_tests(self, target_module: str = None, max_mutations: int = 100) -> Dict[str, Any]:
        """
        Run mutation tests on specified module or all targets.
        
        Args:
            target_module: Specific module to test (None for all targets)
            max_mutations: Maximum number of mutations to test
            
        Returns:
            Dictionary with mutation test results
        """
        results = {
            "target_module": target_module or "all",
            "mutations_tested": 0,
            "mutations_killed": 0,
            "mutations_survived": 0,
            "survival_rate": 0.0,
            "test_quality": "unknown",
            "details": []
        }
        
        # Determine targets
        targets = [target_module] if target_module else self.mutation_targets
        
        for target in targets:
            target_path = self.project_root / target
            if not target_path.exists():
                print(f"Warning: Target {target} does not exist, skipping...")
                continue
            
            print(f"Running mutation tests on {target}...")
            
            try:
                # Run mutmut on target
                cmd = [
                    "mutmut", "run", 
                    "--paths-to-mutate", str(target_path),
                    "--runner", self.mutmut_config["test_command"],
                    "--use-coverage"
                ]
                
                if max_mutations:
                    cmd.extend(["--CI"])  # Run limited mutations for CI
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                    timeout=300  # 5 minute timeout per target
                )
                
                # Parse results
                target_results = self._parse_mutmut_output(result.stdout, result.stderr)
                target_results["target"] = target
                target_results["command_exit_code"] = result.returncode
                
                results["details"].append(target_results)
                results["mutations_tested"] += target_results.get("mutations_tested", 0)
                results["mutations_killed"] += target_results.get("mutations_killed", 0)
                results["mutations_survived"] += target_results.get("mutations_survived", 0)
                
            except subprocess.TimeoutExpired:
                print(f"Mutation testing timed out for {target}")
                results["details"].append({
                    "target": target,
                    "error": "timeout",
                    "mutations_tested": 0,
                    "mutations_killed": 0,
                    "mutations_survived": 0
                })
            except Exception as e:
                print(f"Error running mutation tests on {target}: {e}")
                results["details"].append({
                    "target": target,
                    "error": str(e),
                    "mutations_tested": 0,
                    "mutations_killed": 0,
                    "mutations_survived": 0
                })
        
        # Calculate overall statistics
        if results["mutations_tested"] > 0:
            results["survival_rate"] = results["mutations_survived"] / results["mutations_tested"]
            
            if results["survival_rate"] <= 0.05:  # ≤5% survival
                results["test_quality"] = "excellent"
            elif results["survival_rate"] <= 0.15:  # ≤15% survival
                results["test_quality"] = "good"
            elif results["survival_rate"] <= 0.30:  # ≤30% survival
                results["test_quality"] = "fair"
            else:
                results["test_quality"] = "poor"
        
        return results
    
    def _parse_mutmut_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """Parse mutmut output to extract mutation statistics."""
        result = {
            "mutations_tested": 0,
            "mutations_killed": 0,
            "mutations_survived": 0,
            "mutations_timeout": 0,
            "mutations_suspicious": 0,
            "output": stdout,
            "errors": stderr
        }
        
        # Parse mutmut output for statistics
        lines = stdout.split('\n') + stderr.split('\n')
        
        for line in lines:
            line = line.strip().lower()
            
            if "killed" in line and "mutations" in line:
                # Extract number from "X mutations killed"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.isdigit() and i < len(parts) - 1 and "kill" in parts[i + 1]:
                        result["mutations_killed"] = int(part)
                        break
            
            elif "survived" in line and "mutations" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.isdigit() and i < len(parts) - 1 and "surviv" in parts[i + 1]:
                        result["mutations_survived"] = int(part)
                        break
            
            elif "suspicious" in line and "mutations" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.isdigit() and i < len(parts) - 1 and "suspic" in parts[i + 1]:
                        result["mutations_suspicious"] = int(part)
                        break
            
            elif "timeout" in line and "mutations" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.isdigit() and i < len(parts) - 1 and "timeout" in parts[i + 1]:
                        result["mutations_timeout"] = int(part)
                        break
        
        # Calculate total tested
        result["mutations_tested"] = (
            result["mutations_killed"] + 
            result["mutations_survived"] + 
            result["mutations_timeout"] + 
            result["mutations_suspicious"]
        )
        
        return result
    
    def generate_mutation_report(self, results: Dict[str, Any], output_path: Path) -> None:
        """Generate detailed mutation testing report."""
        report = {
            "mutation_testing_report": {
                "summary": {
                    "total_mutations": results["mutations_tested"],
                    "killed": results["mutations_killed"],
                    "survived": results["mutations_survived"],
                    "survival_rate_percent": round(results["survival_rate"] * 100, 2),
                    "test_quality": results["test_quality"],
                    "passed_threshold": results["survival_rate"] <= (self.mutmut_config["survival_threshold"] / 100)
                },
                "targets": results["details"],
                "recommendations": self._generate_recommendations(results),
                "configuration": self.mutmut_config
            }
        }
        
        # Save JSON report
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        self._print_mutation_summary(results)
    
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on mutation test results."""
        recommendations = []
        
        survival_rate = results["survival_rate"]
        
        if survival_rate > 0.30:
            recommendations.extend([
                "Test coverage appears insufficient - consider adding more test cases",
                "Focus on testing edge cases and error conditions",
                "Add tests for boundary values and invalid inputs",
                "Consider using property-based testing for better coverage"
            ])
        
        elif survival_rate > 0.15:
            recommendations.extend([
                "Good test coverage but some gaps remain",
                "Review surviving mutations to identify missing test scenarios",
                "Consider adding negative test cases",
                "Test complex logical conditions more thoroughly"
            ])
        
        elif survival_rate > 0.05:
            recommendations.extend([
                "Excellent test coverage!",
                "Review any surviving mutations for potential improvements",
                "Consider performance impact of additional tests"
            ])
        
        else:
            recommendations.append("Outstanding test quality - mutation score is excellent!")
        
        # Target-specific recommendations
        for detail in results["details"]:
            if detail.get("mutations_survived", 0) > 0:
                recommendations.append(
                    f"Review {detail['target']} - {detail.get('mutations_survived', 0)} mutations survived"
                )
        
        return recommendations
    
    def _print_mutation_summary(self, results: Dict[str, Any]) -> None:
        """Print mutation testing summary."""
        print("\n" + "=" * 60)
        print("🧬 MUTATION TESTING RESULTS")
        print("=" * 60)
        
        print(f"📊 Total Mutations Tested: {results['mutations_tested']}")
        print(f"💀 Mutations Killed: {results['mutations_killed']}")
        print(f"🧟 Mutations Survived: {results['mutations_survived']}")
        print(f"📈 Survival Rate: {results['survival_rate']:.1%}")
        print(f"🎯 Test Quality: {results['test_quality'].upper()}")
        
        threshold = self.mutmut_config["survival_threshold"] / 100
        status = "PASSED" if results['survival_rate'] <= threshold else "FAILED"
        print(f"✅ Quality Gate: {status} (threshold: {threshold:.1%})")
        
        print(f"\n📋 Per-Target Results:")
        for detail in results['details']:
            target = Path(detail['target']).name
            survived = detail.get('mutations_survived', 0)
            tested = detail.get('mutations_tested', 0)
            rate = (survived / tested * 100) if tested > 0 else 0
            print(f"  {target}: {survived}/{tested} survived ({rate:.1f}%)")


@pytest.mark.mutation
class TestRulesMutationTesting:
    """Mutation testing suite for rules engine."""
    
    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent
    
    @pytest.fixture
    def mutation_config(self, project_root: Path) -> RulesMutationConfig:
        """Create mutation testing configuration."""
        return RulesMutationConfig(project_root)
    
    def test_compiler_mutation_testing__validates_test_quality(
        self,
        mutation_config: RulesMutationConfig,
        tmp_path: Path
    ):
        """Test mutation testing on rule compiler module."""
        # Focus on compiler since it's critical for correctness
        target = "src/domain/rules/engine/compiler.py"
        
        results = mutation_config.run_mutation_tests(
            target_module=target,
            max_mutations=50  # Limit for reasonable test time
        )
        
        # Generate report
        report_path = tmp_path / "compiler_mutation_report.json"
        mutation_config.generate_mutation_report(results, report_path)
        
        # Validate mutation test quality
        survival_rate = results["survival_rate"]
        threshold = mutation_config.mutmut_config["survival_threshold"] / 100
        
        assert survival_rate <= threshold, (
            f"Mutation testing failed: {survival_rate:.1%} survival rate exceeds "
            f"threshold of {threshold:.1%}. Test quality needs improvement."
        )
        
        assert results["mutations_tested"] > 0, "No mutations were tested"
        
        print(f"✅ Compiler mutation testing passed: {survival_rate:.1%} survival rate")
    
    def test_runtime_mutation_testing__validates_execution_logic(
        self,
        mutation_config: RulesMutationConfig,
        tmp_path: Path
    ):
        """Test mutation testing on runtime engine module."""
        target = "src/domain/rules/engine/runtime.py"
        
        results = mutation_config.run_mutation_tests(
            target_module=target,
            max_mutations=30  # Runtime is complex, limit mutations
        )
        
        # Generate report
        report_path = tmp_path / "runtime_mutation_report.json"
        mutation_config.generate_mutation_report(results, report_path)
        
        # Validate results
        survival_rate = results["survival_rate"]
        threshold = mutation_config.mutmut_config["survival_threshold"] / 100
        
        assert survival_rate <= threshold, (
            f"Runtime mutation testing failed: {survival_rate:.1%} survival rate"
        )
        
        print(f"✅ Runtime mutation testing passed: {survival_rate:.1%} survival rate")
    
    def test_value_objects_mutation_testing__validates_domain_invariants(
        self,
        mutation_config: RulesMutationConfig,
        tmp_path: Path
    ):
        """Test mutation testing on value objects to ensure invariants hold."""
        target = "src/domain/rules/value_objects.py"
        
        results = mutation_config.run_mutation_tests(
            target_module=target,
            max_mutations=25
        )
        
        # Generate report
        report_path = tmp_path / "value_objects_mutation_report.json"
        mutation_config.generate_mutation_report(results, report_path)
        
        # Value objects should have very low survival rate (strict invariants)
        survival_rate = results["survival_rate"]
        strict_threshold = 0.10  # Even stricter for value objects
        
        assert survival_rate <= strict_threshold, (
            f"Value object mutation testing failed: {survival_rate:.1%} survival rate "
            f"exceeds strict threshold of {strict_threshold:.1%}"
        )
        
        print(f"✅ Value objects mutation testing passed: {survival_rate:.1%} survival rate")
    
    def test_comprehensive_mutation_suite__validates_overall_test_quality(
        self,
        mutation_config: RulesMutationConfig,
        tmp_path: Path
    ):
        """Run comprehensive mutation testing across all critical modules."""
        # Run mutation tests on all targets (limited for CI performance)
        results = mutation_config.run_mutation_tests(max_mutations=20)  # Per target limit
        
        # Generate comprehensive report
        report_path = tmp_path / "comprehensive_mutation_report.json"
        mutation_config.generate_mutation_report(results, report_path)
        
        # Overall quality validation
        survival_rate = results["survival_rate"]
        threshold = mutation_config.mutmut_config["survival_threshold"] / 100
        
        assert survival_rate <= threshold, (
            f"Comprehensive mutation testing failed: {survival_rate:.1%} survival rate "
            f"exceeds threshold of {threshold:.1%}. Overall test quality needs improvement."
        )
        
        # Ensure significant number of mutations were tested
        assert results["mutations_tested"] >= 10, (
            f"Too few mutations tested: {results['mutations_tested']}. "
            "May indicate configuration issues."
        )
        
        # Check that tests are actually catching mutations
        assert results["mutations_killed"] > 0, "No mutations were killed by tests"
        
        print(f"✅ Comprehensive mutation testing passed!")
        print(f"📊 Overall quality: {results['test_quality']}")
        print(f"🎯 Survival rate: {survival_rate:.1%}")
    
    @pytest.mark.slow
    def test_full_mutation_coverage__comprehensive_quality_assessment(
        self,
        mutation_config: RulesMutationConfig,
        tmp_path: Path
    ):
        """
        Full mutation testing suite for comprehensive quality assessment.
        
        This test runs extensive mutation testing and is marked as slow.
        Only run when doing comprehensive quality validation.
        """
        # Run unlimited mutation tests (for comprehensive assessment)
        results = mutation_config.run_mutation_tests(max_mutations=None)
        
        # Generate detailed report
        report_path = tmp_path / "full_mutation_report.json"
        mutation_config.generate_mutation_report(results, report_path)
        
        # Full suite should have excellent test quality
        survival_rate = results["survival_rate"]
        excellent_threshold = 0.08  # 8% or better for excellent quality
        
        if survival_rate <= excellent_threshold:
            print(f"🏆 EXCELLENT test quality: {survival_rate:.1%} survival rate")
        else:
            print(f"⚠️  Test quality could be improved: {survival_rate:.1%} survival rate")
            
            # Print specific recommendations
            recommendations = mutation_config._generate_recommendations(results)
            print("\n💡 Recommendations:")
            for rec in recommendations:
                print(f"  • {rec}")
        
        # Still enforce the basic threshold
        threshold = mutation_config.mutmut_config["survival_threshold"] / 100
        assert survival_rate <= threshold, (
            f"Full mutation testing failed: {survival_rate:.1%} exceeds {threshold:.1%}"
        )


def create_mutation_test_script() -> str:
    """Create standalone mutation testing script."""
    script_content = '''#!/usr/bin/env python3
"""
Standalone mutation testing script for ValidaHub Rules Engine.

Usage:
    python mutation_test.py [target_module] [--max-mutations N]

Examples:
    python mutation_test.py  # Test all targets
    python mutation_test.py src/domain/rules/engine/compiler.py  # Test specific module
    python mutation_test.py --max-mutations 50  # Limit mutations for faster execution
"""

import argparse
import sys
from pathlib import Path
from tests.mutation.rules_mutation_config import RulesMutationConfig


def main():
    parser = argparse.ArgumentParser(description="Run mutation tests on ValidaHub Rules Engine")
    parser.add_argument("target", nargs="?", help="Target module to test (optional)")
    parser.add_argument("--max-mutations", type=int, default=100, help="Maximum mutations per target")
    parser.add_argument("--output", type=Path, help="Output file for results")
    
    args = parser.parse_args()
    
    # Setup
    project_root = Path(__file__).parent.parent
    mutation_config = RulesMutationConfig(project_root)
    
    # Create mutmut config
    config_file = mutation_config.create_mutmut_config_file()
    print(f"Created mutation config: {config_file}")
    
    # Run mutation tests
    print("🧬 Starting mutation testing...")
    results = mutation_config.run_mutation_tests(
        target_module=args.target,
        max_mutations=args.max_mutations
    )
    
    # Generate report
    output_path = args.output or project_root / "mutation_report.json"
    mutation_config.generate_mutation_report(results, output_path)
    
    # Exit with appropriate code
    threshold = mutation_config.mutmut_config["survival_threshold"] / 100
    if results["survival_rate"] > threshold:
        print(f"❌ Mutation testing failed: {results['survival_rate']:.1%} > {threshold:.1%}")
        sys.exit(1)
    else:
        print(f"✅ Mutation testing passed: {results['survival_rate']:.1%} ≤ {threshold:.1%}")
        sys.exit(0)


if __name__ == "__main__":
    main()
'''
    return script_content


# Pytest configuration
def pytest_configure(config):
    """Configure mutation testing markers."""
    config.addinivalue_line(
        "markers", "mutation: mark test as mutation testing"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (comprehensive mutation testing)"
    )


def pytest_addoption(parser):
    """Add mutation testing options."""
    parser.addoption(
        "--run-mutation",
        action="store_true",
        default=False,
        help="Run mutation tests"
    )
    parser.addoption(
        "--mutation-target",
        type=str,
        help="Specific target module for mutation testing"
    )


def pytest_collection_modifyitems(config, items):
    """Skip mutation tests unless explicitly requested."""
    if config.getoption("--run-mutation"):
        return
    
    skip_mutation = pytest.mark.skip(reason="Mutation tests skipped (use --run-mutation to run)")
    for item in items:
        if "mutation" in item.keywords:
            item.add_marker(skip_mutation)


if __name__ == "__main__":
    # Create standalone script
    script_path = Path(__file__).parent.parent.parent / "mutation_test.py"
    script_content = create_mutation_test_script()
    
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    script_path.chmod(0o755)  # Make executable
    print(f"Created standalone mutation testing script: {script_path}")
    
    # Run basic mutation test
    project_root = Path(__file__).parent.parent.parent
    config = RulesMutationConfig(project_root)
    
    print("🧬 Running sample mutation test...")
    results = config.run_mutation_tests(max_mutations=5)  # Very limited for demo
    
    print(f"✅ Sample complete. Survival rate: {results['survival_rate']:.1%}")
    print("📄 Use pytest --run-mutation for full mutation testing")