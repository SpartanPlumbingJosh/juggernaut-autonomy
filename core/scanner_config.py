"""Opportunity Scanner Configuration Module.

This module centralizes all configuration for the proactive opportunity
scanning system, including scan intervals, scoring thresholds, and
source-specific settings.

L5-REV-04: Activate opportunity scanner in production.

Configuration Hierarchy:
1. Environment variables (highest priority)
2. Database settings (scheduled_tasks.config)
3. Default values in this module (lowest priority)
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# SCAN INTERVAL CONFIGURATION
# =============================================================================

class ScanInterval(Enum):
    """Predefined scan intervals for different scan types."""
    RAPID = 3600           # 1 hour - for time-sensitive opportunities
    STANDARD = 14400       # 4 hours - default production interval
    CONSERVATIVE = 28800   # 8 hours - for rate-limited sources
    DAILY = 86400          # 24 hours - for sources that update daily


# Production scan schedule (cron expressions)
PRODUCTION_SCAN_SCHEDULES: Dict[str, str] = {
    "opportunity_scan": "0 */4 * * *",      # Every 4 hours
    "expired_domains": "0 6 * * *",         # Daily at 6 AM UTC
    "trending_niches": "0 */6 * * *",       # Every 6 hours
    "saas_ideas": "0 9 * * 1",              # Weekly on Monday 9 AM UTC
    "competitor_analysis": "0 0 * * 0",     # Weekly on Sunday midnight
}

# Minimum intervals between scans (prevents over-scanning)
MIN_SCAN_INTERVALS: Dict[str, int] = {
    "default": 3600,            # 1 hour minimum between any scans
    "expired_domains": 43200,   # 12 hours (rate limiting)
    "trending_niches": 14400,   # 4 hours
    "saas_ideas": 86400,        # 24 hours
}


# =============================================================================
# SCORING THRESHOLDS CONFIGURATION
# =============================================================================

@dataclass
class ScoringThresholds:
    """Thresholds for opportunity scoring and qualification."""

    # Minimum score to consider an opportunity worth reviewing
    min_review_score: float = 0.4

    # Minimum score to automatically create an evaluation task
    min_qualified_score: float = 0.7

    # Score above which opportunity gets high priority
    high_priority_score: float = 0.85

    # Score above which to notify immediately
    urgent_notification_score: float = 0.95

    # Minimum estimated value (cents) to qualify
    min_value_cents: int = 1000  # $10 minimum

    # Maximum opportunities to create tasks for per scan
    max_tasks_per_scan: int = 10


# Default scoring thresholds for production
DEFAULT_SCORING_THRESHOLDS = ScoringThresholds()


@dataclass
class ScoringWeights:
    """Weights for different scoring factors."""

    # Source quality - how reliable is the source
    source_quality: float = 0.25

    # Estimated value - potential revenue
    estimated_value: float = 0.30

    # Category fit - how well it matches our focus areas
    category_fit: float = 0.20

    # Timing - how time-sensitive is this opportunity
    timing: float = 0.15

    # Competition - inverse of competition level
    competition: float = 0.10

    def validate(self) -> bool:
        """Verify weights sum to 1.0."""
        total = (self.source_quality + self.estimated_value +
                 self.category_fit + self.timing + self.competition)
        return abs(total - 1.0) < 0.001

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary format for DB storage."""
        return {
            "source_quality": self.source_quality,
            "estimated_value": self.estimated_value,
            "category_fit": self.category_fit,
            "timing": self.timing,
            "competition": self.competition,
        }


# Default scoring weights
DEFAULT_SCORING_WEIGHTS = ScoringWeights()


# =============================================================================
# SOURCE CONFIGURATION
# =============================================================================

@dataclass
class SourceConfig:
    """Configuration for a specific opportunity source."""

    name: str
    source_type: str
    enabled: bool = True
    scan_frequency_hours: int = 24
    priority: int = 5  # 1-10, higher = more important
    filters: Dict[str, Any] = field(default_factory=dict)
    rate_limit_per_hour: Optional[int] = None


# Production source configurations
PRODUCTION_SOURCE_CONFIGS: Dict[str, SourceConfig] = {
    "expired_domains": SourceConfig(
        name="ExpiredDomains.net",
        source_type="expired_domains",
        enabled=True,
        scan_frequency_hours=24,
        priority=8,
        filters={
            "tld": [".com", ".net", ".org"],
            "min_backlinks": 10,
            "min_domain_age_years": 3,
            "max_price_usd": 500,
        },
        rate_limit_per_hour=10,
    ),
    "trending_niches": SourceConfig(
        name="Google Trends",
        source_type="trending_niches",
        enabled=True,
        scan_frequency_hours=12,
        priority=7,
        filters={
            "geo": "US",
            "categories": ["business", "technology", "health"],
            "rising_threshold": 100,
            "breakout_only": True,
        },
        rate_limit_per_hour=20,
    ),
    "saas_ideas": SourceConfig(
        name="Product Hunt",
        source_type="saas_ideas",
        enabled=True,
        scan_frequency_hours=24,
        priority=6,
        filters={
            "min_upvotes": 100,
            "track_categories": [
                "productivity",
                "developer-tools",
                "artificial-intelligence",
                "marketing",
            ],
            "competitor_gap_detection": True,
        },
        rate_limit_per_hour=30,
    ),
}


# =============================================================================
# SCANNER CONFIGURATION CLASS
# =============================================================================

@dataclass
class ScannerConfig:
    """Complete scanner configuration for production use."""

    # Basic settings
    enabled: bool = True
    scan_all_sources: bool = True

    # Scoring configuration
    scoring_thresholds: ScoringThresholds = field(
        default_factory=lambda: DEFAULT_SCORING_THRESHOLDS
    )
    scoring_weights: ScoringWeights = field(
        default_factory=lambda: DEFAULT_SCORING_WEIGHTS
    )

    # Task creation
    create_tasks_for_high_scoring: bool = True
    max_tasks_per_scan: int = 10

    # Notifications
    notify_on_high_value: bool = True
    high_value_threshold_cents: int = 100000  # $1000

    # Logging
    log_all_opportunities: bool = True
    log_scoring_details: bool = False  # Verbose scoring logs

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for DB storage."""
        return {
            "enabled": self.enabled,
            "scan_all_sources": self.scan_all_sources,
            "min_confidence_score": self.scoring_thresholds.min_qualified_score,
            "min_review_score": self.scoring_thresholds.min_review_score,
            "high_priority_score": self.scoring_thresholds.high_priority_score,
            "create_tasks_for_high_scoring": self.create_tasks_for_high_scoring,
            "max_tasks_per_scan": self.max_tasks_per_scan,
            "notify_on_high_value": self.notify_on_high_value,
            "high_value_threshold_cents": self.high_value_threshold_cents,
            "scoring_weights": self.scoring_weights.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScannerConfig":
        """Create from dictionary (e.g., from database)."""
        thresholds = ScoringThresholds(
            min_qualified_score=data.get("min_confidence_score", 0.7),
            min_review_score=data.get("min_review_score", 0.4),
            high_priority_score=data.get("high_priority_score", 0.85),
        )

        weights_data = data.get("scoring_weights", {})
        weights = ScoringWeights(
            source_quality=weights_data.get("source_quality", 0.25),
            estimated_value=weights_data.get("estimated_value", 0.30),
            category_fit=weights_data.get("category_fit", 0.20),
            timing=weights_data.get("timing", 0.15),
            competition=weights_data.get("competition", 0.10),
        )

        return cls(
            enabled=data.get("enabled", True),
            scan_all_sources=data.get("scan_all_sources", True),
            scoring_thresholds=thresholds,
            scoring_weights=weights,
            create_tasks_for_high_scoring=data.get(
                "create_tasks_for_high_scoring", True
            ),
            max_tasks_per_scan=data.get("max_tasks_per_scan", 10),
            notify_on_high_value=data.get("notify_on_high_value", True),
            high_value_threshold_cents=data.get("high_value_threshold_cents", 100000),
        )

    @classmethod
    def from_env(cls) -> "ScannerConfig":
        """Create from environment variables."""
        return cls(
            enabled=os.getenv("SCANNER_ENABLED", "true").lower() == "true",
            scan_all_sources=os.getenv(
                "SCANNER_ALL_SOURCES", "true"
            ).lower() == "true",
            scoring_thresholds=ScoringThresholds(
                min_qualified_score=float(
                    os.getenv("SCANNER_MIN_SCORE", "0.7")
                ),
            ),
            create_tasks_for_high_scoring=os.getenv(
                "SCANNER_CREATE_TASKS", "true"
            ).lower() == "true",
            max_tasks_per_scan=int(os.getenv("SCANNER_MAX_TASKS", "10")),
        )


# Production configuration singleton
PRODUCTION_CONFIG = ScannerConfig()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_scanner_config(execute_sql_func=None) -> ScannerConfig:
    """Get scanner configuration from database or defaults.

    Args:
        execute_sql_func: Function to execute SQL queries.

    Returns:
        ScannerConfig instance with current settings.
    """
    if execute_sql_func is None:
        return PRODUCTION_CONFIG

    try:
        result = execute_sql_func("""
            SELECT config FROM scheduled_tasks
            WHERE task_type = 'opportunity_scan'
            AND enabled = true
            ORDER BY priority DESC
            LIMIT 1
        """)
        rows = result.get("rows", [])
        if rows and rows[0].get("config"):
            config_data = rows[0]["config"]
            if isinstance(config_data, str):
                config_data = json.loads(config_data)
            return ScannerConfig.from_dict(config_data)
    except Exception as e:
        logger.warning("Failed to load scanner config from DB: %s", e)

    return PRODUCTION_CONFIG


def update_scanner_config(
    execute_sql_func,
    updates: Dict[str, Any],
    task_id: Optional[str] = None,
) -> bool:
    """Update scanner configuration in database.

    Args:
        execute_sql_func: Function to execute SQL queries.
        updates: Dictionary of configuration updates.
        task_id: Optional specific task ID to update.

    Returns:
        True if update succeeded.
    """
    current = get_scanner_config(execute_sql_func)
    current_dict = current.to_dict()
    current_dict.update(updates)

    config_json = json.dumps(current_dict).replace("'", "''")

    if task_id:
        sql = f"""
            UPDATE scheduled_tasks
            SET config = '{config_json}'::jsonb,
                updated_at = NOW()
            WHERE id = '{task_id}'
        """
    else:
        sql = f"""
            UPDATE scheduled_tasks
            SET config = '{config_json}'::jsonb,
                updated_at = NOW()
            WHERE task_type = 'opportunity_scan'
            AND enabled = true
        """

    try:
        result = execute_sql_func(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.error("Failed to update scanner config: %s", e)
        return False


def validate_config(config: ScannerConfig) -> List[str]:
    """Validate a scanner configuration.

    Args:
        config: Configuration to validate.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []

    # Validate scoring weights
    if not config.scoring_weights.validate():
        errors.append("Scoring weights must sum to 1.0")

    # Validate thresholds
    thresholds = config.scoring_thresholds
    if thresholds.min_review_score >= thresholds.min_qualified_score:
        errors.append(
            "min_review_score must be less than min_qualified_score"
        )
    if thresholds.min_qualified_score >= thresholds.high_priority_score:
        errors.append(
            "min_qualified_score must be less than high_priority_score"
        )

    # Validate task limits
    if config.max_tasks_per_scan < 1 or config.max_tasks_per_scan > 100:
        errors.append("max_tasks_per_scan must be between 1 and 100")

    return errors


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums and constants
    "ScanInterval",
    "PRODUCTION_SCAN_SCHEDULES",
    "MIN_SCAN_INTERVALS",
    # Scoring
    "ScoringThresholds",
    "ScoringWeights",
    "DEFAULT_SCORING_THRESHOLDS",
    "DEFAULT_SCORING_WEIGHTS",
    # Source configuration
    "SourceConfig",
    "PRODUCTION_SOURCE_CONFIGS",
    # Main configuration
    "ScannerConfig",
    "PRODUCTION_CONFIG",
    # Utilities
    "get_scanner_config",
    "update_scanner_config",
    "validate_config",
]
