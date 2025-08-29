"""
ValidaHub Rules Compiler - YAML to IR.

Este módulo implementa a compilação de arquivos YAML de regras para
Intermediate Representation (IR) otimizada para execução.
"""

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import yaml
import jsonschema
from pathlib import Path

from .ir_types import (
    CompiledRuleSet, CompiledRule, CompiledCondition, CompiledAction,
    CCMMapping, FieldMapping, Transform, TransformType,
    ExecutionPlan, ExecutionPhase, RuleGroup, PhaseType,
    ConditionType, ActionType, RuleScope, Severity, ExecutionMode,
    CompatibilityConfig, CompilationStats
)
from src.domain.rules.value_objects import SemVer

logger = logging.getLogger(__name__)


class CompilationError(Exception):
    """Erro durante compilação de regras."""
    
    def __init__(self, message: str, rule_id: Optional[str] = None, line_number: Optional[int] = None):
        super().__init__(message)
        self.rule_id = rule_id
        self.line_number = line_number


class RuleCompiler:
    """
    Compilador de regras YAML para IR.
    
    Responsabilidades:
    - Validação de schema YAML
    - Compilação para estruturas otimizadas
    - Otimização do plano de execução
    - Geração de checksums para cache
    - Detecção de dependências entre regras
    """
    
    def __init__(self, schema_path: Optional[str] = None):
        """
        Inicializa o compilador.
        
        Args:
            schema_path: Caminho para o schema JSON de validação
        """
        self.schema_path = schema_path
        self.schema: Optional[Dict] = None
        
        # Cache de expressões compiladas
        self._regex_cache: Dict[str, re.Pattern] = {}
        self._transform_cache: Dict[str, Any] = {}
        
        # Estatísticas de compilação
        self.stats = CompilationStats()
        
        if schema_path:
            self._load_schema()
    
    def _load_schema(self) -> None:
        """Carrega o schema JSON para validação."""
        try:
            if self.schema_path:
                with open(self.schema_path, 'r') as f:
                    self.schema = json.load(f)
        except Exception as e:
            logger.warning(f"Não foi possível carregar schema {self.schema_path}: {e}")
    
    def compile_yaml(self, yaml_content: Union[str, Dict]) -> CompiledRuleSet:
        """
        Compila YAML de regras para IR.
        
        Args:
            yaml_content: Conteúdo YAML (string ou dict já parseado)
            
        Returns:
            RuleSet compilado
            
        Raises:
            CompilationError: Erro durante compilação
        """
        start_time = time.perf_counter()
        
        try:
            # Parse do YAML se necessário
            if isinstance(yaml_content, str):
                yaml_data = yaml.safe_load(yaml_content)
                source_content = yaml_content
            else:
                yaml_data = yaml_content
                source_content = yaml.dump(yaml_data, default_flow_style=False)
            
            # Validação de schema
            if self.schema:
                self._validate_schema(yaml_data)
            
            # Geração de checksum
            checksum = self._generate_checksum(source_content)
            
            # Compilação das seções
            ccm_mapping = self._compile_ccm_mapping(yaml_data.get('ccm_mapping', {}))
            rules = self._compile_rules(yaml_data.get('rules', []))
            execution_plan = self._create_execution_plan(rules)
            compatibility_config = self._create_compatibility_config(yaml_data.get('compatibility', {}))
            
            # Estatísticas finais
            compilation_time = (time.perf_counter() - start_time) * 1000
            self.stats = CompilationStats(
                total_rules=len(rules),
                rules_by_type=self._count_rules_by_type(rules),
                rules_by_field=self._count_rules_by_field(rules),
                compilation_time_ms=compilation_time,
                optimizations_applied=len(execution_plan.optimizations),
                warnings_count=0,  # TODO: Implementar contagem de warnings
                errors_count=0     # TODO: Implementar contagem de erros
            )
            
            return CompiledRuleSet(
                schema_version=yaml_data.get('schema_version', '1.0.0'),
                checksum=checksum,
                compiled_at=datetime.now(timezone.utc),
                marketplace=yaml_data.get('marketplace', 'unknown'),
                version=SemVer.from_string(yaml_data.get('version', '1.0.0')),
                ccm_mapping=ccm_mapping,
                rules=rules,
                execution_plan=execution_plan,
                compatibility=compatibility_config,
                stats=self.stats
            )
            
        except Exception as e:
            logger.error(f"Erro durante compilação: {e}")
            if isinstance(e, CompilationError):
                raise
            else:
                raise CompilationError(f"Erro de compilação: {e}")
    
    def _validate_schema(self, yaml_data: Dict) -> None:
        """Valida YAML contra o schema."""
        try:
            jsonschema.validate(yaml_data, self.schema)
        except jsonschema.ValidationError as e:
            raise CompilationError(f"Erro de validação de schema: {e.message}")
    
    def _generate_checksum(self, content: str) -> str:
        """Gera checksum SHA-256 do conteúdo."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _compile_ccm_mapping(self, mapping_data: Dict) -> CCMMapping:
        """Compila mapeamento CCM."""
        field_mappings = {}
        transforms = {}
        
        for ccm_field, mapping_config in mapping_data.items():
            if isinstance(mapping_config, str):
                # Mapeamento simples: field direto
                field_mappings[ccm_field] = FieldMapping(
                    source_field=mapping_config,
                    required=False
                )
            elif isinstance(mapping_config, dict):
                # Mapeamento complexo
                source_field = mapping_config.get('source', ccm_field)
                
                transform = None
                if 'transform' in mapping_config:
                    transform = self._compile_transform(mapping_config['transform'])
                
                field_mappings[ccm_field] = FieldMapping(
                    source_field=source_field,
                    transform=transform,
                    default_value=mapping_config.get('default'),
                    required=mapping_config.get('required', False)
                )
        
        # Ordem de validação baseada em dependências
        validation_order = self._determine_validation_order(field_mappings)
        
        return CCMMapping(
            field_mappings=field_mappings,
            transforms=transforms,
            validation_order=validation_order
        )
    
    def _compile_transform(self, transform_data: Dict) -> Transform:
        """Compila definição de transformação."""
        transform_type = TransformType(transform_data.get('type', 'custom'))
        expression = transform_data.get('expression')
        params = transform_data.get('params', {})
        
        # Compilar expressão se necessário
        compiled_expression = None
        if transform_type == TransformType.CUSTOM and expression:
            compiled_expression = self._compile_custom_expression(expression)
        elif transform_type in [TransformType.UPPER, TransformType.LOWER]:
            # Transformações simples não precisam compilação
            pass
        
        return Transform(
            type=transform_type,
            expression=expression,
            params=params,
            compiled_expression=compiled_expression
        )
    
    def _compile_rules(self, rules_data: List[Dict]) -> Dict[str, CompiledRule]:
        """Compila lista de regras."""
        compiled_rules = {}
        
        for rule_data in rules_data:
            try:
                rule = self._compile_single_rule(rule_data)
                compiled_rules[rule.id] = rule
            except Exception as e:
                rule_id = rule_data.get('id', 'unknown')
                logger.error(f"Erro ao compilar regra {rule_id}: {e}")
                raise CompilationError(f"Erro na regra {rule_id}: {e}", rule_id=rule_id)
        
        return compiled_rules
    
    def _compile_single_rule(self, rule_data: Dict) -> CompiledRule:
        """Compila uma regra individual."""
        rule_id = rule_data['id']
        field = rule_data['field']
        rule_type = ActionType(rule_data['type'])
        precedence = rule_data.get('precedence', 500)
        scope = RuleScope(rule_data.get('scope', 'row'))
        
        # Compilar condição
        condition = None
        if 'condition' in rule_data:
            condition = self._compile_condition(rule_data['condition'], field)
        else:
            # Condição padrão: sempre verdadeira
            condition = CompiledCondition(
                type=ConditionType.SIMPLE,
                operator="not_empty",
                field=field
            )
        
        # Compilar ação
        action = self._compile_action(rule_data['action'], rule_type)
        
        # Metadados
        message = rule_data.get('message', f'Rule {rule_id} violation')
        severity = Severity(rule_data.get('severity', 'error'))
        enabled = rule_data.get('enabled', True)
        tags = rule_data.get('tags', [])
        
        return CompiledRule(
            id=rule_id,
            field=field,
            type=rule_type,
            precedence=precedence,
            scope=scope,
            condition=condition,
            action=action,
            message=message,
            severity=severity,
            enabled=enabled,
            tags=tags
        )
    
    def _compile_condition(self, condition_data: Dict, default_field: str) -> CompiledCondition:
        """Compila condição de regra."""
        # Detectar tipo de condição
        if any(key in condition_data for key in ['and', 'or', 'not']):
            return self._compile_logical_condition(condition_data, default_field)
        else:
            return self._compile_simple_condition(condition_data, default_field)
    
    def _compile_simple_condition(self, condition_data: Dict, default_field: str) -> CompiledCondition:
        """Compila condição simples."""
        operator = condition_data.get('operator', 'not_empty')
        value = condition_data.get('value')
        case_sensitive = condition_data.get('case_sensitive', True)
        field = condition_data.get('field', default_field)
        
        # Compilar valor se necessário
        compiled_value = None
        if operator in ['matches', 'regex']:
            if value:
                compiled_value = self._compile_regex(str(value))
        elif operator in ['in', 'not_in']:
            if isinstance(value, str):
                # Converter string separada por vírgula em lista
                compiled_value = [item.strip() for item in value.split(',')]
            else:
                compiled_value = value
        
        return CompiledCondition(
            type=ConditionType.SIMPLE,
            operator=operator,
            value=compiled_value or value,
            compiled_value=compiled_value,
            case_sensitive=case_sensitive,
            field=field
        )
    
    def _compile_logical_condition(self, condition_data: Dict, default_field: str) -> CompiledCondition:
        """Compila condição lógica."""
        if 'and' in condition_data:
            subconditions = [
                self._compile_condition(subcond, default_field) 
                for subcond in condition_data['and']
            ]
            return CompiledCondition(
                type=ConditionType.LOGICAL,
                operator="and",
                field=default_field,
                subconditions=subconditions,
                logical_op="and"
            )
        elif 'or' in condition_data:
            subconditions = [
                self._compile_condition(subcond, default_field)
                for subcond in condition_data['or']
            ]
            return CompiledCondition(
                type=ConditionType.LOGICAL,
                operator="or",
                field=default_field,
                subconditions=subconditions,
                logical_op="or"
            )
        elif 'not' in condition_data:
            subcondition = self._compile_condition(condition_data['not'], default_field)
            return CompiledCondition(
                type=ConditionType.LOGICAL,
                operator="not",
                field=default_field,
                subconditions=[subcondition],
                logical_op="not"
            )
        else:
            raise CompilationError("Condição lógica inválida")
    
    def _compile_action(self, action_data: Dict, rule_type: ActionType) -> CompiledAction:
        """Compila ação de regra."""
        action_type = ActionType(action_data.get('type', rule_type.value))
        
        if action_type == ActionType.ASSERT:
            return CompiledAction(
                type=action_type,
                stop_on_error=action_data.get('stop_on_error', False)
            )
        elif action_type == ActionType.TRANSFORM:
            operation = action_data.get('operation', 'set')
            value = action_data.get('value')
            expression = action_data.get('expression')
            params = action_data.get('params', {})
            
            # Compilar expressão customizada
            compiled_expression = None
            if operation == 'custom' and expression:
                compiled_expression = self._compile_custom_expression(expression)
            
            return CompiledAction(
                type=action_type,
                operation=operation,
                value=value,
                compiled_expression=compiled_expression,
                params=params
            )
        elif action_type == ActionType.SUGGEST:
            suggestions = action_data.get('suggestions', [])
            confidence = action_data.get('confidence', 0.8)
            
            return CompiledAction(
                type=action_type,
                suggestions=suggestions,
                confidence=confidence
            )
        else:
            raise CompilationError(f"Tipo de ação desconhecido: {action_type}")
    
    def _compile_regex(self, pattern: str) -> re.Pattern:
        """Compila regex com cache."""
        if pattern in self._regex_cache:
            return self._regex_cache[pattern]
        
        try:
            compiled_regex = re.compile(pattern)
            self._regex_cache[pattern] = compiled_regex
            return compiled_regex
        except re.error as e:
            raise CompilationError(f"Regex inválido '{pattern}': {e}")
    
    def _compile_custom_expression(self, expression: str) -> Any:
        """Compila expressão customizada (placeholder)."""
        # TODO: Implementar compilação de expressões customizadas
        # Por segurança, poderia usar um subset de Python ou DSL própria
        return expression
    
    def _create_execution_plan(self, rules: Dict[str, CompiledRule]) -> ExecutionPlan:
        """Cria plano otimizado de execução."""
        # Análise de dependências
        field_deps = self._analyze_field_dependencies(rules)
        
        # Agrupamento por tipo e precedência
        rule_groups = self._create_rule_groups(rules, field_deps)
        
        # Criação de fases
        phases = self._create_execution_phases(rule_groups)
        
        # Índices para acesso rápido
        field_index = self._create_field_index(rules)
        precedence_index = self._create_precedence_index(rules)
        
        # Grupos paralelos
        parallel_groups = self._identify_parallel_groups(rules, field_deps)
        
        # Otimizações aplicadas
        optimizations = [
            "precedence_ordering",
            "dependency_resolution", 
            "vectorization_grouping",
            "parallel_execution"
        ]
        
        return ExecutionPlan(
            phases=phases,
            optimizations=optimizations,
            field_index=field_index,
            precedence_index=precedence_index,
            parallel_groups=parallel_groups
        )
    
    def _analyze_field_dependencies(self, rules: Dict[str, CompiledRule]) -> Dict[str, Set[str]]:
        """Analisa dependências entre campos."""
        dependencies = {}
        
        for rule_id, rule in rules.items():
            deps = set()
            
            # Analisar dependências na condição
            deps.update(self._extract_condition_dependencies(rule.condition))
            
            # Analisar dependências na ação (para transforms que usam outros campos)
            deps.update(self._extract_action_dependencies(rule.action))
            
            # Remover autoependência
            deps.discard(rule.field)
            
            if deps:
                dependencies[rule.field] = deps
        
        return dependencies
    
    def _extract_condition_dependencies(self, condition: CompiledCondition) -> Set[str]:
        """Extrai dependências de campo de uma condição."""
        deps = set()
        
        if condition.field:
            deps.add(condition.field)
        
        # Recursivamente analisar subcondições
        for subcond in condition.subconditions:
            deps.update(self._extract_condition_dependencies(subcond))
        
        return deps
    
    def _extract_action_dependencies(self, action: CompiledAction) -> Set[str]:
        """Extrai dependências de campo de uma ação."""
        deps = set()
        
        # TODO: Analisar expressões customizadas para extrair referências de campo
        # Por exemplo, expressões como "{other_field} + 10" 
        
        return deps
    
    def _create_rule_groups(self, rules: Dict[str, CompiledRule], 
                           dependencies: Dict[str, Set[str]]) -> List[RuleGroup]:
        """Cria grupos de regras baseado em dependências e compatibilidade."""
        groups = []
        
        # Ordenar regras por precedência
        sorted_rules = sorted(rules.values(), key=lambda r: (r.precedence, r.id))
        
        # Agrupar por compatibilidade de execução
        current_group = []
        current_mode = ExecutionMode.SEQUENTIAL
        
        for rule in sorted_rules:
            # Determinar modo de execução preferido
            preferred_mode = self._determine_execution_mode(rule)
            
            # Verificar se pode ser agrupado com regras atuais
            if (not current_group or 
                (preferred_mode == current_mode and 
                 self._can_group_rules(current_group, [rule.id], dependencies))):
                current_group.append(rule.id)
                current_mode = preferred_mode
            else:
                # Finalizar grupo atual
                if current_group:
                    groups.append(RuleGroup(
                        rule_ids=current_group,
                        execution_mode=current_mode,
                        dependencies=self._get_group_dependencies(current_group, dependencies)
                    ))
                
                # Iniciar novo grupo
                current_group = [rule.id]
                current_mode = preferred_mode
        
        # Adicionar último grupo
        if current_group:
            groups.append(RuleGroup(
                rule_ids=current_group,
                execution_mode=current_mode,
                dependencies=self._get_group_dependencies(current_group, dependencies)
            ))
        
        return groups
    
    def _determine_execution_mode(self, rule: CompiledRule) -> ExecutionMode:
        """Determina modo de execução preferido para uma regra."""
        # Regras de escopo row podem ser vetorizadas mais facilmente
        if rule.scope == RuleScope.ROW and self._is_vectorizable_rule(rule):
            return ExecutionMode.VECTORIZED
        # Regras independentes podem ser paralelizadas
        elif rule.scope == RuleScope.ROW:
            return ExecutionMode.PARALLEL
        else:
            return ExecutionMode.SEQUENTIAL
    
    def _is_vectorizable_rule(self, rule: CompiledRule) -> bool:
        """Verifica se regra pode ser vetorizada."""
        # Regras com operadores simples são mais fáceis de vetorizar
        if rule.condition.type == ConditionType.SIMPLE:
            vectorizable_ops = {
                'eq', 'ne', 'gt', 'gte', 'lt', 'lte',
                'contains', 'startswith', 'endswith', 'matches',
                'in', 'not_in', 'empty', 'not_empty',
                'length_eq', 'length_gt', 'length_lt',
                'is_number', 'is_email', 'is_url', 'is_date'
            }
            return rule.condition.operator in vectorizable_ops
        
        return False
    
    def _can_group_rules(self, current_group: List[str], new_rules: List[str], 
                        dependencies: Dict[str, Set[str]]) -> bool:
        """Verifica se regras podem ser agrupadas sem conflito de dependências."""
        # Verificação simplificada - na prática seria mais complexa
        return len(current_group) + len(new_rules) <= 10  # Limite arbitrário
    
    def _get_group_dependencies(self, rule_ids: List[str], 
                               dependencies: Dict[str, Set[str]]) -> List[str]:
        """Obtém dependências externas de um grupo de regras."""
        group_fields = set(rule_ids)  # Simplificação - assumindo rule_id == field
        external_deps = set()
        
        for rule_id in rule_ids:
            if rule_id in dependencies:
                external_deps.update(dependencies[rule_id] - group_fields)
        
        return list(external_deps)
    
    def _create_execution_phases(self, rule_groups: List[RuleGroup]) -> List[ExecutionPhase]:
        """Cria fases de execução."""
        phases = []
        
        # Fase 1: Validações (assertions)
        validation_groups = [g for g in rule_groups if self._is_validation_group(g)]
        if validation_groups:
            phases.append(ExecutionPhase(
                name="validation",
                phase_type=PhaseType.VALIDATION,
                rule_groups=validation_groups,
                can_vectorize=any(g.execution_mode == ExecutionMode.VECTORIZED for g in validation_groups)
            ))
        
        # Fase 2: Transformações
        transform_groups = [g for g in rule_groups if self._is_transform_group(g)]
        if transform_groups:
            phases.append(ExecutionPhase(
                name="transformation",
                phase_type=PhaseType.TRANSFORMATION,
                rule_groups=transform_groups,
                can_vectorize=any(g.execution_mode == ExecutionMode.VECTORIZED for g in transform_groups)
            ))
        
        # Fase 3: Sugestões
        suggestion_groups = [g for g in rule_groups if self._is_suggestion_group(g)]
        if suggestion_groups:
            phases.append(ExecutionPhase(
                name="suggestion",
                phase_type=PhaseType.SUGGESTION,
                rule_groups=suggestion_groups,
                can_vectorize=False  # Sugestões geralmente não são vetorizáveis
            ))
        
        return phases
    
    def _is_validation_group(self, group: RuleGroup) -> bool:
        """Verifica se grupo é de validação."""
        # Placeholder - na prática verificaria o tipo das regras
        return "validation" in group.rule_ids[0] if group.rule_ids else False
    
    def _is_transform_group(self, group: RuleGroup) -> bool:
        """Verifica se grupo é de transformação."""
        return "transform" in group.rule_ids[0] if group.rule_ids else False
    
    def _is_suggestion_group(self, group: RuleGroup) -> bool:
        """Verifica se grupo é de sugestão."""
        return "suggest" in group.rule_ids[0] if group.rule_ids else False
    
    def _create_field_index(self, rules: Dict[str, CompiledRule]) -> Dict[str, List[str]]:
        """Cria índice de regras por campo."""
        field_index = {}
        for rule_id, rule in rules.items():
            if rule.field not in field_index:
                field_index[rule.field] = []
            field_index[rule.field].append(rule_id)
        return field_index
    
    def _create_precedence_index(self, rules: Dict[str, CompiledRule]) -> Dict[int, List[str]]:
        """Cria índice de regras por precedência."""
        precedence_index = {}
        for rule_id, rule in rules.items():
            if rule.precedence not in precedence_index:
                precedence_index[rule.precedence] = []
            precedence_index[rule.precedence].append(rule_id)
        return precedence_index
    
    def _identify_parallel_groups(self, rules: Dict[str, CompiledRule],
                                 dependencies: Dict[str, Set[str]]) -> List[List[str]]:
        """Identifica grupos de regras que podem executar em paralelo."""
        parallel_groups = []
        
        # Algoritmo simplificado - agrupar regras sem dependências mútuas
        independent_rules = [
            rule_id for rule_id, rule in rules.items()
            if rule.field not in dependencies or not dependencies[rule.field]
        ]
        
        # Agrupar em lotes para paralelização
        batch_size = 4  # Número de threads
        for i in range(0, len(independent_rules), batch_size):
            batch = independent_rules[i:i + batch_size]
            if len(batch) > 1:  # Só vale a pena paralelizar com 2+ regras
                parallel_groups.append(batch)
        
        return parallel_groups
    
    def _create_compatibility_config(self, config_data: Dict) -> CompatibilityConfig:
        """Cria configuração de compatibilidade."""
        return CompatibilityConfig(
            auto_apply_patch=config_data.get('auto_apply_patch', True),
            shadow_period_days=config_data.get('shadow_period_days', 30),
            require_major_opt_in=config_data.get('require_major_opt_in', True),
            validate_field_removals=config_data.get('validate_field_removals', True),
            validate_type_changes=config_data.get('validate_type_changes', True),
            validate_constraint_tightening=config_data.get('validate_constraint_tightening', True),
            fallback_on_error=config_data.get('fallback_on_error', True),
            max_fallback_versions=config_data.get('max_fallback_versions', 3)
        )
    
    def _count_rules_by_type(self, rules: Dict[str, CompiledRule]) -> Dict[str, int]:
        """Conta regras por tipo."""
        counts = {}
        for rule in rules.values():
            rule_type = rule.type.value
            counts[rule_type] = counts.get(rule_type, 0) + 1
        return counts
    
    def _count_rules_by_field(self, rules: Dict[str, CompiledRule]) -> Dict[str, int]:
        """Conta regras por campo."""
        counts = {}
        for rule in rules.values():
            field = rule.field
            counts[field] = counts.get(field, 0) + 1
        return counts
    
    def _determine_validation_order(self, field_mappings: Dict[str, FieldMapping]) -> List[str]:
        """Determina ordem de validação baseada em dependências."""
        # Algoritmo simples - na prática seria mais sofisticado
        return list(field_mappings.keys())