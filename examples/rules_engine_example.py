"""
Exemplo de uso completo do ValidaHub Rules Engine.

Este script demonstra como usar o sistema de regras completo:
1. Compilação de YAML para IR
2. Execução das regras sobre dados CSV
3. Análise dos resultados
"""


import pandas as pd
from src.application.services import CCMValidationService
from src.domain.rules.engine import CompilationError, RuleCompiler, RuleExecutionEngine


def main():
    """Exemplo principal de uso do Rules Engine."""
    
    print("=" * 60)
    print("VALIDAHUB RULES ENGINE - EXEMPLO COMPLETO")
    print("=" * 60)
    
    # 1. Definir regras YAML
    rules_yaml = """
schema_version: "1.0.0"
marketplace: "exemplo"
version: "1.0.0"

metadata:
  name: "Regras de Exemplo"
  description: "Exemplo básico de regras ValidaHub"
  author: "ValidaHub Team"

ccm_mapping:
  sku: 
    source: "codigo"
    required: true
  title: 
    source: "nome"
    required: true
  price_brl: 
    source: "preco"
    required: true
  brand: "marca"
  description: "descricao"

rules:
  - id: "sku_required"
    type: "assert"
    field: "sku"
    scope: "row"
    precedence: 100
    condition:
      operator: "not_empty"
    action:
      type: "assert"
      stop_on_error: true
    message: "SKU é obrigatório"
    severity: "error"

  - id: "title_length"
    type: "assert"
    field: "title"
    scope: "row"
    precedence: 200
    condition:
      and:
        - operator: "length_gt"
          value: 5
        - operator: "length_lt"
          value: 100
    action:
      type: "assert"
    message: "Título deve ter entre 5 e 100 caracteres"
    severity: "warning"

  - id: "price_positive"
    type: "assert"
    field: "price_brl"
    scope: "row"
    precedence: 300
    condition:
      operator: "gt"
      value: 0
    action:
      type: "assert"
    message: "Preço deve ser positivo"
    severity: "error"

  - id: "title_normalize"
    type: "transform"
    field: "title"
    scope: "row"
    precedence: 400
    condition:
      operator: "not_empty"
    action:
      type: "transform"
      operation: "trim"
    message: "Título normalizado"
    severity: "info"

  - id: "brand_suggest"
    type: "suggest"
    field: "brand"
    scope: "row"
    precedence: 500
    condition:
      operator: "empty"
    action:
      type: "suggest"
      suggestions: ["Marca Genérica", "Sem Marca"]
      confidence: 0.5
    message: "Sugestão de marca para produto sem marca"
    severity: "info"
"""
    
    # 2. Criar dados de teste
    test_data = pd.DataFrame([
        {
            'codigo': 'PROD001',
            'nome': '  Smartphone Premium  ',
            'descricao': 'Smartphone com tecnologia avançada',
            'marca': 'TechBrand',
            'preco': 1299.90
        },
        {
            'codigo': 'PROD002', 
            'nome': 'TV',  # Muito curto
            'descricao': 'Smart TV',
            'marca': '',  # Vazio - será sugerido
            'preco': 2500.00
        },
        {
            'codigo': '',  # Vazio - erro
            'nome': 'Notebook Gamer Ultra Premium com Placa de Vídeo Dedicada e Processador de Última Geração',  # Muito longo
            'descricao': 'Notebook para jogos',
            'marca': 'GameBrand',
            'preco': -100.00  # Negativo - erro
        }
    ])
    
    print(f"\n📊 Dados de teste: {len(test_data)} produtos")
    print(test_data.to_string(index=False))
    
    try:
        # 3. Compilar regras
        print("\n🔧 Compilando regras...")
        compiler = RuleCompiler()
        compiled_rules = compiler.compile_yaml(rules_yaml)
        
        print("✅ Compilação concluída:")
        print(f"   - {len(compiled_rules.rules)} regras compiladas")
        print(f"   - {len(compiled_rules.execution_plan.phases)} fases de execução")
        print(f"   - Checksum: {compiled_rules.checksum[:8]}...")
        
        # 4. Executar regras
        print("\n⚡ Executando regras...")
        engine = RuleExecutionEngine(
            enable_vectorization=True,
            enable_cache=True
        )
        
        result = engine.execute_rules(compiled_rules, test_data)
        
        # 5. Analisar resultados
        print("\n📈 Resultados da execução:")
        print(f"   - Tempo: {result.stats.execution_time_ms:.2f}ms")
        print(f"   - Regras executadas: {result.stats.rules_executed}")
        print(f"   - Erros: {len(result.errors)}")
        print(f"   - Warnings: {len(result.warnings)}")
        print(f"   - Transformações: {len(result.transformations)}")
        print(f"   - Sugestões: {len(result.suggestions)}")
        
        # 6. Mostrar erros
        if result.errors:
            print("\n❌ ERROS ENCONTRADOS:")
            for error in result.errors:
                print(f"   Linha {error.row_index}: {error.field} - {error.message}")
                print(f"      Valor: '{error.actual_value}'")
        
        # 7. Mostrar warnings
        if result.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in result.warnings:
                print(f"   Linha {warning.row_index}: {warning.field} - {warning.message}")
                print(f"      Valor: '{warning.actual_value}'")
        
        # 8. Mostrar transformações
        if result.transformations:
            print("\n🔄 TRANSFORMAÇÕES APLICADAS:")
            for transform in result.transformations:
                print(f"   Linha {transform.row_index}: {transform.field}")
                print(f"      De: '{transform.original_value}'")
                print(f"      Para: '{transform.transformed_value}'")
        
        # 9. Mostrar sugestões
        if result.suggestions:
            print("\n💡 SUGESTÕES:")
            for suggestion in result.suggestions:
                print(f"   Linha {suggestion.row_index}: {suggestion.field}")
                print(f"      Atual: '{suggestion.current_value}'")
                print(f"      Sugestões: {', '.join(suggestion.suggested_values)}")
                print(f"      Confiança: {suggestion.confidence:.1%}")
        
        # 10. Validação CCM (exemplo adicional)
        print("\n🔍 VALIDAÇÃO CCM:")
        ccm_service = CCMValidationService()
        for idx, row in test_data.iterrows():
            ccm_validation = ccm_service.validate_record(row.to_dict())
            valid_fields = sum(1 for v in ccm_validation if v.is_valid)
            total_fields = len(ccm_validation)
            print(f"   Linha {idx}: {valid_fields}/{total_fields} campos válidos")
        
        # 11. Relatório de performance
        print("\n⚡ PERFORMANCE:")
        throughput = len(test_data) / (result.stats.execution_time_ms / 1000)
        print(f"   - Throughput: {throughput:.0f} linhas/seg")
        print(f"   - Memória: {result.stats.memory_usage_mb:.1f}MB")
        print(f"   - Operações vetorizadas: {result.stats.vectorized_operations}")
        
        # 12. Status final
        success_rate = 1 - (len(result.errors) / len(test_data))
        print("\n✅ RESUMO FINAL:")
        print(f"   - Taxa de sucesso: {success_rate:.1%}")
        print(f"   - Qualidade dos dados: {'boa' if success_rate > 0.8 else 'necessita atenção'}")
        
        if result.has_errors:
            print("   - ⚠️  Dados contêm erros que precisam ser corrigidos")
        else:
            print("   - ✅ Todos os dados passaram nas validações críticas")
            
    except CompilationError as e:
        print(f"\n❌ Erro de compilação: {e}")
        if e.rule_id:
            print(f"   Regra: {e.rule_id}")
        return 1
        
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 60)
    print("EXEMPLO CONCLUÍDO COM SUCESSO!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())