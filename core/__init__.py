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

__all__ = [
    "query_db",
    "log_execution",
    "get_logs",
    "cleanup_old_logs",
    "get_log_summary",
    "create_opportunity",
    "update_opportunity",
    "get_opportunities",
    "record_revenue",
    "get_revenue_summary",
    "get_revenue_events",
    "write_memory",
    "read_memories",
    "update_memory_importance",
    "send_message",
    "get_messages",
    "acknowledge_message",
    "mark_message_read",
]
