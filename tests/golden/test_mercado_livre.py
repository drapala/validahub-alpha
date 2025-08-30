"""
Golden tests for Mercado Livre marketplace rules.

Tests ensure consistent behavior of rule compilation and execution
against known-good fixtures representing real marketplace requirements.
"""

import pytest
import pandas as pd
from pathlib import Path
from typing import Dict, Any

from tests.golden.conftest import GoldenTestHelper


@pytest.mark.golden
class TestMercadoLivreGolden:
    """Golden tests for Mercado Livre marketplace rules."""
    
    @pytest.fixture
    def marketplace_name(self) -> str:
        """Marketplace identifier."""
        return "mercado_livre"
    
    @pytest.fixture
    def sample_products_csv(self, input_fixtures_path: Path, marketplace_name: str) -> Path:
        """Path to sample products CSV fixture."""
        return input_fixtures_path / f"{marketplace_name}_products.csv"
    
    @pytest.fixture
    def rules_yaml(self, rules_fixtures_path: Path, marketplace_name: str) -> Path:
        """Path to rules YAML fixture."""
        return rules_fixtures_path / f"{marketplace_name}_rules.yaml"
    
    @pytest.fixture
    def expected_results_json(self, expected_fixtures_path: Path, marketplace_name: str) -> Path:
        """Path to expected results JSON fixture."""
        return expected_fixtures_path / f"{marketplace_name}_validation_results.json"
    
    def test_mercado_livre_validation__with_sample_products__matches_expected_results(
        self,
        compiler,
        engine,
        golden_helper: GoldenTestHelper,
        sample_products_csv: Path,
        rules_yaml: Path,
        expected_results_json: Path,
        request
    ):
        """RED: Test ML validation produces expected results."""
        # Skip if files don't exist (will be created by setup)
        if not all(p.exists() for p in [sample_products_csv, rules_yaml, expected_results_json]):
            pytest.skip("Golden fixtures not yet created - run with --update-golden first")
        
        # Load test data
        products_df = golden_helper.load_csv_fixture(sample_products_csv)
        rules_yaml_content = golden_helper.load_rules_fixture(rules_yaml)
        expected_results = golden_helper.load_expected_results(expected_results_json)
        
        # Compile and execute rules
        compiled_rules = compiler.compile_yaml(rules_yaml_content)
        execution_result = engine.execute_rules(compiled_rules, products_df)
        
        # Normalize results for comparison
        actual_results = golden_helper.normalize_execution_result(execution_result)
        
        # Update golden files if requested
        if request.config.getoption("--update-golden"):
            golden_helper.save_results_as_fixture(actual_results, expected_results_json)
            pytest.skip("Updated golden fixture - run again to test")
        
        # Compare results
        differences = golden_helper.compare_results(actual_results, expected_results)
        
        assert not differences, f"Results differ from golden fixture:\n" + "\n".join(differences)
    
    def test_mercado_livre_title_validation__with_various_titles__validates_correctly(
        self,
        compiler,
        engine,
        golden_helper: GoldenTestHelper,
        input_fixtures_path: Path,
        expected_fixtures_path: Path,
        rules_fixtures_path: Path,
        request
    ):
        """Test title validation rules with edge cases."""
        fixture_name = "mercado_livre_title_validation"
        
        # Define test data
        test_data = pd.DataFrame({
            'title': [
                'iPhone 13 Pro 128GB Azul Sierra',  # Valid
                'TV',  # Too short
                '',  # Empty
                None,  # None
                'A' * 200,  # Too long
                'iPhone!@#$%',  # Special chars
                'iPhone 13 - Original',  # Valid with hyphen
                'iphone 13 pro',  # Lowercase (should be transformed)
                '   iPhone 13   ',  # Leading/trailing spaces
                'IPHONE 13 PRO MAX SUPER LONG TITLE WITH MANY WORDS',  # All caps
            ],
            'price': [999.99] * 10,
            'category': ['Celulares'] * 10
        })
        
        # Define rules focused on title validation
        rules_content = {
            "schema_version": "1.0.0",
            "marketplace": "mercado_livre",
            "version": "2.1.0",
            "rules": [
                {
                    "id": "ml_title_required",
                    "field": "title",
                    "type": "assert",
                    "precedence": 100,
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Título é obrigatório",
                    "severity": "error"
                },
                {
                    "id": "ml_title_min_length",
                    "field": "title",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {"operator": "length_gt", "value": 5},
                    "action": {"type": "assert"},
                    "message": "Título deve ter mais de 5 caracteres",
                    "severity": "error"
                },
                {
                    "id": "ml_title_max_length",
                    "field": "title",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {"operator": "length_lt", "value": 120},
                    "action": {"type": "assert"},
                    "message": "Título deve ter menos de 120 caracteres",
                    "severity": "error"
                },
                {
                    "id": "ml_title_case_transform",
                    "field": "title",
                    "type": "transform",
                    "precedence": 300,
                    "condition": {"operator": "not_empty"},
                    "action": {
                        "type": "transform",
                        "operation": "title_case",
                        "params": {"preserve_acronyms": True}
                    },
                    "message": "Aplicar formatação de título"
                },
                {
                    "id": "ml_title_trim_spaces",
                    "field": "title",
                    "type": "transform",
                    "precedence": 150,
                    "condition": {"operator": "not_empty"},
                    "action": {
                        "type": "transform",
                        "operation": "trim"
                    },
                    "message": "Remover espaços desnecessários"
                }
            ]
        }
        
        # Execute test
        self._execute_golden_test(
            fixture_name,
            test_data,
            rules_content,
            compiler,
            engine,
            golden_helper,
            input_fixtures_path,
            expected_fixtures_path,
            rules_fixtures_path,
            request
        )
    
    def test_mercado_livre_price_validation__with_various_prices__validates_correctly(
        self,
        compiler,
        engine,
        golden_helper: GoldenTestHelper,
        input_fixtures_path: Path,
        expected_fixtures_path: Path,
        rules_fixtures_path: Path,
        request
    ):
        """Test price validation and formatting rules."""
        fixture_name = "mercado_livre_price_validation"
        
        # Define test data with various price scenarios
        test_data = pd.DataFrame({
            'title': ['Produto Teste'] * 12,
            'price': [
                '99.99',      # Valid string
                99.99,        # Valid float
                '0',          # Zero (invalid)
                '-10.50',     # Negative (invalid)
                '',           # Empty (invalid)
                None,         # None (invalid)
                '1.234,56',   # Brazilian format (needs transformation)
                'R$ 150,00',  # With currency symbol
                '999999.99',  # Very high (warning)
                '0.01',       # Very low (edge case)
                'abc',        # Non-numeric (invalid)
                '1.50.99',    # Invalid decimal format
            ],
            'category': ['Geral'] * 12
        })
        
        # Define price-focused rules
        rules_content = {
            "schema_version": "1.0.0",
            "marketplace": "mercado_livre",
            "version": "2.1.0",
            "rules": [
                {
                    "id": "ml_price_required",
                    "field": "price",
                    "type": "assert",
                    "precedence": 100,
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Preço é obrigatório",
                    "severity": "error"
                },
                {
                    "id": "ml_price_is_number",
                    "field": "price",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {"operator": "is_number"},
                    "action": {"type": "assert"},
                    "message": "Preço deve ser um número válido",
                    "severity": "error"
                },
                {
                    "id": "ml_price_positive",
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
                    "message": "Preço deve ser maior que zero",
                    "severity": "error"
                },
                {
                    "id": "ml_price_high_warning",
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
                    "message": "Preço muito alto - verificar se está correto",
                    "severity": "warning"
                },
                {
                    "id": "ml_price_format_cleanup",
                    "field": "price",
                    "type": "transform",
                    "precedence": 150,
                    "condition": {"operator": "not_empty"},
                    "action": {
                        "type": "transform",
                        "operation": "clean_price",
                        "params": {
                            "remove_currency_symbols": True,
                            "convert_decimal_comma": True
                        }
                    },
                    "message": "Limpar formatação do preço"
                },
                {
                    "id": "ml_price_format_final",
                    "field": "price",
                    "type": "transform",
                    "precedence": 500,
                    "condition": {"operator": "is_number"},
                    "action": {
                        "type": "transform",
                        "operation": "format",
                        "value": "{:.2f}",
                        "params": {"decimal_places": 2}
                    },
                    "message": "Formatar preço com 2 casas decimais"
                }
            ]
        }
        
        # Execute test
        self._execute_golden_test(
            fixture_name,
            test_data,
            rules_content,
            compiler,
            engine,
            golden_helper,
            input_fixtures_path,
            expected_fixtures_path,
            rules_fixtures_path,
            request
        )
    
    def test_mercado_livre_category_suggestions__with_missing_categories__suggests_correctly(
        self,
        compiler,
        engine,
        golden_helper: GoldenTestHelper,
        input_fixtures_path: Path,
        expected_fixtures_path: Path,
        rules_fixtures_path: Path,
        request
    ):
        """Test category suggestion rules based on title/description context."""
        fixture_name = "mercado_livre_category_suggestions"
        
        # Define test data with titles that should trigger category suggestions
        test_data = pd.DataFrame({
            'title': [
                'iPhone 13 Pro 128GB Azul',
                'Notebook Dell Inspiron 15',
                'Camiseta Nike Dri-FIT',
                'Livro Dom Casmurro Machado de Assis',
                'Panela de Pressão Tramontina 4.5L',
                'Produto sem contexto específico',
                'Tênis Adidas Ultraboost 22',
                'Smart TV Samsung 55"',
            ],
            'price': [1299.99, 2499.99, 89.90, 29.90, 159.90, 49.90, 599.99, 2899.99],
            'category': [
                '',          # Empty - should suggest "Celulares"
                '',          # Empty - should suggest "Informática"  
                '',          # Empty - should suggest "Roupas"
                '',          # Empty - should suggest "Livros"
                '',          # Empty - should suggest "Casa e Jardim"
                '',          # Empty - no clear suggestion
                'Calçados',  # Already has category - no suggestion
                '',          # Empty - should suggest "Eletrônicos"
            ]
        })
        
        # Define category suggestion rules
        rules_content = {
            "schema_version": "1.0.0",
            "marketplace": "mercado_livre",
            "version": "2.1.0",
            "rules": [
                {
                    "id": "ml_suggest_celulares",
                    "field": "category",
                    "type": "suggest",
                    "precedence": 100,
                    "condition": {
                        "and": [
                            {"field": "category", "operator": "empty"},
                            {
                                "field": "title",
                                "operator": "matches",
                                "value": r"(?i)(iphone|samsung|motorola|xiaomi|celular|smartphone)"
                            }
                        ]
                    },
                    "action": {
                        "type": "suggest",
                        "suggestions": ["Celulares e Telefones", "Celulares"],
                        "confidence": 0.9
                    },
                    "message": "Categoria sugerida baseada no título"
                },
                {
                    "id": "ml_suggest_informatica",
                    "field": "category",
                    "type": "suggest",
                    "precedence": 100,
                    "condition": {
                        "and": [
                            {"field": "category", "operator": "empty"},
                            {
                                "field": "title",
                                "operator": "matches",
                                "value": r"(?i)(notebook|laptop|computador|pc|dell|hp|lenovo)"
                            }
                        ]
                    },
                    "action": {
                        "type": "suggest",
                        "suggestions": ["Informática", "Computação"],
                        "confidence": 0.85
                    },
                    "message": "Categoria sugerida para produtos de informática"
                },
                {
                    "id": "ml_suggest_roupas",
                    "field": "category",
                    "type": "suggest", 
                    "precedence": 100,
                    "condition": {
                        "and": [
                            {"field": "category", "operator": "empty"},
                            {
                                "field": "title",
                                "operator": "matches",
                                "value": r"(?i)(camiseta|blusa|calça|short|vestido|nike|adidas)"
                            }
                        ]
                    },
                    "action": {
                        "type": "suggest",
                        "suggestions": ["Roupas e Acessórios", "Moda"],
                        "confidence": 0.80
                    },
                    "message": "Categoria sugerida para roupas"
                },
                {
                    "id": "ml_suggest_livros",
                    "field": "category", 
                    "type": "suggest",
                    "precedence": 100,
                    "condition": {
                        "and": [
                            {"field": "category", "operator": "empty"},
                            {
                                "field": "title",
                                "operator": "matches",
                                "value": r"(?i)(livro|revista|manual|guia|romance|biografia)"
                            }
                        ]
                    },
                    "action": {
                        "type": "suggest",
                        "suggestions": ["Livros e Revistas", "Literatura"],
                        "confidence": 0.95
                    },
                    "message": "Categoria sugerida para livros"
                },
                {
                    "id": "ml_suggest_casa_jardim",
                    "field": "category",
                    "type": "suggest",
                    "precedence": 100,
                    "condition": {
                        "and": [
                            {"field": "category", "operator": "empty"},
                            {
                                "field": "title",
                                "operator": "matches",
                                "value": r"(?i)(panela|frigideira|tramontina|casa|cozinha|utensilio)"
                            }
                        ]
                    },
                    "action": {
                        "type": "suggest",
                        "suggestions": ["Casa, Móveis e Decoração", "Utilidades Domésticas"],
                        "confidence": 0.80
                    },
                    "message": "Categoria sugerida para casa e jardim"
                },
                {
                    "id": "ml_suggest_calcados",
                    "field": "category",
                    "type": "suggest",
                    "precedence": 100,
                    "condition": {
                        "and": [
                            {"field": "category", "operator": "empty"},
                            {
                                "field": "title",
                                "operator": "matches",
                                "value": r"(?i)(tenis|sapato|sandalia|bota|chinelo|nike|adidas|converse)"
                            }
                        ]
                    },
                    "action": {
                        "type": "suggest",
                        "suggestions": ["Calçados", "Tênis"],
                        "confidence": 0.85
                    },
                    "message": "Categoria sugerida para calçados"
                },
                {
                    "id": "ml_suggest_eletronicos",
                    "field": "category",
                    "type": "suggest",
                    "precedence": 100,
                    "condition": {
                        "and": [
                            {"field": "category", "operator": "empty"},
                            {
                                "field": "title",
                                "operator": "matches",
                                "value": r"(?i)(tv|televisao|smart tv|samsung|lg|sony)"
                            }
                        ]
                    },
                    "action": {
                        "type": "suggest",
                        "suggestions": ["Eletrônicos", "TV e Audio"],
                        "confidence": 0.90
                    },
                    "message": "Categoria sugerida para eletrônicos"
                }
            ]
        }
        
        # Execute test
        self._execute_golden_test(
            fixture_name,
            test_data,
            rules_content,
            compiler,
            engine,
            golden_helper,
            input_fixtures_path,
            expected_fixtures_path,
            rules_fixtures_path,
            request
        )
    
    def test_mercado_livre_comprehensive__with_realistic_products__validates_end_to_end(
        self,
        compiler,
        engine,
        golden_helper: GoldenTestHelper,
        input_fixtures_path: Path,
        expected_fixtures_path: Path,
        rules_fixtures_path: Path,
        request
    ):
        """Comprehensive end-to-end test with realistic ML product data."""
        fixture_name = "mercado_livre_comprehensive"
        
        # Define realistic product data with common issues
        test_data = pd.DataFrame({
            'title': [
                'iPhone 13 Pro 128GB Azul Sierra Original',
                'TV Samsung 55" 4K Smart QLED',
                '',  # Missing title
                'Camiseta',  # Too short
                'Notebook Dell i7 16GB SSD 512GB',
                'LIVRO DOM CASMURRO - MACHADO DE ASSIS',
                'Tênis Nike Air Max 90 Masculino Preto',
                '   Produto com espaços   ',
                'A' * 150,  # Too long
                'Produto Normal Teste'
            ],
            'price': [
                '1299,99',    # Brazilian format
                2899.50,      # Float
                '',           # Missing price  
                '0',          # Zero price
                'R$ 2.499,00', # With currency
                29.90,        # Valid
                '-199.99',    # Negative
                '599,99',     # Brazilian format
                '99999,99',   # Very high
                49.90         # Valid
            ],
            'category': [
                'Celulares',          # Valid
                '',                   # Missing - should suggest
                'Eletrônicos',        # Valid  
                '',                   # Missing - should suggest
                'Informática',        # Valid
                '',                   # Missing - should suggest  
                '',                   # Missing - should suggest
                'Geral',              # Valid
                'Casa e Jardim',      # Valid
                ''                    # Missing - no clear suggestion
            ],
            'description': [
                'iPhone 13 Pro com 128GB de armazenamento, cor Azul Sierra, novo e lacrado.',
                'Smart TV Samsung QLED 55 polegadas com resolução 4K.',
                '',
                'Camiseta básica.',
                'Notebook Dell com processador Intel Core i7, 16GB RAM e SSD 512GB.',
                'Livro clássico da literatura brasileira de Machado de Assis.',
                'Tênis Nike Air Max 90 na cor preta, tamanho 42.',
                'Descrição do produto com espaços extras.',
                'Descrição muito longa que pode causar problemas de validação em alguns marketplaces.',
                'Produto de teste com descrição normal.'
            ]
        })
        
        # Comprehensive rules combining all validations
        rules_content = {
            "schema_version": "1.0.0",
            "marketplace": "mercado_livre",
            "version": "2.1.0",
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
                # Title validations
                {
                    "id": "ml_title_required",
                    "field": "title",
                    "type": "assert",
                    "precedence": 100,
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Título é obrigatório",
                    "severity": "error"
                },
                {
                    "id": "ml_title_length",
                    "field": "title", 
                    "type": "assert",
                    "precedence": 200,
                    "condition": {
                        "and": [
                            {"operator": "length_gt", "value": 5},
                            {"operator": "length_lt", "value": 120}
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "Título deve ter entre 5 e 120 caracteres",
                    "severity": "error"
                },
                # Price validations
                {
                    "id": "ml_price_required",
                    "field": "price",
                    "type": "assert",
                    "precedence": 100,
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Preço é obrigatório",
                    "severity": "error"
                },
                {
                    "id": "ml_price_positive",
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
                    "message": "Preço deve ser maior que zero",
                    "severity": "error"
                },
                # Category suggestions
                {
                    "id": "ml_suggest_electronics",
                    "field": "category",
                    "type": "suggest",
                    "precedence": 400,
                    "condition": {
                        "and": [
                            {"field": "category", "operator": "empty"},
                            {
                                "field": "title",
                                "operator": "matches", 
                                "value": r"(?i)(tv|samsung|smart|qled)"
                            }
                        ]
                    },
                    "action": {
                        "type": "suggest",
                        "suggestions": ["Eletrônicos", "TV e Audio"],
                        "confidence": 0.90
                    },
                    "message": "Categoria sugerida para eletrônicos"
                }
            ],
            "compatibility": {
                "auto_apply_patch": True,
                "shadow_period_days": 30
            }
        }
        
        # Execute test
        self._execute_golden_test(
            fixture_name,
            test_data,
            rules_content,
            compiler,
            engine,
            golden_helper,
            input_fixtures_path,
            expected_fixtures_path,
            rules_fixtures_path,
            request
        )
    
    def _execute_golden_test(
        self,
        fixture_name: str,
        test_data: pd.DataFrame,
        rules_content: Dict[str, Any],
        compiler,
        engine,
        golden_helper: GoldenTestHelper,
        input_fixtures_path: Path,
        expected_fixtures_path: Path,
        rules_fixtures_path: Path,
        request
    ):
        """Execute a golden test with consistent pattern."""
        # Define fixture paths
        csv_path = input_fixtures_path / f"{fixture_name}.csv"
        yaml_path = rules_fixtures_path / f"{fixture_name}.yaml"
        json_path = expected_fixtures_path / f"{fixture_name}.json"
        
        # Save test data if updating or doesn't exist
        if request.config.getoption("--update-golden") or not csv_path.exists():
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            test_data.to_csv(csv_path, index=False)
        
        # Save rules if updating or doesn't exist  
        if request.config.getoption("--update-golden") or not yaml_path.exists():
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            import yaml
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(rules_content, f, default_flow_style=False, allow_unicode=True)
        
        # Execute rules
        compiled_rules = compiler.compile_yaml(rules_content)
        execution_result = engine.execute_rules(compiled_rules, test_data)
        actual_results = golden_helper.normalize_execution_result(execution_result)
        
        # Update or compare results
        if request.config.getoption("--update-golden"):
            golden_helper.save_results_as_fixture(actual_results, json_path)
            pytest.skip("Updated golden fixture - run again to test")
        
        # Load expected results and compare
        if not json_path.exists():
            pytest.skip("Golden fixture doesn't exist - run with --update-golden first")
        
        expected_results = golden_helper.load_expected_results(json_path)
        differences = golden_helper.compare_results(actual_results, expected_results)
        
        assert not differences, f"Results differ from golden fixture:\n" + "\n".join(differences)