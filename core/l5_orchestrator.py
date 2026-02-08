"""
L5 Autonomy Orchestrator

This module activates all Level 5 capabilities by wiring together:
- Learning capture and application loop
- Health monitoring daemon
- Escalation timeout checker
- Executive reporting
- Goal tracking
- Experiment lifecycle management

This is the "glue" that makes all L5 components work together.
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# AVAILABILITY FLAGS
# =============================================================================

LEARNING_APPLICATION_AVAILABLE = False
HEALTH_MONITORING_AVAILABLE = False
ESCALATION_AVAILABLE = False
EXECUTIVE_REPORT_AVAILABLE = False
TASK_SCHEDULING_AVAILABLE = False
EXPERIMENT_LIFECYCLE_AVAILABLE = False
GOAL_TRACKING_AVAILABLE = False
GOAL_DECOMPOSITION_AVAILABLE = False

try:
    from core.learning_application import execute_learning_application_cycle
    LEARNING_APPLICATION_AVAILABLE = True
except ImportError as e:
    logger.warning("Learning application not available: %s", e)

try:
    from core.goal_decomposer import decompose_goals_cycle
    GOAL_DECOMPOSITION_AVAILABLE = True
except ImportError as e:
    logger.warning("Goal decomposition not available: %s", e)

try:
    from core.monitoring import check_all_components, get_health_status
    HEALTH_MONITORING_AVAILABLE = True
except ImportError as e:
    logger.warning("Health monitoring not available: %s", e)

try:
    from core.escalation_manager import EscalationManager, EscalationLevel, RiskLevel
    ESCALATION_AVAILABLE = True
except ImportError as e:
    logger.warning("Escalation manager not available: %s", e)

try:
    from core.executive_reporter import generate_executive_report
    EXECUTIVE_REPORT_AVAILABLE = True
except ImportError as e:
    logger.warning("Executive reporter not available: %s", e)

try:
    from core.goal_tracker import update_goal_progress
    GOAL_TRACKING_AVAILABLE = True
except ImportError as e:
    logger.warning("Goal tracker not available: %s", e)

try:
    from core.experiment_executor import progress_experiments
    from core.learning_loop import on_experiment_complete
    EXPERIMENT_LIFECYCLE_AVAILABLE = True
except ImportError as e:
    logger.warning("Experiment lifecycle not available: %s", e)

# =============================================================================
# L5 ORCHESTRATOR CLASS
# =============================================================================

class L5Orchestrator:
    """
    Orchestrates all Level 5 autonomous capabilities.
    
    This class manages the background daemons that make the system
    truly autonomous at L5 level.
    """
    
    def __init__(
        self,
        execute_sql_func: Callable[[str], Dict[str, Any]],
        escape_value_func: Callable[[Any], str],
        log_action_func: Callable[..., Any],
    ):
        self.execute_sql = execute_sql_func
        self.escape_value = escape_value_func
        self.log_action = log_action_func
        
        self.is_running = False
        self.threads: List[threading.Thread] = []
        self.stop_event = threading.Event()
        
        # Initialize escalation manager if available
        self.escalation_manager = None
        if ESCALATION_AVAILABLE:
            try:
                self.escalation_manager = EscalationManager(self)
            except Exception as e:
                logger.error("Failed to initialize escalation manager: %s", e)
    
    def start(self):
        """Start all L5 background daemons."""
        if self.is_running:
            logger.warning("L5 orchestrator already running")
            return
        
        self.is_running = True
        self.stop_event.clear()
        
        # Start goal decomposition daemon (CRITICAL - generates work!)
        if GOAL_DECOMPOSITION_AVAILABLE:
            t = threading.Thread(target=self._goal_decomposition_loop, daemon=True)
            t.start()
            self.threads.append(t)
            logger.info("Started goal decomposition daemon")
        
        # Start learning application daemon
        if LEARNING_APPLICATION_AVAILABLE:
            t = threading.Thread(target=self._learning_application_loop, daemon=True)
            t.start()
            self.threads.append(t)
            logger.info("Started learning application daemon")
        
        # Start health monitoring daemon
        if HEALTH_MONITORING_AVAILABLE:
            t = threading.Thread(target=self._health_monitoring_loop, daemon=True)
            t.start()
            self.threads.append(t)
            logger.info("Started health monitoring daemon")
        
        # Start escalation timeout checker
        if ESCALATION_AVAILABLE:
            t = threading.Thread(target=self._escalation_timeout_loop, daemon=True)
            t.start()
            self.threads.append(t)
            logger.info("Started escalation timeout daemon")
        
        # Start executive reporting daemon
        if EXECUTIVE_REPORT_AVAILABLE:
            t = threading.Thread(target=self._executive_reporting_loop, daemon=True)
            t.start()
            self.threads.append(t)
            logger.info("Started executive reporting daemon")
        
        # Start goal tracking daemon
        if GOAL_TRACKING_AVAILABLE:
            t = threading.Thread(target=self._goal_tracking_loop, daemon=True)
            t.start()
            self.threads.append(t)
            logger.info("Started goal tracking daemon")
        
        # Start experiment lifecycle daemon
        if EXPERIMENT_LIFECYCLE_AVAILABLE:
            t = threading.Thread(target=self._experiment_lifecycle_loop, daemon=True)
            t.start()
            self.threads.append(t)
            logger.info("Started experiment lifecycle daemon")
        
        self.log_action(
            "l5.orchestrator.started",
            "L5 orchestrator started with all daemons",
            level="info",
            output_data={
                "goal_decomposition": GOAL_DECOMPOSITION_AVAILABLE,
                "learning_application": LEARNING_APPLICATION_AVAILABLE,
                "health_monitoring": HEALTH_MONITORING_AVAILABLE,
                "escalation": ESCALATION_AVAILABLE,
                "executive_report": EXECUTIVE_REPORT_AVAILABLE,
                "goal_tracking": GOAL_TRACKING_AVAILABLE,
                "experiment_lifecycle": EXPERIMENT_LIFECYCLE_AVAILABLE,
            }
        )
    
    def stop(self):
        """Stop all L5 background daemons."""
        if not self.is_running:
            return
        
        self.is_running = False
        self.stop_event.set()
        
        # Wait for threads to finish (with timeout)
        for t in self.threads:
            t.join(timeout=5.0)
        
        self.threads = []
        logger.info("L5 orchestrator stopped")
    
    # =========================================================================
    # DAEMON LOOPS
    # =========================================================================
    
    def _goal_decomposition_loop(self):
        """Periodically decompose goals into executable tasks - THE TASK GENERATOR."""
        interval = 180  # 3 minutes - frequent to keep queue filled
        
        while not self.stop_event.is_set():
            try:
                if GOAL_DECOMPOSITION_AVAILABLE:
                    result = decompose_goals_cycle(
                        execute_sql=self.execute_sql,
                        log_action=self.log_action
                    )
                    
                    if result.get("tasks_created", 0) > 0:
                        logger.info(
                            "Goal decomposer: Created %d tasks from %d goals",
                            result["tasks_created"],
                            result["goals_processed"]
                        )
                        self.log_action(
                            "goal_decomposer.cycle_complete",
                            f"Generated {result['tasks_created']} tasks from goals",
                            level="info",
                            output_data=result
                        )
            except Exception as e:
                logger.error("Error in goal decomposition loop: %s", e)
                self.log_action(
                    "goal_decomposer.error",
                    f"Goal decomposition failed: {str(e)[:200]}",
                    level="error",
                    output_data={"error": str(e)}
                )
            
            self.stop_event.wait(interval)
    
    def _learning_application_loop(self):
        """Periodically apply captured learnings to improve the system."""
        interval = 300  # 5 minutes
        
        while not self.stop_event.is_set():
            try:
                if LEARNING_APPLICATION_AVAILABLE:
                    result = execute_learning_application_cycle(
                        execute_sql_func=self.execute_sql,
                        escape_value_func=self.escape_value,
                        log_action_func=self.log_action,
                        max_learnings=10,
                    )
                    
                    if result.get("learnings_applied", 0) > 0:
                        logger.info(
                            "Applied %d learnings (processed %d)",
                            result["learnings_applied"],
                            result["learnings_processed"]
                        )
            except Exception as e:
                logger.error("Error in learning application loop: %s", e)
            
            self.stop_event.wait(interval)
    
    def _health_monitoring_loop(self):
        """Periodically check system health and detect anomalies."""
        interval = 60  # 1 minute
        
        while not self.stop_event.is_set():
            try:
                if HEALTH_MONITORING_AVAILABLE:
                    health = check_all_components()
                    
                    if health.get("overall_status") == "unhealthy":
                        logger.error("System health is UNHEALTHY: %s", health)
                        self.log_action(
                            "health.critical",
                            "System health check failed",
                            level="error",
                            output_data=health
                        )
                    elif health.get("overall_status") == "degraded":
                        logger.warning("System health is DEGRADED: %s", health)
            except Exception as e:
                logger.error("Error in health monitoring loop: %s", e)
            
            self.stop_event.wait(interval)
    
    def _escalation_timeout_loop(self):
        """Check for escalations that have timed out and need action."""
        interval = 300  # 5 minutes
        
        while not self.stop_event.is_set():
            try:
                if ESCALATION_AVAILABLE and self.escalation_manager:
                    # Check for timed-out escalations
                    self._check_escalation_timeouts()
            except Exception as e:
                logger.error("Error in escalation timeout loop: %s", e)
            
            self.stop_event.wait(interval)
    
    def _executive_reporting_loop(self):
        """Generate executive reports on schedule."""
        interval = 3600  # 1 hour
        
        while not self.stop_event.is_set():
            try:
                if EXECUTIVE_REPORT_AVAILABLE:
                    report = generate_executive_report(
                        execute_sql=self.execute_sql,
                        log_action=self.log_action,
                    )
                    
                    logger.info(
                        "Generated executive report: %d tasks completed, %d active goals",
                        report.get("tasks_completed_24h", 0),
                        report.get("active_goals", 0)
                    )
            except Exception as e:
                logger.error("Error in executive reporting loop: %s", e)
            
            self.stop_event.wait(interval)
    
    def _goal_tracking_loop(self):
        """Update goal progress based on system activity."""
        interval = 600  # 10 minutes
        
        while not self.stop_event.is_set():
            try:
                if GOAL_TRACKING_AVAILABLE:
                    result = update_goal_progress(
                        execute_sql=self.execute_sql,
                        log_action=self.log_action,
                    )
                    
                    if result.get("goals_updated", 0) > 0:
                        logger.info("Updated progress for %d goals", result["goals_updated"])
            except Exception as e:
                logger.error("Error in goal tracking loop: %s", e)
            
            self.stop_event.wait(interval)
    
    def _experiment_lifecycle_loop(self):
        """Manage experiment lifecycle from creation to conclusion."""
        interval = 300  # 5 minutes
        
        while not self.stop_event.is_set():
            try:
                if EXPERIMENT_LIFECYCLE_AVAILABLE:
                    # Progress active experiments
                    progress_result = progress_experiments(
                        execute_sql=self.execute_sql,
                        log_action=self.log_action,
                    )
                    
                    if progress_result:
                        logger.info("Progressed experiments: %s", progress_result)
            except Exception as e:
                logger.error("Error in experiment lifecycle loop: %s", e)
            
            self.stop_event.wait(interval)
    
    # =========================================================================
    # ESCALATION METHODS
    # =========================================================================
    
    def _check_escalation_timeouts(self):
        """Check for and handle escalation timeouts."""
        try:
            # Find approvals that have timed out
            timeout_sql = """
                SELECT id, escalation_level, escalation_reason, created_at
                FROM approvals
                WHERE decision = 'pending'
                  AND expires_at < NOW()
            """
            result = self.execute_sql(timeout_sql)
            
            for row in result.get("rows", []):
                approval_id = row["id"]
                current_level = row.get("escalation_level", 0)
                
                # Escalate to next level
                next_level = self._get_next_escalation_level(current_level)
                
                if next_level:
                    # Update approval with escalation
                    update_sql = f"""
                        UPDATE approvals
                        SET escalation_level = {next_level},
                            escalation_reason = COALESCE(escalation_reason, '') || 
                                ' Escalated from level {current_level} to {next_level} at ' || NOW() || ' due to timeout.',
                            expires_at = NOW() + INTERVAL '1 hour',
                            updated_at = NOW()
                        WHERE id = '{approval_id}'
                    """
                    self.execute_sql(update_sql)
                    
                    self.log_action(
                        "escalation.auto_escalated",
                        f"Approval {approval_id} auto-escalated to level {next_level} due to timeout",
                        level="warning",
                        output_data={
                            "approval_id": approval_id,
                            "from_level": current_level,
                            "to_level": next_level
                        }
                    )
        except Exception as e:
            logger.error("Error checking escalation timeouts: %s", e)
    
    def _get_next_escalation_level(self, current_level: str) -> Optional[str]:
        """Get the next escalation level in the chain."""
        hierarchy = ["worker", "orchestrator", "owner"]
        
        if current_level in hierarchy:
            idx = hierarchy.index(current_level)
            if idx < len(hierarchy) - 1:
                return hierarchy[idx + 1]
        
        return None
    
    # =========================================================================
    # IMPACT SIMULATION
    # =========================================================================
    
    def simulate_impact(
        self,
        change_type: str,
        change_description: str,
        affected_components: List[str]
    ) -> Dict[str, Any]:
        """
        Simulate the impact of a proposed change before deployment.
        
        This is L5 requirement: Impact Simulation - Models expected outcomes
        before deploying changes.
        """
        try:
            # Get recent similar changes and their outcomes
            similar_sql = f"""
                SELECT 
                    change_type,
                    AVG(CASE WHEN success THEN 1 ELSE 0 END) as success_rate,
                    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_sec,
                    COUNT(*) as sample_size
                FROM change_history
                WHERE change_type = '{change_type}'
                  AND created_at > NOW() - INTERVAL '30 days'
                GROUP BY change_type
            """
            result = self.execute_sql(similar_sql)
            
            historical = result.get("rows", [{}])[0] if result.get("rows") else {}
            
            # Get current system health
            health = get_health_status() if HEALTH_MONITORING_AVAILABLE else {"overall_status": "unknown"}
            
            # Calculate risk score
            risk_score = 0.5  # Base risk
            
            # Adjust based on system health
            if health.get("overall_status") == "unhealthy":
                risk_score += 0.3
            elif health.get("overall_status") == "degraded":
                risk_score += 0.15
            
            # Adjust based on historical success rate
            success_rate = historical.get("success_rate", 0.5)
            risk_score += (1 - success_rate) * 0.2
            
            # Cap at 1.0
            risk_score = min(1.0, risk_score)
            
            simulation_result = {
                "change_type": change_type,
                "change_description": change_description,
                "affected_components": affected_components,
                "risk_score": round(risk_score, 2),
                "risk_level": "high" if risk_score > 0.7 else "medium" if risk_score > 0.4 else "low",
                "historical_success_rate": round(float(success_rate), 2),
                "historical_sample_size": historical.get("sample_size", 0),
                "current_system_health": health.get("overall_status"),
                "recommendation": "proceed_with_caution" if risk_score > 0.6 else "proceed",
                "estimated_success_probability": round(1 - risk_score, 2),
                "simulated_at": datetime.now(timezone.utc).isoformat()
            }
            
            self.log_action(
                "impact.simulation_complete",
                f"Impact simulation for {change_type}: {simulation_result['risk_level']} risk",
                level="info",
                output_data=simulation_result
            )
            
            return simulation_result
            
        except Exception as e:
            logger.error("Error in impact simulation: %s", e)
            return {
                "change_type": change_type,
                "error": str(e),
                "risk_level": "unknown",
                "recommendation": "manual_review"
            }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def start_l5_orchestrator(
    execute_sql_func: Callable[[str], Dict[str, Any]],
    escape_value_func: Callable[[Any], str],
    log_action_func: Callable[..., Any],
) -> L5Orchestrator:
    """
    Start the L5 orchestrator with all daemons.
    
    This is the main entry point for activating L5 autonomy.
    
    Args:
        execute_sql_func: Function to execute SQL queries
        escape_value_func: Function to escape values for SQL
        log_action_func: Function to log actions
        
    Returns:
        Running L5Orchestrator instance
    """
    orchestrator = L5Orchestrator(
        execute_sql_func=execute_sql_func,
        escape_value_func=escape_value_func,
        log_action_func=log_action_func,
    )
    orchestrator.start()
    return orchestrator


def get_l5_status() -> Dict[str, Any]:
    """Get status of all L5 components."""
    return {
        "goal_decomposition": GOAL_DECOMPOSITION_AVAILABLE,
        "learning_application": LEARNING_APPLICATION_AVAILABLE,
        "health_monitoring": HEALTH_MONITORING_AVAILABLE,
        "escalation": ESCALATION_AVAILABLE,
        "executive_report": EXECUTIVE_REPORT_AVAILABLE,
        "goal_tracking": GOAL_TRACKING_AVAILABLE,
        "experiment_lifecycle": EXPERIMENT_LIFECYCLE_AVAILABLE,
        "checked_at": datetime.now(timezone.utc).isoformat()
    }
