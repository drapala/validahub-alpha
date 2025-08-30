"""
Golden tests for Amazon marketplace rules.

Tests Amazon-specific validation requirements including UPC codes,
brand restrictions, and category mapping requirements.
"""

import pytest
import pandas as pd
from pathlib import Path
from typing import Dict, Any

from tests.golden.conftest import GoldenTestHelper


@pytest.mark.golden
class TestAmazonGolden:
    """Golden tests for Amazon marketplace rules."""
    
    @pytest.fixture
    def marketplace_name(self) -> str:
        """Marketplace identifier."""
        return "amazon"
    
    def test_amazon_upc_validation__with_various_upc_codes__validates_correctly(
        self,
        compiler,
        engine,
        golden_helper: GoldenTestHelper,
        input_fixtures_path: Path,
        expected_fixtures_path: Path,
        rules_fixtures_path: Path,
        request
    ):
        """Test UPC code validation specific to Amazon requirements."""
        fixture_name = "amazon_upc_validation"
        
        # Define test data with various UPC scenarios
        test_data = pd.DataFrame({
            'title': ['Test Product'] * 12,
            'price': [19.99] * 12,
            'category': ['Electronics'] * 12,
            'brand': ['TestBrand'] * 12,
            'upc': [
                '012345678905',      # Valid UPC-A (12 digits)
                '123456789012',      # Valid UPC-A
                '12345678901',       # Invalid (11 digits)
                '1234567890123',     # Invalid (13 digits)
                '012345678906',      # Invalid check digit
                '',                  # Empty (invalid for most categories)
                None,                # None (invalid)
                'ABC123456789',      # Contains letters
                '012-345-678-905',   # With dashes (needs cleaning)
                ' 012345678905 ',    # With spaces (needs trimming)
                '0123456789',        # Too short
                'EXEMPT',            # Amazon exemption keyword
            ]
        })
        
        # Amazon UPC validation rules
        rules_content = {
            "schema_version": "1.0.0",
            "marketplace": "amazon", 
            "version": "3.0.0",
            "rules": [
                {
                    "id": "amazon_upc_required",
                    "field": "upc",
                    "type": "assert",
                    "precedence": 100,
                    "condition": {
                        "or": [
                            {"operator": "not_empty"},
                            {"operator": "eq", "value": "EXEMPT"}
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "UPC is required for Amazon listings (or EXEMPT)",
                    "severity": "error"
                },
                {
                    "id": "amazon_upc_format",
                    "field": "upc",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {
                        "or": [
                            {"operator": "eq", "value": "EXEMPT"},
                            {"operator": "matches", "value": r"^\d{12}$"}
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "UPC must be 12 digits or EXEMPT",
                    "severity": "error"
                },
                {
                    "id": "amazon_upc_checksum",
                    "field": "upc",
                    "type": "assert",
                    "precedence": 300,
                    "condition": {
                        "or": [
                            {"operator": "eq", "value": "EXEMPT"},
                            {"operator": "matches", "value": "^(?!012345678906).*$"}  # Simple invalid checksum example
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "UPC checksum validation failed",
                    "severity": "error"
                },
                {
                    "id": "amazon_upc_cleanup",
                    "field": "upc",
                    "type": "transform",
                    "precedence": 150,
                    "condition": {"operator": "not_empty"},
                    "action": {
                        "type": "transform",
                        "operation": "clean_upc",
                        "params": {
                            "remove_dashes": True,
                            "trim_spaces": True,
                            "uppercase": True
                        }
                    },
                    "message": "Clean UPC format"
                }
            ]
        }
        
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
    
    def test_amazon_brand_restrictions__with_various_brands__validates_correctly(
        self,
        compiler,
        engine,
        golden_helper: GoldenTestHelper,
        input_fixtures_path: Path,
        expected_fixtures_path: Path,
        rules_fixtures_path: Path,
        request
    ):
        """Test Amazon brand restrictions and gating requirements."""
        fixture_name = "amazon_brand_restrictions"
        
        # Test data with restricted and unrestricted brands
        test_data = pd.DataFrame({
            'title': [
                'Apple iPhone 13 Pro',
                'Nike Air Max 90',
                'Sony WH-1000XM4 Headphones', 
                'Generic Brand Product',
                'No Brand Product',
                'Samsung Galaxy S22',
                'Louis Vuitton Handbag',
                'Unknown Brand Item',
                'Disney Mickey Mouse Shirt',
                'TestBrand Product'
            ],
            'price': [999.99, 129.99, 299.99, 29.99, 19.99, 899.99, 2999.99, 39.99, 24.99, 49.99],
            'category': ['Electronics'] * 10,
            'upc': ['123456789012'] * 10,
            'brand': [
                'Apple',           # Restricted - requires authorization
                'Nike',            # Restricted - requires authorization
                'Sony',            # May require authorization
                'Generic',         # Generic brand - allowed
                '',                # Missing brand
                'Samsung',         # Electronics brand - may require gating
                'Louis Vuitton',   # Luxury brand - highly restricted
                'UnknownBrand',    # Unknown brand
                'Disney',          # Licensed brand - requires authorization
                'TestBrand'        # Test brand
            ]
        })
        
        # Amazon brand restriction rules
        rules_content = {
            "schema_version": "1.0.0",
            "marketplace": "amazon",
            "version": "3.0.0",
            "rules": [
                {
                    "id": "amazon_brand_required",
                    "field": "brand",
                    "type": "assert",
                    "precedence": 100,
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Brand is required for Amazon listings",
                    "severity": "error"
                },
                {
                    "id": "amazon_apple_restriction",
                    "field": "brand",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {
                        "not": {"operator": "eq", "value": "Apple", "case_sensitive": False}
                    },
                    "action": {"type": "assert"},
                    "message": "Apple brand requires authorization - contact Amazon",
                    "severity": "error"
                },
                {
                    "id": "amazon_nike_restriction",
                    "field": "brand",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {
                        "not": {"operator": "eq", "value": "Nike", "case_sensitive": False}
                    },
                    "action": {"type": "assert"},
                    "message": "Nike brand requires authorization",
                    "severity": "error"
                },
                {
                    "id": "amazon_luxury_brand_warning",
                    "field": "brand",
                    "type": "assert",
                    "precedence": 300,
                    "condition": {
                        "not": {
                            "operator": "in",
                            "value": ["Louis Vuitton", "Gucci", "Chanel", "Hermès"],
                            "case_sensitive": False
                        }
                    },
                    "action": {"type": "assert"},
                    "message": "Luxury brands require special authorization and authentication",
                    "severity": "warning"
                },
                {
                    "id": "amazon_disney_licensing",
                    "field": "brand",
                    "type": "assert",
                    "precedence": 300,
                    "condition": {
                        "not": {"operator": "eq", "value": "Disney", "case_sensitive": False}
                    },
                    "action": {"type": "assert"},
                    "message": "Disney products require licensing verification",
                    "severity": "warning"
                },
                {
                    "id": "amazon_electronics_gating",
                    "field": "brand",
                    "type": "assert",
                    "precedence": 250,
                    "condition": {
                        "or": [
                            {"field": "category", "operator": "ne", "value": "Electronics"},
                            {
                                "not": {
                                    "operator": "in",
                                    "value": ["Samsung", "Sony", "LG"],
                                    "case_sensitive": False
                                }
                            }
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "Major electronics brands may require category approval",
                    "severity": "warning"
                }
            ]
        }
        
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
    
    def test_amazon_category_mapping__with_various_categories__maps_correctly(
        self,
        compiler,
        engine,
        golden_helper: GoldenTestHelper,
        input_fixtures_path: Path,
        expected_fixtures_path: Path,
        rules_fixtures_path: Path,
        request
    ):
        """Test Amazon category mapping and Browse Tree Guide compliance."""
        fixture_name = "amazon_category_mapping"
        
        # Test data with categories that need mapping/validation
        test_data = pd.DataFrame({
            'title': [
                'Wireless Bluetooth Headphones',
                'Cotton T-Shirt Medium',
                'Kitchen Knife Set',
                'Baby Formula 800g',
                'Organic Dog Food',
                'Vitamin D3 Supplement',
                'Romance Novel Paperback',
                'Invalid Category Product'
            ],
            'price': [79.99, 24.99, 89.99, 29.99, 34.99, 19.99, 12.99, 39.99],
            'brand': ['TestBrand'] * 8,
            'upc': ['123456789012'] * 8,
            'category': [
                'Electronics > Audio > Headphones',     # Valid path
                'Clothing',                             # Needs more specific mapping
                'Home & Kitchen',                       # Valid
                'Baby Products > Formula',              # Valid but restricted
                'Pet Supplies > Dog > Food',            # Valid
                'Health & Personal Care',               # Needs more specific
                'Books > Fiction > Romance',            # Valid
                'Invalid Category'                      # Invalid category
            ]
        })
        
        # Amazon category validation rules
        rules_content = {
            "schema_version": "1.0.0",
            "marketplace": "amazon",
            "version": "3.0.0",
            "rules": [
                {
                    "id": "amazon_category_required",
                    "field": "category",
                    "type": "assert",
                    "precedence": 100,
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Category is required for Amazon listings",
                    "severity": "error"
                },
                {
                    "id": "amazon_valid_category_path",
                    "field": "category",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {
                        "or": [
                            {"operator": "startswith", "value": "Electronics"},
                            {"operator": "startswith", "value": "Clothing"},
                            {"operator": "startswith", "value": "Home & Kitchen"},
                            {"operator": "startswith", "value": "Baby Products"},
                            {"operator": "startswith", "value": "Pet Supplies"},
                            {"operator": "startswith", "value": "Health & Personal Care"},
                            {"operator": "startswith", "value": "Books"},
                            {"operator": "startswith", "value": "Sports & Outdoors"}
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "Category must be from Amazon's Browse Tree Guide",
                    "severity": "error"
                },
                {
                    "id": "amazon_baby_formula_restriction",
                    "field": "category",
                    "type": "assert",
                    "precedence": 300,
                    "condition": {
                        "not": {"operator": "contains", "value": "Formula"}
                    },
                    "action": {"type": "assert"},
                    "message": "Baby formula requires special approval and compliance",
                    "severity": "error"
                },
                {
                    "id": "amazon_health_supplement_warning",
                    "field": "category",
                    "type": "assert",
                    "precedence": 250,
                    "condition": {
                        "not": {"operator": "eq", "value": "Health & Personal Care"}
                    },
                    "action": {"type": "assert"},
                    "message": "Health products require more specific category path",
                    "severity": "warning"
                },
                {
                    "id": "amazon_clothing_specificity",
                    "field": "category",
                    "type": "suggest",
                    "precedence": 400,
                    "condition": {
                        "and": [
                            {"operator": "eq", "value": "Clothing"},
                            {"field": "title", "operator": "contains", "value": "T-Shirt", "case_sensitive": False}
                        ]
                    },
                    "action": {
                        "type": "suggest",
                        "suggestions": [
                            "Clothing, Shoes & Jewelry > Men > Clothing > Shirts > T-Shirts",
                            "Clothing, Shoes & Jewelry > Women > Clothing > Tops & Tees > T-Shirts"
                        ],
                        "confidence": 0.85
                    },
                    "message": "Consider more specific category path for better visibility"
                }
            ]
        }
        
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
    
    def test_amazon_title_optimization__with_various_titles__optimizes_correctly(
        self,
        compiler,
        engine,
        golden_helper: GoldenTestHelper,
        input_fixtures_path: Path,
        expected_fixtures_path: Path,
        rules_fixtures_path: Path,
        request
    ):
        """Test Amazon title optimization for search visibility."""
        fixture_name = "amazon_title_optimization"
        
        # Test data with titles needing Amazon optimization
        test_data = pd.DataFrame({
            'title': [
                'iPhone 13 Pro 128GB Azul',                           # Missing key attributes
                'WIRELESS BLUETOOTH HEADPHONES WITH NOISE CANCEL',    # All caps
                'Nike shoes',                                          # Too vague
                'Samsung Galaxy S22 Ultra 256GB 5G Smartphone Black', # Good title
                'Best headphones ever!!!',                            # Promotional language
                'iPhone - Original - New - Sealed - Fast Shipping',   # Too many dashes
                'Bluetooth Headphones, Wireless, Over Ear, 30Hr Battery', # Good with features
                'Product Title',                                       # Generic
                'MacBook Pro 13-inch M2 Chip 8GB RAM 256GB SSD',     # Needs brand
                'Amazing Product You Must Buy Now! Limited Time!'     # Promotional/spammy
            ],
            'price': [999.99, 79.99, 129.99, 1199.99, 59.99, 999.99, 89.99, 39.99, 1299.99, 29.99],
            'brand': ['Apple', 'Generic', 'Nike', 'Samsung', 'TestBrand', 'Apple', 'SoundBrand', 'TestBrand', 'Apple', 'TestBrand'],
            'category': ['Electronics'] * 10,
            'upc': ['123456789012'] * 10
        })
        
        # Amazon title optimization rules
        rules_content = {
            "schema_version": "1.0.0",
            "marketplace": "amazon",
            "version": "3.0.0",
            "rules": [
                {
                    "id": "amazon_title_length",
                    "field": "title",
                    "type": "assert",
                    "precedence": 100,
                    "condition": {
                        "and": [
                            {"operator": "length_gt", "value": 5},
                            {"operator": "length_lte", "value": 200}
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "Amazon title must be 5-200 characters",
                    "severity": "error"
                },
                {
                    "id": "amazon_no_promotional_language",
                    "field": "title",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {
                        "not": {
                            "operator": "matches",
                            "value": r"(?i)(best|amazing|must buy|limited time|sale|deal|free shipping|fastest)"
                        }
                    },
                    "action": {"type": "assert"},
                    "message": "Amazon titles cannot contain promotional language",
                    "severity": "error"
                },
                {
                    "id": "amazon_excessive_punctuation",
                    "field": "title",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {
                        "not": {
                            "operator": "matches",
                            "value": r"[!]{2,}|[?]{2,}|[\-]{3,}"
                        }
                    },
                    "action": {"type": "assert"},
                    "message": "Avoid excessive punctuation in Amazon titles",
                    "severity": "error"
                },
                {
                    "id": "amazon_all_caps_warning",
                    "field": "title",
                    "type": "assert",
                    "precedence": 300,
                    "condition": {
                        "not": {
                            "operator": "matches",
                            "value": r"^[A-Z\s\d\-,]+$"
                        }
                    },
                    "action": {"type": "assert"},
                    "message": "Avoid ALL CAPS in Amazon titles - use proper case",
                    "severity": "warning"
                },
                {
                    "id": "amazon_brand_in_title",
                    "field": "title",
                    "type": "assert",
                    "precedence": 250,
                    "condition": {
                        "or": [
                            {"field": "brand", "operator": "empty"},
                            {
                                "field": "title",
                                "operator": "contains",
                                "value": "{brand}",  # Placeholder for brand field reference
                                "case_sensitive": False
                            }
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "Consider including brand name in title for better searchability",
                    "severity": "warning"
                },
                {
                    "id": "amazon_title_case_transform",
                    "field": "title",
                    "type": "transform",
                    "precedence": 150,
                    "condition": {
                        "operator": "matches",
                        "value": r"^[A-Z\s\d\-,]+$"  # All caps
                    },
                    "action": {
                        "type": "transform",
                        "operation": "title_case",
                        "params": {
                            "preserve_brand_case": True,
                            "preserve_acronyms": True
                        }
                    },
                    "message": "Convert all caps to title case"
                },
                {
                    "id": "amazon_clean_excessive_dashes",
                    "field": "title",
                    "type": "transform",
                    "precedence": 160,
                    "condition": {
                        "operator": "matches",
                        "value": r"[\-]{3,}"
                    },
                    "action": {
                        "type": "transform",
                        "operation": "regex_replace",
                        "params": {
                            "pattern": r"[\-]{2,}",
                            "replacement": " - "
                        }
                    },
                    "message": "Clean up excessive dashes"
                }
            ]
        }
        
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
    
    def test_amazon_comprehensive__with_realistic_products__validates_end_to_end(
        self,
        compiler,
        engine,
        golden_helper: GoldenTestHelper,
        input_fixtures_path: Path,
        expected_fixtures_path: Path,
        rules_fixtures_path: Path,
        request
    ):
        """Comprehensive Amazon validation test with realistic product data."""
        fixture_name = "amazon_comprehensive"
        
        # Realistic Amazon product data with various validation scenarios
        test_data = pd.DataFrame({
            'title': [
                'Wireless Bluetooth Headphones with Active Noise Cancellation',
                'Samsung Galaxy S22 Ultra 256GB 5G Smartphone - Phantom Black',
                'Apple iPhone 13 Pro 128GB - Sierra Blue',
                'BEST DEAL EVER - Nike Air Max 90 Shoes!!!',
                'Organic Baby Formula - Stage 1',
                'Generic USB-C Cable 6ft',
                'Sony WH-1000XM4 Wireless Noise Canceling Headphones',
                ''  # Empty title
            ],
            'price': [89.99, 1199.99, 999.99, 129.99, 34.99, 12.99, 349.99, 19.99],
            'brand': ['AudioBrand', 'Samsung', 'Apple', 'Nike', 'BabyBrand', 'Generic', 'Sony', ''],
            'category': [
                'Electronics > Audio > Headphones',
                'Electronics > Cell Phones > Smartphones',
                'Electronics > Cell Phones > Smartphones', 
                'Invalid Category',
                'Baby Products > Formula',
                'Electronics > Cables',
                'Electronics > Audio > Headphones',
                'Electronics'
            ],
            'upc': [
                '123456789012',   # Valid
                '987654321098',   # Valid
                '',               # Missing (Apple requires UPC)
                '111111111111',   # Valid
                'EXEMPT',         # Exempt
                '123456789',      # Invalid length
                '456789012345',   # Valid
                '999999999999'    # Valid
            ],
            'description': [
                'High-quality wireless headphones with 30-hour battery life.',
                'Latest Samsung flagship with 108MP camera and S Pen.',
                'Apple iPhone with A15 Bionic chip and Pro camera system.',
                'Best Nike shoes with amazing comfort and style.',
                'Organic baby formula for infants 0-6 months.',
                'Durable USB-C cable for fast charging and data transfer.',
                'Sony premium headphones with industry-leading noise cancellation.',
                'No description provided.'
            ]
        })
        
        # Comprehensive Amazon rules combining all validations
        rules_content = {
            "schema_version": "1.0.0",
            "marketplace": "amazon",
            "version": "3.0.0",
            "ccm_mapping": {
                "title": {
                    "source": "title",
                    "required": True,
                    "transform": {"type": "trim"}
                },
                "brand": {
                    "source": "brand", 
                    "required": True
                },
                "upc": {
                    "source": "upc",
                    "required": True,
                    "transform": {"type": "clean_upc"}
                }
            },
            "rules": [
                # Basic required fields
                {
                    "id": "amazon_title_required",
                    "field": "title",
                    "type": "assert",
                    "precedence": 50,
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Title is required",
                    "severity": "error"
                },
                {
                    "id": "amazon_brand_required", 
                    "field": "brand",
                    "type": "assert",
                    "precedence": 50,
                    "condition": {"operator": "not_empty"},
                    "action": {"type": "assert"},
                    "message": "Brand is required",
                    "severity": "error"
                },
                # Title validations
                {
                    "id": "amazon_title_no_promotional",
                    "field": "title",
                    "type": "assert",
                    "precedence": 100,
                    "condition": {
                        "not": {
                            "operator": "matches",
                            "value": r"(?i)(best|deal|amazing|must buy|limited)"
                        }
                    },
                    "action": {"type": "assert"},
                    "message": "Promotional language not allowed in titles",
                    "severity": "error"
                },
                # Brand restrictions
                {
                    "id": "amazon_apple_restriction",
                    "field": "brand",
                    "type": "assert", 
                    "precedence": 200,
                    "condition": {
                        "not": {"operator": "eq", "value": "Apple"}
                    },
                    "action": {"type": "assert"},
                    "message": "Apple brand requires authorization",
                    "severity": "error"
                },
                {
                    "id": "amazon_nike_restriction",
                    "field": "brand",
                    "type": "assert",
                    "precedence": 200,
                    "condition": {
                        "not": {"operator": "eq", "value": "Nike"}
                    },
                    "action": {"type": "assert"},
                    "message": "Nike brand requires authorization", 
                    "severity": "error"
                },
                # UPC validations
                {
                    "id": "amazon_upc_required_for_apple",
                    "field": "upc",
                    "type": "assert",
                    "precedence": 300,
                    "condition": {
                        "or": [
                            {"field": "brand", "operator": "ne", "value": "Apple"},
                            {"operator": "not_empty"}
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "UPC required for Apple products",
                    "severity": "error"
                },
                {
                    "id": "amazon_valid_upc_format",
                    "field": "upc",
                    "type": "assert",
                    "precedence": 350,
                    "condition": {
                        "or": [
                            {"operator": "eq", "value": "EXEMPT"},
                            {"operator": "matches", "value": r"^\d{12}$"}
                        ]
                    },
                    "action": {"type": "assert"},
                    "message": "UPC must be 12 digits or EXEMPT",
                    "severity": "error"
                },
                # Category validations
                {
                    "id": "amazon_valid_category",
                    "field": "category",
                    "type": "assert",
                    "precedence": 250,
                    "condition": {
                        "operator": "matches",
                        "value": r"^(Electronics|Baby Products|Clothing)"
                    },
                    "action": {"type": "assert"},
                    "message": "Invalid Amazon category path",
                    "severity": "error"
                },
                {
                    "id": "amazon_baby_formula_restriction",
                    "field": "category",
                    "type": "assert",
                    "precedence": 400,
                    "condition": {
                        "not": {"operator": "contains", "value": "Formula"}
                    },
                    "action": {"type": "assert"},
                    "message": "Baby formula requires special approval",
                    "severity": "error"
                }
            ],
            "compatibility": {
                "auto_apply_patch": False,  # Amazon requires manual approval for rule changes
                "shadow_period_days": 60,
                "require_major_opt_in": True
            }
        }
        
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