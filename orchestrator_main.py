"""
JUGGERNAUT Orchestrator Entry Point
===================================

Main entry point for the orchestrator service that coordinates multi-agent
task execution, handles failures, and manages escalations.

This service runs continuously and:
1) Discovers available agents via discover_agents()
2) Routes pending tasks to appropriate workers via route_task()
3) Handles agent failures via handle_agent_failure()
4) Checks and auto-escalates timed-out escalations
5) Synchronizes shared memory across agents
6) Garbage collects expired memory entries periodically

Usage:
    python orchestrator_main.py
"""

import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Configure logging before other imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("orchestrator")

# Import orchestration functions
try:
    from core.orchestration import (
        SwarmTask,
        TaskPriority,
        check_escalation_timeouts,
        detect_agent_failures,
        discover_agents,
        garbage_collect_memory,
        get_resource_status,
        handle_agent_failure,
        log_coordination_event,
        route_task,
        run_health_check,
        sync_memory_to_agents,
        write_shared_memory,
        update_worker_heartbeat,
    )
except ImportError as e:
    logger.error("Failed to import orchestration module: %s", str(e))
    sys.exit(1)

# =============================================================================
# CONSTANTS
# =============================================================================

# Worker identification
WORKER_ID: str = os.getenv("WORKER_ID", "ORCHESTRATOR")

# Timing constants (in seconds)
ORCHESTRATION_INTERVAL_SECONDS: int = 30
HEALTH_CHECK_INTERVAL_SECONDS: int = 60
MEMORY_SYNC_INTERVAL_SECONDS: int = 120
FAILURE_CHECK_INTERVAL_SECONDS: int = 45
ESCALATION_CHECK_INTERVAL_SECONDS: int = 60
GARBAGE_COLLECT_INTERVAL_SECONDS: int = 3600  # Run GC every hour
CRITICAL_MONITOR_INTERVAL_SECONDS: int = 300  # Run critical checks every 5 minutes
ERROR_SCAN_INTERVAL_SECONDS: int = 900  # Run error scanning every 15 minutes
STALE_TASK_RESET_INTERVAL_SECONDS: int = 600  # Run stale task reset every 10 minutes

# Thresholds
MIN_AGENT_HEALTH_SCORE: float = 0.3
MAX_TASKS_PER_CYCLE: int = 10
HEARTBEAT_TIMEOUT_SECONDS: int = 120
MEMORY_MAX_AGE_DAYS: int = 30

# =============================================================================
# GLOBAL STATE
# =============================================================================

_running: bool = True
_last_health_check: float = 0.0
_last_memory_sync: float = 0.0
_last_failure_check: float = 0.0
_last_escalation_check: float = 0.0
_last_garbage_collect: float = 0.0
_last_critical_monitor: float = 0.0
_last_error_scan: float = 0.0
_last_stale_task_reset: float = 0.0
_cycle_count: int = 0


def _signal_handler(signum: int, frame: Any) -> None:
    """
    Handle shutdown signals gracefully.

    Args:
        signum: Signal number received
        frame: Current stack frame
    """
    global _running
    logger.info("Received signal %d, initiating graceful shutdown...", signum)
    _running = False


# =============================================================================
# CORE ORCHESTRATION FUNCTIONS
# =============================================================================


def discover_available_agents() -> List[Dict[str, Any]]:
    """
    Discover all available agents in the system.

    Returns:
        List of agent records with their status and capabilities
    """
    try:
        agents = discover_agents(
            capability=None,
            status=None,
            min_health_score=MIN_AGENT_HEALTH_SCORE
        )

        active_count = sum(
            1 for a in agents
            if a.get("status") not in ("offline", "error")
        )

        logger.info(
            "Discovered %d agents (%d active)",
            len(agents),
            active_count
        )

        return agents
    except Exception as e:
        logger.error("Failed to discover agents: %s", str(e))
        return []


def fetch_pending_tasks() -> List[Dict[str, Any]]:
    """
    Fetch pending tasks that need routing.

    Returns:
        List of pending task records
    """
    from core.orchestration import _query

    sql = f"""
    SELECT
        id, task_type, title, description, priority, goal_id,
        created_at, payload
    FROM governance_tasks
    WHERE status = 'pending'
      AND (assigned_worker IS NULL OR assigned_worker = '')
    ORDER BY
        CASE priority
            WHEN 'critical' THEN 1
            WHEN 'high' THEN 2
            WHEN 'medium' THEN 3
            WHEN 'low' THEN 4
            ELSE 5
        END,
        created_at ASC
    LIMIT {MAX_TASKS_PER_CYCLE}
    """

    try:
        result = _query(sql)
        tasks = result.get("rows", [])

        if tasks:
            logger.info("Found %d pending tasks to route", len(tasks))

        return tasks
    except Exception as e:
        logger.error("Failed to fetch pending tasks: %s", str(e))
        return []


def route_pending_tasks(agents: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Route pending tasks to available agents.

    Args:
        agents: List of available agents

    Returns:
        Dict with counts of routed and failed assignments
    """
    results = {"routed": 0, "failed": 0, "no_agent": 0}

    if not agents:
        logger.warning("No agents available for task routing")
        return results

    pending_tasks = fetch_pending_tasks()

    for task_record in pending_tasks:
        try:
            # Create SwarmTask for routing
            priority_value = task_record.get("priority", "medium")
            priority_map = {
                "critical": TaskPriority.CRITICAL,
                "high": TaskPriority.HIGH,
                "medium": TaskPriority.NORMAL,
                "low": TaskPriority.LOW,
            }

            swarm_task = SwarmTask(
                task_id=task_record["id"],
                task_type=task_record.get("task_type", ""),
                description=task_record.get("description", ""),
                priority=priority_map.get(priority_value, TaskPriority.NORMAL),
                goal_id=task_record.get("goal_id"),
            )

            # Route to best agent
            target_agent = route_task(swarm_task)

            if target_agent:
                # Assign the task
                from core.orchestration import orchestrator_assign_task

                assign_result = orchestrator_assign_task(
                    task_id=task_record["id"],
                    target_worker_id=target_agent,
                    reason="capability_match"
                )

                if assign_result.get("success"):
                    results["routed"] += 1
                    logger.info(
                        "Routed task '%s' to %s",
                        task_record.get("title", task_record["id"]),
                        target_agent
                    )
                else:
                    results["failed"] += 1
                    logger.warning(
                        "Failed to assign task %s: %s",
                        task_record["id"],
                        assign_result.get("error", "Unknown error")
                    )
            else:
                results["no_agent"] += 1
                logger.warning(
                    "No suitable agent found for task: %s",
                    task_record.get("title", task_record["id"])
                )

        except Exception as e:
            results["failed"] += 1
            logger.error(
                "Error routing task %s: %s",
                task_record.get("id", "unknown"),
                str(e)
            )

    return results


def handle_detected_failures() -> int:
    """
    Detect and handle agent failures.

    Returns:
        Number of failures handled
    """
    handled_count = 0

    try:
        failed_agents = detect_agent_failures(
            heartbeat_threshold_seconds=HEARTBEAT_TIMEOUT_SECONDS
        )

        for agent in failed_agents:
            worker_id = agent.get("worker_id")

            if not worker_id:
                continue

            logger.warning(
                "Detected failed agent: %s (last heartbeat: %s)",
                worker_id,
                agent.get("last_heartbeat", "unknown")
            )

            try:
                result = handle_agent_failure(worker_id)

                logger.info(
                    "Handled failure for %s: %d tasks reassigned",
                    worker_id,
                    result.get("tasks_reassigned", 0)
                )

                if result.get("escalation_id"):
                    logger.warning(
                        "Created escalation %s for stranded tasks",
                        result["escalation_id"]
                    )

                handled_count += 1

            except Exception as e:
                logger.error(
                    "Failed to handle agent failure for %s: %s",
                    worker_id,
                    str(e)
                )

        return handled_count

    except Exception as e:
        logger.error("Error detecting agent failures: %s", str(e))
        return 0


def check_and_escalate_timeouts() -> int:
    """
    Check for escalation timeouts and auto-escalate as needed.

    Returns:
        Number of escalations auto-escalated
    """
    try:
        escalated_ids = check_escalation_timeouts()

        if escalated_ids:
            logger.info(
                "Auto-escalated %d timed-out escalations: %s",
                len(escalated_ids),
                ", ".join(str(eid)[:8] for eid in escalated_ids[:5])
            )

        return len(escalated_ids)

    except Exception as e:
        logger.error("Error checking escalation timeouts: %s", str(e))
        return 0


def sync_shared_memory() -> int:
    """
    Synchronize critical shared memory across agents.

    Returns:
        Number of agents synced
    """
    synced_count = 0

    try:
        # Write orchestrator status to shared memory
        status = get_resource_status()

        write_shared_memory(
            key="orchestrator_status",
            value={
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "worker_id": WORKER_ID,
                "cycle_count": _cycle_count,
                "resource_status": status,
            },
            writer_id=WORKER_ID,
            scope="global",
            ttl_seconds=MEMORY_SYNC_INTERVAL_SECONDS * 2
        )

        # Sync orchestrator status to all agents
        synced_count = sync_memory_to_agents(
            key="orchestrator_status",
            scope="global",
            target_agents=None  # Sync to all with read access
        )

        if synced_count > 0:
            logger.debug("Synced shared memory to %d agents", synced_count)

        return synced_count

    except Exception as e:
        logger.error("Error syncing shared memory: %s", str(e))
        return 0


def run_memory_garbage_collection() -> int:
    """
    Clean up expired and old shared memory entries.

    Returns:
        Number of entries deleted
    """
    try:
        deleted_count = garbage_collect_memory(max_age_days=MEMORY_MAX_AGE_DAYS)

        if deleted_count > 0:
            logger.info(
                "Memory garbage collection: deleted %d expired entries",
                deleted_count
            )

        return deleted_count

    except Exception as e:
        logger.error("Error during memory garbage collection: %s", str(e))
        return 0


def perform_health_check() -> Dict[str, Any]:
    """
    Perform comprehensive health check on the system.

    Returns:
        Health check results
    """
    try:
        health = run_health_check()

        status = health.get("status", "unknown")
        issues = health.get("issues", [])

        if status == "healthy":
            logger.info("Health check: HEALTHY")
        elif status == "warning":
            logger.warning(
                "Health check: WARNING - %d issues detected",
                len(issues)
            )
        elif status == "degraded":
            logger.warning(
                "Health check: DEGRADED - %d issues (high severity)",
                len(issues)
            )
        else:
            logger.error(
                "Health check: %s - %d issues",
                status.upper(),
                len(issues)
            )

            for issue in issues:
                logger.error(
                    "  Issue: %s [%s]",
                    issue.get("type", "unknown"),
                    issue.get("severity", "unknown")
                )

        return health

    except Exception as e:
        logger.error("Health check failed: %s", str(e))
        return {"status": "error", "error": str(e), "issues": []}


def run_orchestration_cycle() -> None:
    """
    Run a single orchestration cycle.

    This is the main work unit that:
    1) Discovers agents
    2) Routes tasks
    3) Handles failures
    4) Checks escalations
    5) Syncs memory
    6) Garbage collects expired memory
    """
    global _last_health_check, _last_memory_sync
    global _last_failure_check, _last_escalation_check
    global _last_garbage_collect, _last_critical_monitor
    global _last_error_scan, _last_stale_task_reset, _cycle_count

    current_time = time.time()
    _cycle_count += 1

    logger.info("=== Orchestration cycle %d starting ===", _cycle_count)

    # Step 1: Discover available agents
    agents = discover_available_agents()

    # Update orchestrator heartbeat (so HQ doesn't show ORCHESTRATOR stale)
    try:
        update_worker_heartbeat(WORKER_ID)
    except Exception:
        pass

    # Step 2: Route pending tasks
    if agents:
        routing_results = route_pending_tasks(agents)

        if routing_results["routed"] > 0 or routing_results["failed"] > 0:
            logger.info(
                "Task routing: %d routed, %d failed, %d no agent",
                routing_results["routed"],
                routing_results["failed"],
                routing_results["no_agent"]
            )

    # Step 3: Check for agent failures (periodic)
    if current_time - _last_failure_check >= FAILURE_CHECK_INTERVAL_SECONDS:
        failures_handled = handle_detected_failures()
        _last_failure_check = current_time

        if failures_handled > 0:
            logger.info("Handled %d agent failures", failures_handled)

    # Step 4: Check escalation timeouts (periodic)
    if current_time - _last_escalation_check >= ESCALATION_CHECK_INTERVAL_SECONDS:
        escalated = check_and_escalate_timeouts()
        _last_escalation_check = current_time

    # Step 5: Sync shared memory (periodic)
    if current_time - _last_memory_sync >= MEMORY_SYNC_INTERVAL_SECONDS:
        synced = sync_shared_memory()
        _last_memory_sync = current_time

    # Step 6: Health check (periodic)
    if current_time - _last_health_check >= HEALTH_CHECK_INTERVAL_SECONDS:
        health = perform_health_check()
        _last_health_check = current_time

        # Log coordination event for tracking
        log_coordination_event(
            "orchestrator_cycle",
            {
                "cycle": _cycle_count,
                "agents_discovered": len(agents),
                "health_status": health.get("status", "unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    # Step 7: Garbage collect expired memory (periodic - hourly)
    if current_time - _last_garbage_collect >= GARBAGE_COLLECT_INTERVAL_SECONDS:
        gc_deleted = run_memory_garbage_collection()
        _last_garbage_collect = current_time

    # Step 8: Critical monitoring (periodic - every 5 minutes)
    if current_time - _last_critical_monitor >= CRITICAL_MONITOR_INTERVAL_SECONDS:
        try:
            from core.critical_monitoring import check_critical_issues
            from core.database import execute_sql
            
            critical_result = check_critical_issues(execute_sql, log_coordination_event)
            _last_critical_monitor = current_time
            
            if critical_result.get("critical_issues", 0) > 0:
                logger.critical(
                    "CRITICAL: %d issues detected - check execution_logs",
                    critical_result["critical_issues"]
                )
        except Exception as e:
            logger.error("Critical monitoring failed: %s", str(e))

    # Step 9: Error scanning for self-fix (periodic - every 15 minutes)
    if current_time - _last_error_scan >= ERROR_SCAN_INTERVAL_SECONDS:
        try:
            from core.error_to_task import scan_errors_and_create_tasks
            from core.database import execute_sql
            
            scan_result = scan_errors_and_create_tasks(execute_sql, log_coordination_event)
            _last_error_scan = current_time
            
            if scan_result.get("tasks_created", 0) > 0:
                logger.info(
                    "Error scanning: Created %d code_fix tasks from %d patterns",
                    scan_result["tasks_created"],
                    scan_result.get("patterns_found", 0)
                )
        except Exception as e:
            logger.error("Error scanning failed: %s", str(e))

    # Step 10: Stale task reset (periodic - every 10 minutes)
    if current_time - _last_stale_task_reset >= STALE_TASK_RESET_INTERVAL_SECONDS:
        try:
            from core.stale_task_reset import reset_stale_tasks
            from core.database import execute_sql
            
            reset_result = reset_stale_tasks(execute_sql, log_coordination_event, stale_threshold_minutes=30)
            _last_stale_task_reset = current_time
            
            if reset_result.get("reset_count", 0) > 0:
                logger.warning(
                    "Stale task reset: Reset %d tasks stuck in_progress for 30+ minutes",
                    reset_result["reset_count"]
                )
        except Exception as e:
            logger.error("Stale task reset failed: %s", str(e))

    logger.info("=== Orchestration cycle %d complete ===", _cycle_count)


def main() -> int:
    """
    Main entry point for the orchestrator service.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    global _running, _last_health_check, _last_failure_check
    global _last_escalation_check, _last_memory_sync, _last_garbage_collect
    global _last_critical_monitor, _last_error_scan, _last_stale_task_reset

    # Register signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logger.info("=" * 60)
    logger.info("JUGGERNAUT Orchestrator starting")
    logger.info("Worker ID: %s", WORKER_ID)
    logger.info("Orchestration interval: %d seconds", ORCHESTRATION_INTERVAL_SECONDS)
    logger.info("Memory sync interval: %d seconds", MEMORY_SYNC_INTERVAL_SECONDS)
    logger.info("Garbage collection interval: %d seconds", GARBAGE_COLLECT_INTERVAL_SECONDS)
    logger.info("=" * 60)

    # Initialize timing
    current_time = time.time()
    _last_health_check = current_time
    _last_memory_sync = current_time
    _last_failure_check = current_time
    _last_escalation_check = current_time
    _last_garbage_collect = current_time
    _last_critical_monitor = current_time
    _last_error_scan = current_time

    # Initial health check
    logger.info("Running initial health check...")
    initial_health = perform_health_check()

    if initial_health.get("status") == "critical":
        logger.warning(
            "System in CRITICAL state at startup - continuing with caution"
        )

    # Log startup event
    log_coordination_event(
        "orchestrator_started",
        {
            "worker_id": WORKER_ID,
            "initial_health": initial_health.get("status", "unknown"),
            "memory_sync_interval": MEMORY_SYNC_INTERVAL_SECONDS,
            "garbage_collect_interval": GARBAGE_COLLECT_INTERVAL_SECONDS,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Main orchestration loop
    logger.info("Entering main orchestration loop...")

    try:
        while _running:
            try:
                run_orchestration_cycle()
            except Exception as e:
                logger.error("Error in orchestration cycle: %s", str(e))

            # Sleep between cycles
            if _running:
                time.sleep(ORCHESTRATION_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")

    # Cleanup
    logger.info("Orchestrator shutting down...")

    log_coordination_event(
        "orchestrator_stopped",
        {
            "worker_id": WORKER_ID,
            "cycles_completed": _cycle_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    logger.info("Orchestrator stopped after %d cycles", _cycle_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
