"""
JUGGERNAUT Core Module
"""

from .database import (
    # Core
    query_db,
    
    # Logging (Phase 1.1)
    log_execution,
    get_logs,
    cleanup_old_logs,
    get_log_summary,
    
    # Opportunities (Phase 3.1)
    create_opportunity,
    update_opportunity,
    get_opportunities,
    
    # Revenue (Phase 3.2)
    record_revenue,
    get_revenue_summary,
    get_revenue_events,
    
    # Memory (Phase 1.2)
    write_memory,
    read_memories,
    update_memory_importance,
    
    # Communication (Phase 1.3)
    send_message,
    get_messages,
    acknowledge_message,
    mark_message_read,
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
    # Phase 2.6 Approvals
    "request_approval", "get_pending_approvals", "approve", "reject",
    "check_approval_status", "is_task_approved",
    # Phase 2.7 Permissions
    "check_permission", "can_worker_execute",
    # Phase 3.1 Opportunities
    "create_opportunity", "update_opportunity", "get_opportunities",
    # Phase 3.2 Revenue
    "record_revenue", "get_revenue_summary", "get_revenue_events",
    # Convenience
    "get_worker_dashboard", "get_system_status",
]
