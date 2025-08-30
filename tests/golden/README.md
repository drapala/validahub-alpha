# Golden Tests para ValidaHub Rules

## Overview

Os Golden Tests garantem que as transformações e validações de regras produzam resultados consistentes e previsíveis. Cada marketplace tem seu próprio conjunto de fixtures que cobrem cenários reais de dados.

## Estrutura dos Testes

```
tests/golden/
├── README.md                    # Este arquivo
├── shared/                      # Fixtures compartilhadas
│   ├── ccm_base.csv            # Exemplo base do CCM
│   └── invalid_data.csv        # Casos de erro comuns
├── mercado_livre/              # Testes específicos do Mercado Livre
│   ├── fixtures/
│   ├── rules/
│   └── expected/
├── amazon/                     # Testes específicos da Amazon
│   ├── fixtures/
│   ├── rules/  
│   └── expected/
├── magalu/                     # Testes específicos da Magazine Luiza
│   ├── fixtures/
│   ├── rules/
│   └── expected/
└── test_golden.py              # Runner dos testes golden
```

## Metodologia dos Golden Tests

### 1. Input Fixtures
- `fixtures/input/` contém CSVs com dados reais (anonimizados) de cada marketplace
- Cobrem casos normais, edge cases e dados inválidos
- Nomeação: `{scenario}_{size}.csv` (ex: `produtos_normais_100.csv`)

### 2. Rule Definitions  
- `rules/` contém arquivos YAML com regras específicas do marketplace
- Versionados seguindo SemVer
- Testam diferentes combinações de regras

### 3. Expected Outputs
- `expected/` contém os resultados esperados das transformações
- Formato JSON com estrutura padronizada
- Incluem validações, transformações e sugestões

### 4. Test Execution
- Tests executam automaticamente no CI/CD
- Comparam output atual com expected usando diff
- Falham se há mudanças não intencionais no comportamento

## Cenários de Teste por Marketplace

### Mercado Livre
- **Produtos normais**: Eletrônicos, roupas, casa & jardim
- **Casos especiais**: Produtos com variações, kits, bundled
- **Validações específicas**: GTIN obrigatório para certas categorias
- **Transformações**: Normalização de título, preço com desconto

### Amazon
- **Produtos normais**: Livros, eletrônicos, casa & cozinha  
- **Casos especiais**: Produtos Amazon Choice, Prime exclusivos
- **Validações específicas**: UPC/EAN para categoria, brand restrictions
- **Transformações**: Bullet points, imagens múltiplas

### Magazine Luiza
- **Produtos normais**: Eletrodomésticos, móveis, informática
- **Casos especiais**: Produtos marketplace vs próprios
- **Validações específicas**: NCM obrigatório, dimensões para frete
- **Transformações**: Adequação de categoria, preços promocionais

## Execução dos Testes

### Comando Básico
```bash
# Executar todos os golden tests
pytest tests/golden/ -v

# Executar testes de um marketplace específico
pytest tests/golden/mercado_livre/ -v

# Executar com coverage
pytest tests/golden/ --cov=src/domain/rules --cov-report=html
```

### Comando de Regeneração
```bash
# Regenerar expected outputs (usar com cuidado!)
pytest tests/golden/ --golden-regen

# Regenerar apenas um marketplace
pytest tests/golden/amazon/ --golden-regen
```

### Debug Mode
```bash
# Executar em modo debug com diffs detalhados
pytest tests/golden/ -v -s --golden-diff
```

## Estrutura do Expected Output

### Formato JSON Padrão
```json
{
  "metadata": {
    "input_file": "produtos_normais_100.csv",
    "rules_version": "1.2.0",
    "execution_date": "2024-08-29T10:30:00Z",
    "total_rows": 100,
    "processing_time_ms": 45.2
  },
  "validation_results": [
    {
      "row_index": 0,
      "field": "sku", 
      "rule_id": "sku_required",
      "severity": "error",
      "message": "SKU é obrigatório",
      "original_value": null,
      "suggested_value": null
    }
  ],
  "transformations": [
    {
      "row_index": 0,
      "field": "title",
      "rule_id": "title_normalize", 
      "original_value": "  smartphone SAMSUNG galaxy s21  ",
      "transformed_value": "Smartphone Samsung Galaxy S21",
      "operation": "normalize_title"
    }
  ],
  "suggestions": [
    {
      "row_index": 5,
      "field": "category_path",
      "rule_id": "category_suggest",
      "current_value": "Eletrônicos",
      "suggested_values": [
        "Eletrônicos > Smartphones > Android",
        "Eletrônicos > Smartphones > Samsung"
      ],
      "confidence": 0.89,
      "reason": "Baseado no título e marca do produto"
    }
  ],
  "statistics": {
    "total_errors": 5,
    "total_warnings": 12, 
    "total_transformations": 87,
    "total_suggestions": 23,
    "fields_validated": 15,
    "rules_executed": 25
  }
}
```

## Boas Práticas

### 1. Nomeação de Fixtures
```
produtos_normais_100.csv          # 100 produtos típicos
produtos_invalidos_50.csv         # 50 casos de erro
produtos_edge_cases_25.csv        # 25 casos extremos
produtos_performance_10k.csv      # 10k produtos para benchmark
```

### 2. Versionamento de Regras
- Sempre version bump quando regras mudam
- Manter compatibility tests entre versões  
- Documentar breaking changes no CHANGELOG

### 3. Manutenção
- Revisar fixtures trimestralmente
- Adicionar novos casos quando bugs são encontrados
- Remover fixtures obsoletas após 2 releases

### 4. Performance
- Fixtures de performance separadas
- Benchmark targets: 50k linhas < 3s
- Alertas se degradação > 20%

## Integração com CI/CD

### GitHub Actions
```yaml
name: Golden Tests
on: [push, pull_request]

jobs:
  golden-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements-test.txt
      - name: Run Golden Tests
        run: |
          pytest tests/golden/ -v --tb=short
      - name: Upload artifacts on failure
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: golden-test-diffs
          path: tests/golden/diffs/
```

### Regras de Merge
- Golden tests DEVEM passar antes do merge
- Changes em expected outputs requerem review manual
- Performance regressions bloqueiam deploy

## Troubleshooting

### Tests Falhando Após Changes
1. Verificar se as mudanças são intencionais
2. Se sim, regenerar expected outputs com `--golden-regen`
3. Revisar diffs cuidadosamente
4. Commit os novos expected files

### Performance Degradation
1. Executar benchmark individual: `pytest tests/golden/performance/`
2. Verificar memory usage e bottlenecks
3. Otimizar regras ou engine se necessário
4. Atualizar targets se justificado

### Fixtures Desatualizadas  
1. Coletar novos samples de dados reais
2. Anonimizar dados sensíveis
3. Atualizar fixtures mantendo mesmo formato
4. Regenerar expected outputs

## Contribuindo

### Adicionando Novo Marketplace
1. Criar diretório `tests/golden/{marketplace}/`
2. Adicionar fixtures realistas
3. Definir regras específicas
4. Gerar expected outputs
5. Atualizar este README

### Adicionando Novos Cenários
1. Identificar gap na cobertura
2. Criar fixture específica
3. Documentar cenário no código
4. Adicionar ao test suite

Para dúvidas ou suporte, consulte a [documentação técnica](../../docs/rules/) ou abra uma issue.