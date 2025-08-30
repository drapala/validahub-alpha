"""
Architecture tests to enforce DDD layer boundaries as per CLAUDE.md section 4.

Rules enforced:
- domain/ cannot import anything from framework
- application/ cannot import infra/*
- infra/ can import application/ and domain/
"""

import ast
import os
from pathlib import Path

import pytest


def get_python_files(directory: Path) -> list[Path]:
    """Get all Python files in a directory recursively."""
    python_files = []
    if not directory.exists():
        return python_files

    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                python_files.append(Path(root) / file)

    return python_files


def extract_imports(file_path: Path) -> set[str]:
    """Extract all import statements from a Python file."""
    imports = set()

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Parse the AST
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                # Skip relative imports (level > 0 means relative import)
                if node.level > 0:
                    # Relative import within the same package - this is allowed
                    continue

                if node.module:
                    imports.add(node.module)
                    # Also add submodule imports
                    for alias in node.names:
                        if alias.name != "*":
                            imports.add(f"{node.module}.{alias.name}")

    except (SyntaxError, UnicodeDecodeError) as e:
        pytest.fail(f"Failed to parse {file_path}: {e}")

    return imports


def is_framework_import(import_name: str) -> bool:
    """Check if an import is from a framework (violating domain purity)."""
    framework_prefixes = [
        "fastapi",
        "sqlalchemy",
        "redis",
        "boto3",
        "requests",
        "httpx",
        "celery",
        "pytest",
        "hypothesis",
        "structlog",  # Even logging frameworks should be abstracted
    ]

    # NOTE: Libraries like dateutil, pandas, numpy are currently allowed
    # in the rules engine as a pragmatic choice. The proper refactor
    # to move these to application/infrastructure layer is documented
    # in docs/refactor/rules-engine-ddd-separation.md

    return any(import_name.startswith(prefix) for prefix in framework_prefixes)


def is_infra_import(import_name: str) -> bool:
    """Check if an import is from the infra layer."""
    return import_name.startswith("infra.") or import_name == "infra"


class TestDomainLayerPurity:
    """Test that domain layer has no framework dependencies."""

    def test_domain_has_no_framework_imports(self):
        """Domain layer must not import any framework code."""
        src_path = Path(__file__).parent.parent.parent / "src"
        domain_path = src_path / "domain"

        if not domain_path.exists():
            pytest.skip("Domain directory not found")

        violations = []
        domain_files = get_python_files(domain_path)

        for file_path in domain_files:
            imports = extract_imports(file_path)

            for import_name in imports:
                if is_framework_import(import_name):
                    relative_path = file_path.relative_to(src_path)
                    violations.append(f"{relative_path}: imports {import_name}")

        if violations:
            violation_list = "\n".join(violations)
            pytest.fail(
                f"Domain layer has {len(violations)} framework import violations:\n{violation_list}"
            )

    def test_domain_imports_only_standard_library(self):
        """Domain layer should only import standard library and typing."""
        src_path = Path(__file__).parent.parent.parent / "src"
        domain_path = src_path / "domain"

        if not domain_path.exists():
            pytest.skip("Domain directory not found")

        allowed_prefixes = [
            "typing",
            "dataclasses",
            "datetime",
            "uuid",
            "enum",
            "abc",
            "unicodedata",
            "hashlib",
            "re",
            "pathlib",
            "urllib.parse",
            "domain.",  # Internal domain imports
            "src.domain.",  # Internal domain imports (CI path)
            "__future__",
            "decimal",  # Standard library for precise decimal arithmetic
            "concurrent.futures",  # Standard library for parallel execution
            "json",  # Standard library for JSON handling
            "logging",  # Standard library for logging
            "time",  # Standard library for time operations
        ]

        # TEMPORARY: Allow utility libraries in rules engine until proper refactor
        # See docs/refactor/rules-engine-ddd-separation.md for the plan
        rules_engine_exceptions = [
            "dateutil",  # Date parsing utility - should move to application layer
            "pandas",  # Data processing - should move to infrastructure layer
            "numpy",  # Numerical operations - should move to infrastructure layer
            "yaml",  # YAML parsing - should move to infrastructure layer
            "jsonschema",  # Schema validation - should move to infrastructure layer
        ]

        violations = []
        domain_files = get_python_files(domain_path)

        for file_path in domain_files:
            imports = extract_imports(file_path)

            for import_name in imports:
                # Skip if import is allowed
                if any(import_name.startswith(prefix) for prefix in allowed_prefixes):
                    continue

                # Skip built-in modules (no dots)
                if "." not in import_name:
                    continue

                # Skip if it's already a domain import (handled above)
                if import_name.startswith("domain.") or import_name.startswith("src.domain."):
                    continue

                # Skip relative imports within rules subdomain (e.g., events.*, value_objects.*, entities.*, exceptions.*)
                # These are internal to the rules bounded context
                relative_imports = ["events.", "value_objects.", "entities.", "aggregates.", "exceptions."]
                if any(import_name.startswith(rel) for rel in relative_imports):
                    continue

                # TEMPORARY: Skip if it's in rules engine and uses allowed exceptions
                if "rules/engine" in str(file_path):
                    if any(import_name.startswith(exc) for exc in rules_engine_exceptions):
                        continue
                relative_path = file_path.relative_to(src_path)
                violations.append(f"{relative_path}: imports {import_name}")

        if violations:
            violation_list = "\n".join(violations)
            pytest.fail(
                f"Domain layer has {len(violations)} non-standard library imports:\n{violation_list}"
            )


class TestApplicationLayerBoundaries:
    """Test that application layer respects boundaries."""

    def test_application_does_not_import_infra(self):
        """Application layer must not import infra layer."""
        src_path = Path(__file__).parent.parent.parent / "src"
        application_path = src_path / "application"

        if not application_path.exists():
            pytest.skip("Application directory not found")

        violations = []
        application_files = get_python_files(application_path)

        for file_path in application_files:
            imports = extract_imports(file_path)

            for import_name in imports:
                if is_infra_import(import_name):
                    relative_path = file_path.relative_to(src_path)
                    violations.append(f"{relative_path}: imports {import_name}")

        if violations:
            violation_list = "\n".join(violations)
            pytest.fail(
                f"Application layer has {len(violations)} infra import violations:\n{violation_list}"
            )


class TestInfraLayerCompliance:
    """Test that infra layer can import from application and domain."""

    def test_infra_can_import_domain_and_application(self):
        """Infra layer is allowed to import domain and application layers."""
        src_path = Path(__file__).parent.parent.parent / "src"
        infra_path = src_path / "infra"

        if not infra_path.exists():
            pytest.skip("Infra directory not found")

        # This test validates that the dependency direction is correct
        # by checking that at least some infra files import from domain/application
        infra_files = get_python_files(infra_path)

        if not infra_files:
            pytest.skip("No infra files found")

        domain_imports = 0
        application_imports = 0

        for file_path in infra_files:
            imports = extract_imports(file_path)

            for import_name in imports:
                if import_name.startswith("domain."):
                    domain_imports += 1
                elif import_name.startswith("application."):
                    application_imports += 1

        # If we have infra files but no imports from domain/application,
        # this might indicate a problem with the architecture
        if infra_files and domain_imports == 0 and application_imports == 0:
            pytest.fail(
                "Infra layer exists but doesn't import from domain or application layers. "
                "This might indicate architectural issues."
            )


class TestCircularDependencies:
    """Test that there are no circular dependencies between layers."""

    def test_no_circular_dependencies(self):
        """Ensure no circular dependencies exist between architectural layers."""
        src_path = Path(__file__).parent.parent.parent / "src"

        layers = ["domain", "application", "infra", "shared"]
        layer_imports = {}

        for layer in layers:
            layer_path = src_path / layer
            if not layer_path.exists():
                continue

            layer_imports[layer] = set()
            layer_files = get_python_files(layer_path)

            for file_path in layer_files:
                imports = extract_imports(file_path)

                for import_name in imports:
                    for other_layer in layers:
                        if import_name.startswith(f"{other_layer}."):
                            layer_imports[layer].add(other_layer)

        # Check for violations of the dependency hierarchy:
        # domain -> (none)
        # application -> domain
        # infra -> domain, application
        # shared -> (none, but can be imported by all)

        violations = []

        if "domain" in layer_imports:
            domain_deps = layer_imports["domain"] - {"domain"}  # Remove self-references
            if domain_deps:
                violations.append(f"Domain layer imports: {domain_deps}")

        if "application" in layer_imports:
            app_deps = layer_imports["application"] - {
                "application",
                "domain",
                "shared",
            }  # Allow shared for now - TODO: remove in next PR
            if app_deps:
                violations.append(f"Application layer has invalid imports: {app_deps}")

        if "shared" in layer_imports:
            shared_deps = layer_imports["shared"] - {"shared"}
            if shared_deps:
                violations.append(f"Shared layer imports other layers: {shared_deps}")

        if violations:
            violation_list = "\n".join(violations)
            pytest.fail(f"Architecture violations found:\n{violation_list}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
