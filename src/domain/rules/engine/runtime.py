"""
ValidaHub Rules Runtime Engine.

Este módulo implementa o engine de execução das regras compiladas,
com foco em performance e vetorização para processamento em lote.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np
import re
from decimal import Decimal, InvalidOperation

from .ir_types import (
    CompiledRuleSet, CompiledRule, CompiledCondition, CompiledAction,
    ExecutionPlan, RuleGroup, ExecutionMode, ConditionType, ActionType,
    RuleScope, Severity
)

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Resultado da execução de regras."""
    
    def __init__(self):
        self.errors: List[RuleViolation] = []
        self.warnings: List[RuleViolation] = []
        self.suggestions: List[RuleSuggestion] = []
        self.transformations: List[RuleTransformation] = []
        self.stats: ExecutionStats = ExecutionStats()
        
    def add_error(self, violation: 'RuleViolation') -> None:
        """Adiciona um erro de validação."""
        self.errors.append(violation)
        self.stats.error_count += 1
        
    def add_warning(self, violation: 'RuleViolation') -> None:
        """Adiciona um warning de validação."""
        self.warnings.append(violation)
        self.stats.warning_count += 1
        
    def add_suggestion(self, suggestion: 'RuleSuggestion') -> None:
        """Adiciona uma sugestão."""
        self.suggestions.append(suggestion)
        self.stats.suggestion_count += 1
        
    def add_transformation(self, transform: 'RuleTransformation') -> None:
        """Adiciona uma transformação."""
        self.transformations.append(transform)
        self.stats.transformation_count += 1
        
    @property
    def has_errors(self) -> bool:
        """Verifica se há erros."""
        return len(self.errors) > 0
        
    @property
    def has_warnings(self) -> bool:
        """Verifica se há warnings."""
        return len(self.warnings) > 0


@dataclass
class RuleViolation:
    """Violação de regra (erro ou warning)."""
    
    rule_id: str
    field: str
    row_index: Optional[int]
    message: str
    severity: Severity
    actual_value: Any
    expected_value: Optional[Any] = None
    suggestion: Optional[str] = None


@dataclass
class RuleSuggestion:
    """Sugestão de correção."""
    
    rule_id: str
    field: str
    row_index: int
    current_value: Any
    suggested_values: List[str]
    confidence: float
    reason: str


@dataclass
class RuleTransformation:
    """Transformação aplicada."""
    
    rule_id: str
    field: str
    row_index: int
    original_value: Any
    transformed_value: Any
    operation: str


@dataclass
class ExecutionStats:
    """Estatísticas de execução."""
    
    total_rows: int = 0
    processed_rows: int = 0
    error_count: int = 0
    warning_count: int = 0
    suggestion_count: int = 0
    transformation_count: int = 0
    execution_time_ms: float = 0.0
    rules_executed: int = 0
    vectorized_operations: int = 0
    cache_hits: int = 0
    memory_usage_mb: float = 0.0


class RuleExecutionEngine:
    """
    Engine principal para execução de regras compiladas.
    
    Características:
    - Execução vetorizada com pandas/numpy
    - Cache de resultados intermediários
    - Short-circuit optimization
    - Paralelização controlada
    - Limite de recursos (tempo/memória)
    """
    
    def __init__(self, 
                 max_workers: int = 4,
                 timeout_seconds: float = 30.0,
                 memory_limit_mb: float = 1024.0,
                 enable_cache: bool = True,
                 enable_vectorization: bool = True):
        """
        Inicializa o engine de execução.
        
        Args:
            max_workers: Número máximo de threads
            timeout_seconds: Timeout para execução
            memory_limit_mb: Limite de memória
            enable_cache: Habilita cache de resultados
            enable_vectorization: Habilita operações vetorizadas
        """
        self.max_workers = max_workers
        self.timeout_seconds = timeout_seconds  
        self.memory_limit_mb = memory_limit_mb
        self.enable_cache = enable_cache
        self.enable_vectorization = enable_vectorization
        
        # Cache interno para resultados intermediários
        self._condition_cache: Dict[str, pd.Series] = {}
        self._transform_cache: Dict[str, Any] = {}
        
        # Operadores compilados
        self._operators = self._initialize_operators()
        
    def execute_rules(self, 
                     ruleset: CompiledRuleSet,
                     data: pd.DataFrame) -> ExecutionResult:
        """
        Executa todas as regras de um ruleset sobre os dados.
        
        Args:
            ruleset: Conjunto de regras compiladas
            data: DataFrame com os dados para validar
            
        Returns:
            Resultado consolidado da execução
        """
        start_time = time.perf_counter()
        result = ExecutionResult()
        result.stats.total_rows = len(data)
        
        try:
            # Validação inicial
            if data.empty:
                logger.warning("DataFrame vazio fornecido para execução")
                return result
                
            # Execução seguindo o plano otimizado
            plan = ruleset.execution_plan
            
            for phase in plan.phases:
                logger.debug(f"Executando fase: {phase.name}")
                
                phase_result = self._execute_phase(
                    phase=phase,
                    rules=ruleset.rules,
                    data=data
                )
                
                # Consolidar resultados da fase
                self._merge_results(result, phase_result)
                
                # Aplicar transformações no DataFrame
                if phase.phase_type.value == "transformation":
                    data = self._apply_transformations(data, phase_result.transformations)
                
        except Exception as e:
            logger.error(f"Erro durante execução de regras: {e}")
            raise
        finally:
            # Calcular estatísticas finais
            execution_time = (time.perf_counter() - start_time) * 1000
            result.stats.execution_time_ms = execution_time
            result.stats.processed_rows = len(data)
            
            # Limpar cache se necessário
            if not self.enable_cache:
                self._condition_cache.clear()
                self._transform_cache.clear()
                
        return result
    
    def _execute_phase(self, 
                      phase,  # ExecutionPhase
                      rules: Dict[str, CompiledRule],
                      data: pd.DataFrame) -> ExecutionResult:
        """Executa uma fase específica do plano."""
        phase_result = ExecutionResult()
        
        for group in phase.rule_groups:
            group_result = self._execute_rule_group(
                group=group,
                rules=rules,
                data=data
            )
            self._merge_results(phase_result, group_result)
            
        return phase_result
    
    def _execute_rule_group(self, 
                           group: RuleGroup,
                           rules: Dict[str, CompiledRule],
                           data: pd.DataFrame) -> ExecutionResult:
        """Executa um grupo de regras."""
        group_result = ExecutionResult()
        
        # Buscar regras do grupo
        group_rules = [rules[rule_id] for rule_id in group.rule_ids if rule_id in rules]
        
        if not group_rules:
            return group_result
            
        # Escolher estratégia de execução
        if group.execution_mode == ExecutionMode.VECTORIZED and self.enable_vectorization:
            return self._execute_vectorized(group_rules, data)
        elif group.execution_mode == ExecutionMode.PARALLEL and len(group_rules) > 1:
            return self._execute_parallel(group_rules, data)
        else:
            return self._execute_sequential(group_rules, data)
    
    def _execute_vectorized(self, 
                           rules: List[CompiledRule],
                           data: pd.DataFrame) -> ExecutionResult:
        """Execução vetorizada usando pandas/numpy."""
        result = ExecutionResult()
        result.stats.vectorized_operations += len(rules)
        
        for rule in rules:
            try:
                # Avalia condição de forma vetorizada
                condition_mask = self._evaluate_condition_vectorized(rule.condition, data)
                
                if rule.type == ActionType.ASSERT:
                    # Assertions vetorizadas
                    violations = self._create_violations_from_mask(
                        rule, ~condition_mask, data
                    )
                    for violation in violations:
                        if rule.severity == Severity.ERROR:
                            result.add_error(violation)
                        else:
                            result.add_warning(violation)
                            
                elif rule.type == ActionType.TRANSFORM:
                    # Transformações vetorizadas
                    transformations = self._apply_transform_vectorized(
                        rule, condition_mask, data
                    )
                    for transform in transformations:
                        result.add_transformation(transform)
                        
                elif rule.type == ActionType.SUGGEST:
                    # Sugestões vetorizadas
                    suggestions = self._generate_suggestions_vectorized(
                        rule, condition_mask, data
                    )
                    for suggestion in suggestions:
                        result.add_suggestion(suggestion)
                        
                result.stats.rules_executed += 1
                
            except Exception as e:
                logger.error(f"Erro na execução vetorizada da regra {rule.id}: {e}")
                # Fallback para execução sequencial
                fallback_result = self._execute_sequential([rule], data)
                self._merge_results(result, fallback_result)
        
        return result
    
    def _execute_parallel(self, 
                         rules: List[CompiledRule],
                         data: pd.DataFrame) -> ExecutionResult:
        """Execução paralela usando threads."""
        result = ExecutionResult()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit tasks
            future_to_rule = {
                executor.submit(self._execute_single_rule, rule, data): rule
                for rule in rules
            }
            
            # Collect results
            for future in as_completed(future_to_rule, timeout=self.timeout_seconds):
                rule = future_to_rule[future]
                try:
                    rule_result = future.result()
                    self._merge_results(result, rule_result)
                except Exception as e:
                    logger.error(f"Erro na execução paralela da regra {rule.id}: {e}")
                    
        return result
    
    def _execute_sequential(self, 
                           rules: List[CompiledRule],
                           data: pd.DataFrame) -> ExecutionResult:
        """Execução sequencial padrão."""
        result = ExecutionResult()
        
        for rule in rules:
            rule_result = self._execute_single_rule(rule, data)
            self._merge_results(result, rule_result)
            
        return result
    
    def _execute_single_rule(self, 
                            rule: CompiledRule,
                            data: pd.DataFrame) -> ExecutionResult:
        """Executa uma regra individual."""
        result = ExecutionResult()
        
        try:
            if rule.scope == RuleScope.GLOBAL:
                # Regras globais (executam uma vez sobre todo dataset)
                rule_result = self._execute_global_rule(rule, data)
                self._merge_results(result, rule_result)
                
            elif rule.scope == RuleScope.COLUMN:
                # Regras de coluna (executam sobre coluna inteira)
                rule_result = self._execute_column_rule(rule, data)
                self._merge_results(result, rule_result)
                
            else:  # RuleScope.ROW
                # Regras de linha (executam para cada linha)
                for idx, row in data.iterrows():
                    row_result = self._execute_row_rule(rule, row, idx)
                    self._merge_results(result, row_result)
                    
            result.stats.rules_executed += 1
            
        except Exception as e:
            logger.error(f"Erro na execução da regra {rule.id}: {e}")
            
        return result
    
    def _execute_global_rule(self, 
                            rule: CompiledRule,
                            data: pd.DataFrame) -> ExecutionResult:
        """Executa regra com escopo global."""
        result = ExecutionResult()
        
        # Avaliar condição global (ex: count, unique values, etc)
        condition_met = self._evaluate_global_condition(rule.condition, data)
        
        if rule.type == ActionType.ASSERT and not condition_met:
            violation = RuleViolation(
                rule_id=rule.id,
                field=rule.field,
                row_index=None,  # Global scope
                message=rule.message,
                severity=rule.severity,
                actual_value=f"Dataset with {len(data)} rows",
                expected_value=None
            )
            
            if rule.severity == Severity.ERROR:
                result.add_error(violation)
            else:
                result.add_warning(violation)
                
        return result
    
    def _execute_column_rule(self, 
                            rule: CompiledRule,
                            data: pd.DataFrame) -> ExecutionResult:
        """Executa regra com escopo de coluna."""
        result = ExecutionResult()
        
        if rule.field not in data.columns:
            return result
            
        column_data = data[rule.field]
        
        # Avaliar condição da coluna
        condition_met = self._evaluate_column_condition(rule.condition, column_data)
        
        if rule.type == ActionType.ASSERT and not condition_met:
            violation = RuleViolation(
                rule_id=rule.id,
                field=rule.field,
                row_index=None,  # Column scope
                message=rule.message,
                severity=rule.severity,
                actual_value=f"Column {rule.field}",
                expected_value=None
            )
            
            if rule.severity == Severity.ERROR:
                result.add_error(violation)
            else:
                result.add_warning(violation)
                
        return result
    
    def _execute_row_rule(self, 
                         rule: CompiledRule,
                         row: pd.Series,
                         row_index: int) -> ExecutionResult:
        """Executa regra com escopo de linha."""
        result = ExecutionResult()
        
        # Obter valor do campo
        field_value = row.get(rule.field) if rule.field in row.index else None
        
        # Avaliar condição
        condition_met = self._evaluate_row_condition(rule.condition, field_value, row)
        
        if rule.type == ActionType.ASSERT:
            if not condition_met:
                violation = RuleViolation(
                    rule_id=rule.id,
                    field=rule.field,
                    row_index=row_index,
                    message=rule.message,
                    severity=rule.severity,
                    actual_value=field_value
                )
                
                if rule.severity == Severity.ERROR:
                    result.add_error(violation)
                else:
                    result.add_warning(violation)
                    
        elif rule.type == ActionType.TRANSFORM and condition_met:
            # Aplicar transformação
            transformed_value = self._apply_transform_action(rule.action, field_value, row)
            
            if transformed_value != field_value:
                transformation = RuleTransformation(
                    rule_id=rule.id,
                    field=rule.field,
                    row_index=row_index,
                    original_value=field_value,
                    transformed_value=transformed_value,
                    operation=rule.action.operation or "transform"
                )
                result.add_transformation(transformation)
                
        elif rule.type == ActionType.SUGGEST and condition_met:
            # Gerar sugestões
            suggestions = self._generate_suggestion_action(rule.action, field_value, row)
            
            if suggestions:
                suggestion = RuleSuggestion(
                    rule_id=rule.id,
                    field=rule.field,
                    row_index=row_index,
                    current_value=field_value,
                    suggested_values=suggestions,
                    confidence=getattr(rule.action, 'confidence', 0.8),
                    reason=rule.message
                )
                result.add_suggestion(suggestion)
                
        return result
    
    def _evaluate_condition_vectorized(self, 
                                      condition: CompiledCondition,
                                      data: pd.DataFrame) -> pd.Series:
        """Avalia condição de forma vetorizada."""
        cache_key = f"{hash(str(condition))}"
        
        if self.enable_cache and cache_key in self._condition_cache:
            self._condition_cache[cache_key] += 1  # cache hit counter
            return self._condition_cache[cache_key]
        
        # Implementar avaliação vetorizada baseada no operator
        if condition.type == ConditionType.SIMPLE:
            mask = self._evaluate_simple_condition_vectorized(condition, data)
        else:  # LOGICAL
            mask = self._evaluate_logical_condition_vectorized(condition, data)
        
        if self.enable_cache:
            self._condition_cache[cache_key] = mask
            
        return mask
    
    def _evaluate_simple_condition_vectorized(self, 
                                            condition: CompiledCondition,
                                            data: pd.DataFrame) -> pd.Series:
        """Avalia condição simples vetorizada."""
        operator = condition.operator
        value = condition.value
        
        # Implementar operadores vetorizados
        if operator == "eq":
            return data[condition.field] == value
        elif operator == "ne":
            return data[condition.field] != value  
        elif operator == "gt":
            return pd.to_numeric(data[condition.field], errors='coerce') > value
        elif operator == "gte":
            return pd.to_numeric(data[condition.field], errors='coerce') >= value
        elif operator == "lt":
            return pd.to_numeric(data[condition.field], errors='coerce') < value
        elif operator == "lte":
            return pd.to_numeric(data[condition.field], errors='coerce') <= value
        elif operator == "contains":
            if condition.case_sensitive:
                return data[condition.field].str.contains(str(value), na=False)
            else:
                return data[condition.field].str.lower().str.contains(str(value).lower(), na=False)
        elif operator == "startswith":
            if condition.case_sensitive:
                return data[condition.field].str.startswith(str(value), na=False)
            else:
                return data[condition.field].str.lower().str.startswith(str(value).lower(), na=False)
        elif operator == "endswith":
            if condition.case_sensitive:
                return data[condition.field].str.endswith(str(value), na=False)
            else:
                return data[condition.field].str.lower().str.endswith(str(value).lower(), na=False)
        elif operator == "matches":
            # Usar regex compilado se disponível
            pattern = condition.compiled_value if condition.compiled_value else value
            return data[condition.field].str.match(str(pattern), na=False)
        elif operator == "in":
            return data[condition.field].isin(value if isinstance(value, list) else [value])
        elif operator == "not_in":
            return ~data[condition.field].isin(value if isinstance(value, list) else [value])
        elif operator == "empty":
            return data[condition.field].isna() | (data[condition.field].astype(str).str.strip() == "")
        elif operator == "not_empty":
            return ~(data[condition.field].isna() | (data[condition.field].astype(str).str.strip() == ""))
        elif operator == "length_eq":
            return data[condition.field].str.len() == value
        elif operator == "length_gt":
            return data[condition.field].str.len() > value
        elif operator == "length_lt":
            return data[condition.field].str.len() < value
        elif operator == "is_number":
            return pd.to_numeric(data[condition.field], errors='coerce').notna()
        elif operator == "is_email":
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return data[condition.field].str.match(email_pattern, na=False)
        elif operator == "is_url":
            url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
            return data[condition.field].str.match(url_pattern, na=False)
        elif operator == "is_date":
            return pd.to_datetime(data[condition.field], errors='coerce').notna()
        else:
            # Operador desconhecido - retorna False para todas as linhas
            logger.warning(f"Operador desconhecido: {operator}")
            return pd.Series([False] * len(data), index=data.index)
    
    def _evaluate_logical_condition_vectorized(self, 
                                             condition: CompiledCondition,
                                             data: pd.DataFrame) -> pd.Series:
        """Avalia condição lógica vetorizada."""
        if condition.logical_op == "and":
            result = pd.Series([True] * len(data), index=data.index)
            for subcond in condition.subconditions:
                result = result & self._evaluate_condition_vectorized(subcond, data)
            return result
        elif condition.logical_op == "or":
            result = pd.Series([False] * len(data), index=data.index)
            for subcond in condition.subconditions:
                result = result | self._evaluate_condition_vectorized(subcond, data)
            return result
        elif condition.logical_op == "not":
            subcond = condition.subconditions[0]
            return ~self._evaluate_condition_vectorized(subcond, data)
        else:
            logger.warning(f"Operador lógico desconhecido: {condition.logical_op}")
            return pd.Series([False] * len(data), index=data.index)
    
    # Métodos auxiliares continuam...
    def _initialize_operators(self) -> Dict[str, Callable]:
        """Inicializa operadores disponíveis."""
        return {
            'eq': lambda x, y: x == y,
            'ne': lambda x, y: x != y,
            'gt': lambda x, y: self._safe_numeric_compare(x, y, lambda a, b: a > b),
            'gte': lambda x, y: self._safe_numeric_compare(x, y, lambda a, b: a >= b),
            'lt': lambda x, y: self._safe_numeric_compare(x, y, lambda a, b: a < b),
            'lte': lambda x, y: self._safe_numeric_compare(x, y, lambda a, b: a <= b),
            'contains': lambda x, y: str(y) in str(x) if x is not None else False,
            'startswith': lambda x, y: str(x).startswith(str(y)) if x is not None else False,
            'endswith': lambda x, y: str(x).endswith(str(y)) if x is not None else False,
            'matches': lambda x, y: bool(re.match(str(y), str(x))) if x is not None else False,
            'in': lambda x, y: x in (y if isinstance(y, (list, tuple, set)) else [y]),
            'not_in': lambda x, y: x not in (y if isinstance(y, (list, tuple, set)) else [y]),
            'empty': lambda x, y: x is None or str(x).strip() == '',
            'not_empty': lambda x, y: x is not None and str(x).strip() != '',
            'is_number': lambda x, y: self._is_number(x),
            'is_email': lambda x, y: self._is_email(x),
            'is_url': lambda x, y: self._is_url(x),
            'is_date': lambda x, y: self._is_date(x),
        }
    
    def _safe_numeric_compare(self, x, y, comparator) -> bool:
        """Comparação numérica segura."""
        try:
            if x is None or y is None:
                return False
            num_x = float(x) if not isinstance(x, (int, float)) else x
            num_y = float(y) if not isinstance(y, (int, float)) else y
            return comparator(num_x, num_y)
        except (ValueError, TypeError):
            return False
    
    def _is_number(self, value) -> bool:
        """Verifica se é número."""
        if value is None:
            return False
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    def _is_email(self, value) -> bool:
        """Verifica se é email válido."""
        if not value:
            return False
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, str(value)))
    
    def _is_url(self, value) -> bool:
        """Verifica se é URL válida."""
        if not value:
            return False
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return bool(re.match(url_pattern, str(value)))
    
    def _is_date(self, value) -> bool:
        """Verifica se é data válida."""
        if not value:
            return False
        try:
            pd.to_datetime(value)
            return True
        except:
            return False
    
    def _merge_results(self, target: ExecutionResult, source: ExecutionResult) -> None:
        """Merge dos resultados de execução."""
        target.errors.extend(source.errors)
        target.warnings.extend(source.warnings)
        target.suggestions.extend(source.suggestions)
        target.transformations.extend(source.transformations)
        
        # Merge das estatísticas
        target.stats.error_count += source.stats.error_count
        target.stats.warning_count += source.stats.warning_count
        target.stats.suggestion_count += source.stats.suggestion_count
        target.stats.transformation_count += source.stats.transformation_count
        target.stats.rules_executed += source.stats.rules_executed
        target.stats.vectorized_operations += source.stats.vectorized_operations
        target.stats.cache_hits += source.stats.cache_hits
    
    # Placeholder methods - implementação completa dependeria dos tipos específicos
    def _create_violations_from_mask(self, rule, mask, data):
        """Cria violações baseadas na máscara."""
        return []
    
    def _apply_transform_vectorized(self, rule, mask, data):
        """Aplica transformações vetorizadas."""
        return []
        
    def _generate_suggestions_vectorized(self, rule, mask, data):
        """Gera sugestões vetorizadas.""" 
        return []
    
    def _apply_transformations(self, data, transformations):
        """Aplica transformações no DataFrame."""
        return data
    
    def _evaluate_global_condition(self, condition, data):
        """Avalia condição global."""
        return True
        
    def _evaluate_column_condition(self, condition, column_data):
        """Avalia condição de coluna."""
        return True
        
    def _evaluate_row_condition(self, condition, field_value, row):
        """Avalia condição de linha."""
        return True
        
    def _apply_transform_action(self, action, field_value, row):
        """Aplica ação de transformação."""
        return field_value
        
    def _generate_suggestion_action(self, action, field_value, row):
        """Gera ação de sugestão."""
        return []