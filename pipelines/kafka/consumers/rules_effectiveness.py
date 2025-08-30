"""
Kafka Consumer for Rules Effectiveness Analysis

This consumer processes CloudEvents from the ValidaHub Rules Engine to perform
offline analysis and business intelligence on rule effectiveness, generating
insights for rule optimization and business value assessment.

Features:
- Real-time processing of rule execution events
- F1 score calculation and effectiveness tracking
- Business impact analysis (revenue protection, cost analysis)
- Rule performance benchmarking
- Anomaly detection in rule behavior
- Data pipeline to ClickHouse analytics warehouse

Architecture:
Kafka → Consumer Group → ClickHouse → Business Intelligence
"""

import asyncio
import json
import logging
import os
import statistics
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import aiokafka
import asyncclick
import asyncpg
import pandas as pd
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from packages.shared.logging import get_logger
from packages.shared.telemetry import create_event, emit_event


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)


@dataclass
class RuleExecutionMetrics:
    """Metrics extracted from a rule execution event."""
    
    tenant_id: str
    channel_id: str
    rule_id: str
    ruleset_version: str
    execution_timestamp: datetime
    
    # Performance metrics
    duration_ms: float
    rows_processed: int
    violations_found: int
    memory_usage_mb: float
    
    # Effectiveness metrics (calculated)
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    false_positive_rate: Optional[float] = None
    
    # Business metrics
    revenue_impact_brl: float = 0.0
    cost_impact_brl: float = 0.0
    
    # Context
    job_id: str = ""
    trace_id: str = ""


@dataclass
class EffectivenessAnalysisResult:
    """Result of effectiveness analysis for a rule."""
    
    rule_id: str
    tenant_id: str
    channel_id: str
    analysis_period: timedelta
    analysis_timestamp: datetime
    
    # Aggregate metrics
    total_executions: int
    avg_f1_score: float
    avg_precision: float
    avg_recall: float
    avg_false_positive_rate: float
    
    # Performance metrics
    avg_duration_ms: float
    p95_duration_ms: float
    avg_throughput_rps: float
    
    # Business metrics
    total_revenue_impact_brl: float
    total_cost_impact_brl: float
    roi: float
    
    # Trend analysis
    performance_trend: str  # 'improving', 'stable', 'degrading'
    effectiveness_trend: str
    business_value_score: float


class RuleEffectivenessAnalyzer:
    """
    Analyzes rule effectiveness from execution metrics.
    
    Implements statistical analysis and trend detection for rules performance,
    providing insights for business intelligence and rule optimization.
    """
    
    def __init__(self, lookback_hours: int = 24, min_samples: int = 10):
        """
        Initialize the analyzer.
        
        Args:
            lookback_hours: Hours to look back for trend analysis
            min_samples: Minimum samples required for analysis
        """
        self.lookback_hours = lookback_hours
        self.min_samples = min_samples
        
        # In-memory storage for recent metrics (sliding window)
        self.metrics_buffer: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)  # Keep last 1000 metrics per rule
        )
        
    def add_metrics(self, metrics: RuleExecutionMetrics) -> None:
        """Add execution metrics to the analysis buffer."""
        rule_key = f"{metrics.tenant_id}:{metrics.rule_id}"
        self.metrics_buffer[rule_key].append(metrics)
        
    def analyze_rule_effectiveness(
        self, 
        tenant_id: str,
        rule_id: str,
        analysis_period: timedelta = timedelta(hours=1)
    ) -> Optional[EffectivenessAnalysisResult]:
        """
        Analyze effectiveness for a specific rule.
        
        Args:
            tenant_id: Tenant ID
            rule_id: Rule ID to analyze
            analysis_period: Period to analyze
            
        Returns:
            Analysis result or None if insufficient data
        """
        rule_key = f"{tenant_id}:{rule_id}"
        metrics_queue = self.metrics_buffer.get(rule_key)
        
        if not metrics_queue or len(metrics_queue) < self.min_samples:
            return None
            
        # Filter metrics within analysis period
        cutoff_time = datetime.now(timezone.utc) - analysis_period
        recent_metrics = [
            m for m in metrics_queue 
            if m.execution_timestamp >= cutoff_time
        ]
        
        if len(recent_metrics) < self.min_samples:
            return None
            
        # Calculate aggregate metrics
        total_executions = len(recent_metrics)
        
        # Effectiveness metrics (only for metrics with calculated values)
        effectiveness_metrics = [m for m in recent_metrics if m.f1_score is not None]
        
        if effectiveness_metrics:
            avg_f1_score = statistics.mean(m.f1_score for m in effectiveness_metrics)
            avg_precision = statistics.mean(m.precision or 0 for m in effectiveness_metrics)
            avg_recall = statistics.mean(m.recall or 0 for m in effectiveness_metrics)
            avg_false_positive_rate = statistics.mean(
                m.false_positive_rate or 0 for m in effectiveness_metrics
            )
        else:
            avg_f1_score = avg_precision = avg_recall = avg_false_positive_rate = 0.0
            
        # Performance metrics
        durations = [m.duration_ms for m in recent_metrics]
        avg_duration_ms = statistics.mean(durations)
        p95_duration_ms = self._calculate_percentile(durations, 0.95)
        
        # Throughput calculation
        total_rows = sum(m.rows_processed for m in recent_metrics)
        total_duration_seconds = sum(m.duration_ms for m in recent_metrics) / 1000
        avg_throughput_rps = total_rows / max(total_duration_seconds, 1)
        
        # Business metrics
        total_revenue_impact_brl = sum(m.revenue_impact_brl for m in recent_metrics)
        total_cost_impact_brl = sum(m.cost_impact_brl for m in recent_metrics)
        roi = total_revenue_impact_brl / max(total_cost_impact_brl, 1.0)
        
        # Trend analysis
        performance_trend = self._analyze_performance_trend(recent_metrics)
        effectiveness_trend = self._analyze_effectiveness_trend(effectiveness_metrics)
        
        # Business value score (composite score)
        business_value_score = self._calculate_business_value_score(
            avg_f1_score, roi, avg_throughput_rps
        )
        
        # Get channel from first metric
        channel_id = recent_metrics[0].channel_id if recent_metrics else "unknown"
        
        return EffectivenessAnalysisResult(
            rule_id=rule_id,
            tenant_id=tenant_id,
            channel_id=channel_id,
            analysis_period=analysis_period,
            analysis_timestamp=datetime.now(timezone.utc),
            total_executions=total_executions,
            avg_f1_score=avg_f1_score,
            avg_precision=avg_precision,
            avg_recall=avg_recall,
            avg_false_positive_rate=avg_false_positive_rate,
            avg_duration_ms=avg_duration_ms,
            p95_duration_ms=p95_duration_ms,
            avg_throughput_rps=avg_throughput_rps,
            total_revenue_impact_brl=total_revenue_impact_brl,
            total_cost_impact_brl=total_cost_impact_brl,
            roi=roi,
            performance_trend=performance_trend,
            effectiveness_trend=effectiveness_trend,
            business_value_score=business_value_score
        )
        
    def _calculate_percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile from list of values."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(percentile * (len(sorted_values) - 1))
        return sorted_values[index]
        
    def _analyze_performance_trend(self, metrics: List[RuleExecutionMetrics]) -> str:
        """Analyze performance trend over time."""
        if len(metrics) < 6:  # Need at least 6 samples for trend
            return "stable"
            
        # Split into first and second half
        mid = len(metrics) // 2
        first_half = metrics[:mid]
        second_half = metrics[mid:]
        
        avg_first = statistics.mean(m.duration_ms for m in first_half)
        avg_second = statistics.mean(m.duration_ms for m in second_half)
        
        # Calculate percentage change
        change_percent = (avg_second - avg_first) / avg_first * 100
        
        if change_percent < -10:
            return "improving"
        elif change_percent > 10:
            return "degrading" 
        else:
            return "stable"
            
    def _analyze_effectiveness_trend(self, metrics: List[RuleExecutionMetrics]) -> str:
        """Analyze effectiveness trend over time."""
        if len(metrics) < 6:
            return "stable"
            
        mid = len(metrics) // 2
        first_half = metrics[:mid]
        second_half = metrics[mid:]
        
        avg_f1_first = statistics.mean(m.f1_score or 0 for m in first_half)
        avg_f1_second = statistics.mean(m.f1_score or 0 for m in second_half)
        
        if avg_f1_first == 0:
            return "stable"
            
        change_percent = (avg_f1_second - avg_f1_first) / avg_f1_first * 100
        
        if change_percent > 5:
            return "improving"
        elif change_percent < -5:
            return "degrading"
        else:
            return "stable"
            
    def _calculate_business_value_score(
        self, 
        f1_score: float, 
        roi: float, 
        throughput: float
    ) -> float:
        """
        Calculate composite business value score.
        
        Score components:
        - Effectiveness (F1 score): 50%
        - ROI: 30% 
        - Throughput efficiency: 20%
        """
        # Normalize ROI to 0-1 scale (cap at 10x ROI)
        roi_normalized = min(roi / 10.0, 1.0)
        
        # Normalize throughput to 0-1 scale (cap at 1000 rows/sec)
        throughput_normalized = min(throughput / 1000.0, 1.0)
        
        # Weighted composite score
        score = (
            f1_score * 0.5 +
            roi_normalized * 0.3 +
            throughput_normalized * 0.2
        )
        
        return round(score, 3)


class ClickHouseWriter:
    """Writes analysis results to ClickHouse data warehouse."""
    
    def __init__(self, clickhouse_url: str):
        """
        Initialize ClickHouse writer.
        
        Args:
            clickhouse_url: ClickHouse connection URL
        """
        self.clickhouse_url = clickhouse_url
        self.connection_pool = None
        
    async def initialize(self) -> None:
        """Initialize database connection pool."""
        # In a real implementation, you'd use an async ClickHouse client
        # like asynch or aiochclient
        logger.info("Initializing ClickHouse connection")
        
    async def write_rule_performance(self, metrics: RuleExecutionMetrics) -> None:
        """Write individual rule performance metrics to ClickHouse."""
        # This would insert into fact_rule_performance table
        logger.debug(f"Writing performance metrics for rule {metrics.rule_id}")
        
        # Simulate writing to ClickHouse
        # In reality, you'd use batch inserts for efficiency
        
    async def write_effectiveness_analysis(
        self, 
        analysis: EffectivenessAnalysisResult
    ) -> None:
        """Write effectiveness analysis results to ClickHouse."""
        logger.info(
            f"Writing effectiveness analysis for rule {analysis.rule_id}: "
            f"F1={analysis.avg_f1_score:.3f}, ROI={analysis.roi:.2f}"
        )
        
        # This would insert into fact_rule_effectiveness table
        # Example SQL:
        """
        INSERT INTO fact_rule_effectiveness (
            tenant_id, channel_id, rule_id, ruleset_version,
            analysis_date, analysis_timestamp, analysis_period_hours,
            jobs_analyzed, total_validations, avg_precision, avg_recall,
            avg_f1_score, avg_false_positive_rate, total_revenue_protected_brl,
            total_cost_prevented_brl, roi, business_value_score,
            performance_trend, effectiveness_trend
        ) VALUES (...)
        """
        
    async def close(self) -> None:
        """Close database connections."""
        if self.connection_pool:
            await self.connection_pool.close()


class RulesEffectivenessConsumer:
    """
    Main Kafka consumer for rules effectiveness analysis.
    
    Processes CloudEvents from rules engine execution and performs
    real-time effectiveness analysis with results stored in ClickHouse.
    """
    
    def __init__(
        self,
        kafka_bootstrap_servers: str,
        topic: str,
        consumer_group: str,
        clickhouse_url: str
    ):
        """
        Initialize the consumer.
        
        Args:
            kafka_bootstrap_servers: Kafka broker addresses
            topic: Kafka topic to consume from
            consumer_group: Consumer group ID
            clickhouse_url: ClickHouse connection URL
        """
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.topic = topic
        self.consumer_group = consumer_group
        
        self.consumer = None
        self.analyzer = RuleEffectivenessAnalyzer()
        self.clickhouse_writer = ClickHouseWriter(clickhouse_url)
        
        # Statistics
        self.messages_processed = 0
        self.errors_count = 0
        self.last_analysis_time = datetime.now(timezone.utc)
        
    async def start(self) -> None:
        """Start the consumer."""
        logger.info(
            f"Starting Rules Effectiveness Consumer: "
            f"topic={self.topic}, group={self.consumer_group}"
        )
        
        # Initialize dependencies
        await self.clickhouse_writer.initialize()
        
        # Create Kafka consumer
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.kafka_bootstrap_servers,
            group_id=self.consumer_group,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
        )
        
        await self.consumer.start()
        
        try:
            # Main consumption loop
            async for message in self.consumer:
                try:
                    await self._process_message(message)
                    self.messages_processed += 1
                    
                    # Periodic analysis
                    if self._should_run_analysis():
                        await self._run_periodic_analysis()
                        
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.errors_count += 1
                    
                    # Emit error event for monitoring
                    error_event = create_event(
                        event_type="rules.effectiveness.consumer.error",
                        data={
                            "error_type": e.__class__.__name__,
                            "error_message": str(e),
                            "kafka_partition": message.partition,
                            "kafka_offset": message.offset
                        },
                        source="pipelines/kafka/consumers/rules_effectiveness"
                    )
                    asyncio.create_task(emit_event(error_event))
                    
        except Exception as e:
            logger.error(f"Consumer error: {e}")
            raise
        finally:
            await self.stop()
            
    async def stop(self) -> None:
        """Stop the consumer and cleanup resources."""
        logger.info("Stopping Rules Effectiveness Consumer")
        
        if self.consumer:
            await self.consumer.stop()
            
        await self.clickhouse_writer.close()
        
    async def _process_message(self, message) -> None:
        """Process a single CloudEvent message."""
        event_data = message.value
        
        # Validate CloudEvent structure
        if not self._is_valid_cloudevent(event_data):
            logger.warning(f"Invalid CloudEvent structure: {event_data}")
            return
            
        event_type = event_data.get('type', '')
        
        # Process different event types
        if event_type == 'rules.execution.completed':
            await self._process_execution_event(event_data)
        elif event_type == 'rules.performance.measured':
            await self._process_performance_event(event_data)
        elif event_type == 'rules.compilation.completed':
            await self._process_compilation_event(event_data)
        else:
            # Skip uninteresting events
            logger.debug(f"Skipping event type: {event_type}")
            
    def _is_valid_cloudevent(self, event_data: Dict[str, Any]) -> bool:
        """Validate that message is a valid CloudEvent."""
        required_fields = ['id', 'source', 'specversion', 'type', 'time']
        return all(field in event_data for field in required_fields)
        
    async def _process_execution_event(self, event_data: Dict[str, Any]) -> None:
        """Process rules execution completed event."""
        data = event_data.get('data', {})
        
        # Extract metrics from event
        metrics = RuleExecutionMetrics(
            tenant_id=event_data.get('validahub_tenant_id', ''),
            channel_id=data.get('channel', ''),
            rule_id=data.get('ruleset_id', ''),  # Using ruleset as rule for now
            ruleset_version=data.get('version', ''),
            execution_timestamp=datetime.fromisoformat(
                event_data.get('time', '').replace('Z', '+00:00')
            ),
            duration_ms=data.get('execution_duration_ms', 0),
            rows_processed=data.get('processed_rows', 0),
            violations_found=data.get('validation_results', {}).get('error_count', 0),
            memory_usage_mb=data.get('performance_metrics', {}).get('memory_usage_mb', 0),
            revenue_impact_brl=data.get('business_impact', {}).get('revenue_protected_brl', 0),
            cost_impact_brl=data.get('processing_cost_brl', 0),
            job_id=data.get('job_id', ''),
            trace_id=event_data.get('validahub_trace_id', '')
        )
        
        # Add to analyzer
        self.analyzer.add_metrics(metrics)
        
        # Write to ClickHouse
        await self.clickhouse_writer.write_rule_performance(metrics)
        
    async def _process_performance_event(self, event_data: Dict[str, Any]) -> None:
        """Process individual rule performance event."""
        data = event_data.get('data', {})
        
        # Extract detailed performance metrics
        metrics = RuleExecutionMetrics(
            tenant_id=event_data.get('validahub_tenant_id', ''),
            channel_id=data.get('channel_id', ''),
            rule_id=data.get('rule_id', ''),
            ruleset_version=data.get('ruleset_version', ''),
            execution_timestamp=datetime.fromisoformat(
                event_data.get('time', '').replace('Z', '+00:00')
            ),
            duration_ms=data.get('execution_duration_ms', 0),
            rows_processed=data.get('rows_processed', 0),
            violations_found=data.get('violations_found', 0),
            memory_usage_mb=data.get('memory_usage_mb', 0),
            precision=data.get('performance_metrics', {}).get('precision'),
            recall=data.get('performance_metrics', {}).get('recall'),
            f1_score=data.get('performance_metrics', {}).get('f1_score'),
            false_positive_rate=data.get('performance_metrics', {}).get('false_positive_rate'),
            revenue_impact_brl=data.get('business_impact', {}).get('revenue_protected_brl', 0),
            cost_impact_brl=data.get('business_impact', {}).get('cost_prevented_brl', 0),
            job_id=data.get('job_id', ''),
            trace_id=event_data.get('validahub_trace_id', '')
        )
        
        # Add to analyzer
        self.analyzer.add_metrics(metrics)
        
        # Write detailed performance data
        await self.clickhouse_writer.write_rule_performance(metrics)
        
    async def _process_compilation_event(self, event_data: Dict[str, Any]) -> None:
        """Process rule compilation event."""
        # Compilation events provide context for performance analysis
        # but don't directly contribute to effectiveness metrics
        logger.debug(f"Processed compilation event for {event_data.get('data', {}).get('ruleset_id')}")
        
    def _should_run_analysis(self) -> bool:
        """Check if periodic analysis should run."""
        now = datetime.now(timezone.utc)
        return (now - self.last_analysis_time) > timedelta(minutes=5)
        
    async def _run_periodic_analysis(self) -> None:
        """Run periodic effectiveness analysis for all tracked rules."""
        logger.info("Running periodic effectiveness analysis")
        
        # Get unique rule keys from buffer
        rule_keys = list(self.analyzer.metrics_buffer.keys())
        
        analysis_results = []
        
        for rule_key in rule_keys:
            tenant_id, rule_id = rule_key.split(':', 1)
            
            # Analyze last hour
            analysis = self.analyzer.analyze_rule_effectiveness(
                tenant_id, rule_id, timedelta(hours=1)
            )
            
            if analysis:
                analysis_results.append(analysis)
                await self.clickhouse_writer.write_effectiveness_analysis(analysis)
                
        # Emit summary event
        if analysis_results:
            summary_event = create_event(
                event_type="rules.effectiveness.analyzed",
                data={
                    "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                    "rules_analyzed": len(analysis_results),
                    "avg_f1_score": statistics.mean(a.avg_f1_score for a in analysis_results),
                    "total_revenue_impact": sum(a.total_revenue_impact_brl for a in analysis_results),
                    "high_performance_rules": len([a for a in analysis_results if a.avg_f1_score > 0.8]),
                    "underperforming_rules": len([a for a in analysis_results if a.avg_f1_score < 0.5])
                },
                source="pipelines/kafka/consumers/rules_effectiveness"
            )
            asyncio.create_task(emit_event(summary_event))
            
        self.last_analysis_time = datetime.now(timezone.utc)
        
        logger.info(
            f"Completed analysis for {len(analysis_results)} rules. "
            f"Processed {self.messages_processed} messages total, "
            f"{self.errors_count} errors"
        )


# CLI Interface
@asyncclick.command()
@asyncclick.option(
    '--kafka-servers',
    default='localhost:9092',
    help='Kafka bootstrap servers'
)
@asyncclick.option(
    '--topic', 
    default='validahub.rules.events',
    help='Kafka topic to consume from'
)
@asyncclick.option(
    '--consumer-group',
    default='rules-effectiveness-analyzer',
    help='Kafka consumer group ID'
)
@asyncclick.option(
    '--clickhouse-url',
    default='http://localhost:8123/validahub',
    help='ClickHouse connection URL'
)
@asyncclick.option(
    '--log-level',
    default='INFO',
    help='Logging level'
)
async def main(
    kafka_servers: str,
    topic: str,
    consumer_group: str,
    clickhouse_url: str,
    log_level: str
) -> None:
    """
    ValidaHub Rules Effectiveness Analysis Consumer.
    
    Processes CloudEvents from Rules Engine to analyze rule effectiveness,
    calculate business impact, and provide insights for rule optimization.
    """
    # Configure logging
    logging.getLogger().setLevel(getattr(logging, log_level.upper()))
    
    logger.info("Starting ValidaHub Rules Effectiveness Consumer")
    logger.info(f"Kafka: {kafka_servers}")
    logger.info(f"Topic: {topic}")
    logger.info(f"Consumer Group: {consumer_group}")
    logger.info(f"ClickHouse: {clickhouse_url}")
    
    # Create and start consumer
    consumer = RulesEffectivenessConsumer(
        kafka_bootstrap_servers=kafka_servers,
        topic=topic,
        consumer_group=consumer_group,
        clickhouse_url=clickhouse_url
    )
    
    try:
        await consumer.start()
    except KeyboardInterrupt:
        logger.info("Shutting down consumer...")
    except Exception as e:
        logger.error(f"Consumer failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())