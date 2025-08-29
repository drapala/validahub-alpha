# ValidaHub Rules - Intermediate Representation (IR) Specification

## Overview

A Intermediate Representation (IR) é uma estrutura de dados otimizada para execução rápida das regras de validação e transformação. O IR é gerado através da compilação dos arquivos YAML de regras, fornecendo uma representação normalizada, cacheable e versionada.

## Objetivos do IR

1. **Performance**: Estrutura otimizada para processamento em lote de 50k+ linhas
2. **Versionamento**: Controle de compatibilidade e migração entre versões
3. **Cache**: Representação determinística para cache Redis com TTL
4. **Hot-reload**: Invalidação inteligente baseada em checksum
5. **Vetorização**: Compatibilidade com pandas/pyarrow para operações vetorizadas

## Estrutura do IR

### Schema Principal

```python
@dataclass(frozen=True)
class CompiledRuleSet:
    """Representação compilada de um conjunto de regras."""
    
    # Metadados do IR
    schema_version: str           # Versão do schema IR (ex: "1.0.0")
    checksum: str                # SHA-256 do YAML original
    compiled_at: datetime        # Timestamp de compilação
    marketplace: str             # Identificador do marketplace
    version: SemVer             # Versão semântica das regras
    
    # Mapeamento CCM
    ccm_mapping: CCMMapping     # Mapeamento para Canonical CSV Model
    
    # Regras compiladas
    rules: Dict[str, CompiledRule]  # Regras indexadas por field
    execution_plan: ExecutionPlan   # Plano de execução otimizado
    
    # Configurações de compatibilidade
    compatibility: CompatibilityConfig
    
    # Estatísticas de compilação
    stats: CompilationStats
```

### Mapeamento CCM

```python
@dataclass(frozen=True)
class CCMMapping:
    """Mapeamento de campos para o Canonical CSV Model."""
    
    field_mappings: Dict[str, FieldMapping]  # CCM field -> source mapping
    transforms: Dict[str, Transform]         # Transformações pré-aplicadas
    validation_order: List[str]              # Ordem de validação dos campos
    
@dataclass(frozen=True)
class FieldMapping:
    """Mapeamento individual de campo."""
    
    source_field: str                    # Campo de origem
    transform: Optional[Transform]       # Transformação aplicada
    default_value: Optional[Any]         # Valor padrão
    required: bool = False              # Se o campo é obrigatório
    
@dataclass(frozen=True) 
class Transform:
    """Transformação de dados."""
    
    type: TransformType                 # Tipo de transformação
    expression: Optional[str]           # Expressão custom
    params: Dict[str, Any]             # Parâmetros da transformação
    compiled_expression: Optional[Any] # Expressão compilada (regex, função, etc)
```

### Regras Compiladas

```python
@dataclass(frozen=True)
class CompiledRule:
    """Regra compilada para execução rápida."""
    
    id: str                           # Identificador único
    field: str                       # Campo CCM alvo
    type: RuleType                   # assert, transform, suggest
    precedence: int                  # Prioridade (0=maior)
    scope: RuleScope                # row, column, global
    
    # Condições compiladas
    condition: CompiledCondition    # Condição normalizada
    
    # Ação compilada  
    action: CompiledAction          # Ação otimizada
    
    # Metadados
    message: str                    # Mensagem de erro/aviso
    severity: Severity             # error, warning, info
    enabled: bool = True           # Se a regra está ativa
    tags: List[str]               # Tags para categorização

@dataclass(frozen=True)
class CompiledCondition:
    """Condição compilada e otimizada."""
    
    type: ConditionType              # simple, logical
    operator: str                    # Operador (eq, gt, contains, etc)
    value: Optional[Any]            # Valor de comparação
    compiled_value: Optional[Any]   # Valor compilado (regex Pattern, etc)
    case_sensitive: bool = True     # Para operações de string
    
    # Para condições lógicas
    subconditions: List['CompiledCondition'] = None
    logical_op: Optional[str] = None  # and, or, not

@dataclass(frozen=True)
class CompiledAction:
    """Ação compilada para execução."""
    
    type: ActionType                # assert, transform, suggest
    operation: Optional[str]        # Operação específica
    value: Optional[Any]           # Valor alvo
    compiled_expression: Optional[Any] # Expressão compilada
    params: Dict[str, Any]         # Parâmetros adicionais
    stop_on_error: bool = False    # Para assertions
```

### Plano de Execução

```python
@dataclass(frozen=True)
class ExecutionPlan:
    """Plano otimizado de execução das regras."""
    
    # Fases de execução
    phases: List[ExecutionPhase]
    
    # Otimizações aplicadas
    optimizations: List[str]
    
    # Índices para acesso rápido
    field_index: Dict[str, List[str]]    # field -> rule_ids
    precedence_index: Dict[int, List[str]] # precedence -> rule_ids
    
    # Configuração de paralelização
    parallel_groups: List[List[str]]     # Grupos de regras paralelas
    
@dataclass(frozen=True) 
class ExecutionPhase:
    """Fase de execução com regras agrupadas."""
    
    name: str                       # Nome da fase
    phase_type: PhaseType          # validation, transformation, suggestion
    rule_groups: List[RuleGroup]   # Grupos de regras da fase
    can_vectorize: bool           # Se suporta vetorização
    
@dataclass(frozen=True)
class RuleGroup:
    """Grupo de regras que podem executar juntas."""
    
    rule_ids: List[str]           # IDs das regras do grupo
    execution_mode: ExecutionMode # sequential, parallel, vectorized
    dependencies: List[str]       # Dependências de outros grupos
```

## Algoritmos de Otimização

### 1. Ordenação por Precedência

```python
def optimize_precedence_order(rules: List[CompiledRule]) -> List[CompiledRule]:
    """
    Ordena regras por precedência e dependências.
    
    Algoritmo:
    1. Ordena por precedência (0 = maior prioridade)
    2. Resolve dependências entre campos
    3. Agrupa regras independentes para paralelização
    """
    
    # Ordenação topológica considerando:
    # - Precedência numérica
    # - Dependências de campo (transform antes de assert)
    # - Escopo (global -> column -> row)
```

### 2. Short-Circuit por Campo

```python
def optimize_short_circuit(rules: List[CompiledRule]) -> List[CompiledRule]:
    """
    Aplica otimização de short-circuit.
    
    Estratégias:
    1. Para assertions: falha rápida em erro
    2. Para transforms: skip se campo já válido
    3. Para suggests: limit por confidence score
    """
```

### 3. Vetorização por Lote

```python
def create_vectorization_plan(rules: List[CompiledRule]) -> VectorizationPlan:
    """
    Cria plano de vetorização pandas/pyarrow.
    
    Agrupa regras por:
    1. Tipo de operação (numeric, string, date)
    2. Compatibilidade com pandas ops
    3. Memória estimada para processamento
    """
```

## Sistema de Cache e Hot-Reload

### Cache Redis

```python
# Estrutura das chaves de cache
CACHE_KEYS = {
    "ruleset": "rules:compiled:{marketplace}:{version}:{checksum}",
    "metadata": "rules:meta:{marketplace}:{version}",
    "stats": "rules:stats:{marketplace}:{version}:{date}"
}

# TTL por tipo
CACHE_TTL = {
    "compiled_rules": 3600,      # 1 hora
    "metadata": 86400,           # 24 horas  
    "stats": 604800              # 7 dias
}
```

### Hot-Reload com Invalidação

```python
@dataclass
class HotReloadConfig:
    """Configuração de hot-reload."""
    
    enabled: bool = True
    check_interval: int = 30          # segundos
    invalidation_strategy: str = "checksum"  # checksum, timestamp, version
    fallback_version: Optional[str] = None
    
def should_reload(current_checksum: str, cached_checksum: str) -> bool:
    """
    Determina se deve fazer reload baseado no checksum.
    
    Estratégias de invalidação:
    1. Checksum diferente = reload imediato
    2. Versão major diferente = reload controlado
    3. Falha de cache = reload com fallback
    """
```

## Versionamento e Compatibilidade

### Políticas de Compatibilidade

```python
@dataclass(frozen=True)
class CompatibilityConfig:
    """Configuração de compatibilidade entre versões."""
    
    # Políticas de auto-aplicação
    auto_apply_patch: bool = True      # Patches aplicam automaticamente
    shadow_period_days: int = 30       # Período sombra para minor
    require_major_opt_in: bool = True  # Major requer opt-in manual
    
    # Validações de breaking changes
    validate_field_removals: bool = True
    validate_type_changes: bool = True
    validate_constraint_tightening: bool = True
    
    # Fallback strategies
    fallback_on_error: bool = True
    max_fallback_versions: int = 3

def check_compatibility(old_ir: CompiledRuleSet, new_ir: CompiledRuleSet) -> CompatibilityReport:
    """
    Analisa compatibilidade entre versões de IR.
    
    Verifica:
    1. Mudanças em campos CCM
    2. Alterações em regras existentes 
    3. Novas dependências
    4. Breaking changes em transformações
    """
```

### Migração de IR

```python
@dataclass
class MigrationPlan:
    """Plano de migração entre versões."""
    
    from_version: SemVer
    to_version: SemVer 
    compatibility_level: Compatibility  # MAJOR, MINOR, PATCH
    
    # Ações de migração
    field_migrations: List[FieldMigration]
    rule_migrations: List[RuleMigration] 
    data_transforms: List[DataTransform]
    
    # Validações pós-migração
    validation_rules: List[ValidationRule]
    rollback_plan: Optional[RollbackPlan]

def create_migration_plan(from_ir: CompiledRuleSet, to_ir: CompiledRuleSet) -> MigrationPlan:
    """Cria plano de migração automática entre versões."""
```

## Benchmarks e Performance

### Métricas de Performance

```python
@dataclass
class PerformanceMetrics:
    """Métricas de performance do IR."""
    
    # Tempos de execução
    compilation_time_ms: float      # Tempo de compilação YAML -> IR
    loading_time_ms: float          # Tempo de carregamento do cache
    execution_time_ms: float        # Tempo de execução das regras
    
    # Throughput
    rows_per_second: float          # Taxa de processamento
    rules_per_second: float         # Taxa de execução de regras
    
    # Utilização de recursos
    memory_usage_mb: float          # Uso de memória
    cpu_utilization: float          # % CPU utilizado
    cache_hit_rate: float          # Taxa de acerto do cache
    
    # Estatísticas de qualidade
    error_rate: float              # Taxa de erro
    warning_rate: float            # Taxa de warning
    suggestion_accuracy: float     # Precisão das sugestões

# Target SLO: 50k linhas em < 3 segundos
TARGET_SLO = {
    "rows_per_second": 16667,      # 50k / 3s
    "max_execution_time": 3000,    # 3 segundos
    "max_memory_usage": 512,       # 512 MB
    "min_cache_hit_rate": 0.95     # 95% cache hits
}
```

### Harness de Benchmark

```python
def benchmark_ruleset(
    ruleset: CompiledRuleSet,
    test_data: pd.DataFrame,
    iterations: int = 3
) -> PerformanceMetrics:
    """
    Executa benchmark completo do ruleset.
    
    Metodologia:
    1. Aquecimento (1 execução)
    2. Benchmark (3 execuções)
    3. Coleta de métricas detalhadas
    4. Análise estatística (mediana)
    5. Validação contra SLO
    """
```

## Formato de Serialização

### Binário (MessagePack)

```python
def serialize_ir(ruleset: CompiledRuleSet) -> bytes:
    """Serializa IR para formato binário otimizado."""
    
def deserialize_ir(data: bytes) -> CompiledRuleSet:
    """Deserializa IR do formato binário."""

# Vantagens MessagePack:
# - 30-50% menor que JSON
# - 2-3x mais rápido para deserializar
# - Preserva tipos de dados Python
# - Compatível com Redis
```

### JSON (Fallback)

```python
def serialize_ir_json(ruleset: CompiledRuleSet) -> str:
    """Serializa IR para JSON (desenvolvimento/debug)."""
    
# Schema JSON do IR para validação
IR_JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Compiled RuleSet IR",
    # ... definição completa do schema
}
```

## Extensibilidade

### Custom Operators

```python
class CustomOperatorRegistry:
    """Registro de operadores customizados."""
    
    def register_operator(self, name: str, impl: Callable) -> None:
        """Registra novo operador."""
        
    def compile_custom_condition(self, condition: dict) -> CompiledCondition:
        """Compila condição com operador custom."""
```

### Plugin System

```python
class IRCompilerPlugin:
    """Interface para plugins do compilador IR."""
    
    def pre_compile(self, yaml_rules: dict) -> dict:
        """Hook executado antes da compilação."""
        
    def post_compile(self, ir: CompiledRuleSet) -> CompiledRuleSet:
        """Hook executado após a compilação."""
        
    def optimize_execution_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Hook para otimizações customizadas."""
```

## Segurança e Validação

### Validação de Schema

```python
def validate_ir_integrity(ir: CompiledRuleSet) -> ValidationReport:
    """
    Valida integridade do IR compilado.
    
    Verificações:
    1. Schema version compatibility
    2. Checksum integrity  
    3. Rule ID uniqueness
    4. Field reference validity
    5. Circular dependency detection
    6. Expression safety (anti-injection)
    """
```

### Sandbox de Execução

```python
class SecureExecutionContext:
    """Contexto seguro para execução de regras."""
    
    # Limites de segurança
    MAX_EXECUTION_TIME = 5.0        # segundos
    MAX_MEMORY_USAGE = 1024         # MB
    MAX_REGEX_COMPLEXITY = 1000     # steps
    
    # Operações permitidas
    ALLOWED_FUNCTIONS = {
        'len', 'str', 'int', 'float', 'bool',
        'upper', 'lower', 'strip', 'replace'
    }
```

Esta especificação fornece a base técnica completa para implementação do sistema IR do ValidaHub, garantindo performance, segurança e manutenibilidade.