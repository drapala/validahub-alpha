"""
Benchmark de Performance para ValidaHub Rules Engine.

Este módulo implementa testes de benchmark para validar que o sistema
atende ao SLO de processar 50k linhas em menos de 3 segundos.
"""

import json
import logging
import os
import statistics
import sys
import time
import traceback
import tracemalloc
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import psutil
from src.domain.rules.engine.compiler import RuleCompiler
from src.domain.rules.engine.runtime import RuleExecutionEngine

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    """Configuração do benchmark."""

    target_rows: int = 50000
    max_execution_time_ms: float = 3000.0  # 3 segundos
    max_memory_mb: float = 512.0
    min_throughput_rps: float = 16667.0  # 50k / 3s
    iterations: int = 3
    warmup_iterations: int = 1
    results_dir: str = "tests/performance/results"
    generate_test_data: bool = True
    test_data_file: str = "benchmark_50k_data.csv"
    rules_file: str = "tests/golden/mercado_livre/rules/mercado_livre_v1.0.0.yaml"


@dataclass
class BenchmarkMetrics:
    """Métricas de uma execução individual."""

    iteration: int
    rows_processed: int
    execution_time_ms: float
    throughput_rps: float
    memory_peak_mb: float
    memory_avg_mb: float
    cpu_percent: float
    compilation_time_ms: float
    loading_time_ms: float
    validation_time_ms: float
    transformation_time_ms: float
    suggestion_time_ms: float

    # Estatísticas de regras
    total_errors: int
    total_warnings: int
    total_transformations: int
    total_suggestions: int
    rules_executed: int

    # Performance flags
    slo_time_met: bool
    slo_memory_met: bool
    slo_throughput_met: bool
    slo_overall_met: bool


@dataclass
class BenchmarkReport:
    """Relatório consolidado do benchmark."""

    config: BenchmarkConfig
    metrics: list[BenchmarkMetrics]

    # Estatísticas agregadas
    avg_execution_time_ms: float
    median_execution_time_ms: float
    p95_execution_time_ms: float
    p99_execution_time_ms: float

    avg_throughput_rps: float
    median_throughput_rps: float

    avg_memory_mb: float
    peak_memory_mb: float

    avg_cpu_percent: float

    # SLO Compliance
    slo_compliance_rate: float
    passes_slo: bool

    # Recommendations
    recommendations: list[str]

    # Timestamp
    generated_at: datetime


class PerformanceBenchmark:
    """
    Classe principal para execução de benchmarks de performance.

    Executa múltiplas iterações do processamento de regras,
    coleta métricas detalhadas e gera relatório de compliance.
    """

    def __init__(self, config: BenchmarkConfig | None = None):
        """
        Inicializa o benchmark.

        Args:
            config: Configuração personalizada do benchmark
        """
        self.config = config or BenchmarkConfig()
        self.compiler = RuleCompiler()
        self.engine = RuleExecutionEngine(
            max_workers=4,
            timeout_seconds=10.0,
            memory_limit_mb=self.config.max_memory_mb,
            enable_cache=True,
            enable_vectorization=True,
        )

        # Criar diretório de resultados
        os.makedirs(self.config.results_dir, exist_ok=True)

        # Setup logging
        self._setup_logging()

    def run_benchmark(self) -> BenchmarkReport:
        """
        Executa o benchmark completo.

        Returns:
            Relatório detalhado do benchmark
        """
        logger.info(f"Iniciando benchmark com {self.config.target_rows} linhas")
        logger.info(
            f"SLO Target: {self.config.max_execution_time_ms}ms, {self.config.max_memory_mb}MB"
        )

        try:
            # Preparar dados e regras
            test_data = self._prepare_test_data()
            compiled_rules = self._compile_rules()

            logger.info(f"Dataset preparado: {len(test_data)} linhas")
            logger.info(f"Regras compiladas: {len(compiled_rules.rules)} regras")

            # Aquecimento
            self._warmup(compiled_rules, test_data.head(1000))

            # Execuções do benchmark
            metrics = []
            for iteration in range(self.config.iterations):
                logger.info(f"Executando iteração {iteration + 1}/{self.config.iterations}")

                iteration_metrics = self._run_single_iteration(
                    iteration=iteration + 1, rules=compiled_rules, data=test_data
                )

                metrics.append(iteration_metrics)
                logger.info(
                    f"Iteração {iteration + 1}: {iteration_metrics.execution_time_ms:.2f}ms, "
                    f"{iteration_metrics.throughput_rps:.0f} rps, "
                    f"SLO: {'✓' if iteration_metrics.slo_overall_met else '✗'}"
                )

            # Gerar relatório
            report = self._generate_report(metrics)

            # Salvar resultados
            self._save_results(report)

            # Log summary
            self._log_summary(report)

            return report

        except Exception as e:
            logger.error(f"Erro durante benchmark: {e}")
            logger.error(traceback.format_exc())
            raise

    def _prepare_test_data(self) -> pd.DataFrame:
        """Prepara dados de teste."""
        test_data_path = os.path.join(self.config.results_dir, self.config.test_data_file)

        if self.config.generate_test_data or not os.path.exists(test_data_path):
            logger.info("Gerando dados de teste...")
            data = self._generate_test_data()
            data.to_csv(test_data_path, index=False)
            logger.info(f"Dados salvos em {test_data_path}")
        else:
            logger.info(f"Carregando dados existentes de {test_data_path}")
            data = pd.read_csv(test_data_path)

        return data

    def _generate_test_data(self) -> pd.DataFrame:
        """Gera dados sintéticos para teste."""
        np.random.seed(42)  # Para reprodutibilidade

        rows = []
        for i in range(self.config.target_rows):
            row = {
                "sku": f"ML{i:06d}",
                "titulo": self._generate_product_title(),
                "descricao": self._generate_product_description(),
                "marca": self._generate_brand(),
                "codigo_barras": self._generate_barcode() if np.random.random() > 0.3 else "",
                "preco": round(np.random.uniform(10.0, 5000.0), 2),
                "moeda": "BRL",
                "disponibilidade": np.random.randint(0, 100),
                "peso_gramas": np.random.randint(50, 50000),
                "comprimento_cm": round(np.random.uniform(5.0, 200.0), 1),
                "largura_cm": round(np.random.uniform(5.0, 150.0), 1),
                "altura_cm": round(np.random.uniform(2.0, 100.0), 1),
                "categoria": self._generate_category(),
                "imagens": self._generate_image_urls(),
                "atributos": self._generate_attributes(),
            }

            # Introduzir alguns dados inválidos propositalmente
            if np.random.random() < 0.05:  # 5% de dados inválidos
                row = self._make_invalid_data(row)

            rows.append(row)

        return pd.DataFrame(rows)

    def _generate_product_title(self) -> str:
        """Gera título de produto sintético."""
        products = [
            "Smartphone Samsung Galaxy",
            "iPhone Apple",
            "Notebook Lenovo",
            "TV Smart LG",
            "Geladeira Electrolux",
            "Máquina de Lavar Brastemp",
            "Air Fryer Philco",
            "Aspirador Electrolux",
            "Micro-ondas Panasonic",
            "Tênis Nike",
            "Relógio Casio",
            "Perfume Natura",
        ]

        variants = [
            "128GB Preto",
            "256GB Azul",
            "15 Polegadas",
            "55 Polegadas",
            "462L Frost Free",
            "12kg Automática",
            "3L Inox",
            "1200W",
            "30L Digital",
            "Air Max Masculino",
            "Digital Resistente",
            "Essencial 100ml",
        ]

        product = np.random.choice(products)
        variant = np.random.choice(variants)

        return f"{product} {variant}"

    def _generate_product_description(self) -> str:
        """Gera descrição de produto sintética."""
        descriptions = [
            "Produto de alta qualidade com excelente custo-benefício.",
            "Design moderno e funcionalidade avançada para o dia a dia.",
            "Tecnologia de ponta com garantia de satisfação.",
            "Ideal para uso doméstico e profissional.",
            "Produto premium com características únicas.",
        ]

        return np.random.choice(descriptions)

    def _generate_brand(self) -> str:
        """Gera marca aleatória."""
        brands = [
            "Samsung",
            "Apple",
            "LG",
            "Sony",
            "Electrolux",
            "Brastemp",
            "Philco",
            "Panasonic",
            "Nike",
            "Adidas",
            "Casio",
            "Natura",
        ]

        return np.random.choice(brands)

    def _generate_barcode(self) -> str:
        """Gera código de barras sintético."""
        return "".join([str(np.random.randint(0, 10)) for _ in range(13)])

    def _generate_category(self) -> str:
        """Gera categoria aleatória."""
        categories = [
            "Celulares e Telefones > Celulares e Smartphones",
            "Computação > Notebooks",
            "Casa e Eletrodomésticos > TVs",
            "Casa e Eletrodomésticos > Eletrodomésticos > Refrigeração",
            "Casa e Eletrodomésticos > Eletrodomésticos",
            "Roupas e Calçados > Calçados > Tênis",
            "Joias e Relógios > Relógios",
            "Beleza e Cuidado Pessoal > Perfumaria",
        ]

        return np.random.choice(categories)

    def _generate_image_urls(self) -> str:
        """Gera URLs de imagens sintéticas."""
        num_images = np.random.randint(1, 6)
        urls = []

        for i in range(num_images):
            urls.append(f"https://http2.mlstatic.com/D_NQ_NP_{i:03d}.jpg")

        return ",".join(urls)

    def _generate_attributes(self) -> str:
        """Gera atributos JSON sintéticos."""
        attributes = {
            "cor": np.random.choice(["Preto", "Branco", "Azul", "Vermelho"]),
            "tamanho": np.random.choice(["P", "M", "G", "GG", "38", "42", "46"]),
            "material": np.random.choice(["Plástico", "Metal", "Tecido", "Couro"]),
        }

        return json.dumps(attributes)

    def _make_invalid_data(self, row: dict) -> dict:
        """Introduz dados inválidos propositalmente."""
        invalid_modifications = [
            lambda r: r.update({"sku": ""}),  # SKU vazio
            lambda r: r.update({"titulo": ""}),  # Título vazio
            lambda r: r.update({"preco": -100}),  # Preço negativo
            lambda r: r.update({"codigo_barras": "123"}),  # Código inválido
            lambda r: r.update({"peso_gramas": -50}),  # Peso negativo
        ]

        modification = np.random.choice(invalid_modifications)
        modification(row)

        return row

    def _compile_rules(self):
        """Compila as regras YAML."""
        logger.info("Compilando regras...")
        start_time = time.perf_counter()

        with open(self.config.rules_file, encoding="utf-8") as f:
            yaml_content = f.read()

        compiled_rules = self.compiler.compile_yaml(yaml_content)

        compilation_time = (time.perf_counter() - start_time) * 1000
        logger.info(f"Regras compiladas em {compilation_time:.2f}ms")

        return compiled_rules

    def _warmup(self, rules, sample_data: pd.DataFrame):
        """Executa aquecimento do sistema."""
        logger.info("Executando aquecimento...")

        for _i in range(self.config.warmup_iterations):
            self.engine.execute_rules(rules, sample_data)

        logger.info("Aquecimento concluído")

    def _run_single_iteration(self, iteration: int, rules, data: pd.DataFrame) -> BenchmarkMetrics:
        """Executa uma iteração individual do benchmark."""

        # Monitoramento de recursos
        process = psutil.Process()

        # Inicia monitoramento de memória
        tracemalloc.start()

        # Timestamps
        start_time = time.perf_counter()
        start_cpu_time = process.cpu_percent()

        try:
            # Execução das regras
            result = self.engine.execute_rules(rules, data)

            # Fim da execução
            end_time = time.perf_counter()
            end_cpu_time = process.cpu_percent()

            # Métricas de memória
            current_memory, peak_memory = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            # Cálculo de métricas
            execution_time_ms = (end_time - start_time) * 1000
            throughput_rps = len(data) / (execution_time_ms / 1000)
            memory_peak_mb = peak_memory / (1024 * 1024)
            memory_avg_mb = current_memory / (1024 * 1024)
            cpu_percent = (end_cpu_time + start_cpu_time) / 2

            # SLO compliance
            slo_time_met = execution_time_ms <= self.config.max_execution_time_ms
            slo_memory_met = memory_peak_mb <= self.config.max_memory_mb
            slo_throughput_met = throughput_rps >= self.config.min_throughput_rps
            slo_overall_met = slo_time_met and slo_memory_met and slo_throughput_met

            return BenchmarkMetrics(
                iteration=iteration,
                rows_processed=len(data),
                execution_time_ms=execution_time_ms,
                throughput_rps=throughput_rps,
                memory_peak_mb=memory_peak_mb,
                memory_avg_mb=memory_avg_mb,
                cpu_percent=cpu_percent,
                compilation_time_ms=rules.stats.compilation_time_ms,
                loading_time_ms=0,  # TODO: Implementar se necessário
                validation_time_ms=0,  # TODO: Extrair do result.stats
                transformation_time_ms=0,  # TODO: Extrair do result.stats
                suggestion_time_ms=0,  # TODO: Extrair do result.stats
                total_errors=len(result.errors),
                total_warnings=len(result.warnings),
                total_transformations=len(result.transformations),
                total_suggestions=len(result.suggestions),
                rules_executed=result.stats.rules_executed,
                slo_time_met=slo_time_met,
                slo_memory_met=slo_memory_met,
                slo_throughput_met=slo_throughput_met,
                slo_overall_met=slo_overall_met,
            )

        except Exception as e:
            tracemalloc.stop()
            logger.error(f"Erro na iteração {iteration}: {e}")
            raise

    def _generate_report(self, metrics: list[BenchmarkMetrics]) -> BenchmarkReport:
        """Gera relatório consolidado."""

        # Estatísticas de tempo de execução
        execution_times = [m.execution_time_ms for m in metrics]
        avg_execution_time = statistics.mean(execution_times)
        median_execution_time = statistics.median(execution_times)
        p95_execution_time = np.percentile(execution_times, 95)
        p99_execution_time = np.percentile(execution_times, 99)

        # Estatísticas de throughput
        throughputs = [m.throughput_rps for m in metrics]
        avg_throughput = statistics.mean(throughputs)
        median_throughput = statistics.median(throughputs)

        # Estatísticas de memória
        memory_peaks = [m.memory_peak_mb for m in metrics]
        memory_avgs = [m.memory_avg_mb for m in metrics]
        avg_memory = statistics.mean(memory_avgs)
        peak_memory = max(memory_peaks)

        # Estatísticas de CPU
        cpu_usages = [m.cpu_percent for m in metrics]
        avg_cpu = statistics.mean(cpu_usages)

        # SLO Compliance
        slo_compliant_count = sum(1 for m in metrics if m.slo_overall_met)
        slo_compliance_rate = slo_compliant_count / len(metrics)
        passes_slo = slo_compliance_rate >= 0.8  # 80% das execuções devem passar

        # Recomendações
        recommendations = self._generate_recommendations(metrics)

        return BenchmarkReport(
            config=self.config,
            metrics=metrics,
            avg_execution_time_ms=avg_execution_time,
            median_execution_time_ms=median_execution_time,
            p95_execution_time_ms=p95_execution_time,
            p99_execution_time_ms=p99_execution_time,
            avg_throughput_rps=avg_throughput,
            median_throughput_rps=median_throughput,
            avg_memory_mb=avg_memory,
            peak_memory_mb=peak_memory,
            avg_cpu_percent=avg_cpu,
            slo_compliance_rate=slo_compliance_rate,
            passes_slo=passes_slo,
            recommendations=recommendations,
            generated_at=datetime.now(UTC),
        )

    def _generate_recommendations(self, metrics: list[BenchmarkMetrics]) -> list[str]:
        """Gera recomendações baseadas nos resultados."""
        recommendations = []

        # Análise de tempo
        avg_time = statistics.mean([m.execution_time_ms for m in metrics])
        if avg_time > self.config.max_execution_time_ms:
            recommendations.append(
                f"Tempo médio ({avg_time:.0f}ms) excede SLO ({self.config.max_execution_time_ms:.0f}ms). "
                "Considere otimizar regras ou aumentar paralelização."
            )

        # Análise de memória
        peak_memory = max([m.memory_peak_mb for m in metrics])
        if peak_memory > self.config.max_memory_mb:
            recommendations.append(
                f"Pico de memória ({peak_memory:.1f}MB) excede limite ({self.config.max_memory_mb:.1f}MB). "
                "Considere processamento em lotes menores."
            )

        # Análise de throughput
        avg_throughput = statistics.mean([m.throughput_rps for m in metrics])
        if avg_throughput < self.config.min_throughput_rps:
            recommendations.append(
                f"Throughput ({avg_throughput:.0f} rps) abaixo do target ({self.config.min_throughput_rps:.0f} rps). "
                "Considere vetorização ou cache mais agressivo."
            )

        # Análise de variabilidade
        time_std = statistics.stdev([m.execution_time_ms for m in metrics])
        time_cv = time_std / avg_time  # Coeficiente de variação
        if time_cv > 0.1:  # Mais de 10% de variação
            recommendations.append(
                f"Alta variabilidade no tempo de execução (CV: {time_cv:.2%}). "
                "Verifique garbage collection e contenção de recursos."
            )

        return recommendations

    def _save_results(self, report: BenchmarkReport):
        """Salva resultados em arquivo."""
        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")

        # JSON detalhado
        json_file = os.path.join(self.config.results_dir, f"benchmark_report_{timestamp}.json")
        with open(json_file, "w") as f:
            # Converter para dict serializable
            report_dict = asdict(report)
            # Converter datetime para string
            report_dict["generated_at"] = report.generated_at.isoformat()
            json.dump(report_dict, f, indent=2, default=str)

        # CSV com métricas
        csv_file = os.path.join(self.config.results_dir, f"benchmark_metrics_{timestamp}.csv")
        metrics_df = pd.DataFrame([asdict(m) for m in report.metrics])
        metrics_df.to_csv(csv_file, index=False)

        # Relatório texto
        txt_file = os.path.join(self.config.results_dir, f"benchmark_summary_{timestamp}.txt")
        with open(txt_file, "w") as f:
            f.write(self._format_text_report(report))

        logger.info("Resultados salvos em:")
        logger.info(f"  JSON: {json_file}")
        logger.info(f"  CSV:  {csv_file}")
        logger.info(f"  TXT:  {txt_file}")

    def _format_text_report(self, report: BenchmarkReport) -> str:
        """Formata relatório em texto."""
        lines = [
            "=" * 80,
            "VALIDAHUB RULES ENGINE - PERFORMANCE BENCHMARK REPORT",
            "=" * 80,
            "",
            f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Target Rows: {report.config.target_rows:,}",
            f"Iterations: {report.config.iterations}",
            "",
            "SLO TARGETS:",
            f"  Max Execution Time: {report.config.max_execution_time_ms:,.0f}ms",
            f"  Max Memory Usage:   {report.config.max_memory_mb:,.0f}MB",
            f"  Min Throughput:     {report.config.min_throughput_rps:,.0f} rows/sec",
            "",
            "RESULTS SUMMARY:",
            f"  SLO Compliance:     {report.slo_compliance_rate:.1%} ({'PASS' if report.passes_slo else 'FAIL'})",
            f"  Avg Execution Time: {report.avg_execution_time_ms:,.1f}ms",
            f"  Median Exec Time:   {report.median_execution_time_ms:,.1f}ms",
            f"  P95 Execution Time: {report.p95_execution_time_ms:,.1f}ms",
            f"  Avg Throughput:     {report.avg_throughput_rps:,.0f} rows/sec",
            f"  Peak Memory:        {report.peak_memory_mb:,.1f}MB",
            f"  Avg CPU Usage:      {report.avg_cpu_percent:.1f}%",
            "",
            "ITERATION DETAILS:",
        ]

        for m in report.metrics:
            status = "PASS" if m.slo_overall_met else "FAIL"
            lines.append(
                f"  #{m.iteration}: {m.execution_time_ms:,.1f}ms, "
                f"{m.throughput_rps:,.0f} rps, "
                f"{m.memory_peak_mb:.1f}MB, "
                f"{status}"
            )

        if report.recommendations:
            lines.extend(
                ["", "RECOMMENDATIONS:", *[f"  • {rec}" for rec in report.recommendations]]
            )

        lines.extend(["", "=" * 80])

        return "\n".join(lines)

    def _log_summary(self, report: BenchmarkReport):
        """Log do resumo dos resultados."""
        logger.info("=" * 60)
        logger.info("BENCHMARK COMPLETED")
        logger.info("=" * 60)
        logger.info(
            f"SLO Compliance: {report.slo_compliance_rate:.1%} ({'PASS' if report.passes_slo else 'FAIL'})"
        )
        logger.info(
            f"Avg Time: {report.avg_execution_time_ms:.1f}ms (target: {report.config.max_execution_time_ms:.0f}ms)"
        )
        logger.info(
            f"Avg Throughput: {report.avg_throughput_rps:.0f} rps (target: {report.config.min_throughput_rps:.0f} rps)"
        )
        logger.info(
            f"Peak Memory: {report.peak_memory_mb:.1f}MB (limit: {report.config.max_memory_mb:.0f}MB)"
        )

        if report.recommendations:
            logger.warning(f"{len(report.recommendations)} recommendations generated")
            for rec in report.recommendations:
                logger.warning(f"  • {rec}")

        logger.info("=" * 60)

    def _setup_logging(self):
        """Configura logging para o benchmark."""
        log_file = os.path.join(self.config.results_dir, "benchmark.log")

        # Configure logger
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
        )


def main():
    """Função principal para execução do benchmark."""

    # Configuração customizada se necessário
    config = BenchmarkConfig(target_rows=50000, iterations=3, generate_test_data=True)

    # Execução do benchmark
    benchmark = PerformanceBenchmark(config)
    report = benchmark.run_benchmark()

    # Exit code baseado no SLO
    exit_code = 0 if report.passes_slo else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
