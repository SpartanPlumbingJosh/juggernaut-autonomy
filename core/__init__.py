"""
JUGGERNAUT Core - Phase 5: Proactive Systems

This module provides L4 capabilities for autonomous operation:
- Opportunity Scanner (5.1): Market scanning, identification, scoring, deduplication
- Monitoring System (5.2): Health checks, performance, anomaly detection, alerts
- Scheduled Tasks (5.3): Cron-like scheduling, dependencies, conflict resolution

Usage:
    from core import (
        # Scanning
        start_scan, complete_scan, identify_opportunity_with_dedup,
        score_opportunity, get_top_opportunities, schedule_scan,
        
        # Monitoring
        record_metric, run_health_check, detect_anomaly,
        get_dashboard_data, get_performance_summary,
        
        # Scheduling
        create_scheduled_task, get_due_tasks, start_task_run,
        complete_task_run, get_schedule_report
    )
"""

# =============================================================================
# PHASE 5.1: OPPORTUNITY SCANNER
# =============================================================================

from .proactive import (
    # Scan Management
    start_scan,
    complete_scan,
    fail_scan,
    get_scan_history,
    
    # Opportunity Identification
    identify_opportunity,
    identify_opportunity_with_dedup,
    
    # Scoring
    score_opportunity,
    bulk_score_opportunities,
    get_top_opportunities,
    
    # Duplicate Detection
    compute_opportunity_fingerprint,
    check_duplicate,
    
    # Scheduling
    schedule_scan,
    get_scheduled_scans,
    
    # Market Scanning
    scan_servicetitan_opportunities,
    scan_angi_leads,
    scan_market_trends,
)

# =============================================================================
# PHASE 5.2: MONITORING SYSTEM
# =============================================================================

from .monitoring import (
    # Metrics
    record_metric,
    record_counter,
    record_latency,
    get_metrics,
    get_metric_stats,
    
    # Health Checks
    run_health_check,
    check_all_components,
    get_health_status,
    
    # Anomaly Detection
    detect_anomaly,
    record_anomaly,
    get_open_anomalies,
    resolve_anomaly,
    
    # Performance
    get_performance_summary,
    check_task_queue_health,
    
    # Dashboard
    get_dashboard_data,
)

# =============================================================================
# PHASE 5.3: SCHEDULED TASKS
# =============================================================================

from .scheduler import (
    # Cron
    parse_cron_expression,
    calculate_next_cron_run,
    
    # Task Management
    create_scheduled_task,
    update_scheduled_task,
    delete_scheduled_task,
    enable_task,
    disable_task,
    get_all_scheduled_tasks,
    
    # Execution
    get_due_tasks,
    start_task_run,
    complete_task_run,
    fail_task_run,
    
    # Dependencies
    check_dependencies_satisfied,
    add_dependency,
    remove_dependency,
    
    # Conflicts
    get_schedule_conflicts,
    resolve_conflict,
    
    # Reporting
    get_schedule_report,
    get_task_run_history,
)

# =============================================================================
# DATABASE UTILITIES
# =============================================================================

from .database import (
    execute_query,
    log_execution,
    get_logs,
)

# =============================================================================
# VERSION
# =============================================================================

__version__ = "5.0.0"
__phase__ = "Phase 5: Proactive Systems"

# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # Phase 5.1 - Opportunity Scanner
    "start_scan",
    "complete_scan",
    "fail_scan",
    "get_scan_history",
    "identify_opportunity",
    "identify_opportunity_with_dedup",
    "score_opportunity",
    "bulk_score_opportunities",
    "get_top_opportunities",
    "compute_opportunity_fingerprint",
    "check_duplicate",
    "schedule_scan",
    "get_scheduled_scans",
    "scan_servicetitan_opportunities",
    "scan_angi_leads",
    "scan_market_trends",
    
    # Phase 5.2 - Monitoring
    "record_metric",
    "record_counter",
    "record_latency",
    "get_metrics",
    "get_metric_stats",
    "run_health_check",
    "check_all_components",
    "get_health_status",
    "detect_anomaly",
    "record_anomaly",
    "get_open_anomalies",
    "resolve_anomaly",
    "get_performance_summary",
    "check_task_queue_health",
    "get_dashboard_data",
    
    # Phase 5.3 - Scheduler
    "parse_cron_expression",
    "calculate_next_cron_run",
    "create_scheduled_task",
    "update_scheduled_task",
    "delete_scheduled_task",
    "enable_task",
    "disable_task",
    "get_all_scheduled_tasks",
    "get_due_tasks",
    "start_task_run",
    "complete_task_run",
    "fail_task_run",
    "check_dependencies_satisfied",
    "add_dependency",
    "remove_dependency",
    "get_schedule_conflicts",
    "resolve_conflict",
    "get_schedule_report",
    "get_task_run_history",
    
    # Database
    "execute_query",
    "log_execution",
    "get_logs",
]
