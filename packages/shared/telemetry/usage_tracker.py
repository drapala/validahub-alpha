"""
User behavior and product usage tracking for ValidaHub.

This module provides comprehensive tracking of user interactions, feature adoption,
and product usage patterns to drive data-driven product decisions.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from .emitter import get_emitter
from .envelope import create_event


class UserAction(Enum):
    """Standardized user actions for consistent tracking."""
    
    # Authentication & Onboarding
    LOGIN = "user.login"
    LOGOUT = "user.logout"
    SIGNUP = "user.signup"
    ONBOARDING_STARTED = "onboarding.started"
    ONBOARDING_COMPLETED = "onboarding.completed"
    ONBOARDING_ABANDONED = "onboarding.abandoned"
    
    # Job Management
    JOB_SUBMIT = "job.submit"
    JOB_VIEW = "job.view"
    JOB_RETRY = "job.retry"
    JOB_CANCEL = "job.cancel"
    JOB_DOWNLOAD = "job.download"
    
    # Dashboard & Navigation
    DASHBOARD_VIEW = "dashboard.view"
    PAGE_VIEW = "page.view"
    NAVIGATION = "navigation"
    SEARCH = "search"
    FILTER_APPLY = "filter.apply"
    
    # Features & Tools
    FEATURE_USED = "feature.used"
    TOOL_OPENED = "tool.opened"
    INTEGRATION_SETUP = "integration.setup"
    API_KEY_GENERATED = "api_key.generated"
    
    # Data & Files
    FILE_UPLOAD = "file.upload"
    FILE_DOWNLOAD = "file.download"
    DATA_EXPORT = "data.export"
    TEMPLATE_DOWNLOAD = "template.download"
    
    # Settings & Configuration
    SETTINGS_CHANGED = "settings.changed"
    PROFILE_UPDATED = "profile.updated"
    NOTIFICATION_PREFERENCE = "notification.preference"
    
    # Support & Feedback
    HELP_ACCESSED = "help.accessed"
    FEEDBACK_SUBMITTED = "feedback.submitted"
    SUPPORT_CONTACTED = "support.contacted"
    
    # Business Actions
    SUBSCRIPTION_UPGRADE = "subscription.upgrade"
    SUBSCRIPTION_DOWNGRADE = "subscription.downgrade"
    BILLING_VIEWED = "billing.viewed"
    INVOICE_DOWNLOADED = "invoice.downloaded"


class FeatureCategory(Enum):
    """Feature categories for adoption tracking."""
    CORE = "core"                     # Essential features
    ADVANCED = "advanced"             # Power user features
    INTEGRATION = "integration"       # API, webhooks, connectors
    ANALYTICS = "analytics"           # Reports, insights, dashboards
    COLLABORATION = "collaboration"   # Team features, sharing
    AUTOMATION = "automation"         # Rules, workflows, triggers


@dataclass
class UserSession:
    """User session tracking data."""
    session_id: str
    user_id: str
    tenant_id: str
    
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None
    
    # Session attributes
    user_agent: str | None = None
    ip_address: str | None = None
    device_type: str = "unknown"      # desktop, mobile, tablet
    browser: str = "unknown"
    os: str = "unknown"
    
    # Activity tracking
    page_views: int = 0
    actions_performed: int = 0
    features_used: list[str] = field(default_factory=list)
    pages_visited: list[str] = field(default_factory=list)
    
    # Engagement metrics
    active_time_seconds: int = 0      # Time actively using the app
    idle_time_seconds: int = 0        # Time idle but session active
    bounce_rate: float = 0.0          # 1 page view = bounce
    
    def update_activity(self):
        """Update last activity timestamp."""
        now = datetime.now(UTC)
        
        # Calculate idle time
        time_since_last = (now - self.last_activity).total_seconds()
        if time_since_last < 300:  # 5 minutes threshold for active time
            self.active_time_seconds += int(time_since_last)
        else:
            self.idle_time_seconds += int(time_since_last)
        
        self.last_activity = now
        self.actions_performed += 1
    
    def end_session(self):
        """End the session and calculate final metrics."""
        self.end_time = datetime.now(UTC)
        
        # Calculate total session duration
        total_duration = (self.end_time - self.start_time).total_seconds()
        
        # Update bounce rate
        self.bounce_rate = 1.0 if self.page_views <= 1 else 0.0
        
        return {
            "session_id": self.session_id,
            "duration_seconds": int(total_duration),
            "active_time_seconds": self.active_time_seconds,
            "idle_time_seconds": self.idle_time_seconds,
            "pages_visited": len(set(self.pages_visited)),
            "unique_features_used": len(set(self.features_used)),
            "actions_per_minute": self.actions_performed / (total_duration / 60) if total_duration > 0 else 0,
            "engagement_rate": self.active_time_seconds / total_duration if total_duration > 0 else 0,
            "bounce_rate": self.bounce_rate,
        }


class UsageTracker:
    """
    Comprehensive usage tracking for ValidaHub user behavior.
    
    This class provides methods to track all user interactions, feature adoption,
    and product usage patterns for data-driven product development.
    """
    
    def __init__(self):
        self.emitter = get_emitter()
        self.active_sessions: dict[str, UserSession] = {}
        self.feature_registry: dict[str, FeatureCategory] = {}
        self._initialize_feature_registry()
    
    def _initialize_feature_registry(self):
        """Initialize the feature registry with categories."""
        core_features = [
            "job_submit", "job_view", "file_upload", "dashboard_view",
            "validation_results", "error_review"
        ]
        
        advanced_features = [
            "bulk_operations", "custom_rules", "data_transformation",
            "advanced_filters", "job_scheduling", "template_creation"
        ]
        
        integration_features = [
            "api_usage", "webhook_setup", "marketplace_integration",
            "csv_connector", "automated_workflows"
        ]
        
        analytics_features = [
            "performance_dashboard", "data_quality_reports", "trend_analysis",
            "export_analytics", "custom_reports"
        ]
        
        collaboration_features = [
            "team_management", "role_assignment", "shared_templates",
            "comment_system", "approval_workflows"
        ]
        
        automation_features = [
            "auto_correction", "rule_automation", "notification_rules",
            "smart_suggestions", "ml_insights"
        ]
        
        # Register features by category
        for feature in core_features:
            self.feature_registry[feature] = FeatureCategory.CORE
        for feature in advanced_features:
            self.feature_registry[feature] = FeatureCategory.ADVANCED
        for feature in integration_features:
            self.feature_registry[feature] = FeatureCategory.INTEGRATION
        for feature in analytics_features:
            self.feature_registry[feature] = FeatureCategory.ANALYTICS
        for feature in collaboration_features:
            self.feature_registry[feature] = FeatureCategory.COLLABORATION
        for feature in automation_features:
            self.feature_registry[feature] = FeatureCategory.AUTOMATION
    
    def start_session(
        self,
        session_id: str,
        user_id: str,
        tenant_id: str,
        user_agent: str | None = None,
        ip_address: str | None = None
    ) -> UserSession:
        """Start tracking a new user session."""
        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            user_agent=user_agent,
            ip_address=ip_address
        )
        
        # Parse user agent for device info
        if user_agent:
            session.device_type = self._parse_device_type(user_agent)
            session.browser = self._parse_browser(user_agent)
            session.os = self._parse_os(user_agent)
        
        self.active_sessions[session_id] = session
        
        # Track session start event
        self.track_action(
            UserAction.LOGIN,
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            context={
                "device_type": session.device_type,
                "browser": session.browser,
                "os": session.os,
            }
        )
        
        return session
    
    def end_session(self, session_id: str) -> dict[str, Any] | None:
        """End a user session and emit session summary."""
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        session_summary = session.end_session()
        
        # Emit session completed event
        event = create_event(
            event_type="session.completed",
            data={
                "user_id": session.user_id,
                "session_summary": session_summary,
                "feature_usage": {
                    feature: session.features_used.count(feature)
                    for feature in set(session.features_used)
                },
                "navigation_pattern": session.pages_visited,
            },
            subject=f"session:{session_id}",
            source="usage.tracker",
            tenant_id=session.tenant_id,
            actor_id=session.user_id
        )
        
        self.emitter.emit_event(event, force_emit=True)
        
        # Clean up
        del self.active_sessions[session_id]
        
        return session_summary
    
    def track_action(
        self,
        action: UserAction,
        user_id: str,
        tenant_id: str,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
        revenue_impact: float | None = None
    ):
        """Track a user action with comprehensive context."""
        # Update session if active
        if session_id and session_id in self.active_sessions:
            self.active_sessions[session_id].update_activity()
        
        # Prepare event data
        event_data = {
            "user_id": user_id,
            "action": action.value,
            "session_id": session_id,
            "timestamp": datetime.now(UTC).isoformat(),
            **(context or {})
        }
        
        # Determine if this is a business-critical action
        business_actions = {
            UserAction.SUBSCRIPTION_UPGRADE,
            UserAction.JOB_SUBMIT,
            UserAction.INTEGRATION_SETUP,
            UserAction.API_KEY_GENERATED
        }
        
        if action in business_actions or revenue_impact:
            # Use business event tracking
            self.emitter.track_business_event(
                event_type=action.value,
                business_data=event_data,
                revenue_impact_brl=revenue_impact,
                tenant_id=tenant_id,
                actor_id=user_id
            )
        else:
            # Regular product usage event
            event = create_event(
                event_type=action.value,
                data=event_data,
                subject=f"user:{user_id}",
                source="usage.tracker",
                tenant_id=tenant_id,
                actor_id=user_id
            )
            
            self.emitter.emit_event(event)
        
        # Track feature usage separately
        if action == UserAction.FEATURE_USED and context and "feature_name" in context:
            self.track_feature_usage(
                feature_name=context["feature_name"],
                user_id=user_id,
                tenant_id=tenant_id,
                session_id=session_id,
                usage_context=context
            )
    
    def track_feature_usage(
        self,
        feature_name: str,
        user_id: str,
        tenant_id: str,
        session_id: str | None = None,
        usage_context: dict[str, Any] | None = None
    ):
        """Track feature usage with adoption metrics."""
        # Update session feature tracking
        if session_id and session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.features_used.append(feature_name)
        
        # Determine feature category
        feature_category = self.feature_registry.get(feature_name, FeatureCategory.CORE)
        
        # Track feature adoption event
        event_data = {
            "feature_name": feature_name,
            "feature_category": feature_category.value,
            "user_id": user_id,
            "session_id": session_id,
            "usage_context": usage_context or {},
        }
        
        event = create_event(
            event_type="feature.used",
            data=event_data,
            subject=f"feature:{feature_name}",
            source="usage.tracker",
            tenant_id=tenant_id,
            actor_id=user_id
        )
        
        self.emitter.emit_event(event)
        
        # Track feature adoption metric
        self.emitter.emit_metric(
            name="feature_usage_total",
            value=1,
            metric_type="counter",
            tags={
                "feature_name": feature_name,
                "feature_category": feature_category.value,
                "tenant_id": tenant_id,
            }
        )
    
    def track_page_view(
        self,
        page_name: str,
        user_id: str,
        tenant_id: str,
        session_id: str,
        page_metadata: dict[str, Any] | None = None
    ):
        """Track page views for navigation analysis."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.page_views += 1
            session.pages_visited.append(page_name)
            session.update_activity()
        
        # Track page view event
        event_data = {
            "page_name": page_name,
            "user_id": user_id,
            "session_id": session_id,
            "page_metadata": page_metadata or {},
            "referrer": page_metadata.get("referrer") if page_metadata else None,
        }
        
        self.track_action(
            UserAction.PAGE_VIEW,
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            context=event_data
        )
    
    def track_conversion_funnel(
        self,
        funnel_name: str,
        step_name: str,
        user_id: str,
        tenant_id: str,
        step_data: dict[str, Any] | None = None
    ):
        """Track user progress through conversion funnels."""
        event_data = {
            "funnel_name": funnel_name,
            "step_name": step_name,
            "step_data": step_data or {},
            "user_id": user_id,
        }
        
        event = create_event(
            event_type="funnel.step_completed",
            data=event_data,
            subject=f"funnel:{funnel_name}",
            source="usage.tracker",
            tenant_id=tenant_id,
            actor_id=user_id
        )
        
        self.emitter.emit_event(event, force_emit=True)
        
        # Track funnel metrics
        self.emitter.emit_metric(
            name="funnel_step_completion",
            value=1,
            metric_type="counter",
            tags={
                "funnel_name": funnel_name,
                "step_name": step_name,
                "tenant_id": tenant_id,
            }
        )
    
    def track_user_journey(
        self,
        journey_id: str,
        milestone: str,
        user_id: str,
        tenant_id: str,
        milestone_data: dict[str, Any] | None = None
    ):
        """Track user journey milestones for onboarding and engagement."""
        event_data = {
            "journey_id": journey_id,
            "milestone": milestone,
            "milestone_data": milestone_data or {},
            "user_id": user_id,
        }
        
        event = create_event(
            event_type="user_journey.milestone",
            data=event_data,
            subject=f"journey:{journey_id}",
            source="usage.tracker",
            tenant_id=tenant_id,
            actor_id=user_id
        )
        
        self.emitter.emit_event(event, force_emit=True)
    
    def calculate_feature_adoption(
        self,
        tenant_id: str,
        period_days: int = 30
    ) -> dict[str, float]:
        """
        Calculate feature adoption rates for a tenant.
        
        Note: In production, this would query the analytics database.
        Here we return a sample structure.
        """
        # This would be implemented with actual data queries
        return {
            "core_features_adoption": 0.85,
            "advanced_features_adoption": 0.45,
            "integration_features_adoption": 0.25,
            "analytics_features_adoption": 0.60,
            "collaboration_features_adoption": 0.30,
            "automation_features_adoption": 0.15,
        }
    
    def generate_usage_insights(
        self,
        tenant_id: str,
        user_id: str | None = None
    ) -> dict[str, Any]:
        """Generate usage insights and recommendations."""
        # Sample insights - would be calculated from real data
        insights = {
            "engagement_level": "high",  # low, medium, high
            "feature_adoption_score": 0.68,
            "areas_for_improvement": [
                "Advanced features adoption is low",
                "Integration setup not completed",
                "Analytics features underutilized"
            ],
            "recommendations": [
                "Schedule advanced features demo",
                "Provide integration setup assistance", 
                "Share analytics best practices guide"
            ],
            "usage_patterns": {
                "peak_usage_hours": [9, 10, 11, 14, 15],
                "most_used_features": ["job_submit", "dashboard_view", "file_upload"],
                "session_duration_trend": "increasing",
                "bounce_rate": 0.15
            }
        }
        
        return insights
    
    # Helper methods for user agent parsing
    def _parse_device_type(self, user_agent: str) -> str:
        """Parse device type from user agent."""
        user_agent = user_agent.lower()
        if "mobile" in user_agent or "android" in user_agent or "iphone" in user_agent:
            return "mobile"
        elif "tablet" in user_agent or "ipad" in user_agent:
            return "tablet"
        else:
            return "desktop"
    
    def _parse_browser(self, user_agent: str) -> str:
        """Parse browser from user agent."""
        user_agent = user_agent.lower()
        if "chrome" in user_agent:
            return "chrome"
        elif "firefox" in user_agent:
            return "firefox"
        elif "safari" in user_agent:
            return "safari"
        elif "edge" in user_agent:
            return "edge"
        else:
            return "unknown"
    
    def _parse_os(self, user_agent: str) -> str:
        """Parse operating system from user agent."""
        user_agent = user_agent.lower()
        if "windows" in user_agent:
            return "windows"
        elif "mac" in user_agent:
            return "macos"
        elif "linux" in user_agent:
            return "linux"
        elif "android" in user_agent:
            return "android"
        elif "ios" in user_agent:
            return "ios"
        else:
            return "unknown"


# Global usage tracker instance
_usage_tracker: UsageTracker | None = None


def get_usage_tracker() -> UsageTracker:
    """Get the global usage tracker."""
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker()
    return _usage_tracker


# Convenience functions
def track_user_action(
    action: UserAction,
    user_id: str,
    tenant_id: str,
    session_id: str | None = None,
    context: dict[str, Any] | None = None,
    revenue_impact: float | None = None
):
    """Track user action using global tracker."""
    get_usage_tracker().track_action(
        action, user_id, tenant_id, session_id, context, revenue_impact
    )


def track_feature_usage(
    feature_name: str,
    user_id: str,
    tenant_id: str,
    session_id: str | None = None,
    usage_context: dict[str, Any] | None = None
):
    """Track feature usage using global tracker."""
    get_usage_tracker().track_feature_usage(
        feature_name, user_id, tenant_id, session_id, usage_context
    )


def start_user_session(
    session_id: str,
    user_id: str,
    tenant_id: str,
    user_agent: str | None = None,
    ip_address: str | None = None
) -> UserSession:
    """Start user session using global tracker."""
    return get_usage_tracker().start_session(
        session_id, user_id, tenant_id, user_agent, ip_address
    )