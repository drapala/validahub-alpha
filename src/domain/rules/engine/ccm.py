"""
Canonical CSV Model (CCM) - Modelo de dados padronizado para marketplaces.

Este módulo define o modelo canônico para dados de produtos em marketplaces,
fornecendo uma interface consistente independente da plataforma de origem.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple
from urllib.parse import urlparse
import re
import pandas as pd

logger = logging.getLogger(__name__)


class CCMFieldType(Enum):
    """Tipos de campos do CCM."""
    
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    URL = "url"
    DATE = "date"
    CURRENCY = "currency"


class ValidationSeverity(Enum):
    """Severidade de validação CCM."""
    
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class CCMField:
    """Definição de campo do CCM."""
    
    name: str
    type: CCMFieldType
    required: bool = False
    max_length: Optional[int] = None
    min_length: Optional[int] = None
    pattern: Optional[str] = None
    allowed_values: Optional[List[str]] = None
    description: str = ""
    
    def __post_init__(self):
        """Validação da definição do campo."""
        if self.pattern:
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"Pattern inválido para campo {self.name}: {e}")


@dataclass
class CCMValidationResult:
    """Resultado de validação CCM."""
    
    field: str
    is_valid: bool
    severity: ValidationSeverity = ValidationSeverity.ERROR
    message: str = ""
    suggestion: Optional[str] = None
    original_value: Any = None
    normalized_value: Any = None


class CanonicalCSVModel:
    """
    Modelo Canônico CSV para dados de produtos em marketplaces.
    
    Define campos padronizados que todos os marketplaces devem mapear,
    fornecendo validação, normalização e transformação de dados.
    """
    
    # Definição dos campos CCM padrão
    FIELDS = {
        # Identificação básica
        'sku': CCMField(
            name='sku',
            type=CCMFieldType.STRING,
            required=True,
            max_length=100,
            pattern=r'^[A-Za-z0-9\-_\.]+$',
            description='Stock Keeping Unit - Identificador único do produto'
        ),
        'title': CCMField(
            name='title',
            type=CCMFieldType.STRING,
            required=True,
            max_length=200,
            min_length=10,
            description='Título/nome do produto'
        ),
        'description': CCMField(
            name='description', 
            type=CCMFieldType.STRING,
            required=False,
            max_length=5000,
            min_length=20,
            description='Descrição detalhada do produto'
        ),
        
        # Marca e categorização
        'brand': CCMField(
            name='brand',
            type=CCMFieldType.STRING,
            required=False,
            max_length=100,
            description='Marca do produto'
        ),
        'category_path': CCMField(
            name='category_path',
            type=CCMFieldType.STRING,
            required=False,
            max_length=500,
            description='Caminho da categoria (ex: Eletrônicos > Smartphones > iPhone)'
        ),
        
        # Códigos de identificação
        'gtin': CCMField(
            name='gtin',
            type=CCMFieldType.STRING,
            required=False,
            pattern=r'^(\d{8}|\d{12}|\d{13}|\d{14})$',
            description='Global Trade Item Number (EAN, UPC, etc.)'
        ),
        'ncm': CCMField(
            name='ncm',
            type=CCMFieldType.STRING,
            required=False,
            pattern=r'^\d{4}\.\d{2}\.\d{2}$',
            description='Nomenclatura Comum do Mercosul (formato: XXXX.XX.XX)'
        ),
        
        # Preço e moeda
        'price_brl': CCMField(
            name='price_brl',
            type=CCMFieldType.DECIMAL,
            required=True,
            description='Preço em Reais Brasileiros'
        ),
        'currency': CCMField(
            name='currency',
            type=CCMFieldType.STRING,
            required=False,
            allowed_values=['BRL', 'USD', 'EUR'],
            description='Código da moeda (ISO 4217)'
        ),
        
        # Estoque
        'stock': CCMField(
            name='stock',
            type=CCMFieldType.INTEGER,
            required=False,
            description='Quantidade em estoque'
        ),
        
        # Dimensões físicas
        'weight_kg': CCMField(
            name='weight_kg',
            type=CCMFieldType.DECIMAL,
            required=False,
            description='Peso em quilogramas'
        ),
        'length_cm': CCMField(
            name='length_cm',
            type=CCMFieldType.DECIMAL,
            required=False,
            description='Comprimento em centímetros'
        ),
        'width_cm': CCMField(
            name='width_cm',
            type=CCMFieldType.DECIMAL,
            required=False,
            description='Largura em centímetros'
        ),
        'height_cm': CCMField(
            name='height_cm',
            type=CCMFieldType.DECIMAL,
            required=False,
            description='Altura em centímetros'
        ),
        
        # Multimídia e atributos
        'images': CCMField(
            name='images',
            type=CCMFieldType.ARRAY,
            required=False,
            description='Lista de URLs das imagens do produto'
        ),
        'attributes': CCMField(
            name='attributes',
            type=CCMFieldType.OBJECT,
            required=False,
            description='Atributos específicos do produto (JSON)'
        )
    }
    
    def __init__(self):
        """Inicializa o modelo CCM."""
        self.validators = self._initialize_validators()
        self.normalizers = self._initialize_normalizers()
    
    def validate_record(self, record: Dict[str, Any]) -> List[CCMValidationResult]:
        """
        Valida um registro completo contra o modelo CCM.
        
        Args:
            record: Dicionário com dados do produto
            
        Returns:
            Lista de resultados de validação
        """
        results = []
        
        # Validar campos obrigatórios
        for field_name, field_def in self.FIELDS.items():
            if field_def.required and field_name not in record:
                results.append(CCMValidationResult(
                    field=field_name,
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Campo obrigatório '{field_name}' não encontrado",
                    original_value=None
                ))
                continue
            
            # Validar campo se presente
            if field_name in record:
                field_result = self.validate_field(field_name, record[field_name])
                results.append(field_result)
        
        # Validações cross-field
        cross_field_results = self._validate_cross_fields(record)
        results.extend(cross_field_results)
        
        return results
    
    def validate_field(self, field_name: str, value: Any) -> CCMValidationResult:
        """
        Valida um campo individual.
        
        Args:
            field_name: Nome do campo CCM
            value: Valor a ser validado
            
        Returns:
            Resultado da validação
        """
        if field_name not in self.FIELDS:
            return CCMValidationResult(
                field=field_name,
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message=f"Campo '{field_name}' não reconhecido no CCM",
                original_value=value
            )
        
        field_def = self.FIELDS[field_name]
        
        # Valor nulo/vazio
        if value is None or (isinstance(value, str) and value.strip() == ""):
            if field_def.required:
                return CCMValidationResult(
                    field=field_name,
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Campo obrigatório '{field_name}' está vazio",
                    original_value=value
                )
            else:
                return CCMValidationResult(
                    field=field_name,
                    is_valid=True,
                    original_value=value,
                    normalized_value=None
                )
        
        # Validação por tipo
        validator = self.validators.get(field_def.type)
        if validator:
            return validator(field_def, value)
        else:
            return CCMValidationResult(
                field=field_name,
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                message=f"Validador não implementado para tipo {field_def.type}",
                original_value=value,
                normalized_value=value
            )
    
    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza um registro completo aplicando transformações padrão.
        
        Args:
            record: Registro original
            
        Returns:
            Registro normalizado
        """
        normalized = {}
        
        for field_name, value in record.items():
            if field_name in self.FIELDS:
                field_def = self.FIELDS[field_name]
                normalizer = self.normalizers.get(field_def.type)
                
                if normalizer and value is not None:
                    try:
                        normalized[field_name] = normalizer(value)
                    except Exception as e:
                        logger.warning(f"Erro ao normalizar campo {field_name}: {e}")
                        normalized[field_name] = value
                else:
                    normalized[field_name] = value
            else:
                # Campo não reconhecido - manter como está
                normalized[field_name] = value
        
        return normalized
    
    def transform_from_marketplace(self, 
                                  data: pd.DataFrame, 
                                  marketplace_mapping: Dict[str, str]) -> pd.DataFrame:
        """
        Transforma dados de marketplace para formato CCM.
        
        Args:
            data: DataFrame com dados originais do marketplace
            marketplace_mapping: Mapeamento de campos marketplace -> CCM
            
        Returns:
            DataFrame transformado para CCM
        """
        # Criar DataFrame vazio com colunas CCM
        ccm_columns = list(self.FIELDS.keys())
        ccm_data = pd.DataFrame(columns=ccm_columns)
        
        # Mapear campos
        for ccm_field, marketplace_field in marketplace_mapping.items():
            if marketplace_field in data.columns and ccm_field in ccm_columns:
                ccm_data[ccm_field] = data[marketplace_field]
        
        # Normalizar dados
        for field_name in ccm_columns:
            if field_name in ccm_data.columns:
                ccm_data[field_name] = ccm_data[field_name].apply(
                    lambda x: self._normalize_field_value(field_name, x)
                )
        
        return ccm_data
    
    def _initialize_validators(self) -> Dict[CCMFieldType, callable]:
        """Inicializa validadores por tipo de campo."""
        return {
            CCMFieldType.STRING: self._validate_string,
            CCMFieldType.INTEGER: self._validate_integer,
            CCMFieldType.DECIMAL: self._validate_decimal,
            CCMFieldType.BOOLEAN: self._validate_boolean,
            CCMFieldType.ARRAY: self._validate_array,
            CCMFieldType.OBJECT: self._validate_object,
            CCMFieldType.URL: self._validate_url,
            CCMFieldType.DATE: self._validate_date,
            CCMFieldType.CURRENCY: self._validate_currency
        }
    
    def _initialize_normalizers(self) -> Dict[CCMFieldType, callable]:
        """Inicializa normalizadores por tipo de campo."""
        return {
            CCMFieldType.STRING: self._normalize_string,
            CCMFieldType.INTEGER: self._normalize_integer,
            CCMFieldType.DECIMAL: self._normalize_decimal,
            CCMFieldType.BOOLEAN: self._normalize_boolean,
            CCMFieldType.ARRAY: self._normalize_array,
            CCMFieldType.OBJECT: self._normalize_object,
            CCMFieldType.URL: self._normalize_url,
            CCMFieldType.DATE: self._normalize_date,
            CCMFieldType.CURRENCY: self._normalize_currency
        }
    
    def _validate_string(self, field_def: CCMField, value: Any) -> CCMValidationResult:
        """Valida campo string."""
        str_value = str(value).strip()
        
        # Verificar comprimento mínimo
        if field_def.min_length and len(str_value) < field_def.min_length:
            return CCMValidationResult(
                field=field_def.name,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Campo '{field_def.name}' muito curto (mín: {field_def.min_length})",
                original_value=value,
                suggestion=f"Forneça pelo menos {field_def.min_length} caracteres"
            )
        
        # Verificar comprimento máximo
        if field_def.max_length and len(str_value) > field_def.max_length:
            return CCMValidationResult(
                field=field_def.name,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Campo '{field_def.name}' muito longo (máx: {field_def.max_length})",
                original_value=value,
                suggestion=f"Limite a {field_def.max_length} caracteres"
            )
        
        # Verificar padrão regex
        if field_def.pattern and not re.match(field_def.pattern, str_value):
            return CCMValidationResult(
                field=field_def.name,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Campo '{field_def.name}' não atende ao padrão exigido",
                original_value=value,
                suggestion=f"Use o formato: {field_def.pattern}"
            )
        
        # Verificar valores permitidos
        if field_def.allowed_values and str_value not in field_def.allowed_values:
            return CCMValidationResult(
                field=field_def.name,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Valor '{str_value}' não permitido para campo '{field_def.name}'",
                original_value=value,
                suggestion=f"Use um dos valores: {', '.join(field_def.allowed_values)}"
            )
        
        return CCMValidationResult(
            field=field_def.name,
            is_valid=True,
            original_value=value,
            normalized_value=str_value
        )
    
    def _validate_integer(self, field_def: CCMField, value: Any) -> CCMValidationResult:
        """Valida campo inteiro."""
        try:
            if isinstance(value, str):
                # Remover separadores de milhares
                clean_value = value.replace(',', '').replace('.', '').strip()
                int_value = int(clean_value)
            else:
                int_value = int(value)
            
            # Validações específicas por campo
            if field_def.name == 'stock' and int_value < 0:
                return CCMValidationResult(
                    field=field_def.name,
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Estoque não pode ser negativo",
                    original_value=value,
                    suggestion="Use um valor maior ou igual a zero"
                )
            
            return CCMValidationResult(
                field=field_def.name,
                is_valid=True,
                original_value=value,
                normalized_value=int_value
            )
            
        except (ValueError, TypeError):
            return CCMValidationResult(
                field=field_def.name,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"'{value}' não é um número inteiro válido",
                original_value=value,
                suggestion="Use apenas dígitos (ex: 123)"
            )
    
    def _validate_decimal(self, field_def: CCMField, value: Any) -> CCMValidationResult:
        """Valida campo decimal."""
        try:
            if isinstance(value, str):
                # Normalizar separadores decimais
                clean_value = value.replace(',', '.').strip()
                # Remover separadores de milhares (assumindo formato BR: 1.234,56)
                if clean_value.count('.') > 1:
                    parts = clean_value.split('.')
                    clean_value = ''.join(parts[:-1]) + '.' + parts[-1]
                decimal_value = Decimal(clean_value)
            else:
                decimal_value = Decimal(str(value))
            
            # Validações específicas por campo
            if field_def.name == 'price_brl' and decimal_value <= 0:
                return CCMValidationResult(
                    field=field_def.name,
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Preço deve ser maior que zero",
                    original_value=value,
                    suggestion="Use um valor positivo (ex: 29.90)"
                )
            
            if field_def.name in ['weight_kg', 'length_cm', 'width_cm', 'height_cm'] and decimal_value < 0:
                return CCMValidationResult(
                    field=field_def.name,
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Dimensão {field_def.name} não pode ser negativa",
                    original_value=value,
                    suggestion="Use um valor positivo ou zero"
                )
            
            return CCMValidationResult(
                field=field_def.name,
                is_valid=True,
                original_value=value,
                normalized_value=float(decimal_value)
            )
            
        except (InvalidOperation, ValueError, TypeError):
            return CCMValidationResult(
                field=field_def.name,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"'{value}' não é um número decimal válido",
                original_value=value,
                suggestion="Use formato numérico (ex: 29.90)"
            )
    
    def _validate_boolean(self, field_def: CCMField, value: Any) -> CCMValidationResult:
        """Valida campo booleano."""
        if isinstance(value, bool):
            return CCMValidationResult(
                field=field_def.name,
                is_valid=True,
                original_value=value,
                normalized_value=value
            )
        
        if isinstance(value, str):
            str_value = value.lower().strip()
            if str_value in ['true', '1', 'yes', 'sim', 'verdadeiro']:
                return CCMValidationResult(
                    field=field_def.name,
                    is_valid=True,
                    original_value=value,
                    normalized_value=True
                )
            elif str_value in ['false', '0', 'no', 'não', 'falso']:
                return CCMValidationResult(
                    field=field_def.name,
                    is_valid=True,
                    original_value=value,
                    normalized_value=False
                )
        
        return CCMValidationResult(
            field=field_def.name,
            is_valid=False,
            severity=ValidationSeverity.ERROR,
            message=f"'{value}' não é um valor booleano válido",
            original_value=value,
            suggestion="Use: true/false, 1/0, sim/não"
        )
    
    def _validate_array(self, field_def: CCMField, value: Any) -> CCMValidationResult:
        """Valida campo array."""
        if isinstance(value, list):
            array_value = value
        elif isinstance(value, str):
            # Assumir formato separado por vírgula
            array_value = [item.strip() for item in value.split(',') if item.strip()]
        else:
            return CCMValidationResult(
                field=field_def.name,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"'{value}' não é um array válido",
                original_value=value,
                suggestion="Use formato: [item1, item2] ou 'item1, item2'"
            )
        
        # Validações específicas para campo images
        if field_def.name == 'images':
            invalid_urls = []
            for url in array_value:
                if not self._is_valid_url(url):
                    invalid_urls.append(url)
            
            if invalid_urls:
                return CCMValidationResult(
                    field=field_def.name,
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"URLs inválidas em images: {', '.join(invalid_urls[:3])}",
                    original_value=value,
                    suggestion="Use URLs completas iniciando com http:// ou https://"
                )
        
        return CCMValidationResult(
            field=field_def.name,
            is_valid=True,
            original_value=value,
            normalized_value=array_value
        )
    
    def _validate_object(self, field_def: CCMField, value: Any) -> CCMValidationResult:
        """Valida campo objeto."""
        if isinstance(value, dict):
            return CCMValidationResult(
                field=field_def.name,
                is_valid=True,
                original_value=value,
                normalized_value=value
            )
        elif isinstance(value, str):
            try:
                import json
                obj_value = json.loads(value)
                return CCMValidationResult(
                    field=field_def.name,
                    is_valid=True,
                    original_value=value,
                    normalized_value=obj_value
                )
            except json.JSONDecodeError:
                return CCMValidationResult(
                    field=field_def.name,
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"'{value}' não é um JSON válido",
                    original_value=value,
                    suggestion="Use formato JSON válido: {\"chave\": \"valor\"}"
                )
        
        return CCMValidationResult(
            field=field_def.name,
            is_valid=False,
            severity=ValidationSeverity.ERROR,
            message=f"'{value}' não é um objeto válido",
            original_value=value,
            suggestion="Use formato JSON: {\"chave\": \"valor\"}"
        )
    
    def _validate_url(self, field_def: CCMField, value: Any) -> CCMValidationResult:
        """Valida campo URL."""
        str_value = str(value).strip()
        
        if self._is_valid_url(str_value):
            return CCMValidationResult(
                field=field_def.name,
                is_valid=True,
                original_value=value,
                normalized_value=str_value
            )
        else:
            return CCMValidationResult(
                field=field_def.name,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"'{str_value}' não é uma URL válida",
                original_value=value,
                suggestion="Use formato: https://exemplo.com/imagem.jpg"
            )
    
    def _validate_date(self, field_def: CCMField, value: Any) -> CCMValidationResult:
        """Valida campo data."""
        try:
            import dateutil.parser as parser
            parsed_date = parser.parse(str(value))
            return CCMValidationResult(
                field=field_def.name,
                is_valid=True,
                original_value=value,
                normalized_value=parsed_date.isoformat()
            )
        except (ValueError, TypeError):
            return CCMValidationResult(
                field=field_def.name,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"'{value}' não é uma data válida",
                original_value=value,
                suggestion="Use formato: YYYY-MM-DD ou DD/MM/YYYY"
            )
    
    def _validate_currency(self, field_def: CCMField, value: Any) -> CCMValidationResult:
        """Valida campo moeda."""
        str_value = str(value).upper().strip()
        
        # Lista de códigos de moeda válidos (ISO 4217)
        valid_currencies = ['BRL', 'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF']
        
        if str_value in valid_currencies:
            return CCMValidationResult(
                field=field_def.name,
                is_valid=True,
                original_value=value,
                normalized_value=str_value
            )
        else:
            return CCMValidationResult(
                field=field_def.name,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Código de moeda '{str_value}' inválido",
                original_value=value,
                suggestion=f"Use um dos códigos: {', '.join(valid_currencies)}"
            )
    
    def _validate_cross_fields(self, record: Dict[str, Any]) -> List[CCMValidationResult]:
        """Valida relacionamentos entre campos."""
        results = []
        
        # Validar dimensões físicas consistentes
        dimensions = ['length_cm', 'width_cm', 'height_cm', 'weight_kg']
        has_any_dimension = any(field in record and record[field] for field in dimensions)
        has_all_dimensions = all(field in record and record[field] for field in dimensions[:3])
        
        if has_any_dimension and not has_all_dimensions:
            results.append(CCMValidationResult(
                field='dimensions',
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="Dimensões físicas incompletas - forneça comprimento, largura e altura",
                suggestion="Inclua todos os campos: length_cm, width_cm, height_cm"
            ))
        
        # Validar preço e moeda
        if 'price_brl' in record and 'currency' in record:
            if record['currency'] and record['currency'] != 'BRL':
                results.append(CCMValidationResult(
                    field='currency_mismatch',
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    message=f"Preço em BRL mas moeda definida como {record['currency']}",
                    suggestion="Use currency='BRL' ou ajuste o campo de preço"
                ))
        
        return results
    
    def _is_valid_url(self, url: str) -> bool:
        """Verifica se é uma URL válida."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
        except:
            return False
    
    def _normalize_field_value(self, field_name: str, value: Any) -> Any:
        """Normaliza valor individual de campo."""
        if field_name not in self.FIELDS or value is None:
            return value
        
        field_def = self.FIELDS[field_name]
        normalizer = self.normalizers.get(field_def.type)
        
        if normalizer:
            try:
                return normalizer(value)
            except:
                return value
        
        return value
    
    # Normalizadores por tipo
    def _normalize_string(self, value: Any) -> str:
        """Normaliza string."""
        return str(value).strip()
    
    def _normalize_integer(self, value: Any) -> int:
        """Normaliza inteiro."""
        if isinstance(value, str):
            clean_value = value.replace(',', '').replace('.', '').strip()
            return int(clean_value)
        return int(value)
    
    def _normalize_decimal(self, value: Any) -> float:
        """Normaliza decimal."""
        if isinstance(value, str):
            clean_value = value.replace(',', '.').strip()
            if clean_value.count('.') > 1:
                parts = clean_value.split('.')
                clean_value = ''.join(parts[:-1]) + '.' + parts[-1]
            return float(Decimal(clean_value))
        return float(value)
    
    def _normalize_boolean(self, value: Any) -> bool:
        """Normaliza booleano."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower().strip() in ['true', '1', 'yes', 'sim', 'verdadeiro']
        return bool(value)
    
    def _normalize_array(self, value: Any) -> List:
        """Normaliza array."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(',') if item.strip()]
        return [value]
    
    def _normalize_object(self, value: Any) -> dict:
        """Normaliza objeto."""
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            import json
            return json.loads(value)
        return {}
    
    def _normalize_url(self, value: Any) -> str:
        """Normaliza URL."""
        url = str(value).strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url
    
    def _normalize_date(self, value: Any) -> str:
        """Normaliza data."""
        import dateutil.parser as parser
        parsed_date = parser.parse(str(value))
        return parsed_date.isoformat()
    
    def _normalize_currency(self, value: Any) -> str:
        """Normaliza moeda."""
        return str(value).upper().strip()


# Instância singleton do modelo CCM
CCM = CanonicalCSVModel()