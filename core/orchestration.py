"""
JUGGERNAUT Multi-Agent Orchestration
Phase 6: L5 Capabilities - Agent Coordination, Resource Allocation, Cross-Agent Memory
================================================================================

Adapted from juggernaut-swarm swarm_orchestrator.py for the juggernaut-autonomy project.
Generic business-building system, not tied to any specific domain.

Architecture:
- Orchestrator: Routes tasks, balances load, handles failures
- Workers: Execute tasks, report results, collaborate
- Memory: Shared state across agents
- Escalation: Human-in-the-loop for high-stakes decisions
"""

import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass, field
import uuid
import logging

# Configure module logger
logger = logging.getLogger(__name__)

# ============================================================
# CONFLICT MANAGER INTEGRATION (HIGH-07)
# ============================================================

# Import conflict manager with graceful degradation
CONFLICT_MANAGER_AVAILABLE = False
_conflict_manager_import_error = None

try:
    from core.conflict_manager import (
        ensure_tables_exist as ensure_conflict_tables,
        acquire_lock,
        release_lock,
        ConflictResolution,
    )
    CONFLICT_MANAGER_AVAILABLE = True
except ImportError as e:
    _conflict_manager_import_error = str(e)
    # Stub functions for graceful degradation
    class ConflictResolution:
        """Stub enum for when conflict_manager is unavailable."""
        GRANTED = "granted"
        DENIED = "denied"
        QUEUED = "queued"
        ESCALATED = "escalated"
    
    def ensure_conflict_tables() -> bool:
        """Stub: conflict_manager module not available."""
        return False
    
    def acquire_lock(*args, **kwargs):
        """Stub: always grants lock when conflict_manager unavailable."""
        return ConflictResolution.GRANTED, None, None
    
    def release_lock(*args, **kwargs) -> bool:
        """Stub: conflict_manager module not available."""
        return True

# Initialize conflict management tables on module load
if CONFLICT_MANAGER_AVAILABLE:
    try:
        if ensure_conflict_tables():
            logger.info("Conflict management tables initialized")
        else:
            logger.warning("Conflict management tables unavailable; disabling conflict locks")
            CONFLICT_MANAGER_AVAILABLE = False
    except Exception as e:
        logger.warning("Failed to initialize conflict tables: %s", str(e))
        CONFLICT_MANAGER_AVAILABLE = False


# ============================================================
# LEARNING CAPTURE INTEGRATION (L5-WIRE-07)
# ============================================================

# Import learning capture with graceful degradation
LEARNING_CAPTURE_AVAILABLE = False
_learning_capture_import_error = None

try:
    from core.learning_capture import capture_task_learning
    LEARNING_CAPTURE_AVAILABLE = True
except ImportError as e:
    _learning_capture_import_error = str(e)
    # Stub function for graceful degradation
    def capture_task_learning(*args, **kwargs):
        """Stub: learning_capture module not available."""
        return (False, None)



# Database configuration (same as agents.py)
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
NEON_CONNECTION_STRING = "postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"


def _query(sql: str) -> Dict[str, Any]:
    """Execute SQL query via HTTP."""
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": NEON_CONNECTION_STRING
    }
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
    
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def _format_value(v: Any) -> str:
    """Format value for SQL."""
    if v is None:
        return "NULL"
    elif isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    elif isinstance(v, (int, float)):
        return str(v)
    elif isinstance(v, (dict, list)):
        json_str = json.dumps(v).replace("'", "''")
        return f"'{json_str}'"
    else:
        escaped = str(v).replace("'", "''")
        return f"'{escaped}'"


# ============================================================
# PHASE 6.0: ENUMS AND DATA CLASSES
# ============================================================

class AgentStatus(Enum):
    """Agent operational states."""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"
    WARMING_UP = "warming_up"


class TaskPriority(Enum):
    """Task priority levels for queue management."""
    CRITICAL = 1  # System failures, revenue-impacting issues
    HIGH = 2      # Time-sensitive
    NORMAL = 3    # Standard operations
    LOW = 4       # Background tasks
    DEFERRED = 5  # Can wait for off-peak


class HandoffReason(Enum):
    """Reasons for agent-to-agent handoffs."""
    CAPABILITY_MATCH = "capability_match"
    LOAD_BALANCING = "load_balancing"
    ESCALATION = "escalation"
    SPECIALIZATION = "specialization"
    PARALLEL_EXECUTION = "parallel_execution"
    FOLLOWUP_REQUIRED = "followup_required"
    FAILURE_RECOVERY = "failure_recovery"


class ConflictType(Enum):
    """Types of resource conflicts between agents."""
    RESOURCE_CONTENTION = "resource_contention"
    BUDGET_EXCEEDED = "budget_exceeded"
    PRIORITY_CONFLICT = "priority_conflict"
    CAPABILITY_OVERLAP = "capability_overlap"
    TIMING_CONFLICT = "timing_conflict"


class EscalationLevel(Enum):
    """Escalation severity levels."""
    INFO = "info"           # FYI, no action needed
    LOW = "low"             # Can wait hours
    MEDIUM = "medium"       # Should address soon
    HIGH = "high"           # Needs attention within hour
    CRITICAL = "critical"   # Immediate human intervention required


@dataclass
class AgentCard:
    """
    Digital identity for an agent in the swarm.
    Defines capabilities, constraints, and communication channels.
    """
    agent_id: str
    name: str
    role: str
    description: str
    capabilities: List[str]
    tools: List[str] = field(default_factory=list)
    preferred_model: str = "google/gemini-flash-1.5"
    escalation_model: str = "anthropic/claude-sonnet-4-20250514"
    max_concurrent_tasks: int = 5
    avg_task_duration_seconds: float = 30.0
    success_rate_threshold: float = 0.85
    max_cost_per_task_cents: int = 100
    daily_cost_limit_cents: int = 1000
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "capabilities": self.capabilities,
            "tools": self.tools,
            "preferred_model": self.preferred_model,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "success_rate_threshold": self.success_rate_threshold
        }


@dataclass
class SwarmTask:
    """
    Task that can be executed by any agent in the swarm.
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = ""
    description: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    source_agent: Optional[str] = None
    target_agent: Optional[str] = None
    handoff_reason: Optional[HandoffReason] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    parent_task_id: Optional[str] = None
    goal_id: Optional[str] = None
    estimated_cost_cents: int = 0
    actual_cost_cents: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "payload": self.payload,
            "priority": self.priority.value if isinstance(self.priority, TaskPriority) else self.priority,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "handoff_reason": self.handoff_reason.value if self.handoff_reason else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "goal_id": self.goal_id,
            "estimated_cost_cents": self.estimated_cost_cents,
            "actual_cost_cents": self.actual_cost_cents
        }


# ============================================================
# PHASE 6.1: AGENT COORDINATION
# ============================================================

def discover_agents(
    capability: str = None,
    status: str = None,
    min_health_score: float = 0.5
) -> List[Dict]:
    """
    Discover available agents, optionally filtered by capability and status.
    
    Args:
        capability: Filter to agents with this capability
        status: Filter to agents with this status (active, idle, busy)
        min_health_score: Minimum health score threshold
    
    Returns:
        List of agent records ordered by health score descending
    """
    conditions = [f"health_score >= {min_health_score}"]
    
    if capability:
        conditions.append(f"capabilities @> {_format_value([capability])}")
    if status:
        conditions.append(f"status = {_format_value(status)}")
    
    where_clause = " AND ".join(conditions)
    
    sql = f"""
    SELECT 
        worker_id, name, description, status, capabilities,
        health_score, current_day_cost_cents, max_cost_per_day_cents,
        tasks_completed, tasks_failed, last_heartbeat,
        max_concurrent_tasks
    FROM worker_registry
    WHERE {where_clause}
    ORDER BY health_score DESC
    """
    
    try:
        result = _query(sql)
        agents = result.get("rows", [])
        
        # Fetch active task counts separately (simpler queries work better)
        for agent in agents:
            try:
                task_sql = f"""
                SELECT COUNT(*) as cnt FROM governance_tasks
                WHERE assigned_worker = {_format_value(agent['worker_id'])}
                  AND status = 'in_progress'
                """
                task_result = _query(task_sql)
                agent['active_task_count'] = int(task_result.get('rows', [{}])[0].get('cnt', 0) or 0)
            except:
                agent['active_task_count'] = 0
        
        return agents
    except Exception as e:
        print(f"Failed to discover agents: {e}")
        return []


def route_task(task: SwarmTask) -> Optional[str]:
    """
    Route a task to the best available agent based on capabilities and load.
    
    Args:
        task: The SwarmTask to route
    
    Returns:
        worker_id of the selected agent, or None if no agent available
    """
    # Get the required capability from task type
    capability = task.task_type.split(".")[0] if task.task_type else None
    
    # Find available agents
    agents = discover_agents(capability=capability, status=None, min_health_score=0.3)
    
    if not agents:
        return None
    
    # Score each agent
    best_agent = None
    best_score = -1
    
    for agent in agents:
        # Skip offline or error agents
        if agent.get("status") in ("offline", "error"):
            continue
        
        # Calculate routing score
        score = 0.0
        
        # Health score weight (40%)
        score += (agent.get("health_score", 0.5) or 0.5) * 0.4
        
        # Availability weight (30%) - inverse of load
        task_count = agent.get("active_task_count", 0) or 0
        max_tasks = agent.get("max_concurrent_tasks", 5) or 5
        load = task_count / max_tasks if max_tasks > 0 else 0.5
        score += (1 - min(load, 1.0)) * 0.3
        
        # Budget headroom weight (20%)
        current_cost = agent.get("current_day_cost_cents", 0) or 0
        max_cost = agent.get("max_cost_per_day_cents", 1000) or 1000
        if max_cost > 0:
            budget_headroom = (max_cost - current_cost) / max_cost
            score += max(0, budget_headroom) * 0.2
        
        # Success rate weight (10%)
        completed = agent.get("tasks_completed", 0) or 0
        failed = agent.get("tasks_failed", 0) or 0
        total = completed + failed
        if total > 0:
            success_rate = completed / total
            score += success_rate * 0.1
        else:
            score += 0.05  # Default for new agents
        
        if score > best_score:
            best_score = score
            best_agent = agent
    
    if best_agent:
        return best_agent.get("worker_id")
    
    return None


def get_agent_workload(worker_id: str) -> Dict[str, Any]:
    """
    Get current workload metrics for an agent.
    
    Returns:
        Dict with task counts, load percentage, and queue depth
    """
    sql = f"""
    SELECT
        COUNT(*) FILTER (WHERE status = 'in_progress') as active_tasks,
        COUNT(*) FILTER (WHERE status = 'pending') as pending_tasks,
        COUNT(*) FILTER (WHERE status = 'completed' AND completed_at > NOW() - INTERVAL '1 hour') as completed_last_hour,
        COUNT(*) FILTER (WHERE status = 'failed' AND completed_at > NOW() - INTERVAL '1 hour') as failed_last_hour
    FROM governance_tasks
    WHERE assigned_worker = {_format_value(worker_id)}
    """
    
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        if rows:
            return rows[0]
    except Exception as e:
        print(f"Failed to get workload: {e}")
    
    return {
        "active_tasks": 0,
        "pending_tasks": 0,
        "completed_last_hour": 0,
        "failed_last_hour": 0
    }


def balance_workload(dry_run: bool = True) -> List[Dict]:
    """
    Rebalance tasks across agents to optimize throughput.
    
    Args:
        dry_run: If True, return recommendations without executing
    
    Returns:
        List of rebalancing actions (taken or recommended)
    """
    actions = []
    
    # Get all active workers with their capacities
    workers_sql = """
    SELECT worker_id, name, max_concurrent_tasks
    FROM worker_registry
    WHERE status::text = 'active'
    """
    
    try:
        workers_result = _query(workers_sql)
        workers = workers_result.get("rows", [])
        
        for worker in workers:
            worker_id = worker['worker_id']
            max_tasks = int(worker.get('max_concurrent_tasks', 5) or 5)
            
            # Count active tasks for this worker
            count_sql = f"""
            SELECT COUNT(*) as cnt FROM governance_tasks
            WHERE assigned_worker = {_format_value(worker_id)}
              AND status = 'in_progress'
            """
            count_result = _query(count_sql)
            active_tasks = int(count_result.get('rows', [{}])[0].get('cnt', 0) or 0)
            
            # Check if overloaded (>80% capacity)
            if active_tasks > max_tasks * 0.8:
                excess = active_tasks - int(max_tasks * 0.7)
                
                if excess > 0:
                    # Get task IDs to potentially move
                    tasks_sql = f"""
                    SELECT id FROM governance_tasks
                    WHERE assigned_worker = {_format_value(worker_id)}
                      AND status = 'in_progress'
                    ORDER BY priority ASC
                    LIMIT {excess}
                    """
                    tasks_result = _query(tasks_sql)
                    task_ids = [r['id'] for r in tasks_result.get('rows', [])]
                    
                    # Find agents to offload to
                    available = discover_agents(status="active", min_health_score=0.7)
                    available = [a for a in available if a['worker_id'] != worker_id and a.get('active_task_count', 0) < a.get('max_concurrent_tasks', 5) * 0.5]
                    
                    for i, task_id in enumerate(task_ids):
                        if i < len(available):
                            action = {
                                "type": "rebalance",
                                "task_id": task_id,
                                "from_agent": worker_id,
                                "to_agent": available[i]["worker_id"],
                                "reason": HandoffReason.LOAD_BALANCING.value
                            }
                            actions.append(action)
                            
                            if not dry_run:
                                handoff_task(
                                    task_id, 
                                    worker_id, 
                                    available[i]["worker_id"],
                                    HandoffReason.LOAD_BALANCING
                                )
    except Exception as e:
        print(f"Failed to balance workload: {e}")
    
    return actions


def handoff_task(
    task_id: str,
    from_agent: str,
    to_agent: str,
    reason: HandoffReason,
    notes: str = None
) -> bool:
    """
    Hand off a task from one agent to another.
    
    Args:
        task_id: ID of the task to hand off
        from_agent: Current owner agent ID
        to_agent: New owner agent ID
        reason: Reason for the handoff
        notes: Optional notes about the handoff
    
    Returns:
        True if handoff successful
    """
    sql = f"""
    UPDATE governance_tasks
    SET 
        assigned_worker = {_format_value(to_agent)},
        status = 'pending',
        started_at = NULL,
        updated_at = NOW(),
        result = jsonb_set(
            COALESCE(result, '{{}}'),
            '{{handoff_history}}',
            COALESCE(result->'handoff_history', '[]'::jsonb) || 
            {_format_value([{
                "from": from_agent,
                "to": to_agent,
                "reason": reason.value,
                "notes": notes,
                "at": datetime.now(timezone.utc).isoformat()
            }])}::jsonb
        )
    WHERE id = {_format_value(task_id)}
      AND assigned_worker = {_format_value(from_agent)}
    """
    
    try:
        result = _query(sql)
        if result.get("rowCount", 0) > 0:
            log_coordination_event(
                "handoff",
                {"task_id": task_id, "from": from_agent, "to": to_agent, "reason": reason.value}
            )
            return True
    except Exception as e:
        print(f"Failed to handoff task: {e}")
    
    return False


def update_worker_heartbeat(worker_id: str) -> bool:
    """
    Update the heartbeat timestamp for a logical worker.
    
    This function updates the last_heartbeat and status for workers like
    ORCHESTRATOR, ANALYST, and STRATEGIST that don't have their own running
    process but are called as functions within the main autonomy engine.
    
    Args:
        worker_id: The worker ID to update (e.g., 'ORCHESTRATOR', 'ANALYST')
    
    Returns:
        True if heartbeat was updated successfully, False otherwise
    """
    sql = f"""
    UPDATE worker_registry 
    SET last_heartbeat = NOW(),
        status = 'active'
    WHERE worker_id = {_format_value(worker_id)}
    """
    
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.warning("Failed to update heartbeat for %s: %s", worker_id, str(e))
        return False


def log_coordination_event(event_type: str, data: Dict, worker_id: str = "ORCHESTRATOR") -> Optional[str]:
    """
    Log an agent coordination event for audit trail.
    
    Also updates the worker's heartbeat to keep it marked as active.
    
    Args:
        event_type: Type of event (handoff, conflict, escalation, etc.)
        data: Event data
        worker_id: Worker ID to log for (default: ORCHESTRATOR)
    
    Returns:
        Event ID or None
    """
    # Update heartbeat for the worker performing the action
    update_worker_heartbeat(worker_id)
    
    sql = f"""
    INSERT INTO execution_logs (
        worker_id, action, message, level, output_data, created_at
    ) VALUES (
        {_format_value(worker_id)},
        {_format_value(event_type)},
        {_format_value(f"Coordination: {event_type}")},
        'info',
        {_format_value(data)},
        NOW()
    ) RETURNING id
    """
    
    try:
        result = _query(sql)
        if result.get("rows"):
            return str(result["rows"][0].get("id"))
    except Exception as e:
        # Silently fail - logging shouldn't break operations
        pass
    
    return None


# ============================================================
# PHASE 6.2: RESOURCE ALLOCATION
# ============================================================

def allocate_budget_to_goal(goal_id: str, budget_cents: int, source: str = "daily_pool") -> bool:
    """
    Allocate budget to a goal for its tasks.
    
    Records the allocation in both the goals table (max_cost_cents) and
    the cost_events table for tracking.
    
    Args:
        goal_id: Goal to allocate budget to
        budget_cents: Amount in cents to allocate
        source: Source of budget allocation (e.g., 'daily_pool', 'manual')
    
    Returns:
        True if allocation successful
    """
    allocation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # First, record the allocation in cost_events table
    cost_event_sql = f"""
    INSERT INTO cost_events (
        id, cost_type, category, description, amount_cents,
        currency, source, goal_id, occurred_at, recorded_at, recorded_by
    ) VALUES (
        {_format_value(allocation_id)},
        'budget_allocation',
        'allocation',
        {_format_value(f'Budget allocation to goal from {source}')},
        {budget_cents},
        'USD',
        {_format_value(source)},
        {_format_value(goal_id)},
        NOW(),
        NOW(),
        'orchestrator'
    )
    """
    
    # Then update the goal's max_cost_cents
    goal_update_sql = f"""
    UPDATE goals
    SET 
        max_cost_cents = COALESCE(max_cost_cents, 0) + {budget_cents},
        updated_at = NOW()
    WHERE id = {_format_value(goal_id)}
    """
    
    try:
        # Insert cost event
        _query(cost_event_sql)
        
        # Update goal
        result = _query(goal_update_sql)
        
        if result.get("rowCount", 0) > 0:
            logger.info(
                "Allocated %d cents to goal %s from %s (event: %s)",
                budget_cents, goal_id, source, allocation_id
            )
            return True
        else:
            logger.warning("Goal %s not found for budget allocation", goal_id)
            return False
            
    except Exception as e:
        logger.error("Failed to allocate budget: %s", str(e))
        return False


def run_daily_budget_allocation(daily_pool_cents: int = 10000) -> Dict[str, Any]:
    """
    Run daily budget allocation to distribute budget to active goals.
    
    This function should be called once per day by the orchestrator.
    It distributes a daily budget pool across active goals based on their
    priority and deadline proximity.
    
    Args:
        daily_pool_cents: Total daily budget pool in cents (default $100)
    
    Returns:
        Dict with allocation results including:
        - goals_count: Number of active goals
        - allocated_count: Number of goals that received allocation
        - total_allocated_cents: Total amount allocated
        - allocations: List of individual allocations
    """
    results = {
        "goals_count": 0,
        "allocated_count": 0,
        "total_allocated_cents": 0,
        "allocations": [],
        "errors": []
    }
    
    # Check if we already ran today
    check_sql = """
    SELECT COUNT(*) as cnt 
    FROM cost_events 
    WHERE cost_type = 'budget_allocation' 
      AND source = 'daily_pool'
      AND DATE(occurred_at) = CURRENT_DATE
    """
    
    try:
        check_result = _query(check_sql)
        if check_result.get("rows") and check_result["rows"][0].get("cnt", 0) > 0:
            logger.info("Daily budget allocation already ran today, skipping")
            results["skipped"] = True
            results["reason"] = "Already ran today"
            return results
    except Exception as e:
        logger.warning("Could not check if daily allocation ran: %s", str(e))
    
    # Get active goals ordered by deadline proximity
    goals_sql = """
    SELECT 
        id, title, 
        COALESCE(max_cost_cents, 0) as current_budget,
        deadline,
        CASE 
            WHEN deadline IS NOT NULL THEN 
                EXTRACT(EPOCH FROM (deadline - NOW())) / 86400
            ELSE 365
        END as days_until_deadline
    FROM goals
    WHERE status IN ('active', 'in_progress')
    ORDER BY 
        CASE WHEN deadline IS NOT NULL THEN 0 ELSE 1 END,
        deadline ASC
    """
    
    try:
        goals_result = _query(goals_sql)
        goals = goals_result.get("rows", [])
        results["goals_count"] = len(goals)
        
        if not goals:
            logger.info("No active goals found for budget allocation")
            return results
        
        # Calculate allocation per goal (equal distribution)
        # Goals with closer deadlines could get more in a future enhancement
        allocation_per_goal = daily_pool_cents // len(goals)
        remainder = daily_pool_cents % len(goals)
        
        for i, goal in enumerate(goals):
            goal_id = goal.get("id")
            goal_title = goal.get("title", "Unknown")
            
            # First goal gets the remainder
            amount = allocation_per_goal + (remainder if i == 0 else 0)
            
            if amount > 0:
                success = allocate_budget_to_goal(
                    goal_id=goal_id,
                    budget_cents=amount,
                    source="daily_pool"
                )
                
                if success:
                    results["allocated_count"] += 1
                    results["total_allocated_cents"] += amount
                    results["allocations"].append({
                        "goal_id": goal_id,
                        "goal_title": goal_title,
                        "amount_cents": amount
                    })
                else:
                    results["errors"].append({
                        "goal_id": goal_id,
                        "error": "Allocation failed"
                    })
        
        logger.info(
            "Daily budget allocation complete: %d/%d goals, %d cents total",
            results["allocated_count"],
            results["goals_count"],
            results["total_allocated_cents"]
        )
        
        return results
        
    except Exception as e:
        logger.error("Failed to run daily budget allocation: %s", str(e))
        results["errors"].append({"error": str(e)})
        return results



def get_resource_status() -> Dict[str, Any]:
    """
    Get current resource utilization across all agents.
    
    Returns:
        Dict with budget status, agent utilization, and bottlenecks
    """
    # Simple aggregation query
    sql = """
    SELECT
        COALESCE(SUM(current_day_cost_cents), 0) as total_daily_spend,
        COALESCE(SUM(max_cost_per_day_cents), 0) as total_daily_budget,
        COALESCE(AVG(health_score), 0) as avg_health_score
    FROM worker_registry
    """
    
    # Count queries by status
    status_sql = """
    SELECT status, COUNT(*) as cnt
    FROM worker_registry
    GROUP BY status
    """
    
    # Count consecutive failures
    failures_sql = """
    SELECT COUNT(*) as cnt FROM worker_registry
    WHERE consecutive_failures >= 3
    """
    
    task_sql = """
    SELECT status, COUNT(*) as cnt
    FROM governance_tasks
    GROUP BY status
    """
    
    try:
        # Get aggregates
        agg_result = _query(sql)
        agg = agg_result.get("rows", [{}])[0]
        
        # Get status counts
        status_result = _query(status_sql)
        status_counts = {r['status']: int(r['cnt']) for r in status_result.get("rows", [])}
        
        # Get failure count
        failures_result = _query(failures_sql)
        unhealthy = int(failures_result.get("rows", [{}])[0].get('cnt', 0) or 0)
        
        # Get task counts
        task_result = _query(task_sql)
        task_counts = {r['status']: int(r['cnt']) for r in task_result.get("rows", [])}
        
        total_spend = int(agg.get("total_daily_spend", 0) or 0)
        total_budget = int(agg.get("total_daily_budget", 1) or 1)
        
        return {
            "budget": {
                "daily_spend": total_spend,
                "daily_limit": total_budget,
                "utilization": total_spend / max(total_budget, 1)
            },
            "agents": {
                "active": status_counts.get("active", 0),
                "idle": status_counts.get("idle", 0),
                "busy": status_counts.get("busy", 0),
                "offline": status_counts.get("offline", 0),
                "error": status_counts.get("error", 0),
                "unhealthy": unhealthy,
                "avg_health": float(agg.get("avg_health_score", 0) or 0)
            },
            "tasks": {
                "pending": task_counts.get("pending", 0),
                "active": task_counts.get("in_progress", 0),
                "completed_hour": task_counts.get("completed", 0),  # Simplified
                "failed_hour": task_counts.get("failed", 0)  # Simplified
            }
        }
    except Exception as e:
        print(f"Failed to get resource status: {e}")
        return {}


def resolve_conflict(
    conflict_type: ConflictType,
    involved_agents: List[str],
    resource_id: str,
    context: Dict = None
) -> Dict[str, Any]:
    """
    Resolve a resource conflict between agents.
    
    Args:
        conflict_type: Type of conflict
        involved_agents: List of agent IDs involved
        resource_id: ID of the contested resource
        context: Additional context about the conflict
    
    Returns:
        Resolution decision with winner and actions
    """
    resolution = {
        "conflict_type": conflict_type.value,
        "involved_agents": involved_agents,
        "resource_id": resource_id,
        "resolution": None,
        "winner": None,
        "actions": []
    }
    
    if not involved_agents:
        resolution["resolution"] = "no_agents_involved"
        return resolution
    
    # Get agent details for comparison
    agents_data = []
    for agent_id in involved_agents:
        sql = f"""
        SELECT worker_id, health_score, tasks_completed, 
               current_day_cost_cents, max_cost_per_day_cents
        FROM worker_registry
        WHERE worker_id = {_format_value(agent_id)}
        """
        try:
            result = _query(sql)
            if result.get("rows"):
                agents_data.append(result["rows"][0])
        except:
            pass
    
    if not agents_data:
        resolution["resolution"] = "no_agent_data"
        return resolution
    
    # Resolution strategies by conflict type
    if conflict_type == ConflictType.RESOURCE_CONTENTION:
        # Winner is agent with highest health score
        winner = max(agents_data, key=lambda a: a.get("health_score", 0) or 0)
        resolution["winner"] = winner["worker_id"]
        resolution["resolution"] = "highest_health_wins"
        
    elif conflict_type == ConflictType.BUDGET_EXCEEDED:
        # Winner is agent with most budget headroom
        def budget_headroom(a):
            current = a.get("current_day_cost_cents", 0) or 0
            max_b = a.get("max_cost_per_day_cents", 1) or 1
            return max_b - current
        winner = max(agents_data, key=budget_headroom)
        resolution["winner"] = winner["worker_id"]
        resolution["resolution"] = "most_budget_headroom_wins"
        
    elif conflict_type == ConflictType.PRIORITY_CONFLICT:
        # Defer to context priority or highest health
        if context and context.get("priority_order"):
            for agent_id in context["priority_order"]:
                if agent_id in involved_agents:
                    resolution["winner"] = agent_id
                    resolution["resolution"] = "context_priority"
                    break
        else:
            winner = max(agents_data, key=lambda a: a.get("tasks_completed", 0) or 0)
            resolution["winner"] = winner["worker_id"]
            resolution["resolution"] = "most_experienced_wins"
    else:
        # Default: health score wins
        winner = max(agents_data, key=lambda a: a.get("health_score", 0) or 0)
        resolution["winner"] = winner["worker_id"]
        resolution["resolution"] = "default_health_wins"
    
    # Log the resolution
    log_coordination_event("conflict_resolved", resolution)
    
    return resolution


# ============================================================
# PHASE 6.3: CROSS-AGENT MEMORY
# ============================================================

def write_shared_memory(
    key: str,
    value: Any,
    writer_id: str,
    scope: str = "global",
    ttl_seconds: int = None,
    permissions: Dict = None
) -> Optional[str]:
    """
    Write to shared memory accessible by multiple agents.
    
    Args:
        key: Memory key
        value: Value to store (will be JSON serialized)
        writer_id: Agent writing the memory
        scope: Memory scope (global, goal, task, agent_group)
        ttl_seconds: Optional time-to-live
        permissions: Optional read/write permissions
    
    Returns:
        Memory ID or None
    """
    expires_at = None
    if ttl_seconds:
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
    
    sql = f"""
    INSERT INTO shared_memory (
        key, value, writer_id, scope, version, 
        permissions, expires_at, created_at, updated_at
    ) VALUES (
        {_format_value(key)},
        {_format_value(value)},
        {_format_value(writer_id)},
        {_format_value(scope)},
        1,
        {_format_value(permissions or {"read": "*", "write": [writer_id]})},
        {_format_value(expires_at)},
        NOW(),
        NOW()
    )
    ON CONFLICT (key, scope) DO UPDATE SET
        value = EXCLUDED.value,
        writer_id = EXCLUDED.writer_id,
        version = shared_memory.version + 1,
        updated_at = NOW()
    RETURNING id, version
    """
    
    try:
        result = _query(sql)
        if result.get("rows"):
            return result["rows"][0].get("id")
    except Exception as e:
        print(f"Failed to write shared memory: {e}")
    
    return None


def read_shared_memory(
    key: str,
    reader_id: str = None,
    scope: str = "global"
) -> Optional[Dict]:
    """
    Read from shared memory.
    
    Args:
        key: Memory key
        reader_id: Agent reading (for permission check)
        scope: Memory scope
    
    Returns:
        Memory record with value, version, and metadata
    """
    sql = f"""
    SELECT id, key, value, writer_id, scope, version, 
           permissions, expires_at, created_at, updated_at
    FROM shared_memory
    WHERE key = {_format_value(key)}
      AND scope = {_format_value(scope)}
      AND (expires_at IS NULL OR expires_at > NOW())
    """
    
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        if rows:
            memory = rows[0]
            
            # Check read permission
            if reader_id:
                permissions = memory.get("permissions", {})
                read_perm = permissions.get("read", "*")
                if read_perm != "*" and reader_id not in read_perm:
                    return None
            
            return memory
    except Exception as e:
        print(f"Failed to read shared memory: {e}")
    
    return None


def sync_memory_to_agents(
    key: str,
    scope: str = "global",
    target_agents: List[str] = None
) -> int:
    """
    Synchronize a shared memory value to multiple agents' local memory.
    
    Args:
        key: Shared memory key to sync
        scope: Memory scope
        target_agents: List of agent IDs to sync to (None = all with read access)
    
    Returns:
        Number of agents synced to
    """
    # Get the shared memory
    memory = read_shared_memory(key, scope=scope)
    if not memory:
        return 0
    
    # Determine target agents
    if not target_agents:
        permissions = memory.get("permissions", {})
        read_perm = permissions.get("read", "*")
        
        if read_perm == "*":
            # Get all active agents
            sql = "SELECT worker_id FROM worker_registry WHERE status != 'offline'"
            try:
                result = _query(sql)
                target_agents = [r["worker_id"] for r in result.get("rows", [])]
            except:
                return 0
        else:
            target_agents = read_perm if isinstance(read_perm, list) else [read_perm]
    
    # Write to each agent's memory
    synced = 0
    for agent_id in target_agents:
        sql = f"""
        INSERT INTO memory (
            worker_id, category, key, value, importance, 
            source, created_at, updated_at
        ) VALUES (
            {_format_value(agent_id)},
            'shared_sync',
            {_format_value(f"shared:{scope}:{key}")},
            {_format_value(memory.get("value"))},
            0.8,
            'orchestrator_sync',
            NOW(),
            NOW()
        )
        ON CONFLICT (worker_id, key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = NOW()
        """
        
        try:
            result = _query(sql)
            if result.get("rowCount", 0) > 0:
                synced += 1
        except:
            pass
    
    return synced


def garbage_collect_memory(max_age_days: int = 30) -> int:
    """
    Clean up expired and old shared memory entries.
    
    Args:
        max_age_days: Delete entries older than this
    
    Returns:
        Number of entries deleted
    """
    sql = f"""
    DELETE FROM shared_memory
    WHERE expires_at < NOW()
       OR (expires_at IS NULL AND updated_at < NOW() - INTERVAL '{max_age_days} days')
    """
    
    try:
        result = _query(sql)
        deleted = result.get("rowCount", 0)
        
        if deleted > 0:
            log_coordination_event("memory_gc", {"deleted": deleted, "max_age_days": max_age_days})
        
        return deleted
    except Exception as e:
        print(f"Failed to garbage collect memory: {e}")
        return 0


# ============================================================
# PHASE 6.4: ESCALATION SYSTEM
# ============================================================

def create_escalation(
    level: EscalationLevel,
    title: str,
    description: str,
    source_agent: str,
    context: Dict = None,
    required_action: str = None,
    timeout_minutes: int = 60
) -> Optional[str]:
    """
    Create an escalation requiring human attention.
    
    Args:
        level: Escalation severity level
        title: Brief title
        description: Detailed description
        source_agent: Agent creating the escalation
        context: Additional context
        required_action: What action is needed
        timeout_minutes: How long before auto-escalating further
    
    Returns:
        Escalation ID or None
    """
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)).isoformat()
    
    sql = f"""
    INSERT INTO escalations (
        level, title, description, source_agent,
        context, required_action, status,
        expires_at, created_at, updated_at
    ) VALUES (
        {_format_value(level.value)},
        {_format_value(title)},
        {_format_value(description)},
        {_format_value(source_agent)},
        {_format_value(context or {})},
        {_format_value(required_action)},
        'open',
        {_format_value(expires_at)},
        NOW(),
        NOW()
    ) RETURNING id
    """
    
    try:
        result = _query(sql)
        if result.get("rows"):
            escalation_id = result["rows"][0].get("id")
            
            # Log the escalation
            log_coordination_event("escalation_created", {
                "id": escalation_id,
                "level": level.value,
                "title": title,
                "source": source_agent
            })
            
            return escalation_id
    except Exception as e:
        print(f"Failed to create escalation: {e}")
    
    return None


def get_open_escalations(
    level: EscalationLevel = None,
    source_agent: str = None
) -> List[Dict]:
    """
    Get all open escalations, optionally filtered.
    
    Args:
        level: Filter by severity level
        source_agent: Filter by source agent
    
    Returns:
        List of open escalation records
    """
    conditions = ["status = 'open'"]
    
    if level:
        conditions.append(f"level = {_format_value(level.value)}")
    if source_agent:
        conditions.append(f"source_agent = {_format_value(source_agent)}")
    
    where_clause = " AND ".join(conditions)
    
    sql = f"""
    SELECT *
    FROM escalations
    WHERE {where_clause}
    ORDER BY 
        CASE level 
            WHEN 'critical' THEN 1
            WHEN 'high' THEN 2
            WHEN 'medium' THEN 3
            WHEN 'low' THEN 4
            ELSE 5
        END,
        created_at ASC
    """
    
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        print(f"Failed to get escalations: {e}")
        return []


def resolve_escalation(
    escalation_id: str,
    resolved_by: str,
    resolution: str,
    notes: str = None
) -> bool:
    """
    Resolve an escalation.
    
    Args:
        escalation_id: Escalation to resolve
        resolved_by: Who resolved it (human or agent ID)
        resolution: Resolution description
        notes: Additional notes
    
    Returns:
        True if resolution successful
    """
    sql = f"""
    UPDATE escalations
    SET 
        status = 'resolved',
        resolved_by = {_format_value(resolved_by)},
        resolution = {_format_value(resolution)},
        notes = {_format_value(notes)},
        resolved_at = NOW(),
        updated_at = NOW()
    WHERE id = {_format_value(escalation_id)}
      AND status = 'open'
    """
    
    try:
        result = _query(sql)
        if result.get("rowCount", 0) > 0:
            log_coordination_event("escalation_resolved", {
                "id": escalation_id,
                "resolved_by": resolved_by,
                "resolution": resolution
            })
            return True
    except Exception as e:
        print(f"Failed to resolve escalation: {e}")
    
    return False


def check_escalation_timeouts() -> List[str]:
    """
    Check for escalations that have timed out and need auto-escalation.
    
    Returns:
        List of escalation IDs that were auto-escalated
    """
    # Find timed-out escalations
    sql = """
    SELECT id, level
    FROM escalations
    WHERE status = 'open'
      AND expires_at < NOW()
    """
    
    escalated = []
    
    try:
        result = _query(sql)
        
        for row in result.get("rows", []):
            escalation_id = row["id"]
            current_level = row["level"]
            
            # Determine next level
            level_order = ["info", "low", "medium", "high", "critical"]
            current_idx = level_order.index(current_level) if current_level in level_order else 0
            next_level = level_order[min(current_idx + 1, len(level_order) - 1)]
            
            # Update escalation
            update_sql = f"""
            UPDATE escalations
            SET 
                level = {_format_value(next_level)},
                expires_at = NOW() + INTERVAL '30 minutes',
                notes = COALESCE(notes, '') || 'Auto-escalated due to timeout. ',
                updated_at = NOW()
            WHERE id = {_format_value(escalation_id)}
            """
            
            _query(update_sql)
            escalated.append(escalation_id)
            
            log_coordination_event("escalation_auto_escalated", {
                "id": escalation_id,
                "from_level": current_level,
                "to_level": next_level
            })
    except Exception as e:
        print(f"Failed to check escalation timeouts: {e}")
    
    return escalated


# ============================================================
# PHASE 6.5: RESILIENCE
# ============================================================

def detect_agent_failures(heartbeat_threshold_seconds: int = 120) -> List[Dict]:
    """
    Detect agents that have failed (missed heartbeats).
    
    Args:
        heartbeat_threshold_seconds: Seconds since last heartbeat to consider failed
    
    Returns:
        List of failed agent records
    """
    # Check by consecutive failures (using text cast for enum compatibility)
    failures_sql = """
    SELECT worker_id, name, status, last_heartbeat, consecutive_failures
    FROM worker_registry
    WHERE status::text NOT IN ('offline', 'maintenance')
      AND consecutive_failures >= 5
    """
    
    # Check by heartbeat timeout
    heartbeat_sql = f"""
    SELECT worker_id, name, status, last_heartbeat, consecutive_failures
    FROM worker_registry
    WHERE status::text NOT IN ('offline', 'maintenance')
      AND last_heartbeat IS NOT NULL
      AND last_heartbeat < NOW() - INTERVAL '{heartbeat_threshold_seconds} seconds'
    """
    
    try:
        results = []
        seen = set()
        
        # Get failure-based failures
        failure_result = _query(failures_sql)
        for r in failure_result.get("rows", []):
            if r['worker_id'] not in seen:
                results.append(r)
                seen.add(r['worker_id'])
        
        # Get heartbeat-based failures
        heartbeat_result = _query(heartbeat_sql)
        for r in heartbeat_result.get("rows", []):
            if r['worker_id'] not in seen:
                results.append(r)
                seen.add(r['worker_id'])
        
        return results
    except Exception as e:
        print(f"Failed to detect failures: {e}")
        return []


def handle_agent_failure(worker_id: str) -> Dict[str, Any]:
    """
    Handle a detected agent failure: reassign tasks, update status.
    
    Args:
        worker_id: Failed agent ID
    
    Returns:
        Dict with failure handling results
    """
    results = {
        "worker_id": worker_id,
        "tasks_reassigned": 0,
        "new_status": None,
        "escalation_id": None
    }
    
    # Mark agent as error
    sql = f"""
    UPDATE worker_registry
    SET status = 'error', updated_at = NOW()
    WHERE worker_id = {_format_value(worker_id)}
    RETURNING name
    """
    
    try:
        result = _query(sql)
        if result.get("rows"):
            results["new_status"] = "error"
    except Exception as e:
        print(f"Failed to update agent status: {e}")
        return results
    
    # Get active tasks for this agent
    tasks_sql = f"""
    SELECT id, task_type, priority, goal_id
    FROM governance_tasks
    WHERE assigned_worker = {_format_value(worker_id)}
      AND status IN ('pending', 'in_progress')
    """
    
    try:
        tasks_result = _query(tasks_sql)
        tasks = tasks_result.get("rows", [])
        
        for task in tasks:
            # Create a SwarmTask for routing
            swarm_task = SwarmTask(
                task_id=task["id"],
                task_type=task.get("task_type", ""),
                priority=TaskPriority(task.get("priority", 3)),
                goal_id=task.get("goal_id")
            )
            
            # Find new agent
            new_agent = route_task(swarm_task)
            
            if new_agent:
                handoff_task(
                    task["id"],
                    worker_id,
                    new_agent,
                    HandoffReason.FAILURE_RECOVERY,
                    f"Auto-reassigned due to agent {worker_id} failure"
                )
                results["tasks_reassigned"] += 1
            else:
                # No agent available - create escalation
                if not results["escalation_id"]:
                    results["escalation_id"] = create_escalation(
                        EscalationLevel.HIGH,
                        f"Agent {worker_id} Failed - Tasks Stranded",
                        f"Agent {worker_id} has failed and {len(tasks)} tasks cannot be reassigned",
                        "ORCHESTRATOR",
                        {"failed_agent": worker_id, "stranded_tasks": [t["id"] for t in tasks]},
                        "Manually reassign tasks or bring agent back online"
                    )
    except Exception as e:
        print(f"Failed to reassign tasks: {e}")
    
    # Log the failure handling
    log_coordination_event("agent_failure_handled", results)
    
    return results


def activate_backup_agent(
    failed_worker_id: str,
    backup_worker_id: str = None
) -> Optional[str]:
    """
    Activate a backup agent to replace a failed one.
    
    Args:
        failed_worker_id: The failed agent
        backup_worker_id: Specific backup to activate (or None to auto-select)
    
    Returns:
        Activated backup agent ID or None
    """
    if not backup_worker_id:
        # Find a suitable backup
        sql = f"""
        SELECT worker_id
        FROM worker_registry
        WHERE status = 'idle'
          AND health_score >= 0.7
          AND worker_id != {_format_value(failed_worker_id)}
        ORDER BY health_score DESC
        LIMIT 1
        """
        
        try:
            result = _query(sql)
            if result.get("rows"):
                backup_worker_id = result["rows"][0]["worker_id"]
        except:
            pass
    
    if not backup_worker_id:
        return None
    
    # Activate the backup
    sql = f"""
    UPDATE worker_registry
    SET 
        status = 'active',
        metadata = jsonb_set(
            COALESCE(metadata, '{{}}'),
            '{{backup_for}}',
            {_format_value(failed_worker_id)}
        ),
        updated_at = NOW()
    WHERE worker_id = {_format_value(backup_worker_id)}
    """
    
    try:
        _query(sql)
        
        log_coordination_event("backup_activated", {
            "failed": failed_worker_id,
            "backup": backup_worker_id
        })
        
        return backup_worker_id
    except Exception as e:
        print(f"Failed to activate backup: {e}")
        return None


def run_health_check() -> Dict[str, Any]:
    """
    Run a comprehensive health check on the swarm.
    
    Returns:
        Health check results with issues found
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "issues": [],
        "metrics": {}
    }
    
    # Get resource status
    resources = get_resource_status()
    health["metrics"] = resources
    
    # Check for agent issues
    if resources.get("agents", {}).get("error", 0) > 0:
        health["issues"].append({
            "type": "agents_in_error",
            "severity": "high",
            "count": resources["agents"]["error"]
        })
    
    if resources.get("agents", {}).get("unhealthy", 0) > 0:
        health["issues"].append({
            "type": "unhealthy_agents",
            "severity": "medium",
            "count": resources["agents"]["unhealthy"]
        })
    
    # Check for task backlog
    pending = resources.get("tasks", {}).get("pending", 0)
    active = resources.get("tasks", {}).get("active", 0)
    if pending > active * 3 and pending > 10:
        health["issues"].append({
            "type": "task_backlog",
            "severity": "medium",
            "pending": pending,
            "active": active
        })
    
    # Check budget utilization
    budget_util = resources.get("budget", {}).get("utilization", 0)
    if budget_util > 0.9:
        health["issues"].append({
            "type": "budget_near_limit",
            "severity": "high",
            "utilization": budget_util
        })
    
    # Check for failed heartbeats
    failed_agents = detect_agent_failures()
    if failed_agents:
        health["issues"].append({
            "type": "failed_agents",
            "severity": "critical",
            "agents": [a["worker_id"] for a in failed_agents]
        })
    
    # Check escalations
    critical_escalations = get_open_escalations(EscalationLevel.CRITICAL)
    if critical_escalations:
        health["issues"].append({
            "type": "critical_escalations",
            "severity": "critical",
            "count": len(critical_escalations)
        })
    
    # Set overall status
    if any(i["severity"] == "critical" for i in health["issues"]):
        health["status"] = "critical"
    elif any(i["severity"] == "high" for i in health["issues"]):
        health["status"] = "degraded"
    elif any(i["severity"] == "medium" for i in health["issues"]):
        health["status"] = "warning"
    
    return health


def auto_recover() -> Dict[str, Any]:
    """
    Run automatic recovery procedures for detected issues.
    
    Returns:
        Recovery actions taken
    """
    actions = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "failures_handled": [],
        "escalations_checked": [],
        "memory_cleaned": 0,
        "workload_balanced": []
    }
    
    # Handle agent failures
    failed_agents = detect_agent_failures()
    for agent in failed_agents:
        result = handle_agent_failure(agent["worker_id"])
        actions["failures_handled"].append(result)
    
    # Check escalation timeouts
    escalated = check_escalation_timeouts()
    actions["escalations_checked"] = escalated
    
    # Garbage collect memory
    actions["memory_cleaned"] = garbage_collect_memory()
    
    # Balance workload
    actions["workload_balanced"] = balance_workload(dry_run=False)
    
    # Log recovery run
    log_coordination_event("auto_recovery_run", actions)
    
    return actions


# ============================================================
# DATABASE SCHEMA SETUP
# ============================================================

def create_phase6_tables() -> bool:
    """
    Create database tables required for Phase 6.
    Safe to run multiple times (uses IF NOT EXISTS).
    
    Returns:
        True if successful
    """
    tables = [
        """
        CREATE TABLE IF NOT EXISTS shared_memory (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key TEXT NOT NULL,
            value JSONB NOT NULL,
            writer_id TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'global',
            version INTEGER NOT NULL DEFAULT 1,
            permissions JSONB DEFAULT '{"read": "*", "write": []}',
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(key, scope)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS escalations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            level TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            source_agent TEXT NOT NULL,
            context JSONB DEFAULT '{}',
            required_action TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            resolved_by TEXT,
            resolution TEXT,
            notes TEXT,
            expires_at TIMESTAMPTZ,
            resolved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shared_memory_key_scope 
        ON shared_memory(key, scope)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shared_memory_expires 
        ON shared_memory(expires_at) WHERE expires_at IS NOT NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_escalations_status_level 
        ON escalations(status, level)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_escalations_source 
        ON escalations(source_agent)
        """
    ]
    
    for sql in tables:
        try:
            _query(sql)
        except Exception as e:
            print(f"Failed to create table/index: {e}")
            return False
    
    return True


# ============================================================

# ============================================================
# L5-01: MULTI-AGENT ORCHESTRATION - CORE FUNCTIONS
# ============================================================

def orchestrator_assign_task(
    task_id: str,
    target_worker_id: str,
    reason: str = "capability_match"
) -> Dict[str, Any]:
    """
    ORCHESTRATOR assigns a task to a specialized worker.
    
    This is the core L5 function that enables ORCHESTRATOR to delegate
    tasks to specialized workers (EXECUTOR, ANALYST, STRATEGIST, etc.).
    
    Uses conflict_manager to acquire resource locks before assignment
    to prevent race conditions with other workers. (HIGH-07)
    
    Args:
        task_id: UUID of the task to assign
        target_worker_id: Worker ID to assign to (e.g., 'EXECUTOR', 'ANALYST')
        reason: Reason for assignment (capability_match, load_balancing, etc.)
    
    Returns:
        Dict with success status, task_id, worker_id, and log_id
    """
    assignment_time = datetime.now(timezone.utc).isoformat()
    
    # HIGH-07: Acquire lock before task assignment to prevent conflicts
    if CONFLICT_MANAGER_AVAILABLE:
        try:
            # Priority 2 for task assignments (HIGH priority)
            resolution, lock, conflict = acquire_lock(
                resource_type="task",
                resource_id=task_id,
                worker_id=target_worker_id,
                priority=2,
                metadata={"reason": reason, "assignment_time": assignment_time}
            )
            
            # Handle lock acquisition result
            if hasattr(resolution, 'value'):
                resolution_value = resolution.value
            else:
                resolution_value = str(resolution)
            
            if resolution_value == "denied":
                logger.warning(
                    "Lock denied for task %s - another worker holds it", task_id
                )
                return {
                    "success": False,
                    "task_id": task_id,
                    "worker_id": target_worker_id,
                    "error": "Resource locked by another worker",
                    "conflict": conflict.id if conflict else None
                }
            elif resolution_value == "queued":
                logger.info("Task %s queued - waiting for lock", task_id)
                return {
                    "success": False,
                    "task_id": task_id,
                    "worker_id": target_worker_id,
                    "error": "Queued - resource busy",
                    "queued": True
                }
            elif resolution_value == "escalated":
                logger.warning("Task %s conflict escalated", task_id)
                return {
                    "success": False,
                    "task_id": task_id,
                    "worker_id": target_worker_id,
                    "error": "Conflict escalated for review"
                }
            # GRANTED - proceed with assignment
            logger.info("Lock acquired for task %s by %s", task_id, target_worker_id)
        except Exception as lock_err:
            logger.error("Lock acquisition failed: %s", str(lock_err))
            # Continue without lock if conflict_manager fails (graceful degradation)
    
    # Update the task assignment
    # L5-WIRE-01: Set status to in_progress directly for automated routing
    # Task flow: pending -> in_progress (orchestrator assigns & starts immediately)
    sql = f"""
    UPDATE governance_tasks
    SET 
        assigned_worker = {_format_value(target_worker_id)},
        status = 'in_progress',
        started_at = NOW(),
        updated_at = NOW(),
        result = jsonb_set(
            COALESCE(result, '{{}}'::jsonb),
            '{{assignment_history}}',
            COALESCE(result->'assignment_history', '[]'::jsonb) || 
            {_format_value([{
                "assigned_to": target_worker_id,
                "assigned_by": "ORCHESTRATOR",
                "reason": reason,
                "at": assignment_time
            }])}::jsonb
        )
    WHERE id = {_format_value(task_id)}
    RETURNING id, title, assigned_worker
    """
    
    try:
        result = _query(sql)
        if result.get("rowCount", 0) > 0:
            task_info = result.get("rows", [{}])[0]
            
            # Log the assignment event
            log_id = log_coordination_event(
                "task_assignment",
                {
                    "task_id": task_id,
                    "task_title": task_info.get("title"),
                    "target_worker": target_worker_id,
                    "reason": reason,
                    "assigned_at": assignment_time,
                    "lock_acquired": CONFLICT_MANAGER_AVAILABLE
                }
            )
            
            return {
                "success": True,
                "task_id": task_id,
                "worker_id": target_worker_id,
                "log_id": log_id,
                "message": f"ORCHESTRATOR assigned task to {target_worker_id}"
            }
    except Exception as e:
        # Release lock on failure if we acquired one
        if CONFLICT_MANAGER_AVAILABLE:
            try:
                release_lock("task", task_id, target_worker_id)
            except Exception:
                pass
        print(f"Failed to assign task: {e}")
    
    return {
        "success": False,
        "task_id": task_id,
        "worker_id": target_worker_id,
        "error": "Assignment failed"
    }

def worker_report_task_status(
    worker_id: str,
    task_id: str,
    status: str,
    result: Dict = None,
    error: str = None,
    metrics: Dict = None
) -> Dict[str, Any]:
    """
    Worker reports task status back to ORCHESTRATOR.
    
    Workers use this to report progress, completion, or failure
    back to the ORCHESTRATOR for tracking and coordination.
    
    Args:
        worker_id: ID of the reporting worker
        task_id: ID of the task being reported on
        status: Status update ('in_progress', 'completed', 'failed', 'blocked')
        result: Task result data (for completion)
        error: Error message (for failure)
        metrics: Performance metrics (duration, tokens used, etc.)
    
    Returns:
        Dict with success status and acknowledgment
    """
    report_time = datetime.now(timezone.utc).isoformat()
    
    # Build the result update
    result_data = {
        "last_status_report": {
            "worker_id": worker_id,
            "status": status,
            "reported_at": report_time,
            "metrics": metrics or {}
        }
    }
    
    if result:
        result_data["task_result"] = result
    if error:
        result_data["error"] = error
    
    # Update task status
    completed_clause = "completed_at = NOW()," if status in ("completed", "failed") else ""
    
    sql = f"""
    UPDATE governance_tasks
    SET 
        status = {_format_value(status)},
        {completed_clause}
        updated_at = NOW(),
        result = COALESCE(result, '{{}}'::jsonb) || {_format_value(result_data)}::jsonb
    WHERE id = {_format_value(task_id)}
      AND assigned_worker = {_format_value(worker_id)}
    RETURNING id, title, status, task_type, description
    """
    
    try:
        query_result = _query(sql)
        if query_result.get("rowCount", 0) > 0:
            task_info = query_result.get("rows", [{}])[0]
            
            # Update worker statistics if completed or failed
            # Update heartbeat for any status report
            _query(f"""
                UPDATE worker_registry 
                SET last_heartbeat = NOW()
                WHERE worker_id = {_format_value(worker_id)}
            """)

            if status == "completed":
                _query(f"""
                    UPDATE worker_registry 
                    SET tasks_completed = tasks_completed + 1,
                        consecutive_failures = 0,
                        last_heartbeat = NOW()
                    WHERE worker_id = {_format_value(worker_id)}
                """)
            elif status == "failed":
                _query(f"""
                    UPDATE worker_registry 
                    SET tasks_failed = tasks_failed + 1,
                        consecutive_failures = consecutive_failures + 1,
                        last_heartbeat = NOW()
                    WHERE worker_id = {_format_value(worker_id)}
                """)
            
            # Log the status report
            log_id = log_coordination_event(
                "worker_status_report",
                {
                    "worker_id": worker_id,
                    "task_id": task_id,
                    "task_title": task_info.get("title"),
                    "status": status,
                    "has_result": result is not None,
                    "has_error": error is not None,
                    "reported_at": report_time
                }
            )
            
            # HIGH-07: Release lock on task completion or failure
            if status in ("completed", "failed") and CONFLICT_MANAGER_AVAILABLE:
                try:
                    lock_released = release_lock("task", task_id, worker_id)
                    if lock_released:
                        logger.info("Lock released for task %s by %s", task_id, worker_id)
                except Exception as release_err:
                    logger.warning("Failed to release lock for task %s: %s", task_id, str(release_err))
            
            # L5-WIRE-07: Capture learning from completed/failed tasks
            if status in ("completed", "failed") and LEARNING_CAPTURE_AVAILABLE:
                try:
                    # Get task details for learning capture
                    duration_ms = metrics.get("duration_ms", 0) if metrics else 0
                    success = (status == "completed")
                    
                    learning_result = capture_task_learning(
                        execute_sql_func=_query,
                        escape_value_func=_format_value,
                        log_action_func=lambda action, msg, **kw: logger.info(
                            "%s: %s %s", action, msg, kw
                        ),
                        task_id=task_id,
                        task_type=task_info.get("task_type", "unknown"),
                        task_title=task_info.get("title", ""),
                        task_description=task_info.get("description", ""),
                        success=success,
                        result=result or {"error": error} if error else {},
                        duration_ms=duration_ms,
                        worker_id=worker_id,
                    )
                    if learning_result[0]:
                        logger.info(
                            "Learning captured for task %s: %s",
                            task_id, learning_result[1]
                        )
                except Exception as learn_err:
                    logger.warning(
                        "Failed to capture learning for task %s: %s",
                        task_id, str(learn_err)
                    )
            
            return {
                "success": True,
                "acknowledged": True,
                "task_id": task_id,
                "worker_id": worker_id,
                "status": status,
                "log_id": log_id,
                "message": f"ORCHESTRATOR received status report from {worker_id}"
            }
    except Exception as e:
        print(f"Failed to report status: {e}")
    
    return {
        "success": False,
        "acknowledged": False,
        "error": "Status report failed"
    }


def orchestrator_parallel_execute(
    task_assignments: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    ORCHESTRATOR assigns multiple tasks to different workers in parallel.
    
    Enables parallel task execution across specialized workers.
    
    Args:
        task_assignments: List of {task_id, worker_id} dicts
    
    Returns:
        Dict with overall success and per-task results
    """
    execution_id = str(uuid.uuid4())[:8]
    start_time = datetime.now(timezone.utc).isoformat()
    
    results = {
        "execution_id": execution_id,
        "started_at": start_time,
        "total_tasks": len(task_assignments),
        "successful": 0,
        "failed": 0,
        "assignments": []
    }
    
    for assignment in task_assignments:
        task_id = assignment.get("task_id")
        worker_id = assignment.get("worker_id")
        
        if not task_id or not worker_id:
            results["assignments"].append({
                "task_id": task_id,
                "worker_id": worker_id,
                "success": False,
                "error": "Missing task_id or worker_id"
            })
            results["failed"] += 1
            continue
        
        # Assign each task
        assign_result = orchestrator_assign_task(
            task_id=task_id,
            target_worker_id=worker_id,
            reason="parallel_execution"
        )
        
        results["assignments"].append({
            "task_id": task_id,
            "worker_id": worker_id,
            "success": assign_result.get("success", False),
            "log_id": assign_result.get("log_id")
        })
        
        if assign_result.get("success"):
            results["successful"] += 1
        else:
            results["failed"] += 1
    
    # Log the parallel execution
    log_coordination_event(
        "parallel_execution",
        {
            "execution_id": execution_id,
            "total_tasks": results["total_tasks"],
            "successful": results["successful"],
            "failed": results["failed"],
            "started_at": start_time
        }
    )
    
    results["success"] = results["failed"] == 0
    return results


def get_worker_activity_log(
    # Note: limit is validated to be an integer
    worker_id: str = None,
    limit: int = 50,
    event_types: List[str] = None
) -> List[Dict]:
    """
    Get activity log for worker(s) from ORCHESTRATOR's tracking.
    
    ORCHESTRATOR uses this to track all worker activities.
    
    Args:
        worker_id: Optional filter for specific worker
        limit: Max number of entries to return
        event_types: Optional filter for event types
    
    Returns:
        List of activity log entries
    """
    conditions = ["1=1"]
    
    if worker_id:
        conditions.append(f"(output_data->>'worker_id' = {_format_value(worker_id)} OR output_data->>'target_worker' = {_format_value(worker_id)})")
    
    if event_types:
        type_list = ", ".join([_format_value(t) for t in event_types])
        conditions.append(f"action IN ({type_list})")
    else:
        conditions.append("action IN ('task_assignment', 'worker_status_report', 'parallel_execution', 'handoff')")
    
    where_clause = " AND ".join(conditions)
    
    sql = f"""
    SELECT id, worker_id, action, message, output_data, created_at
    FROM execution_logs
    WHERE {where_clause}
    ORDER BY created_at DESC
    LIMIT {min(max(int(limit), 1), 1000)}
    """
    
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        print(f"Failed to get activity log: {e}")
        return []


def get_orchestrator_dashboard() -> Dict[str, Any]:
    """
    Get ORCHESTRATOR dashboard showing all worker statuses and activities.
    
    Returns:
        Dashboard data with workers, tasks, and recent activities
    """
    dashboard = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workers": [],
        "task_summary": {},
        "recent_activities": []
    }
    
    # Get all workers with their status
    try:
        workers_result = _query("""
            SELECT 
                worker_id, name, status, level, 
                tasks_completed, tasks_failed, health_score,
                last_heartbeat, max_concurrent_tasks
            FROM worker_registry
            WHERE status != 'offline'
            ORDER BY level DESC, health_score DESC
        """)
        dashboard["workers"] = workers_result.get("rows", [])
    except Exception as e:
        print(f"Failed to get workers: {e}")
    
    # Get task summary
    try:
        task_result = _query("""
            SELECT 
                status, 
                COUNT(*) as count
            FROM governance_tasks
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY status
        """)
        for row in task_result.get("rows", []):
            dashboard["task_summary"][row["status"]] = int(row["count"])
    except Exception as e:
        print(f"Failed to get task summary: {e}")
    
    # Get recent activities
    dashboard["recent_activities"] = get_worker_activity_log(limit=20)
    
    return dashboard

# ============================================================
# EXPORTS
# ============================================================

# ============================================================
# PHASE 6.6: GOAL DECOMPOSITION (L5 CAPABILITY)
# ============================================================


def decompose_goal(
    goal_id: str,
    sub_goals: List[Dict[str, Any]],
    created_by: str = "ORCHESTRATOR"
) -> Dict[str, Any]:
    """
    Decompose a high-level goal into sub-goals.
    
    Args:
        goal_id: Parent goal ID to decompose
        sub_goals: List of sub-goal definitions, each with:
            - title: Sub-goal title (required)
            - description: Sub-goal description
            - success_criteria: JSON object of success criteria
            - deadline: Optional deadline
            - max_cost_cents: Optional budget
        created_by: Who is creating the sub-goals
    
    Returns:
        Dict with success status, created sub-goal IDs, and hierarchy level
    
    Example:
        >>> decompose_goal("root-goal-id", [
        ...     {"title": "Phase 1", "description": "Initial setup"},
        ...     {"title": "Phase 2", "description": "Scale up"}
        ... ])
    """
    created_ids = []
    
    try:
        # Verify parent goal exists
        parent = _query(f"""
            SELECT id, title, status FROM goals WHERE id = {_format_value(goal_id)}
        """)
        
        if not parent.get("rows"):
            return {"success": False, "error": f"Parent goal {goal_id} not found"}
        
        parent_goal = parent["rows"][0]
        
        for sub_goal in sub_goals:
            sub_id = str(uuid.uuid4())
            title = sub_goal.get("title", "Untitled Sub-goal")
            description = sub_goal.get("description", "")
            success_criteria = sub_goal.get("success_criteria", {})
            deadline = sub_goal.get("deadline")
            max_cost = sub_goal.get("max_cost_cents", 0)
            
            _query(f"""
                INSERT INTO goals (
                    id, parent_goal_id, title, description, success_criteria,
                    created_by, status, progress, max_cost_cents, deadline
                ) VALUES (
                    {_format_value(sub_id)},
                    {_format_value(goal_id)},
                    {_format_value(title)},
                    {_format_value(description)},
                    {_format_value(success_criteria)},
                    {_format_value(created_by)},
                    'pending',
                    0,
                    {max_cost},
                    {_format_value(deadline) if deadline else 'NULL'}
                )
            """)
            
            created_ids.append(sub_id)
            logger.info("Created sub-goal '%s' under parent '%s'", title, parent_goal["title"])
        
        log_coordination_event(
            event_type="goal.decomposed",
            initiator=created_by,
            description=f"Decomposed goal '{parent_goal['title']}' into {len(created_ids)} sub-goals"
        )
        
        return {
            "success": True,
            "parent_goal_id": goal_id,
            "parent_title": parent_goal["title"],
            "sub_goal_ids": created_ids,
            "count": len(created_ids)
        }
        
    except Exception as e:
        logger.error("Failed to decompose goal %s: %s", goal_id, str(e))
        return {"success": False, "error": str(e)}


def decompose_goal_to_tasks(
    goal_id: str,
    tasks: List[Dict[str, Any]],
    created_by: str = "ORCHESTRATOR"
) -> Dict[str, Any]:
    """
    Break a goal into executable tasks.
    
    Args:
        goal_id: Goal to create tasks for
        tasks: List of task definitions, each with:
            - title: Task title (required)
            - description: Task description
            - task_type: Type of task (code, research, verification, etc.)
            - priority: low, medium, high, critical
            - payload: Task payload/parameters
            - parent_task_id: Optional parent task for sub-tasks
        created_by: Who is creating the tasks
    
    Returns:
        Dict with success status and created task IDs
    
    Example:
        >>> decompose_goal_to_tasks("goal-id", [
        ...     {"title": "Research competitors", "task_type": "research"},
        ...     {"title": "Build prototype", "task_type": "code"}
        ... ])
    """
    created_ids = []
    
    try:
        # Verify goal exists
        goal = _query(f"""
            SELECT id, title FROM goals WHERE id = {_format_value(goal_id)}
        """)
        
        if not goal.get("rows"):
            return {"success": False, "error": f"Goal {goal_id} not found"}
        
        goal_info = goal["rows"][0]
        
        for task_def in tasks:
            task_id = str(uuid.uuid4())
            title = task_def.get("title", "Untitled Task")
            description = task_def.get("description", "")
            task_type = task_def.get("task_type", "unknown")
            priority = task_def.get("priority", "medium")
            payload = task_def.get("payload", {})
            parent_task_id = task_def.get("parent_task_id")
            
            _query(f"""
                INSERT INTO governance_tasks (
                    id, goal_id, parent_task_id, title, description,
                    task_type, priority, status, payload, created_by
                ) VALUES (
                    {_format_value(task_id)},
                    {_format_value(goal_id)},
                    {_format_value(parent_task_id) if parent_task_id else 'NULL'},
                    {_format_value(title)},
                    {_format_value(description)},
                    {_format_value(task_type)},
                    {_format_value(priority)},
                    'pending',
                    {_format_value(payload)},
                    {_format_value(created_by)}
                )
            """)
            
            created_ids.append(task_id)
            logger.info("Created task '%s' for goal '%s'", title, goal_info["title"])
        
        log_coordination_event(
            event_type="goal.tasks_created",
            initiator=created_by,
            description=f"Created {len(created_ids)} tasks for goal '{goal_info['title']}'"
        )
        
        return {
            "success": True,
            "goal_id": goal_id,
            "goal_title": goal_info["title"],
            "task_ids": created_ids,
            "count": len(created_ids)
        }
        
    except Exception as e:
        logger.error("Failed to create tasks for goal %s: %s", goal_id, str(e))
        return {"success": False, "error": str(e)}


def get_goal_hierarchy(root_goal_id: Optional[str] = None, max_depth: int = 10) -> Dict[str, Any]:
    """
    Get the full goal hierarchy as a tree structure.
    
    Args:
        root_goal_id: Starting goal ID (None for all top-level goals)
        max_depth: Maximum depth to traverse
    
    Returns:
        Dict with the goal tree structure including tasks at each level
    
    Example:
        >>> get_goal_hierarchy()
        {
            "success": True,
            "tree": [
                {
                    "id": "...",
                    "title": "Root Goal",
                    "level": 1,
                    "children": [...],
                    "tasks": [...]
                }
            ]
        }
    """
    try:
        # Use recursive CTE to get full hierarchy
        where_clause = ""
        if root_goal_id:
            where_clause = f"WHERE id = {_format_value(root_goal_id)}"
        else:
            where_clause = "WHERE parent_goal_id IS NULL"
        
        result = _query(f"""
            WITH RECURSIVE goal_tree AS (
                SELECT 
                    id, parent_goal_id, title, description, status, progress,
                    1 as level,
                    ARRAY[id] as path
                FROM goals
                {where_clause}
                
                UNION ALL
                
                SELECT 
                    g.id, g.parent_goal_id, g.title, g.description, g.status, g.progress,
                    gt.level + 1,
                    gt.path || g.id
                FROM goals g
                JOIN goal_tree gt ON g.parent_goal_id = gt.id
                WHERE gt.level < {max_depth}
            )
            SELECT 
                gt.id, gt.parent_goal_id, gt.title, gt.description, 
                gt.status, gt.progress, gt.level,
                (SELECT COUNT(*) FROM governance_tasks t WHERE t.goal_id = gt.id) as task_count
            FROM goal_tree gt
            ORDER BY gt.level, gt.title
        """)
        
        rows = result.get("rows", [])
        
        # Build tree structure
        nodes = {}
        roots = []
        
        for row in rows:
            node = {
                "id": row["id"],
                "parent_goal_id": row["parent_goal_id"],
                "title": row["title"],
                "description": row["description"],
                "status": row["status"],
                "progress": float(row["progress"]) if row["progress"] else 0,
                "level": row["level"],
                "task_count": int(row["task_count"]),
                "children": []
            }
            nodes[row["id"]] = node
            
            if row["parent_goal_id"] is None or (root_goal_id and row["id"] == root_goal_id):
                roots.append(node)
            elif row["parent_goal_id"] in nodes:
                nodes[row["parent_goal_id"]]["children"].append(node)
        
        # Get statistics
        max_level = max(r["level"] for r in rows) if rows else 0
        total_goals = len(rows)
        
        return {
            "success": True,
            "tree": roots,
            "statistics": {
                "total_goals": total_goals,
                "max_depth": max_level,
                "goals_by_level": {
                    level: sum(1 for r in rows if r["level"] == level)
                    for level in range(1, max_level + 1)
                }
            }
        }
        
    except Exception as e:
        logger.error("Failed to get goal hierarchy: %s", str(e))
        return {"success": False, "error": str(e)}


def link_task_to_goal(task_id: str, goal_id: str) -> Dict[str, Any]:
    """
    Link an existing task to a goal.
    
    Args:
        task_id: Task to link
        goal_id: Goal to link to
    
    Returns:
        Dict with success status
    """
    try:
        result = _query(f"""
            UPDATE governance_tasks
            SET goal_id = {_format_value(goal_id)},
                updated_at = NOW()
            WHERE id = {_format_value(task_id)}
            RETURNING id, title
        """)
        
        if not result.get("rows"):
            return {"success": False, "error": "Task not found"}
        
        task = result["rows"][0]
        logger.info("Linked task '%s' to goal %s", task["title"], goal_id)
        
        return {
            "success": True,
            "task_id": task_id,
            "task_title": task["title"],
            "goal_id": goal_id
        }
        
    except Exception as e:
        logger.error("Failed to link task to goal: %s", str(e))
        return {"success": False, "error": str(e)}




__all__ = [
    # Enums
    "AgentStatus",
    "TaskPriority",
    "HandoffReason",
    "ConflictType",
    "EscalationLevel",
    
    # Data Classes
    "AgentCard",
    "SwarmTask",
    
    # 6.1 Agent Coordination
    "discover_agents",
    "route_task",
    "get_agent_workload",
    "balance_workload",
    "handoff_task",
    "log_coordination_event",
    
    # 6.2 Resource Allocation
    "allocate_budget_to_goal",
    "get_resource_status",
    "resolve_conflict",
    
    # 6.3 Cross-Agent Memory
    "write_shared_memory",
    "read_shared_memory",
    "sync_memory_to_agents",
    "garbage_collect_memory",
    
    # 6.4 Escalation System
    "create_escalation",
    "get_open_escalations",
    "resolve_escalation",
    "check_escalation_timeouts",
    
    # 6.5 Resilience
    "detect_agent_failures",
    "handle_agent_failure",
    "activate_backup_agent",
    "run_health_check",
    "auto_recover",
    
    # L5-01: Multi-Agent Orchestration Core
    "orchestrator_assign_task",
    "worker_report_task_status",
    "orchestrator_parallel_execute",
    "get_worker_activity_log",
    "get_orchestrator_dashboard",
    
    # 6.6 Goal Decomposition (L5)
    "decompose_goal",
    "decompose_goal_to_tasks",
    "get_goal_hierarchy",
    "link_task_to_goal",
    
    # Setup
    "create_phase6_tables"
]

