# YAML Schema → IR → Runtime Technical Specification

This document provides the complete technical specification for ValidaHub's Rule Engine, covering YAML schema definition, Intermediate Representation (IR) compilation, and runtime execution with hot-reload capabilities.

---

## File: docs/rules/yaml-schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://validahub.io/schemas/ruleset/v1.0.0",
  "title": "ValidaHub Rule Engine Schema",
  "description": "JSON Schema for YAML-based rule definitions supporting marketplace integrations",
  "type": "object",
  "required": ["schema_version", "metadata", "mapping", "rules"],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "1.0.0",
      "description": "Schema version for backward compatibility"
    },
    "metadata": {
      "type": "object",
      "required": ["marketplace", "version", "created_at"],
      "properties": {
        "marketplace": {
          "type": "string",
          "enum": ["mercadolivre", "amazon", "magalu", "shopee", "carrefour"],
          "description": "Target marketplace identifier"
        },
        "version": {
          "type": "string",
          "pattern": "^\\d+\\.\\d+\\.\\d+$",
          "description": "Semantic version (major.minor.patch)"
        },
        "created_at": {
          "type": "string",
          "format": "date-time",
          "description": "ISO 8601 timestamp of creation"
        },
        "author": {
          "type": "string",
          "maxLength": 100,
          "description": "Rule author identifier"
        },
        "description": {
          "type": "string",
          "maxLength": 500,
          "description": "Human-readable description of changes"
        },
        "breaking_changes": {
          "type": "boolean",
          "default": false,
          "description": "Indicates if version contains breaking changes"
        },
        "dependencies": {
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$"
          },
          "description": "Required compatible versions"
        }
      }
    },
    "mapping": {
      "type": "object",
      "description": "Field mapping from marketplace format to CCM",
      "required": ["field_mappings"],
      "properties": {
        "field_mappings": {
          "type": "object",
          "patternProperties": {
            "^[a-zA-Z_][a-zA-Z0-9_]*$": {
              "oneOf": [
                {
                  "type": "string",
                  "description": "Direct field mapping"
                },
                {
                  "type": "object",
                  "description": "Complex field mapping with transformation",
                  "required": ["source", "transform"],
                  "properties": {
                    "source": {
                      "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}}
                      ],
                      "description": "Source field path(s) using JSONPath"
                    },
                    "transform": {
                      "type": "string",
                      "enum": ["concatenate", "normalize_price", "extract_gtin", "format_dimensions", "clean_text", "convert_units"],
                      "description": "Transformation function to apply"
                    },
                    "parameters": {
                      "type": "object",
                      "description": "Transformation-specific parameters"
                    },
                    "default": {
                      "description": "Default value if source is null/missing"
                    },
                    "required": {
                      "type": "boolean",
                      "default": false,
                      "description": "Whether field is required in output"
                    }
                  }
                }
              ]
            }
          },
          "additionalProperties": false
        },
        "ccm_fields": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["sku", "title", "description", "brand", "gtin", "ncm", "price_brl", "currency", "stock", "weight_kg", "length_cm", "width_cm", "height_cm", "category_path", "images", "attributes"]
          },
          "description": "Target CCM fields produced by this mapping",
          "uniqueItems": true
        }
      }
    },
    "rules": {
      "type": "array",
      "description": "Validation and correction rules",
      "items": {
        "type": "object",
        "required": ["id", "name", "field", "action", "condition"],
        "properties": {
          "id": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9_-]+$",
            "maxLength": 50,
            "description": "Unique rule identifier within ruleset"
          },
          "name": {
            "type": "string",
            "maxLength": 100,
            "description": "Human-readable rule name"
          },
          "description": {
            "type": "string",
            "maxLength": 500,
            "description": "Rule purpose and behavior description"
          },
          "field": {
            "type": "string",
            "description": "Target field using JSONPath (e.g., '$.price_brl', '$.images[*]')"
          },
          "action": {
            "type": "object",
            "required": ["type"],
            "properties": {
              "type": {
                "type": "string",
                "enum": ["assert", "transform", "suggest"],
                "description": "Action type: assert=validation, transform=correction, suggest=recommendation"
              },
              "severity": {
                "type": "string",
                "enum": ["error", "warning", "info"],
                "default": "error",
                "description": "Issue severity level"
              },
              "message": {
                "type": "string",
                "maxLength": 200,
                "description": "User-facing error/warning message"
              },
              "correction": {
                "type": "object",
                "description": "Automatic correction specification (transform actions only)",
                "properties": {
                  "strategy": {
                    "type": "string",
                    "enum": ["replace", "append", "prepend", "normalize", "calculate"],
                    "description": "Correction strategy"
                  },
                  "value": {
                    "description": "Static correction value or template"
                  },
                  "template": {
                    "type": "string",
                    "description": "Template with placeholders for dynamic corrections"
                  }
                }
              },
              "suggestion": {
                "type": "object",
                "description": "Suggestion specification (suggest actions only)",
                "properties": {
                  "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Confidence score for suggestion"
                  },
                  "alternatives": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "value": {"description": "Suggested value"},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0"},
                        "rationale": {"type": "string", "maxLength": 200}
                      }
                    },
                    "maxItems": 5,
                    "description": "List of suggested alternatives"
                  }
                }
              }
            }
          },
          "condition": {
            "type": "object",
            "required": ["operator"],
            "properties": {
              "operator": {
                "type": "string",
                "enum": ["equals", "not_equals", "greater_than", "less_than", "range", "regex", "length", "exists", "type", "in", "not_in", "and", "or", "not"],
                "description": "Comparison operator"
              },
              "value": {
                "description": "Comparison value (type depends on operator)"
              },
              "values": {
                "type": "array",
                "description": "Array of values for 'in' and 'not_in' operators"
              },
              "pattern": {
                "type": "string",
                "description": "Regular expression pattern for 'regex' operator"
              },
              "min": {
                "type": "number",
                "description": "Minimum value for 'range' and 'length' operators"
              },
              "max": {
                "type": "number",
                "description": "Maximum value for 'range' and 'length' operators"
              },
              "data_type": {
                "type": "string",
                "enum": ["string", "number", "boolean", "array", "object", "null"],
                "description": "Expected data type for 'type' operator"
              },
              "conditions": {
                "type": "array",
                "items": {"$ref": "#/properties/rules/items/properties/condition"},
                "description": "Nested conditions for logical operators (and, or, not)"
              }
            }
          },
          "precedence": {
            "type": "integer",
            "minimum": 1,
            "maximum": 1000,
            "default": 100,
            "description": "Rule execution precedence (1=highest, 1000=lowest)"
          },
          "scope": {
            "type": "object",
            "description": "Rule application scope",
            "properties": {
              "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Apply rule only to specific categories"
              },
              "brands": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Apply rule only to specific brands"
              },
              "price_range": {
                "type": "object",
                "properties": {
                  "min": {"type": "number"},
                  "max": {"type": "number"}
                },
                "description": "Apply rule only within price range"
              },
              "conditions": {
                "type": "array",
                "items": {"$ref": "#/properties/rules/items/properties/condition"},
                "description": "Additional scope conditions"
              }
            }
          },
          "enabled": {
            "type": "boolean",
            "default": true,
            "description": "Whether rule is active"
          },
          "tags": {
            "type": "array",
            "items": {
              "type": "string",
              "pattern": "^[a-zA-Z0-9_-]+$"
            },
            "description": "Rule tags for organization and filtering"
          }
        }
      }
    },
    "performance": {
      "type": "object",
      "description": "Performance optimization settings",
      "properties": {
        "batch_size": {
          "type": "integer",
          "minimum": 100,
          "maximum": 10000,
          "default": 1000,
          "description": "Optimal batch size for processing"
        },
        "timeout_ms": {
          "type": "integer",
          "minimum": 1000,
          "maximum": 300000,
          "default": 30000,
          "description": "Maximum execution timeout in milliseconds"
        },
        "cache_ttl": {
          "type": "integer",
          "minimum": 300,
          "maximum": 86400,
          "default": 3600,
          "description": "Compiled rule cache TTL in seconds"
        },
        "parallel_execution": {
          "type": "boolean",
          "default": true,
          "description": "Enable parallel rule execution"
        }
      }
    }
  },
  "examples": [
    {
      "schema_version": "1.0.0",
      "metadata": {
        "marketplace": "mercadolivre",
        "version": "1.2.3",
        "created_at": "2025-08-29T10:30:00Z",
        "author": "rules-team",
        "description": "Added price validation and GTIN normalization",
        "breaking_changes": false
      },
      "mapping": {
        "field_mappings": {
          "sku": "$.id",
          "title": "$.title",
          "price_brl": {
            "source": "$.price",
            "transform": "normalize_price",
            "parameters": {"currency": "BRL"},
            "required": true
          },
          "images": {
            "source": "$.pictures[*].url",
            "transform": "clean_text",
            "default": []
          }
        },
        "ccm_fields": ["sku", "title", "price_brl", "images"]
      },
      "rules": [
        {
          "id": "price_positive",
          "name": "Price Must Be Positive",
          "description": "Ensure price is greater than zero",
          "field": "$.price_brl",
          "action": {
            "type": "assert",
            "severity": "error",
            "message": "Price must be greater than zero"
          },
          "condition": {
            "operator": "greater_than",
            "value": 0
          },
          "precedence": 10
        },
        {
          "id": "title_length",
          "name": "Title Length Validation",
          "field": "$.title",
          "action": {
            "type": "transform",
            "severity": "warning",
            "message": "Title truncated to 60 characters",
            "correction": {
              "strategy": "replace",
              "template": "{{value | truncate(60)}}"
            }
          },
          "condition": {
            "operator": "length",
            "max": 60
          },
          "precedence": 50
        }
      ]
    }
  ]
}
```

---

## File: docs/rules/ir-spec.md

# Intermediate Representation (IR) Specification

## Overview

The IR (Intermediate Representation) is a compiled, optimized format of YAML rules designed for high-performance runtime execution. It provides deterministic compilation output, version stability, and efficient execution patterns.

## IR Structure

### Core IR Schema

```typescript
interface RuleSetIR {
  schema_version: string;           // "1.0.0"
  checksum: string;                 // SHA-256 hash of source YAML + compiler version
  compiled_at: string;              // ISO 8601 timestamp
  compiler_version: string;         // Compiler version used
  source_version: string;           // Source ruleset semantic version
  metadata: IRMetadata;
  mapping: IRMapping;
  rules: IRRule[];
  execution_plan: ExecutionPlan;
  performance_profile: PerformanceProfile;
}

interface IRMetadata {
  marketplace: string;
  original_rule_count: number;
  optimized_rule_count: number;
  field_dependencies: string[];     // List of required input fields
  output_fields: string[];          // List of output CCM fields
  breaking_changes: boolean;
  compatibility_hash: string;       // Hash for compatibility checking
}

interface IRMapping {
  transformations: IRTransformation[];
  field_map: Record<string, FieldMapping>;
  dependency_order: string[];       // Topologically sorted field processing order
}

interface IRTransformation {
  id: string;
  source_fields: string[];
  target_field: string;
  function_name: string;            // Compiled function reference
  parameters: Record<string, any>;
  default_value?: any;
  required: boolean;
}

interface IRRule {
  id: string;
  name: string;
  field_path: CompiledPath;         // Optimized JSONPath
  action_type: "assert" | "transform" | "suggest";
  severity: "error" | "warning" | "info";
  condition: CompiledCondition;
  correction?: CompiledCorrection;
  suggestion?: CompiledSuggestion;
  precedence: number;
  scope: CompiledScope;
  execution_cost: number;           // Estimated microseconds
  dependencies: string[];           // Other rule IDs this depends on
}

interface CompiledPath {
  expression: string;               // Original JSONPath
  ast: PathAST;                    // Parsed abstract syntax tree
  accessor_function: string;        // Compiled accessor function name
  is_array: boolean;
  is_deep: boolean;                // Whether path traverses nested objects
  cost_estimate: number;           // Execution cost in microseconds
}

interface CompiledCondition {
  operator: string;
  evaluator_function: string;      // Compiled evaluator function name
  parameters: any[];               // Pre-processed parameters
  short_circuit: boolean;          // Can short-circuit evaluation
  cost_estimate: number;
  sub_conditions?: CompiledCondition[];
}

interface ExecutionPlan {
  phases: ExecutionPhase[];
  parallel_groups: ParallelGroup[];
  short_circuit_rules: string[];   // Rules that can terminate early
  field_processors: FieldProcessor[];
}

interface ExecutionPhase {
  phase_name: string;              // "mapping", "validation", "correction", "suggestion"
  rules: string[];                 // Rule IDs in execution order
  can_parallelize: boolean;
  estimated_duration_us: number;
}

interface ParallelGroup {
  group_id: string;
  rule_ids: string[];
  estimated_speedup: number;       // Expected parallel speedup factor
}

interface FieldProcessor {
  field_path: string;
  processors: ProcessorChain[];
  batch_optimized: boolean;
}

interface ProcessorChain {
  function_name: string;
  parameters: any[];
  vectorizable: boolean;           // Can use SIMD/vectorized operations
}
```

### Expression Normalization

All JSONPath expressions are normalized to canonical form:

```typescript
interface PathAST {
  type: "root" | "property" | "index" | "slice" | "recursive" | "filter" | "union";
  value?: string | number;
  children?: PathAST[];
  filter_expression?: CompiledCondition;
}

// Example normalization:
// Input:  "$.products[*].price", "$['products'][*]['price']", "$.products.*.price"
// Output: "$.products[*].price" (canonical form)
```

### Checksum Calculation

The IR checksum ensures cache invalidation when source changes:

```python
def normalize_yaml(yaml_content: str) -> str:
    """Normalize YAML for deterministic comparison.
    
    This ensures the same logical YAML produces the same checksum regardless
    of formatting differences like whitespace, key ordering, or comments.
    """
    import yaml
    import json
    
    # Parse YAML to Python objects
    data = yaml.safe_load(yaml_content)
    
    # Convert to JSON with sorted keys for deterministic output
    # JSON ensures consistent formatting and key ordering
    normalized = json.dumps(data, sort_keys=True, separators=(',', ':'))
    
    return normalized

def calculate_checksum(yaml_content: str, compiler_version: str) -> str:
    """Calculate deterministic checksum for IR."""
    normalized_yaml = normalize_yaml(yaml_content)
    combined = f"{normalized_yaml}|{compiler_version}"
    return hashlib.sha256(combined.encode()).hexdigest()
```

## Compilation Process

### Phase 1: Parse & Validate

```python
def compile_phase_1(yaml_content: str) -> ParsedRuleSet:
    """Parse YAML and validate against schema."""
    # 1. Parse YAML
    ruleset = yaml.safe_load(yaml_content)
    
    # 2. Validate against JSON Schema
    validate_schema(ruleset, RULESET_SCHEMA)
    
    # 3. Semantic validation
    validate_field_references(ruleset)
    validate_rule_dependencies(ruleset)
    
    return ParsedRuleSet(ruleset)
```

### Phase 2: Optimize & Normalize

```python
def compile_phase_2(parsed: ParsedRuleSet) -> OptimizedRuleSet:
    """Optimize rules for performance."""
    optimizations = [
        deduplicate_conditions,      # Remove duplicate condition logic
        merge_field_rules,           # Combine rules on same field
        optimize_precedence,         # Reorder for efficiency
        compile_jsonpath,           # Pre-compile JSONPath expressions
        vectorize_operations,        # Identify vectorizable operations
        calculate_costs,            # Estimate execution costs
    ]
    
    optimized = parsed
    for optimization in optimizations:
        optimized = optimization(optimized)
    
    return optimized
```

### Phase 3: Generate IR

```python
def compile_phase_3(optimized: OptimizedRuleSet) -> RuleSetIR:
    """Generate final IR representation."""
    return RuleSetIR(
        checksum=calculate_checksum(optimized.source, COMPILER_VERSION),
        mapping=compile_mapping(optimized.mapping),
        rules=compile_rules(optimized.rules),
        execution_plan=generate_execution_plan(optimized),
        performance_profile=estimate_performance(optimized)
    )
```

## Version Compatibility

### SemVer Compatibility Rules

```python
class VersionCompatibility:
    def is_compatible(self, from_version: str, to_version: str) -> bool:
        """Check if versions are compatible."""
        from_ver = parse_version(from_version)
        to_ver = parse_version(to_version)
        
        # Major version changes are never compatible
        if from_ver.major != to_ver.major:
            return False
            
        # Minor version increases are backward compatible
        if to_ver.minor > from_ver.minor:
            return True
            
        # Same minor, patch increases are compatible
        if (to_ver.minor == from_ver.minor and 
            to_ver.patch >= from_ver.patch):
            return True
            
        return False
    
    def migration_required(self, from_ir: RuleSetIR, to_ir: RuleSetIR) -> bool:
        """Check if IR migration is required."""
        # Different schema versions require migration
        if from_ir.schema_version != to_ir.schema_version:
            return True
            
        # Breaking changes require migration
        if to_ir.metadata.breaking_changes:
            return True
            
        # Incompatible field dependencies require migration
        from_fields = set(from_ir.metadata.field_dependencies)
        to_fields = set(to_ir.metadata.field_dependencies)
        if not from_fields.issubset(to_fields):
            return True
            
        return False
```

### IR Migration Strategy

```python
class IRMigrator:
    def migrate(self, from_ir: RuleSetIR, to_ir: RuleSetIR) -> RuleSetIR:
        """Migrate IR between versions."""
        if not self.can_migrate(from_ir, to_ir):
            raise IncompatibleVersionError()
            
        migration_plan = self.create_migration_plan(from_ir, to_ir)
        return self.execute_migration(migration_plan)
    
    def create_migration_plan(self, from_ir: RuleSetIR, to_ir: RuleSetIR) -> MigrationPlan:
        """Create step-by-step migration plan."""
        return MigrationPlan([
            UpdateSchemaVersion(),
            MigrateFieldMappings(),
            UpdateRuleConditions(),
            RecalculateExecutionPlan(),
            ValidateMigratedIR()
        ])
```

## Performance Optimizations

### Precedence-Based Execution

Rules are executed in precedence order with early termination:

```python
def execute_rules_by_precedence(ir: RuleSetIR, data: dict) -> ExecutionResult:
    """Execute rules in precedence order with short-circuiting."""
    results = []
    
    # Group rules by precedence
    precedence_groups = group_by_precedence(ir.rules)
    
    for precedence, rules in precedence_groups:
        group_results = []
        
        for rule in rules:
            result = execute_rule(rule, data)
            group_results.append(result)
            
            # Short-circuit on critical errors
            if result.severity == "error" and rule.action_type == "assert":
                if should_short_circuit(rule, ir.execution_plan):
                    results.extend(group_results)
                    return ExecutionResult(results, short_circuited=True)
        
        results.extend(group_results)
    
    return ExecutionResult(results)
```

### Field-Level Short-Circuiting

Optimize field access patterns:

```python
class FieldAccessOptimizer:
    def optimize_field_access(self, rules: List[IRRule]) -> Dict[str, List[IRRule]]:
        """Group rules by field for optimized access."""
        field_groups = defaultdict(list)
        
        for rule in rules:
            field_path = rule.field_path.expression
            field_groups[field_path].append(rule)
        
        # Sort each group by precedence
        for field_path, field_rules in field_groups.items():
            field_rules.sort(key=lambda r: r.precedence)
        
        return field_groups
    
    def execute_field_rules(self, field_path: str, rules: List[IRRule], data: dict) -> List[ExecutionResult]:
        """Execute all rules for a field with single data access."""
        # Single field access
        field_value = access_field(data, field_path)
        results = []
        
        for rule in rules:
            # Use cached field value
            result = execute_rule_with_value(rule, field_value)
            results.append(result)
            
            # Early termination on error
            if result.severity == "error" and rule.action_type == "assert":
                break
        
        return results
```

### Batch Vectorization

Vectorize operations for large datasets:

```python
class BatchVectorizer:
    def vectorize_execution(self, ir: RuleSetIR, data_batch: List[dict]) -> BatchExecutionResult:
        """Execute rules on batch with vectorization."""
        vectorizable_rules = [r for r in ir.rules if self.can_vectorize(r)]
        scalar_rules = [r for r in ir.rules if not self.can_vectorize(r)]
        
        # Vectorized execution for compatible rules
        vector_results = self.execute_vectorized(vectorizable_rules, data_batch)
        
        # Scalar execution for complex rules
        scalar_results = []
        for data_row in data_batch:
            row_results = self.execute_scalar(scalar_rules, data_row)
            scalar_results.append(row_results)
        
        return BatchExecutionResult.combine(vector_results, scalar_results)
    
    def can_vectorize(self, rule: IRRule) -> bool:
        """Check if rule can be vectorized."""
        # Simple conditions on primitive fields can be vectorized
        return (
            rule.field_path.is_array == False and
            rule.field_path.is_deep == False and
            rule.condition.operator in ["equals", "greater_than", "less_than", "range"] and
            rule.action_type == "assert"
        )
```

## Caching Strategy

### Cache Key Generation

```python
def generate_cache_key(tenant_id: str, marketplace: str, version: str) -> str:
    """Generate deterministic cache key."""
    return f"ir:v1:{tenant_id}:{marketplace}:{version}"

def generate_checksum_key(checksum: str) -> str:
    """Generate checksum-based cache key."""
    return f"ir:checksum:{checksum}"
```

### Hot-Reload Implementation

```python
class HotReloadManager:
    def __init__(self, cache: Cache, compiler: RuleCompiler):
        self.cache = cache
        self.compiler = compiler
        self.reload_listeners = []
    
    def check_for_updates(self, cache_key: str) -> bool:
        """Check if IR needs updating."""
        cached_ir = self.cache.get(cache_key)
        if not cached_ir:
            return True
            
        # Check if source YAML has changed
        source_checksum = self.get_source_checksum(cache_key)
        if source_checksum != cached_ir.checksum:
            return True
            
        return False
    
    def reload_rules(self, cache_key: str, yaml_content: str) -> RuleSetIR:
        """Hot-reload rules with checksum invalidation."""
        # Compile new IR
        new_ir = self.compiler.compile(yaml_content)
        
        # Update cache
        old_ir = self.cache.get(cache_key)
        self.cache.set(cache_key, new_ir)
        
        # Notify listeners
        for listener in self.reload_listeners:
            listener.on_rules_reloaded(old_ir, new_ir)
        
        return new_ir
    
    def invalidate_related_caches(self, ir: RuleSetIR):
        """Invalidate related cache entries."""
        patterns = [
            f"execution:*:{ir.checksum}",
            f"results:*:{ir.source_version}",
            f"stats:*:{ir.metadata.marketplace}"
        ]
        
        for pattern in patterns:
            self.cache.delete_pattern(pattern)
```

---

## File: docs/rules/runtime.md

# Runtime Execution Engine

## Overview

The Runtime Execution Engine processes compiled IR rules against CSV data with high performance, supporting 50,000+ lines in under 3 seconds through optimized algorithms and parallel processing.

## Core Runtime Architecture

### Execution Engine Interface

```python
class RuleExecutionEngine:
    """High-performance rule execution engine."""
    
    def __init__(self, config: EngineConfig):
        self.config = config
        self.thread_pool = ThreadPoolExecutor(max_workers=config.max_threads)
        self.metrics = ExecutionMetrics()
        self.cache = LRUCache(maxsize=config.cache_size)
    
    def execute(self, ir: RuleSetIR, data: List[dict]) -> ExecutionResult:
        """Execute rules against data with performance optimization."""
        with self.metrics.timer("total_execution"):
            # Phase 1: Data preprocessing
            preprocessed_data = self.preprocess_data(data, ir)
            
            # Phase 2: Mapping transformation
            ccm_data = self.apply_mapping(preprocessed_data, ir.mapping)
            
            # Phase 3: Rule execution
            results = self.execute_rules(ccm_data, ir.rules, ir.execution_plan)
            
            # Phase 4: Post-processing
            return self.postprocess_results(results, ir)
```

### Data Preprocessing

```python
def preprocess_data(self, data: List[dict], ir: RuleSetIR) -> PreprocessedData:
    """Preprocess data for optimal execution."""
    
    # Extract only required fields
    required_fields = ir.metadata.field_dependencies
    filtered_data = []
    
    for row in data:
        filtered_row = {field: row.get(field) for field in required_fields}
        filtered_data.append(filtered_row)
    
    # Build field access indexes
    field_indexes = self.build_field_indexes(filtered_data, ir)
    
    # Detect data patterns for optimization
    patterns = self.analyze_data_patterns(filtered_data)
    
    return PreprocessedData(
        data=filtered_data,
        field_indexes=field_indexes,
        patterns=patterns,
        row_count=len(filtered_data)
    )

def build_field_indexes(self, data: List[dict], ir: RuleSetIR) -> Dict[str, FieldIndex]:
    """Build indexes for frequently accessed fields."""
    indexes = {}
    
    for rule in ir.rules:
        field_path = rule.field_path.expression
        
        # Build index for fields accessed by multiple rules
        access_count = sum(1 for r in ir.rules if r.field_path.expression == field_path)
        if access_count > 1:
            indexes[field_path] = FieldIndex.build(data, field_path)
    
    return indexes
```

### Mapping Execution

```python
def apply_mapping(self, data: PreprocessedData, mapping: IRMapping) -> List[dict]:
    """Transform marketplace data to CCM format."""
    ccm_data = []
    
    # Process transformations in dependency order
    for row in data.data:
        ccm_row = {}
        
        for field in mapping.dependency_order:
            transformation = mapping.field_map[field]
            
            try:
                # Apply transformation
                value = self.apply_transformation(row, transformation)
                ccm_row[field] = value
                
            except TransformationError as e:
                # Handle transformation failure
                if transformation.required:
                    raise MappingError(f"Required field {field}: {e}")
                else:
                    ccm_row[field] = transformation.default_value
        
        ccm_data.append(ccm_row)
    
    return ccm_data

def apply_transformation(self, row: dict, transformation: IRTransformation) -> Any:
    """Apply single field transformation."""
    function_name = transformation.function_name
    parameters = transformation.parameters
    
    # Get transformation function from registry
    transform_func = TRANSFORMATION_REGISTRY[function_name]
    
    # Extract source values
    source_values = []
    for source_field in transformation.source_fields:
        value = jsonpath_extract(row, source_field)
        source_values.append(value)
    
    # Apply transformation
    return transform_func(*source_values, **parameters)
```

### Rule Execution Algorithms

#### Precedence-Ordered Execution

```python
def execute_rules(self, data: List[dict], rules: List[IRRule], plan: ExecutionPlan) -> List[RuleResult]:
    """Execute rules following execution plan."""
    all_results = []
    
    for phase in plan.phases:
        phase_rules = [r for r in rules if r.id in phase.rules]
        
        if phase.can_parallelize and len(data) > self.config.parallel_threshold:
            # Parallel execution for large datasets
            phase_results = self.execute_parallel(data, phase_rules)
        else:
            # Sequential execution
            phase_results = self.execute_sequential(data, phase_rules)
        
        all_results.extend(phase_results)
        
        # Check for early termination
        if self.should_terminate_early(phase_results, plan):
            break
    
    return all_results

def execute_sequential(self, data: List[dict], rules: List[IRRule]) -> List[RuleResult]:
    """Sequential rule execution with field optimization."""
    results = []
    
    # Group rules by field for optimized access
    field_groups = group_rules_by_field(rules)
    
    for row_idx, row in enumerate(data):
        row_results = []
        
        for field_path, field_rules in field_groups.items():
            # Single field access for all rules on this field
            field_value = self.access_field_cached(row, field_path, row_idx)
            
            for rule in field_rules:
                result = self.execute_rule_with_value(rule, field_value, row_idx)
                row_results.append(result)
                
                # Short-circuit on critical errors
                if self.should_short_circuit(result, rule):
                    break
        
        results.extend(row_results)
    
    return results
```

#### Parallel Execution

```python
def execute_parallel(self, data: List[dict], rules: List[IRRule]) -> List[RuleResult]:
    """Parallel rule execution for large datasets."""
    
    # Determine optimal chunk size
    chunk_size = min(
        self.config.max_chunk_size,
        max(len(data) // self.config.max_threads, self.config.min_chunk_size)
    )
    
    # Split data into chunks
    chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
    
    # Submit parallel tasks
    futures = []
    for chunk_idx, chunk in enumerate(chunks):
        future = self.thread_pool.submit(
            self.execute_chunk,
            chunk,
            rules,
            chunk_idx * chunk_size  # Row offset
        )
        futures.append(future)
    
    # Collect results
    all_results = []
    for future in concurrent.futures.as_completed(futures):
        chunk_results = future.result()
        all_results.extend(chunk_results)
    
    return all_results

def execute_chunk(self, chunk: List[dict], rules: List[IRRule], row_offset: int) -> List[RuleResult]:
    """Execute rules on a data chunk."""
    results = []
    
    for local_idx, row in enumerate(chunk):
        global_idx = row_offset + local_idx
        
        for rule in rules:
            result = self.execute_single_rule(rule, row, global_idx)
            results.append(result)
    
    return results
```

#### Batch Vectorization

```python
class VectorizedExecutor:
    """Vectorized rule execution using NumPy."""
    
    def __init__(self):
        import numpy as np
        import pandas as pd
        self.np = np
        self.pd = pd
    
    def execute_vectorized(self, rules: List[IRRule], data: List[dict]) -> List[RuleResult]:
        """Execute compatible rules using vectorized operations."""
        
        # Convert to DataFrame for vectorized operations
        df = self.pd.DataFrame(data)
        results = []
        
        # Group vectorizable rules
        vectorizable = [r for r in rules if self.can_vectorize(r)]
        
        for rule in vectorizable:
            field_name = self.extract_field_name(rule.field_path)
            
            if field_name not in df.columns:
                # Handle missing field
                results.extend(self.create_missing_field_results(rule, len(data)))
                continue
            
            field_values = df[field_name].values
            
            # Apply vectorized condition
            if rule.condition.operator == "greater_than":
                mask = field_values > rule.condition.parameters[0]
            elif rule.condition.operator == "less_than":
                mask = field_values < rule.condition.parameters[0]
            elif rule.condition.operator == "equals":
                mask = field_values == rule.condition.parameters[0]
            elif rule.condition.operator == "range":
                min_val, max_val = rule.condition.parameters[:2]
                mask = (field_values >= min_val) & (field_values <= max_val)
            else:
                # Fallback to scalar execution
                continue
            
            # Create results from mask
            rule_results = self.mask_to_results(rule, mask, field_values)
            results.extend(rule_results)
        
        return results
    
    def can_vectorize(self, rule: IRRule) -> bool:
        """Check if rule can be executed with vectorized operations."""
        return (
            rule.action_type == "assert" and
            not rule.field_path.is_deep and
            not rule.field_path.is_array and
            rule.condition.operator in ["greater_than", "less_than", "equals", "range"]
        )
```

### Field Access Optimization

```python
class FieldAccessCache:
    """Cache for optimizing repeated field access."""
    
    def __init__(self, max_size: int = 10000):
        self.cache = {}
        self.max_size = max_size
        self.access_count = defaultdict(int)
    
    def access_field(self, row: dict, field_path: str, row_idx: int) -> Any:
        """Access field with caching."""
        cache_key = (row_idx, field_path)
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Extract field value
        value = jsonpath_extract(row, field_path)
        
        # Cache if frequently accessed
        self.access_count[field_path] += 1
        if self.access_count[field_path] > 3 and len(self.cache) < self.max_size:
            self.cache[cache_key] = value
        
        return value
    
    def clear_row(self, row_idx: int):
        """Clear cache entries for processed row."""
        keys_to_remove = [k for k in self.cache.keys() if k[0] == row_idx]
        for key in keys_to_remove:
            del self.cache[key]

def jsonpath_extract(data: dict, path: str) -> Any:
    """Optimized JSONPath extraction."""
    # Use compiled JSONPath for performance
    if path.startswith("$.") and "." not in path[2:] and "[" not in path:
        # Simple field access optimization
        field_name = path[2:]
        return data.get(field_name)
    
    # Use full JSONPath for complex expressions
    return jsonpath_ng.parse(path).find(data)
```

### Performance Monitoring

```python
class ExecutionMetrics:
    """Performance metrics collection."""
    
    def __init__(self):
        self.timers = {}
        self.counters = defaultdict(int)
        self.histograms = defaultdict(list)
    
    @contextmanager
    def timer(self, name: str):
        """Context manager for timing operations."""
        start_time = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start_time
            self.histograms[name].append(duration * 1000)  # Convert to ms
    
    def increment(self, counter: str, value: int = 1):
        """Increment counter."""
        self.counters[counter] += value
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        summary = {
            "counters": dict(self.counters),
            "timing_ms": {}
        }
        
        for name, values in self.histograms.items():
            if values:
                summary["timing_ms"][name] = {
                    "count": len(values),
                    "mean": sum(values) / len(values),
                    "p95": sorted(values)[int(len(values) * 0.95)],
                    "p99": sorted(values)[int(len(values) * 0.99)],
                    "max": max(values)
                }
        
        return summary
```

### Error Handling & Recovery

```python
class ExecutionErrorHandler:
    """Handles execution errors with recovery strategies."""
    
    def handle_rule_error(self, rule: IRRule, error: Exception, row_idx: int) -> RuleResult:
        """Handle individual rule execution error."""
        if isinstance(error, FieldNotFoundError):
            # Missing field - return appropriate result based on rule type
            if rule.action_type == "assert":
                return RuleResult.error(rule.id, f"Required field missing: {rule.field_path}", row_idx)
            else:
                return RuleResult.skip(rule.id, "Field not available", row_idx)
        
        elif isinstance(error, ConditionEvaluationError):
            # Condition evaluation failed
            return RuleResult.error(rule.id, f"Condition evaluation failed: {error}", row_idx)
        
        elif isinstance(error, TransformationError):
            # Transformation failed
            if rule.action_type == "transform":
                return RuleResult.warning(rule.id, f"Transformation failed: {error}", row_idx)
            else:
                return RuleResult.error(rule.id, f"Action failed: {error}", row_idx)
        
        else:
            # Unexpected error
            return RuleResult.error(rule.id, f"Unexpected error: {error}", row_idx)
    
    def should_continue(self, error: Exception, config: EngineConfig) -> bool:
        """Determine if execution should continue after error."""
        if config.fail_fast and isinstance(error, CriticalError):
            return False
        
        if isinstance(error, (MemoryError, SystemExit, KeyboardInterrupt)):
            return False
        
        return True
```

---

## File: tests/golden/README.md

# Golden Tests for Rule Engine

Golden tests ensure that rule engine outputs remain consistent across versions and prevent unintended changes to transformation logic.

## Directory Structure

```
tests/golden/
├── README.md                      # This file
├── fixtures/
│   ├── input/                     # Input CSV files by marketplace
│   │   ├── mercadolivre/
│   │   │   ├── basic_products.csv
│   │   │   ├── complex_products.csv
│   │   │   └── edge_cases.csv
│   │   ├── amazon/
│   │   │   ├── basic_products.csv
│   │   │   └── variations.csv
│   │   ├── magalu/
│   │   │   └── catalog_export.csv
│   │   └── shared/
│   │       └── empty_dataset.csv
│   └── expected/                  # Expected output after processing
│       ├── mercadolivre/
│       │   ├── v1.0.0/
│       │   │   ├── basic_products_output.csv
│       │   │   ├── basic_products_corrections.json
│       │   │   └── basic_products_suggestions.json
│       │   └── v1.1.0/
│       │       └── ...
│       ├── amazon/
│       └── magalu/
├── rulesets/                      # Rule definitions for testing
│   ├── mercadolivre/
│   │   ├── v1.0.0/
│   │   │   ├── mapping.yaml
│   │   │   └── rules.yaml
│   │   └── v1.1.0/
│   └── amazon/
└── test_golden.py                 # Golden test runner
```

## Test Fixtures

### Input Data Examples

#### `tests/golden/fixtures/input/mercadolivre/basic_products.csv`

```csv
id,title,price,pictures,category_id,attributes,brand
MLB123,iPhone 14 Pro Max,4999.99,"[{""url"": ""https://img1.jpg""}, {""url"": ""https://img2.jpg""}]",MLB1055,"{""color"": ""Space Gray"", ""storage"": ""256GB""}",Apple
MLB124,Samsung Galaxy S23,2799.00,"[{""url"": ""https://img3.jpg""}]",MLB1055,"{""color"": ""Phantom Black"", ""storage"": ""128GB""}",Samsung  
MLB125,,1599.99,"[]",MLB1055,"{""storage"": ""64GB""}",
MLB126,Redmi Note 12,-100,"[{""url"": ""invalid-url""}]",MLB1055,"{""color"": ""Blue""}",Xiaomi
MLB127,Moto G Power,899.99,"[{""url"": ""https://img4.jpg""}, {""url"": ""https://img5.jpg""}, {""url"": ""https://img6.jpg""}]",MLB1055,"{""brand"": ""Motorola""}",Motorola
```

#### `tests/golden/fixtures/input/mercadolivre/edge_cases.csv`

```csv
id,title,price,pictures,category_id,attributes,brand
MLB200,"Product with ""quotes"" and special chars âéî",299.99,"[{""url"": ""https://example.com/img.jpg""}]",MLB1055,"{}",Test Brand
MLB201,   Whitespace Product   ,0,"[{""url"": """"}]",MLB1055,"{""invalid_json"": }",
MLB202,Very Long Title That Exceeds The Maximum Character Limit And Should Be Truncated To Fit Within The Rules,19.99,"[{""url"": ""https://example.com/very-long-url-that-might-cause-issues.jpg""}]",MLB1055,"{""description"": ""This is a very long description that might need special handling""}",Brand
MLB203,=SUM(A1:A10),1000,"[{""url"": ""javascript:alert('xss')""}]",MLB1055,"{""formula"": ""=1+1""}",Excel
MLB204,NULL,null,"null",null,null,null
```

### Expected Output Examples

#### `tests/golden/fixtures/expected/mercadolivre/v1.0.0/basic_products_output.csv`

```csv
sku,title,description,brand,gtin,ncm,price_brl,currency,stock,weight_kg,length_cm,width_cm,height_cm,category_path,images,attributes
MLB123,iPhone 14 Pro Max,,Apple,,85171200,4999.99,BRL,,,,,,Celulares e Smartphones,"[""https://img1.jpg"",""https://img2.jpg""]","{""color"": ""Space Gray"", ""storage"": ""256GB""}"
MLB124,Samsung Galaxy S23,,Samsung,,85171200,2799.00,BRL,,,,,,Celulares e Smartphones,"[""https://img3.jpg""]","{""color"": ""Phantom Black"", ""storage"": ""128GB""}"
MLB125,Smartphone 64GB,,Unknown,,85171200,1599.99,BRL,,,,,,Celulares e Smartphones,[],"{ ""storage"": ""64GB""}"
MLB126,Redmi Note 12,,Xiaomi,,85171200,0.00,BRL,,,,,,Celulares e Smartphones,[],"{""color"": ""Blue""}"
MLB127,Moto G Power,,Motorola,,85171200,899.99,BRL,,,,,,Celulares e Smartphones,"[""https://img4.jpg"",""https://img5.jpg"",""https://img6.jpg""]","{""brand"": ""Motorola""}"
```

#### `tests/golden/fixtures/expected/mercadolivre/v1.0.0/basic_products_corrections.json`

```json
{
  "corrections": [
    {
      "row": 2,
      "field": "title",
      "original_value": "",
      "corrected_value": "Smartphone 64GB",
      "rule_id": "title_required",
      "correction_type": "generate_from_attributes",
      "timestamp": "2025-08-29T10:30:00Z"
    },
    {
      "row": 2,
      "field": "brand",
      "original_value": "",
      "corrected_value": "Unknown",
      "rule_id": "brand_default",
      "correction_type": "default_value",
      "timestamp": "2025-08-29T10:30:00Z"
    },
    {
      "row": 3,
      "field": "price_brl",
      "original_value": -100,
      "corrected_value": 0.00,
      "rule_id": "price_positive",
      "correction_type": "clamp_minimum",
      "timestamp": "2025-08-29T10:30:00Z"
    }
  ],
  "summary": {
    "total_corrections": 3,
    "correction_types": {
      "generate_from_attributes": 1,
      "default_value": 1,
      "clamp_minimum": 1
    },
    "affected_rows": [2, 3]
  }
}
```

#### `tests/golden/fixtures/expected/mercadolivre/v1.0.0/basic_products_suggestions.json`

```json
{
  "suggestions": [
    {
      "row": 4,
      "field": "images",
      "current_value": ["https://img4.jpg", "https://img5.jpg", "https://img6.jpg"],
      "suggestion_type": "optimization",
      "confidence": 0.85,
      "description": "Consider reducing to 2 images for better performance",
      "proposed_value": ["https://img4.jpg", "https://img5.jpg"],
      "rule_id": "images_optimization"
    }
  ]
}
```

## Test Implementation

### `tests/golden/test_golden.py`

```python
"""Golden tests for rule engine validation."""

import json
import csv
import pytest
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass

from src.rules.compiler import RuleCompiler
from src.rules.runtime import RuleExecutionEngine
from src.rules.ir import RuleSetIR


@dataclass
class GoldenTestCase:
    """Represents a single golden test case."""
    marketplace: str
    version: str
    input_file: Path
    expected_output: Path
    expected_corrections: Path
    expected_suggestions: Path
    ruleset_path: Path


class GoldenTestRunner:
    """Runs golden tests for rule engine."""
    
    def __init__(self):
        self.fixtures_dir = Path(__file__).parent / "fixtures"
        self.compiler = RuleCompiler()
        self.engine = RuleExecutionEngine()
    
    def discover_test_cases(self) -> List[GoldenTestCase]:
        """Discover all golden test cases."""
        test_cases = []
        
        input_dir = self.fixtures_dir / "input"
        expected_dir = self.fixtures_dir / "expected"
        rulesets_dir = Path(__file__).parent / "rulesets"
        
        for marketplace_dir in input_dir.iterdir():
            if not marketplace_dir.is_dir():
                continue
                
            marketplace = marketplace_dir.name
            
            # Find all input files for this marketplace
            for input_file in marketplace_dir.glob("*.csv"):
                test_name = input_file.stem
                
                # Find corresponding expected outputs for all versions
                marketplace_expected = expected_dir / marketplace
                if not marketplace_expected.exists():
                    continue
                
                for version_dir in marketplace_expected.iterdir():
                    if not version_dir.is_dir():
                        continue
                    
                    version = version_dir.name
                    
                    # Check if all expected files exist
                    expected_output = version_dir / f"{test_name}_output.csv"
                    expected_corrections = version_dir / f"{test_name}_corrections.json"
                    expected_suggestions = version_dir / f"{test_name}_suggestions.json"
                    ruleset_path = rulesets_dir / marketplace / version
                    
                    if all(p.exists() for p in [expected_output, expected_corrections, expected_suggestions, ruleset_path]):
                        test_cases.append(GoldenTestCase(
                            marketplace=marketplace,
                            version=version,
                            input_file=input_file,
                            expected_output=expected_output,
                            expected_corrections=expected_corrections,
                            expected_suggestions=expected_suggestions,
                            ruleset_path=ruleset_path
                        ))
        
        return test_cases
    
    def load_ruleset(self, ruleset_path: Path) -> RuleSetIR:
        """Load and compile ruleset from YAML files."""
        mapping_file = ruleset_path / "mapping.yaml"
        rules_file = ruleset_path / "rules.yaml"
        
        # Combine mapping and rules into single ruleset
        import yaml
        
        with open(mapping_file) as f:
            mapping_yaml = yaml.safe_load(f)
        
        with open(rules_file) as f:
            rules_yaml = yaml.safe_load(f)
        
        # Merge into complete ruleset
        combined_ruleset = {
            "schema_version": "1.0.0",
            "metadata": rules_yaml.get("metadata", {}),
            "mapping": mapping_yaml,
            "rules": rules_yaml.get("rules", [])
        }
        
        # Compile to IR
        return self.compiler.compile(yaml.dump(combined_ruleset))
    
    def load_input_data(self, input_file: Path) -> List[Dict[str, Any]]:
        """Load input CSV data."""
        data = []
        with open(input_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(dict(row))
        return data
    
    def load_expected_output(self, output_file: Path) -> List[Dict[str, Any]]:
        """Load expected CSV output."""
        return self.load_input_data(output_file)
    
    def load_expected_json(self, json_file: Path) -> Dict[str, Any]:
        """Load expected JSON data."""
        with open(json_file, encoding='utf-8') as f:
            return json.load(f)
    
    def normalize_csv_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize CSV data for comparison."""
        normalized = []
        for row in data:
            # Remove empty string values and normalize types
            normalized_row = {}
            for key, value in row.items():
                if value == '':
                    normalized_row[key] = None
                elif key in ['price_brl', 'weight_kg', 'length_cm', 'width_cm', 'height_cm']:
                    # Normalize numeric fields
                    try:
                        normalized_row[key] = float(value) if value is not None else None
                    except (ValueError, TypeError):
                        normalized_row[key] = value
                else:
                    normalized_row[key] = value
            normalized.append(normalized_row)
        return normalized
    
    def run_test_case(self, test_case: GoldenTestCase) -> Dict[str, Any]:
        """Run a single golden test case."""
        # Load inputs
        ruleset = self.load_ruleset(test_case.ruleset_path)
        input_data = self.load_input_data(test_case.input_file)
        
        # Execute rules
        result = self.engine.execute(ruleset, input_data)
        
        # Load expected results
        expected_output = self.load_expected_output(test_case.expected_output)
        expected_corrections = self.load_expected_json(test_case.expected_corrections)
        expected_suggestions = self.load_expected_json(test_case.expected_suggestions)
        
        # Compare results
        actual_output = self.normalize_csv_data(result.output_data)
        expected_output_normalized = self.normalize_csv_data(expected_output)
        
        return {
            "test_case": test_case,
            "passed": (
                actual_output == expected_output_normalized and
                result.corrections == expected_corrections["corrections"] and
                result.suggestions == expected_suggestions["suggestions"]
            ),
            "actual_output": actual_output,
            "expected_output": expected_output_normalized,
            "actual_corrections": result.corrections,
            "expected_corrections": expected_corrections["corrections"],
            "actual_suggestions": result.suggestions,
            "expected_suggestions": expected_suggestions["suggestions"]
        }


# Pytest integration
@pytest.fixture
def golden_runner():
    """Fixture providing golden test runner."""
    return GoldenTestRunner()


@pytest.mark.golden
def test_all_golden_cases(golden_runner):
    """Test all discovered golden test cases."""
    test_cases = golden_runner.discover_test_cases()
    
    if not test_cases:
        pytest.skip("No golden test cases found")
    
    failed_cases = []
    
    for test_case in test_cases:
        result = golden_runner.run_test_case(test_case)
        
        if not result["passed"]:
            failed_cases.append({
                "marketplace": test_case.marketplace,
                "version": test_case.version,
                "input_file": test_case.input_file.name,
                "differences": golden_runner.get_differences(result)
            })
    
    if failed_cases:
        failure_summary = "\n".join([
            f"FAILED: {case['marketplace']} {case['version']} - {case['input_file']}"
            for case in failed_cases
        ])
        pytest.fail(f"Golden tests failed:\n{failure_summary}")


@pytest.mark.golden
@pytest.mark.parametrize("marketplace", ["mercadolivre", "amazon", "magalu"])
def test_marketplace_golden_cases(golden_runner, marketplace):
    """Test golden cases for specific marketplace."""
    test_cases = [tc for tc in golden_runner.discover_test_cases() if tc.marketplace == marketplace]
    
    if not test_cases:
        pytest.skip(f"No golden test cases found for {marketplace}")
    
    for test_case in test_cases:
        result = golden_runner.run_test_case(test_case)
        assert result["passed"], f"Golden test failed: {test_case.input_file.name}"


# Performance benchmark integration
@pytest.mark.benchmark
def test_golden_performance_benchmark(golden_runner, benchmark):
    """Benchmark performance against golden test cases."""
    # Use largest test case for benchmarking
    test_cases = golden_runner.discover_test_cases()
    largest_case = max(test_cases, key=lambda tc: tc.input_file.stat().st_size)
    
    # Load test data
    ruleset = golden_runner.load_ruleset(largest_case.ruleset_path)
    input_data = golden_runner.load_input_data(largest_case.input_file)
    
    # Benchmark execution
    result = benchmark(golden_runner.engine.execute, ruleset, input_data)
    
    # Verify performance requirement: 50k lines < 3 seconds
    row_count = len(input_data)
    if row_count >= 50000:
        assert result.execution_time_ms < 3000, f"Performance requirement failed: {result.execution_time_ms}ms for {row_count} rows"


# Test data generation helpers
class GoldenTestGenerator:
    """Helper for generating golden test fixtures."""
    
    def generate_test_case(
        self,
        marketplace: str,
        version: str,
        input_data: List[Dict[str, Any]],
        ruleset: RuleSetIR
    ) -> None:
        """Generate golden test fixtures from actual execution."""
        runner = GoldenTestRunner()
        
        # Execute rules
        result = runner.engine.execute(ruleset, input_data)
        
        # Create output directories
        fixtures_dir = Path(__file__).parent / "fixtures"
        input_dir = fixtures_dir / "input" / marketplace
        expected_dir = fixtures_dir / "expected" / marketplace / version
        
        input_dir.mkdir(parents=True, exist_ok=True)
        expected_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate test files
        test_name = "generated_test"
        
        # Save input CSV
        input_file = input_dir / f"{test_name}.csv"
        with open(input_file, 'w', newline='', encoding='utf-8') as f:
            if input_data:
                writer = csv.DictWriter(f, fieldnames=input_data[0].keys())
                writer.writeheader()
                writer.writerows(input_data)
        
        # Save expected output CSV
        output_file = expected_dir / f"{test_name}_output.csv"
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            if result.output_data:
                writer = csv.DictWriter(f, fieldnames=result.output_data[0].keys())
                writer.writeheader()
                writer.writerows(result.output_data)
        
        # Save expected corrections JSON
        corrections_file = expected_dir / f"{test_name}_corrections.json"
        with open(corrections_file, 'w', encoding='utf-8') as f:
            corrections_data = {
                "corrections": result.corrections,
                "summary": {
                    "total_corrections": len(result.corrections),
                    "affected_rows": list(set(c.row for c in result.corrections))
                }
            }
            json.dump(corrections_data, f, indent=2, ensure_ascii=False)
        
        # Save expected suggestions JSON
        suggestions_file = expected_dir / f"{test_name}_suggestions.json"
        with open(suggestions_file, 'w', encoding='utf-8') as f:
            suggestions_data = {"suggestions": result.suggestions}
            json.dump(suggestions_data, f, indent=2, ensure_ascii=False)
```

## Test Configuration

### `pytest.ini`

```ini
[tool:pytest]
markers =
    golden: marks tests as golden tests (deselect with '-m "not golden"')
    benchmark: marks tests as performance benchmarks
    slow: marks tests as slow running
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
addopts = 
    --strict-markers
    --tb=short
    --cov=src
    --cov-report=term-missing
    --cov-report=html:htmlcov
```

### Running Golden Tests

```bash
# Run all golden tests
pytest tests/golden/ -m golden -v

# Run golden tests for specific marketplace
pytest tests/golden/ -m golden -k "mercadolivre" -v

# Run performance benchmarks
pytest tests/golden/ -m benchmark --benchmark-only

# Generate new golden test fixtures
python -c "
from tests.golden.test_golden import GoldenTestGenerator
generator = GoldenTestGenerator()
# ... generate test case
"

# Update golden files (when rule behavior intentionally changes)
pytest tests/golden/ -m golden --golden-update
```

## Performance Benchmarking

### Benchmark Test Harness

```python
"""Performance benchmark harness for rule engine."""

import time
import statistics
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class BenchmarkResult:
    """Results from performance benchmark."""
    test_name: str
    row_count: int
    rule_count: int
    runs: List[float]  # Execution times in seconds
    
    @property
    def median_time(self) -> float:
        return statistics.median(self.runs)
    
    @property
    def mean_time(self) -> float:
        return statistics.mean(self.runs)
    
    @property
    def rows_per_second(self) -> float:
        return self.row_count / self.median_time
    
    @property
    def passes_slo(self) -> bool:
        """Check if benchmark passes SLO: 50k lines < 3 seconds."""
        if self.row_count < 50000:
            return True
        return self.median_time < 3.0


class BenchmarkHarness:
    """Harness for running performance benchmarks."""
    
    def __init__(self, runs: int = 3):
        self.runs = runs
    
    def benchmark_execution(
        self,
        name: str,
        engine: RuleExecutionEngine,
        ruleset: RuleSetIR,
        data: List[Dict[str, Any]]
    ) -> BenchmarkResult:
        """Run benchmark with multiple iterations."""
        times = []
        
        for run in range(self.runs):
            # Warm up JIT/caches on first run
            if run == 0:
                engine.execute(ruleset, data[:min(100, len(data))])
            
            # Benchmark full execution
            start_time = time.perf_counter()
            result = engine.execute(ruleset, data)
            end_time = time.perf_counter()
            
            execution_time = end_time - start_time
            times.append(execution_time)
            
            # Clear caches between runs for consistent results
            engine.clear_caches()
        
        return BenchmarkResult(
            test_name=name,
            row_count=len(data),
            rule_count=len(ruleset.rules),
            runs=times
        )
    
    def generate_report(self, results: List[BenchmarkResult]) -> str:
        """Generate benchmark report."""
        lines = [
            "# Rule Engine Performance Benchmark Report",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "| Test Case | Rows | Rules | Median (s) | Rows/sec | SLO Pass |",
            "|-----------|------|-------|------------|----------|----------|"
        ]
        
        for result in results:
            slo_status = "✅" if result.passes_slo else "❌"
            lines.append(
                f"| {result.test_name} | {result.row_count:,} | {result.rule_count} | "
                f"{result.median_time:.3f} | {result.rows_per_second:,.0f} | {slo_status} |"
            )
        
        lines.extend([
            "",
            "## Performance Requirements",
            "- **Target**: Process 50,000 rows in < 3 seconds",
            "- **Measurement**: Median of 3 runs",
            "- **Environment**: Isolated test environment",
            ""
        ])
        
        # Detailed results
        lines.append("## Detailed Results")
        for result in results:
            lines.extend([
                f"### {result.test_name}",
                f"- Rows: {result.row_count:,}",
                f"- Rules: {result.rule_count}",
                f"- Runs: {result.runs}",
                f"- Mean: {result.mean_time:.3f}s",
                f"- Median: {result.median_time:.3f}s",
                f"- Throughput: {result.rows_per_second:,.0f} rows/sec",
                ""
            ])
        
        return "\n".join(lines)


# Integration with golden tests
def run_performance_benchmarks():
    """Run performance benchmarks using golden test fixtures."""
    runner = GoldenTestRunner()
    harness = BenchmarkHarness(runs=3)
    
    test_cases = runner.discover_test_cases()
    results = []
    
    for test_case in test_cases:
        ruleset = runner.load_ruleset(test_case.ruleset_path)
        input_data = runner.load_input_data(test_case.input_file)
        
        # Only benchmark larger datasets
        if len(input_data) >= 1000:
            result = harness.benchmark_execution(
                name=f"{test_case.marketplace}_{test_case.version}_{test_case.input_file.stem}",
                engine=runner.engine,
                ruleset=ruleset,
                data=input_data
            )
            results.append(result)
    
    # Generate report
    report = harness.generate_report(results)
    
    # Save report
    report_path = Path(__file__).parent / "benchmark_report.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"Benchmark report saved to: {report_path}")
    
    # Check SLO compliance
    failed_benchmarks = [r for r in results if not r.passes_slo]
    if failed_benchmarks:
        print(f"\n❌ {len(failed_benchmarks)} benchmarks failed SLO requirements")
        for result in failed_benchmarks:
            print(f"  - {result.test_name}: {result.median_time:.3f}s for {result.row_count:,} rows")
        return False
    else:
        print(f"\n✅ All {len(results)} benchmarks passed SLO requirements")
        return True


if __name__ == "__main__":
    success = run_performance_benchmarks()
    exit(0 if success else 1)
```

This comprehensive specification provides a complete technical foundation for ValidaHub's YAML Schema → IR → Runtime system, covering formal schema definitions, stable IR compilation, high-performance runtime execution, hot-reload capabilities, CCM mapping, SemVer compatibility, benchmarking harness, and golden test framework. The system is designed to handle the "50k lines < 3s" performance requirement while maintaining correctness and reliability across marketplace integrations.