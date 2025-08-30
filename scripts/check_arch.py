#!/usr/bin/env python3
"""
Architecture validation script for ValidaHub.
Ensures clean architecture layers are properly isolated.
"""
import ast
import os
import sys


def check_domain_imports():
    """Check that domain layer doesn't import from application or infrastructure."""
    violations = []
    domain_path = 'src/domain'
    
    if not os.path.exists(domain_path):
        print(f"⚠️  Domain path {domain_path} not found")
        return violations
    
    for root, dirs, files in os.walk(domain_path):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath) as f:
                        tree = ast.parse(f.read())
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom):
                            if node.module and ('application' in node.module or 'infrastructure' in node.module or 'infra' in node.module or 'apps' in node.module):
                                violations.append(f'{filepath}: imports {node.module}')
                        elif isinstance(node, ast.Import):
                            for alias in node.names:
                                if 'application' in alias.name or 'infrastructure' in alias.name or 'infra' in alias.name or 'apps' in alias.name:
                                    violations.append(f'{filepath}: imports {alias.name}')
                except Exception as e:
                    print(f"⚠️  Error parsing {filepath}: {e}")
                    
    return violations


def check_application_imports():
    """Check that application layer doesn't import from infrastructure."""
    violations = []
    app_path = 'src/application'
    
    if not os.path.exists(app_path):
        print(f"⚠️  Application path {app_path} not found")
        return violations
    
    for root, dirs, files in os.walk(app_path):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath) as f:
                        tree = ast.parse(f.read())
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom):
                            if node.module and ('infrastructure' in node.module or 'infra' in node.module or 'apps' in node.module):
                                violations.append(f'{filepath}: imports {node.module}')
                        elif isinstance(node, ast.Import):
                            for alias in node.names:
                                if 'infrastructure' in alias.name or 'infra' in alias.name or 'apps' in alias.name:
                                    violations.append(f'{filepath}: imports {alias.name}')
                except Exception as e:
                    print(f"⚠️  Error parsing {filepath}: {e}")
                    
    return violations


def main():
    """Run architecture validation checks."""
    print("Validating architecture dependencies...")
    
    domain_violations = check_domain_imports()
    app_violations = check_application_imports()
    
    has_violations = False
    
    if domain_violations:
        print('❌ Domain layer violations:')
        for v in domain_violations:
            print(f'  {v}')
        has_violations = True
    
    if app_violations:
        print('❌ Application layer violations:')
        for v in app_violations:
            print(f'  {v}')
        has_violations = True
    
    if not has_violations:
        print('✅ Architecture dependencies are valid')
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())