"""
JUGGERNAUT Core Module
Complete Phase 1-6 exports

Phase 1: Core Engine (Logging, Memory, Communication)
Phase 2: Agent Framework (Workers, Goals, Tasks, Tools, Error Recovery, Approvals, Permissions)
Phase 3: Revenue Infrastructure (Opportunities, Revenue, Costs)
Phase 4: Experimentation Framework (Design, Execution, Analysis, Rollback, Learnings)
Phase 5: Proactive Systems (Scanning, Monitoring, Scheduling)
Phase 6: Multi-Agent Orchestration (Agent Coordination, Resource Allocation, Cross-Agent Memory, Escalation, Resilience)
"""

# =============================================================================
# PHASE 1-3: CORE, AGENTS, REVENUE (from database.py, agents.py, tools.py, error_recovery.py)
# =============================================================================

from .database import (
    # Core
    query_db,
    
    # Logging (Phase 1.1)
    log_execution,
    get_logs,
    cleanup_old_logs,
    get_log_summary,
    
    # Memory (Phase 1.2)
    write_memory,
    read_memories,
    update_memory_importance,
    
    # Communication (Phase 1.3)
    send_message,
    get_messages,
    acknowledge_message,
    mark_message_read,
    
    # Opportunities (Phase 3.1)
    create_opportunity,
    update_opportunity,
    get_opportunities,
    
    # Revenue (Phase 3.2)
    record_revenue,
    get_revenue_summary,
    get_revenue_events,
)

from .agents import (
    # Worker Registry (Phase 2.1)
    register_worker,
    update_worker_status,
    worker_heartbeat,
    get_worker,
    list_workers,
    find_workers_by_capability,
    record_worker_task_outcome,
    
    # Goal System (Phase 2.2)
    create_goal,
    get_goal,
    list_goals,
    get_sub_goals,
    update_goal_status,
    assign_goal,
    decompose_goal,
    
    # Task System (Phase 2.3)
    create_task,
    get_task,
    list_tasks,
    get_pending_tasks,
    assign_task,
    start_task,
    complete_task,
    fail_task,
    get_tasks_ready_for_retry,
    
    # Approvals (Phase 2.6)
    request_approval,
    get_pending_approvals,
    approve,
    reject,
    check_approval_status,
    is_task_approved,
    
    # Permissions (Phase 2.7)
    check_permission,
    can_worker_execute,
    
    # Convenience
    get_worker_dashboard,
    get_system_status,
)

from .tools import (
    # Tool Interface (Phase 2.4)
    Tool,
    ToolResult,
    register_tool,
    get_tool,
    list_tools,
    find_tools_by_permission,
    execute_tool,
    get_tool_executions,
    get_execution_stats,
    initialize_builtin_tools,
)

from .error_recovery import (
    # Dead Letter Queue (Phase 2.5)
    move_to_dead_letter,
    get_dead_letter_items,
    resolve_dead_letter,
    retry_dead_letter,
    
    # Alerting (Phase 2.5)
    create_alert,
    get_open_alerts,
    acknowledge_alert,
    resolve_alert,
    check_repeated_failures,
    
    # Graceful Degradation (Phase 2.5)
    get_fallback_worker,
    enable_degraded_mode,
    disable_degraded_mode,
    circuit_breaker_open,
    get_system_health,
)

# =============================================================================
# PHASE 4: EXPERIMENTATION FRAMEWORK (from experiments.py)
# =============================================================================

from .experiments import (
    # Phase 4.1: Experiment Design
    create_experiment_template,
    list_experiment_templates,
    create_experiment,
    get_experiment,
    list_experiments,
    
    # Phase 4.2: Experiment Execution
    start_experiment,
    pause_experiment,
    resume_experiment,
    increment_iteration,
    record_experiment_cost,
    create_variant,
    update_variant_metrics,
    create_checkpoint,
    get_checkpoints,
    get_latest_checkpoint,
    
    # Phase 4.3: Experiment Analysis
    record_result,
    get_result_summary,
    evaluate_success_criteria,
    compare_variants,
    conclude_experiment,
    
    # Phase 4.4: Rollback System
    create_rollback_snapshot,
    execute_rollback,
    check_auto_rollback_triggers,
    
    # Phase 4.5: Self-Improvement (Learnings)
    record_learning,
    extract_learnings,
    get_learnings,
    get_relevant_learnings,
    validate_learning,
    
    # Utilities
    log_experiment_event,
    get_experiment_dashboard,
)

# =============================================================================
# PHASE 5: PROACTIVE SYSTEMS
# =============================================================================

# Phase 5.1: Opportunity Scanner (from proactive.py)
from .proactive import (
    start_scan,
    complete_scan,
    fail_scan,
    get_scan_history,
    identify_opportunity,
    identify_opportunity_with_dedup,
    score_opportunity,
    bulk_score_opportunities,
    get_top_opportunities,
    compute_opportunity_fingerprint,
    check_duplicate,
    schedule_scan,
    get_scheduled_scans,
    scan_servicetitan_opportunities,
    scan_angi_leads,
    scan_market_trends,
)

# Phase 5.2: Monitoring System (from monitoring.py)
from .monitoring import (
    record_metric,
    record_counter,
    record_latency,
    get_metrics,
    get_metric_stats,
    run_health_check,
    check_all_components,
    get_health_status,
    detect_anomaly,
    record_anomaly,
    get_open_anomalies,
    resolve_anomaly,
    get_performance_summary,
    check_task_queue_health,
    get_dashboard_data,
)

# Phase 5.3: Scheduled Tasks (from scheduler.py)
from .scheduler import (
    parse_cron_expression,
    calculate_next_cron_run,
    create_scheduled_task,
    update_scheduled_task,
    delete_scheduled_task,
    enable_task,
    disable_task,
    get_all_scheduled_tasks,
    get_due_tasks,
    start_task_run,
    complete_task_run,
    fail_task_run,
    check_dependencies_satisfied,
    add_dependency,
    remove_dependency,
    get_schedule_conflicts,
    resolve_conflict as resolve_schedule_conflict,
    get_schedule_report,
    get_task_run_history,
)

# =============================================================================
# PHASE 6: MULTI-AGENT ORCHESTRATION (from orchestration.py)
# =============================================================================

from .orchestration import ( (
    # Data Classes & Enums
    AgentStatus,
    TaskPriority,
    HandoffReason,
    ConflictType,
    EscalationLevel,
    AgentCard,
    SwarmTask,
    
    # Phase 6.0: Database Setup
    create_phase6_tables,
    
    # Phase 6.1: Agent Coordination
    discover_agents,
    route_task,
    get_agent_workload,
    balance_workload,
    handoff_task,
    log_coordination_event,
    
    # Phase 6.2: Resource Allocation
    allocate_budget_to_goal,
    get_resource_status,
    resolve_conflict,
    
    # Phase 6.3: Cross-Agent Memory
    write_shared_memory,
    read_shared_memory,
    sync_memory_to_agents,
    garbage_collect_memory,
    
    # Phase 6.4: Escalation System
    create_escalation,
    get_open_escalations,
    resolve_escalation,
    check_escalation_timeouts,
    
    # Phase 6.5: Resilience
    detect_agent_failures,
    handle_agent_failure,
    activate_backup_agent,
    run_health_check as run_orchestration_health_check,
    auto_recover,
)

# =============================================================================
# VERSION
# =============================================================================

__version__ = "6.0.0"
__phase__ = "Phase 6: Multi-Agent Orchestration Complete"

# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # Database
    "query_db",
    
    # Phase 1.1 Logging
    "log_execution", "get_logs", "cleanup_old_logs", "get_log_summary",
    
    # Phase 1.2 Memory
    "write_memory", "read_memories", "update_memory_importance",
    
    # Phase 1.3 Communication
    "send_message", "get_messages", "acknowledge_message", "mark_message_read",
    
    # Phase 2.1 Workers
    "register_worker", "update_worker_status", "worker_heartbeat", 
    "get_worker", "list_workers", "find_workers_by_capability", "record_worker_task_outcome",
    
    # Phase 2.2 Goals
    "create_goal", "get_goal", "list_goals", "get_sub_goals",
    "update_goal_status", "assign_goal", "decompose_goal",
    
    # Phase 2.3 Tasks
    "create_task", "get_task", "list_tasks", "get_pending_tasks",
    "assign_task", "start_task", "complete_task", "fail_task", "get_tasks_ready_for_retry",
    
    # Phase 2.4 Tools
    "Tool", "ToolResult", "register_tool", "get_tool", "list_tools",
    "find_tools_by_permission", "execute_tool", "get_tool_executions", 
    "get_execution_stats", "initialize_builtin_tools",
    
    # Phase 2.5 Error Recovery
    "move_to_dead_letter", "get_dead_letter_items", "resolve_dead_letter", "retry_dead_letter",
    "create_alert", "get_open_alerts", "acknowledge_alert", "resolve_alert", "check_repeated_failures",
    "get_fallback_worker", "enable_degraded_mode", "disable_degraded_mode", 
    "circuit_breaker_open", "get_system_health",
    
    # Phase 2.6 Approvals
    "request_approval", "get_pending_approvals", "approve", "reject",
    "check_approval_status", "is_task_approved",
    
    # Phase 2.7 Permissions
    "check_permission", "can_worker_execute",
    
    # Phase 3.1 Opportunities
    "create_opportunity", "update_opportunity", "get_opportunities",
    
    # Phase 3.2 Revenue
    "record_revenue", "get_revenue_summary", "get_revenue_events",
    
    # Phase 4.1 Experiment Design
    "create_experiment_template", "list_experiment_templates",
    "create_experiment", "get_experiment", "list_experiments",
    
    # Phase 4.2 Experiment Execution
    "start_experiment", "pause_experiment", "resume_experiment",
    "increment_iteration", "record_experiment_cost",
    "create_variant", "update_variant_metrics",
    "create_checkpoint", "get_checkpoints", "get_latest_checkpoint",
    
    # Phase 4.3 Experiment Analysis
    "record_result", "get_result_summary", "evaluate_success_criteria",
    "compare_variants", "conclude_experiment",
    
    # Phase 4.4 Rollback System
    "create_rollback_snapshot", "execute_rollback", "check_auto_rollback_triggers",
    
    # Phase 4.5 Self-Improvement
    "record_learning", "extract_learnings", "get_learnings",
    "get_relevant_learnings", "validate_learning",
    
    # Phase 4 Utilities
    "log_experiment_event", "get_experiment_dashboard",
    
    # Phase 5.1 Opportunity Scanner
    "start_scan", "complete_scan", "fail_scan", "get_scan_history",
    "identify_opportunity", "identify_opportunity_with_dedup",
    "score_opportunity", "bulk_score_opportunities", "get_top_opportunities",
    "compute_opportunity_fingerprint", "check_duplicate",
    "schedule_scan", "get_scheduled_scans",
    "scan_servicetitan_opportunities", "scan_angi_leads", "scan_market_trends",
    
    # Phase 5.2 Monitoring
    "record_metric", "record_counter", "record_latency",
    "get_metrics", "get_metric_stats",
    "run_health_check", "check_all_components", "get_health_status",
    "detect_anomaly", "record_anomaly", "get_open_anomalies", "resolve_anomaly",
    "get_performance_summary", "check_task_queue_health", "get_dashboard_data",
    
    # Phase 5.3 Scheduler
    "parse_cron_expression", "calculate_next_cron_run",
    "create_scheduled_task", "update_scheduled_task", "delete_scheduled_task",
    "enable_task", "disable_task",
    "get_all_scheduled_tasks", "get_due_tasks",
    "start_task_run", "complete_task_run", "fail_task_run",
    "check_dependencies_satisfied", "add_dependency", "remove_dependency",
    "get_schedule_conflicts", "resolve_schedule_conflict",
    "get_schedule_report", "get_task_run_history",
    
    # Phase 6.0 Data Classes & Enums
    "AgentStatus", "TaskPriority", "HandoffReason", "ConflictType", "EscalationLevel",
    "AgentCard", "SwarmTask",
    "create_phase6_tables",
    
    # Phase 6.1 Agent Coordination
    "discover_agents", "route_task", "get_agent_workload",
    "balance_workload", "handoff_task", "log_coordination_event",
    
    # Phase 6.2 Resource Allocation
    "allocate_budget_to_goal", "get_resource_status", "resolve_conflict",
    
    # Phase 6.3 Cross-Agent Memory
    "write_shared_memory", "read_shared_memory",
    "sync_memory_to_agents", "garbage_collect_memory",
    
    # Phase 6.4 Escalation System
    "create_escalation", "get_open_escalations",
    "resolve_escalation", "check_escalation_timeouts",
    
    # Phase 6.5 Resilience
    "detect_agent_failures", "handle_agent_failure",
    "activate_backup_agent", "run_orchestration_health_check", "auto_recover",
    
    # Convenience
    "get_worker_dashboard", "get_system_status",
]
