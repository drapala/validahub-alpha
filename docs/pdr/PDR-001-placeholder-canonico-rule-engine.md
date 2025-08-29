# PDR-001: Placeholder Canônico para Rule Engine

- **Status**: Proposed
- **Data**: 2025-08-29
- **Autor**: PM/BI Visionário

## Contexto

ValidaHub precisa validar CSVs de diferentes marketplaces, mas:
- Cada marketplace tem regras específicas (ML, Magalu, Shopee, etc.)
- Mapear todas as regras reais levaria meses
- MVP precisa gerar valor rapidamente
- Clientes esperam validações básicas que já economizam tempo

Requisitos MVP:
- Validações genéricas que capturam 80% dos erros comuns
- Arquitetura extensível para regras específicas futuras
- Feedback útil para catalogadores

## Decisão

Implementar **Canonical CSV Model (CCM)** com placeholders + **Intelligence Capture**:

```yaml
# Campos obrigatórios
required_fields: [sku, title, price_brl, stock]

# Validações genéricas
validations:
  sku: {regex: "^[A-Z0-9-_]{3,50}$"}
  title: {min_length: 10, max_length: 200}
  price_brl: {type: decimal, min: 0.01}
  stock: {type: integer, min: 0}
  gtin: {regex: "^[0-9]{8,14}$", optional: true}

# Correções automáticas
corrections:
  title: {trim: true, remove_formula_prefix: true}
  price_brl: {normalize_decimal: true}

# NOVO: Intelligence Capture Layer
intelligence:
  error_patterns: "Capture common error types by category/marketplace"
  rule_effectiveness: "Track which rules prevent most errors"
  quality_indicators: "Extract quality signals for benchmarking"
  product_classification: "Categorize products for cross-marketplace analysis"
```

### Intelligence-Enhanced Rule Engine

O rule engine captura inteligência durante validação:

```python
# Every validation becomes training data
def validate_product(product, rules_profile):
    validation_result = apply_rules(product, rules_profile)
    
    # INTELLIGENCE CAPTURE
    capture_validation_intelligence({
        'anonymous_product_hash': hash_product(product),
        'category_inferred': classify_product(product.title),
        'marketplace': rules_profile.marketplace,
        'errors_found': validation_result.errors,
        'quality_signals': extract_quality_indicators(product),
        'rule_effectiveness': track_rules_applied(validation_result)
    })
    
    return validation_result
```

Placeholders simulam marketplaces reais mas capturam dados reais para inteligência futura.

## Consequências

### Positivo
- Time-to-market acelerado (semanas vs meses)
- Já resolve problemas comuns (SKUs malformados, preços inválidos)
- Arquitetura permite evolução para regras específicas
- Clientes veem valor desde o primeiro upload
- **NOVO**: Cada validação gera inteligência para o ecossistema
- **NOVO**: Foundation para network effects e benchmarking
- **NOVO**: Data collection desde day 1 para features futuras

### Negativo
- Validações não refletem 100% as regras dos marketplaces
- Alguns falsos positivos/negativos iniciais
- Pode criar expectativa incorreta sobre precisão
- **NOVO**: Intelligence features só trazem valor com escala (cold start)

## Alternativas Consideradas

### Mapear todas regras reais antes do MVP
- **Prós**: Precisão máxima desde o início
- **Contras**: 6+ meses até primeiro valor, risco de over-engineering

### Mockar regras fixas hardcoded
- **Prós**: Implementação rápida
- **Contras**: Dificulta evolução, não extensível

### Começar só com validação de formato CSV
- **Prós**: Implementação trivial
- **Contras**: Valor limitado, não diferencia da concorrência