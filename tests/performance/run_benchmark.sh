#!/bin/bash

# Script para executar benchmark de performance do ValidaHub Rules Engine
# Uso: ./run_benchmark.sh [target_rows] [iterations]

set -e

# Configurações padrão
TARGET_ROWS=${1:-50000}
ITERATIONS=${2:-3}
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "============================================================"
echo "VALIDAHUB RULES ENGINE - PERFORMANCE BENCHMARK"
echo "============================================================"
echo "Target Rows: $TARGET_ROWS"
echo "Iterations: $ITERATIONS"
echo "Timestamp: $TIMESTAMP"
echo ""

# Criar diretório de resultados se não existir
mkdir -p tests/performance/results

# Verificar se Python está disponível
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não encontrado. Instale Python 3.8+ para continuar."
    exit 1
fi

# Verificar dependências
echo "📋 Verificando dependências..."
python3 -c "import pandas, numpy, psutil, tracemalloc, yaml, jsonschema" 2>/dev/null || {
    echo "❌ Dependências não encontradas. Execute:"
    echo "   pip install -r requirements-test.txt"
    exit 1
}

echo "✅ Dependências verificadas"
echo ""

# Executar benchmark
echo "🚀 Iniciando benchmark..."
echo "   Este processo pode levar alguns minutos..."
echo ""

# Definir variáveis de ambiente para o benchmark
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export BENCHMARK_TARGET_ROWS=$TARGET_ROWS
export BENCHMARK_ITERATIONS=$ITERATIONS
export BENCHMARK_TIMESTAMP=$TIMESTAMP

# Executar o benchmark
if python3 tests/performance/benchmark_50k.py; then
    BENCHMARK_STATUS="SUCCESS"
    EXIT_CODE=0
else
    BENCHMARK_STATUS="FAILED"
    EXIT_CODE=1
fi

echo ""
echo "============================================================"
echo "BENCHMARK COMPLETED: $BENCHMARK_STATUS"
echo "============================================================"

# Mostrar resultados se disponíveis
RESULTS_DIR="tests/performance/results"
SUMMARY_FILE=$(find $RESULTS_DIR -name "benchmark_summary_*.txt" | tail -1)

if [[ -f "$SUMMARY_FILE" ]]; then
    echo ""
    echo "📊 RESUMO DOS RESULTADOS:"
    echo "------------------------"
    cat "$SUMMARY_FILE"
    echo ""
    echo "📁 Arquivos gerados:"
    find $RESULTS_DIR -name "*$TIMESTAMP*" -type f | while read file; do
        echo "   - $(basename $file)"
    done
fi

# SLO Check
if [[ $EXIT_CODE -eq 0 ]]; then
    echo ""
    echo "✅ SLO ATINGIDO - Benchmark passou em todos os critérios"
else
    echo ""
    echo "❌ SLO NÃO ATINGIDO - Performance abaixo do esperado"
    echo ""
    echo "💡 PRÓXIMOS PASSOS:"
    echo "   1. Analisar o relatório detalhado em $RESULTS_DIR"
    echo "   2. Verificar recomendações de otimização"
    echo "   3. Ajustar configurações do engine se necessário"
    echo "   4. Re-executar benchmark após otimizações"
fi

echo ""
echo "============================================================"

exit $EXIT_CODE