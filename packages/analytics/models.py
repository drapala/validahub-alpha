"""
ValidaHub Analytics Data Models - Star Schema Design

This module defines the dimensional data model for ValidaHub's business intelligence.
The design follows Kimball methodology with fact and dimension tables optimized
for marketplace intelligence and revenue attribution.

Schema Overview:
- Facts: job, validation, usage, revenue
- Dimensions: tenant, channel, rule, time, seller
- Derived metrics: ROI, data quality scores, marketplace trends
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class GrainLevel(Enum):
    """Granularity levels for fact tables."""
    TRANSACTION = "transaction"  # Individual job/validation
    DAILY = "daily"             # Daily aggregates
    MONTHLY = "monthly"         # Monthly aggregates
    WEEKLY = "weekly"          # Weekly aggregates


# DIMENSION TABLES

@dataclass
class DimTenant:
    """
    Tenant dimension - SCD Type 2 for historical tracking.
    
    Tracks tenant lifecycle, plan changes, and business attributes
    for segmentation and revenue analysis.
    """
    tenant_id: str                    # Natural key
    tenant_sk: int                    # Surrogate key
    tenant_name: str
    company_name: str | None = None
    plan_type: str = "free"           # free, starter, professional, enterprise
    industry_segment: str | None = None
    company_size: str | None = None # micro, small, medium, large, enterprise
    country_code: str = "BR"
    state_code: str | None = None
    city: str | None = None
    onboarding_date: date | None = None
    plan_upgrade_date: date | None = None
    
    # SCD Type 2 fields
    effective_date: date = field(default_factory=date.today)
    expiration_date: date | None = None
    is_current: bool = True
    version: int = 1
    
    # Business metrics
    monthly_revenue_brl: Decimal = Decimal('0.00')
    total_lifetime_value_brl: Decimal = Decimal('0.00')
    churn_risk_score: float = 0.0      # 0-1 scale
    net_promoter_score: int | None = None
    
    # Usage metrics
    total_jobs_processed: int = 0
    total_data_volume_gb: Decimal = Decimal('0.00')
    average_data_quality_score: float = 0.0
    
    def __post_init__(self) -> None:
        if self.onboarding_date is None:
            self.onboarding_date = date.today()


@dataclass  
class DimChannel:
    """
    Marketplace/Channel dimension.
    
    Tracks marketplace-specific attributes for cross-channel intelligence
    and channel performance analysis.
    """
    channel_sk: int                   # Surrogate key
    channel_code: str                 # Natural key (ml, magalu, shopee, etc.)
    channel_name: str
    channel_category: str             # marketplace, social_commerce, b2b, etc.
    
    # Marketplace attributes
    commission_rate: float | None = None  # Average commission %
    listing_fee_brl: Decimal | None = None
    validation_complexity: str = "medium"    # low, medium, high, very_high
    api_quality_score: float = 8.0           # 1-10 scale
    
    # Rule engine attributes
    total_rules: int = 0
    active_rules: int = 0
    rule_accuracy_rate: float = 0.95
    last_rules_update: date | None = None
    
    # Business metrics
    total_gmv_brl: Decimal = Decimal('0.00')  # Gross Merchandise Value
    average_order_value_brl: Decimal = Decimal('0.00')
    conversion_rate: float = 0.0
    
    # Data quality patterns
    common_error_categories: list[str] = field(default_factory=list)
    data_completeness_rate: float = 0.0
    validation_pass_rate: float = 0.0
    
    def get_validation_difficulty_score(self) -> float:
        """Calculate validation difficulty (1-10 scale)."""
        complexity_scores = {
            "low": 2.0,
            "medium": 5.0, 
            "high": 8.0,
            "very_high": 10.0
        }
        return complexity_scores.get(self.validation_complexity, 5.0)


@dataclass
class DimRule:
    """
    Validation rule dimension.
    
    Tracks rule effectiveness, evolution, and marketplace-specific patterns.
    """
    rule_sk: int                      # Surrogate key
    rule_id: str                      # Natural key
    rule_name: str
    rule_category: str                # pricing, inventory, content, compliance
    rule_type: str                    # validation, correction, enrichment
    severity_level: str               # error, warning, info
    
    # Rule metadata
    channel_code: str                 # Associated marketplace
    rule_version: str = "1.0.0"
    created_date: date = field(default_factory=date.today)
    last_modified_date: date = field(default_factory=date.today)
    is_active: bool = True
    
    # Effectiveness metrics
    true_positive_rate: float = 0.0   # Recall
    precision_rate: float = 0.0       # Precision  
    false_positive_rate: float = 0.0
    accuracy_score: float = 0.0
    
    # Usage statistics
    total_applications: int = 0
    total_violations: int = 0
    monthly_trend: str = "stable"     # increasing, decreasing, stable
    
    # Business impact
    estimated_revenue_protection_brl: Decimal = Decimal('0.00')
    compliance_score: float = 1.0
    automation_rate: float = 0.0      # % of violations auto-corrected
    
    def calculate_f1_score(self) -> float:
        """Calculate F1 score from precision and recall."""
        if self.precision_rate + self.true_positive_rate == 0:
            return 0.0
        return 2 * (self.precision_rate * self.true_positive_rate) / (self.precision_rate + self.true_positive_rate)


@dataclass
class DimSeller:
    """
    Seller dimension for tenant segmentation and behavior analysis.
    """
    seller_sk: int                    # Surrogate key
    seller_id: str                    # Natural key within tenant
    tenant_sk: int                    # Foreign key to tenant
    
    # Seller attributes
    seller_name: str | None = None
    seller_segment: str = "individual" # individual, micro, small, medium, large
    business_category: str | None = None
    years_in_business: int | None = None
    
    # Performance metrics
    total_products: int = 0
    active_products: int = 0
    average_product_price_brl: Decimal = Decimal('0.00')
    total_revenue_brl: Decimal = Decimal('0.00')
    
    # Data quality profile
    data_quality_score: float = 0.0   # 0-100 scale
    validation_compliance_rate: float = 0.0
    common_error_patterns: list[str] = field(default_factory=list)
    improvement_trend: str = "stable" # improving, declining, stable
    
    # Engagement metrics
    last_job_date: date | None = None
    monthly_job_frequency: int = 0
    feature_adoption_score: float = 0.0


@dataclass
class DimTime:
    """
    Standard time dimension with business calendar attributes.
    """
    date_sk: int                      # Surrogate key (YYYYMMDD format)
    full_date: date
    
    # Date attributes
    year: int
    quarter: int
    month: int
    month_name: str
    week_of_year: int
    day_of_month: int
    day_of_week: int
    day_name: str
    
    # Business calendar
    is_weekend: bool = False
    is_holiday: bool = False
    is_business_day: bool = True
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None
    
    # Marketplace seasonality
    is_black_friday_week: bool = False
    is_christmas_season: bool = False  # Nov-Dec
    is_back_to_school: bool = False    # Jan-Feb
    seasonality_factor: float = 1.0    # Demand multiplier
    
    def __post_init__(self) -> None:
        if self.fiscal_year is None:
            # Fiscal year starts in April for Brazil
            if self.month >= 4:
                self.fiscal_year = self.year
            else:
                self.fiscal_year = self.year - 1
        
        if self.fiscal_quarter is None:
            fiscal_month = ((self.month - 4) % 12) + 1
            self.fiscal_quarter = (fiscal_month - 1) // 3 + 1


# FACT TABLES

@dataclass
class FactJob:
    """
    Job processing fact table - Core transactional fact.
    
    Captures every job execution with comprehensive business and technical metrics
    for detailed analysis and attribution.
    """
    job_sk: int                       # Surrogate key
    job_id: str                       # Business key
    
    # Dimension keys
    tenant_sk: int
    channel_sk: int
    date_sk: int                      # Processing date
    submission_date_sk: int           # Submission date
    
    # Job attributes
    job_type: str                     # validation, correction, enrichment
    job_status: str                   # succeeded, failed, cancelled, etc.
    
    # Processing metrics
    submission_timestamp: datetime
    
    # Optional dimension keys
    seller_sk: int | None = None
    
    # Optional processing metrics
    start_timestamp: datetime | None = None
    completion_timestamp: datetime | None = None
    
    # Job attributes with defaults
    priority: str = "normal"          # low, normal, high, urgent
    queue_duration_seconds: int = 0
    processing_duration_seconds: int = 0
    total_duration_seconds: int = 0
    
    # Data volume metrics  
    input_file_size_bytes: int = 0
    output_file_size_bytes: int = 0
    total_records: int = 0
    processed_records: int = 0
    skipped_records: int = 0
    
    # Quality metrics
    validation_errors: int = 0
    validation_warnings: int = 0
    critical_errors: int = 0
    data_quality_score: float = 0.0   # 0-100 scale
    
    # Business metrics
    estimated_revenue_impact_brl: Decimal = Decimal('0.00')
    processing_cost_brl: Decimal = Decimal('0.00')
    storage_cost_brl: Decimal = Decimal('0.00')
    total_cost_brl: Decimal = Decimal('0.00')
    
    # Derived metrics (calculated)
    success_indicator: int = 0         # 1 if succeeded, 0 otherwise
    error_rate: float = 0.0            # errors / total_records
    processing_efficiency: float = 0.0  # records / second
    cost_per_record_brl: Decimal = Decimal('0.00')
    roi_ratio: float = 0.0             # revenue / cost
    
    def __post_init__(self) -> None:
        """Calculate derived metrics."""
        # Success indicator
        self.success_indicator = 1 if self.job_status == "succeeded" else 0
        
        # Error rate
        if self.total_records > 0:
            self.error_rate = self.validation_errors / self.total_records
        
        # Processing efficiency
        if self.processing_duration_seconds > 0:
            self.processing_efficiency = self.processed_records / self.processing_duration_seconds
        
        # Cost per record
        if self.processed_records > 0 and self.total_cost_brl > 0:
            self.cost_per_record_brl = self.total_cost_brl / self.processed_records
        
        # ROI calculation
        if self.total_cost_brl > 0:
            self.roi_ratio = float(self.estimated_revenue_impact_brl / self.total_cost_brl)


@dataclass
class FactValidation:
    """
    Validation rule application fact table.
    
    Captures individual rule violations for detailed marketplace intelligence
    and rule effectiveness analysis.
    """
    validation_sk: int                # Surrogate key
    
    # Dimension keys
    job_sk: int                       # Parent job
    tenant_sk: int
    channel_sk: int
    rule_sk: int
    date_sk: int
    
    # Validation attributes
    violation_type: str               # error, warning, info
    field_name: str                   # Product field that failed
    record_number: int                # Record position in file
    
    # Rule application
    rule_triggered: bool = True
    auto_corrected: bool = False
    correction_confidence: float = 0.0 # 0-1 for ML corrections
    
    # Business context
    product_category: str | None = None
    product_price_brl: Decimal | None = None
    estimated_lost_revenue_brl: Decimal = Decimal('0.00')
    
    # Pattern analysis
    error_category: str = "data_quality"  # pricing, content, compliance, etc.
    error_subcategory: str | None = None
    severity_score: int = 1            # 1-10 scale
    
    # Resolution tracking
    resolution_status: str = "open"    # open, resolved, ignored
    resolution_timestamp: datetime | None = None
    resolution_method: str | None = None  # manual, auto, rule_update
    
    def calculate_business_impact(self) -> dict[str, float]:
        """Calculate business impact metrics."""
        return {
            "revenue_risk": float(self.estimated_lost_revenue_brl),
            "severity_weighted_impact": self.severity_score * float(self.estimated_lost_revenue_brl),
            "automation_opportunity": 1.0 if not self.auto_corrected and self.correction_confidence > 0.8 else 0.0
        }


@dataclass
class FactUsage:
    """
    Daily usage aggregation fact table.
    
    Pre-aggregated metrics for dashboard performance and trend analysis.
    """
    usage_sk: int                     # Surrogate key
    
    # Dimension keys
    tenant_sk: int
    date_sk: int
    channel_sk: int | None = None
    
    # Aggregated metrics
    total_jobs: int = 0
    successful_jobs: int = 0
    failed_jobs: int = 0
    total_records_processed: int = 0
    total_data_volume_gb: Decimal = Decimal('0.00')
    
    # Performance metrics
    average_processing_time_seconds: float = 0.0
    p95_processing_time_seconds: float = 0.0
    total_queue_time_seconds: int = 0
    
    # Quality metrics
    total_validation_errors: int = 0
    total_validation_warnings: int = 0
    average_data_quality_score: float = 0.0
    
    # Business metrics
    total_revenue_attributed_brl: Decimal = Decimal('0.00')
    total_cost_brl: Decimal = Decimal('0.00')
    average_roi: float = 0.0
    
    # Derived KPIs
    success_rate: float = 0.0          # successful_jobs / total_jobs
    error_rate: float = 0.0            # errors / total_records
    cost_efficiency: float = 0.0       # records_processed / cost
    
    def __post_init__(self) -> None:
        """Calculate derived KPIs."""
        if self.total_jobs > 0:
            self.success_rate = self.successful_jobs / self.total_jobs
        
        if self.total_records_processed > 0:
            self.error_rate = self.total_validation_errors / self.total_records_processed
            
            if self.total_cost_brl > 0:
                self.cost_efficiency = self.total_records_processed / float(self.total_cost_brl)


@dataclass
class FactRevenue:
    """
    Revenue attribution fact table.
    
    Tracks revenue attribution at various granularities for comprehensive
    financial analysis and pricing optimization.
    """
    revenue_sk: int                   # Surrogate key
    
    # Dimension keys
    tenant_sk: int
    date_sk: int
    channel_sk: int | None = None
    
    # Revenue components
    subscription_revenue_brl: Decimal = Decimal('0.00')
    usage_revenue_brl: Decimal = Decimal('0.00')
    premium_features_revenue_brl: Decimal = Decimal('0.00')
    total_revenue_brl: Decimal = Decimal('0.00')
    
    # Cost components
    infrastructure_cost_brl: Decimal = Decimal('0.00')
    support_cost_brl: Decimal = Decimal('0.00')
    acquisition_cost_brl: Decimal = Decimal('0.00')
    total_cost_brl: Decimal = Decimal('0.00')
    
    # Usage metrics for attribution
    jobs_processed: int = 0
    data_volume_gb: Decimal = Decimal('0.00')
    premium_features_used: int = 0
    
    # Derived metrics
    gross_profit_brl: Decimal = Decimal('0.00')
    profit_margin: float = 0.0
    revenue_per_job_brl: Decimal = Decimal('0.00')
    cost_per_gb_brl: Decimal = Decimal('0.00')
    
    def __post_init__(self) -> None:
        """Calculate derived metrics."""
        self.gross_profit_brl = self.total_revenue_brl - self.total_cost_brl
        
        if self.total_revenue_brl > 0:
            self.profit_margin = float(self.gross_profit_brl / self.total_revenue_brl)
        
        if self.jobs_processed > 0:
            self.revenue_per_job_brl = self.total_revenue_brl / self.jobs_processed
        
        if self.data_volume_gb > 0:
            self.cost_per_gb_brl = self.total_cost_brl / self.data_volume_gb


# ANALYTICAL VIEWS AND AGGREGATES

@dataclass
class TenantHealthScore:
    """
    Tenant health score calculation for retention and expansion analysis.
    """
    tenant_sk: int
    calculation_date: date
    
    # Component scores (0-100 each)
    usage_score: float = 0.0           # Based on job frequency and volume
    quality_score: float = 0.0         # Based on data quality improvements
    engagement_score: float = 0.0      # Based on feature adoption
    satisfaction_score: float = 0.0    # Based on support interactions
    
    # Overall health metrics
    overall_health_score: float = 0.0  # Weighted average
    churn_risk_level: str = "low"      # low, medium, high, critical
    expansion_opportunity: str = "none" # none, low, medium, high
    
    # Trend indicators
    health_trend: str = "stable"       # improving, declining, stable
    usage_trend: str = "stable"
    quality_trend: str = "stable"
    
    # Recommendations
    recommended_actions: list[str] = field(default_factory=list)
    expansion_opportunities: list[str] = field(default_factory=list)


@dataclass
class MarketplaceIntelligence:
    """
    Cross-marketplace intelligence summary.
    """
    channel_sk: int
    analysis_period: str               # daily, weekly, monthly
    calculation_date: date
    
    # Validation patterns
    total_validations: int = 0
    top_error_categories: list[dict[str, Any]] = field(default_factory=list)
    data_quality_trend: str = "stable"
    
    # Rule effectiveness
    high_performing_rules: list[str] = field(default_factory=list)
    underperforming_rules: list[str] = field(default_factory=list)
    rule_optimization_opportunities: list[dict[str, Any]] = field(default_factory=list)
    
    # Competitive insights
    performance_vs_peers: float = 0.0  # Percentile ranking
    unique_advantages: list[str] = field(default_factory=list)
    improvement_areas: list[str] = field(default_factory=list)
    
    # Business metrics
    revenue_contribution: float = 0.0   # % of total platform revenue
    growth_rate: float = 0.0           # Month-over-month
    customer_satisfaction: float = 0.0  # Derived from success rates


# UTILITY FUNCTIONS FOR ANALYTICS

def calculate_customer_lifetime_value(
    monthly_revenue: Decimal,
    churn_rate: float,
    profit_margin: float = 0.3
) -> Decimal:
    """Calculate Customer Lifetime Value using standard formula."""
    if churn_rate <= 0 or churn_rate >= 1:
        return Decimal('0.00')
    
    # CLV = (Monthly Revenue * Profit Margin) / Monthly Churn Rate
    clv = (monthly_revenue * Decimal(str(profit_margin))) / Decimal(str(churn_rate))
    return clv


def calculate_data_quality_score(
    total_records: int,
    error_count: int,
    warning_count: int,
    completeness_rate: float = 1.0
) -> float:
    """
    Calculate comprehensive data quality score (0-100).
    
    Factors:
    - Error rate (weighted heavily)
    - Warning rate (weighted moderately) 
    - Data completeness
    """
    if total_records == 0:
        return 0.0
    
    error_rate = error_count / total_records
    warning_rate = warning_count / total_records
    
    # Weighted scoring
    accuracy_score = max(0, 100 - (error_rate * 100 * 0.8) - (warning_rate * 100 * 0.2))
    completeness_score = completeness_rate * 100
    
    # Composite score (80% accuracy, 20% completeness)
    quality_score = (accuracy_score * 0.8) + (completeness_score * 0.2)
    
    return min(100, max(0, quality_score))


def generate_business_insights(
    fact_jobs: list[FactJob],
    fact_validations: list[FactValidation],
    dim_channels: list[DimChannel]
) -> dict[str, Any]:
    """Generate automated business insights from fact data."""
    if not fact_jobs:
        return {"insights": []}
    
    insights = []
    
    # Calculate overall metrics
    total_jobs = len(fact_jobs)
    successful_jobs = sum(1 for job in fact_jobs if job.success_indicator == 1)
    success_rate = successful_jobs / total_jobs if total_jobs > 0 else 0
    
    # Success rate insights
    if success_rate < 0.95:
        insights.append({
            "type": "quality_alert",
            "message": f"Job success rate ({success_rate:.1%}) is below SLO target of 95%",
            "severity": "high",
            "recommended_action": "Review failing job patterns and improve error handling"
        })
    elif success_rate > 0.99:
        insights.append({
            "type": "performance_highlight", 
            "message": f"Excellent job success rate of {success_rate:.1%}",
            "severity": "info"
        })
    
    # Cost efficiency insights
    total_revenue = sum(job.estimated_revenue_impact_brl for job in fact_jobs)
    total_cost = sum(job.total_cost_brl for job in fact_jobs)
    
    if total_cost > 0:
        roi = float(total_revenue / total_cost)
        if roi < 2.0:
            insights.append({
                "type": "cost_optimization",
                "message": f"ROI of {roi:.1f}x indicates opportunity for cost optimization",
                "severity": "medium",
                "recommended_action": "Analyze high-cost jobs and optimize resource usage"
            })
    
    # Channel performance insights
    channel_performance: dict[int, dict[str, Any]] = {}
    for job in fact_jobs:
        channel_sk = job.channel_sk
        if channel_sk not in channel_performance:
            channel_performance[channel_sk] = {"jobs": 0, "success": 0, "revenue": Decimal('0.00')}
        
        channel_performance[channel_sk]["jobs"] += 1
        channel_performance[channel_sk]["success"] += job.success_indicator
        channel_performance[channel_sk]["revenue"] += job.estimated_revenue_impact_brl
    
    # Identify best and worst performing channels
    channel_success_rates = {
        channel: perf["success"] / perf["jobs"] 
        for channel, perf in channel_performance.items() 
        if perf["jobs"] >= 10  # Minimum sample size
    }
    
    if channel_success_rates:
        best_channel = max(channel_success_rates, key=lambda x: channel_success_rates[x])
        worst_channel = min(channel_success_rates, key=lambda x: channel_success_rates[x])
        
        insights.append({
            "type": "channel_analysis",
            "message": f"Channel {best_channel} has highest success rate ({channel_success_rates[best_channel]:.1%}), "
                      f"while channel {worst_channel} needs attention ({channel_success_rates[worst_channel]:.1%})",
            "severity": "info"
        })
    
    return {
        "insights": insights,
        "metrics_summary": {
            "total_jobs": total_jobs,
            "success_rate": success_rate,
            "roi": float(total_revenue / total_cost) if total_cost > 0 else 0,
            "total_revenue_brl": float(total_revenue),
            "total_cost_brl": float(total_cost)
        }
    }