"""
Autonomous Execution Engine for Juggernaut.

This module implements the core autonomous loop that:
- Polls for pending tasks from the task queue
- Executes tasks using the Brain with tool capabilities
- Handles task lifecycle (claim, execute, complete/fail)
- Respects safety limits and execution budgets
- Provides telemetry and health monitoring
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from .database import query_db, escape_sql_value
from .unified_brain import BrainService

logger = logging.getLogger(__name__)


class EngineState(Enum):
    """Autonomous engine operational states."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class ExecutionLimits:
    """Safety limits for autonomous execution."""
    max_concurrent_tasks: int = 3
    max_tasks_per_hour: int = 100
    max_cost_per_hour_cents: float = 1000.0  # $10/hour limit
    max_iterations_per_task: int = 30
    cooldown_seconds: float = 5.0
    task_timeout_seconds: float = 300.0  # 5 minutes per task
    max_marketing_budget_cents: float = 50000.0  # $500/day marketing budget
    max_content_volume: int = 50  # Max SEO content pieces per day
    max_ad_campaigns: int = 10  # Max concurrent ad campaigns


@dataclass
class ExecutionMetrics:
    """Metrics for autonomous execution monitoring."""
    tasks_executed: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    total_cost_cents: float = 0.0
    total_iterations: int = 0
    average_task_duration: float = 0.0
    last_execution_time: Optional[datetime] = None
    hourly_task_count: int = 0
    hourly_cost_cents: float = 0.0
    hour_window_start: datetime = field(default_factory=datetime.now)


class AutonomousEngine:
    """
    Autonomous execution engine that continuously polls and executes tasks.
    
    The engine operates in a loop:
    1. Poll for pending tasks (priority: critical > high > medium > low)
    2. Claim task for execution
    3. Execute task using Brain with tools
    4. Update task status (completed/failed)
    5. Record metrics and telemetry
    6. Respect safety limits and cooldowns
    """
    
    def __init__(
        self,
        worker_id: str = "autonomous-engine",
        limits: Optional[ExecutionLimits] = None,
        brain: Optional[BrainService] = None
    ):
        """
        Initialize autonomous engine.
        
        Args:
            worker_id: Identifier for this engine instance
            limits: Execution safety limits
            brain: BrainService instance (creates new if None)
        """
        self.worker_id = worker_id
        self.limits = limits or ExecutionLimits()
        self.brain = brain or BrainService()
        self.state = EngineState.STOPPED
        self.metrics = ExecutionMetrics()
        self.current_tasks: Dict[str, datetime] = {}
        
        logger.info(f"Autonomous engine '{worker_id}' initialized")
    
    def start(self) -> None:
        """Start the autonomous execution loop."""
        if self.state == EngineState.RUNNING:
            logger.warning("Engine already running")
            return
        
        self.state = EngineState.RUNNING
        logger.info(f"Autonomous engine '{self.worker_id}' started")
    
    def stop(self) -> None:
        """Stop the autonomous execution loop."""
        self.state = EngineState.STOPPED
        logger.info(f"Autonomous engine '{self.worker_id}' stopped")
    
    def pause(self) -> None:
        """Pause the autonomous execution loop."""
        self.state = EngineState.PAUSED
        logger.info(f"Autonomous engine '{self.worker_id}' paused")
    
    def resume(self) -> None:
        """Resume the autonomous execution loop."""
        if self.state == EngineState.PAUSED:
            self.state = EngineState.RUNNING
            logger.info(f"Autonomous engine '{self.worker_id}' resumed")
    
    def poll_next_task(self) -> Optional[Dict[str, Any]]:
        """
        Poll for the next pending task to execute.
        
        Returns:
            Task dict or None if no tasks available
        """
        try:
            result = query_db("""
                SELECT id, title, description, priority, task_type, 
                       created_at, metadata
                FROM tasks
                WHERE status = 'pending'
                  AND (assigned_to IS NULL OR assigned_to = '')
                ORDER BY 
                    CASE priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                        ELSE 5
                    END,
                    CASE task_type
                        WHEN 'marketing_funnel' THEN 1
                        WHEN 'seo_content' THEN 2
                        WHEN 'ad_campaign' THEN 3
                        WHEN 'onboarding' THEN 4
                        WHEN 'sales_pipeline' THEN 5
                        ELSE 6
                    END,
                    created_at ASC
                LIMIT 1
            """)
            
            rows = result.get("rows", [])
            if rows:
                task = rows[0]
                logger.info(f"Polled task: {task.get('id')} - {task.get('title')}")
                return task
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to poll tasks: {e}")
            return None
    
    def claim_task(self, task_id: str) -> bool:
        """
        Claim a task for execution.
        
        Args:
            task_id: Task ID to claim
            
        Returns:
            True if successfully claimed
        """
        try:
            result = query_db(f"""
                UPDATE tasks
                SET status = 'in_progress',
                    assigned_to = {escape_sql_value(self.worker_id)},
                    started_at = NOW()
                WHERE id = {escape_sql_value(task_id)}::uuid
                  AND status = 'pending'
            """)
            
            success = result.get("rowCount", 0) > 0
            if success:
                self.current_tasks[task_id] = datetime.now()
                logger.info(f"Claimed task {task_id}")
            else:
                logger.warning(f"Failed to claim task {task_id} - may have been claimed by another worker")
            
            return success
            
        except Exception as e:
            logger.error(f"Error claiming task {task_id}: {e}")
            return False
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task using the Brain.
        
        Args:
            task: Task dictionary
            
        Returns:
            Execution result with success status and details
        """
        task_id = task.get("id")
        title = task.get("title", "")
        description = task.get("description", "")
        task_type = task.get("task_type", "general")
        
        logger.info(f"Executing task {task_id}: {title}")
        
        # Construct question for Brain based on task type
        if task_type == "marketing_funnel":
            question = f"""Marketing Funnel Task: {title}

Description:
{description}

Please analyze and optimize our marketing funnel. Identify bottlenecks, suggest improvements, and implement changes to increase conversion rates."""
        elif task_type == "seo_content":
            question = f"""SEO Content Task: {title}

Description:
{description}

Please generate SEO-optimized content targeting the specified keywords and topics. Ensure proper keyword density, readability, and relevance."""
        elif task_type == "ad_campaign":
            question = f"""Ad Campaign Task: {title}

Description:
{description}

Please create and optimize programmatic ad campaigns across platforms. Set targeting parameters, budgets, and bidding strategies."""
        elif task_type == "onboarding":
            question = f"""Onboarding Task: {title}

Description:
{description}

Please design and implement self-service onboarding flows. Create interactive tutorials, documentation, and automated guidance."""
        elif task_type == "sales_pipeline":
            question = f"""Sales Pipeline Task: {title}

Description:
{description}

Please analyze and optimize our sales pipeline. Identify stages with drop-offs, implement automation, and suggest improvements to increase velocity."""
        else:
            question = f"""Task: {title}

Description:
{description}

Task Type: {task_type}

Please analyze this task and execute it using available tools. Provide a detailed response with your findings and actions taken."""
        
        start_time = time.time()
        
        try:
            # Execute with Brain using streaming for better control
            result = self.brain.consult_with_tools(
                question=question,
                session_id=f"task-{task_id}",
                enable_tools=True,
                auto_execute=True,
            )
            
            duration = time.time() - start_time
            
            # Update metrics
            self.metrics.tasks_executed += 1
            self.metrics.total_iterations += result.get("iterations", 0)
            self.metrics.total_cost_cents += result.get("cost_cents", 0.0)
            
            # Update average duration
            if self.metrics.tasks_executed > 1:
                self.metrics.average_task_duration = (
                    (self.metrics.average_task_duration * (self.metrics.tasks_executed - 1) + duration)
                    / self.metrics.tasks_executed
                )
            else:
                self.metrics.average_task_duration = duration
            
            self.metrics.last_execution_time = datetime.now()
            
            return {
                "success": True,
                "response": result.get("response", ""),
                "tool_executions": result.get("tool_executions", []),
                "iterations": result.get("iterations", 0),
                "cost_cents": result.get("cost_cents", 0.0),
                "duration_seconds": duration,
            }
            
        except Exception as e:
            logger.error(f"Task execution failed for {task_id}: {e}")
            duration = time.time() - start_time
            
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": duration,
            }
    
    def complete_task(self, task_id: str, result: Dict[str, Any]) -> bool:
        """
        Mark task as completed with results.
        
        Args:
            task_id: Task ID
            result: Execution result
            
        Returns:
            True if successfully updated
        """
        try:
            output = result.get("response", result.get("error", ""))
            metadata = {
                "tool_executions": result.get("tool_executions", []),
                "iterations": result.get("iterations", 0),
                "cost_cents": result.get("cost_cents", 0.0),
                "duration_seconds": result.get("duration_seconds", 0.0),
                "executed_by": self.worker_id,
            }
            
            query_db(f"""
                UPDATE tasks
                SET status = 'completed',
                    completed_at = NOW(),
                    output = {escape_sql_value(output)},
                    metadata = {escape_sql_value(str(metadata))}
                WHERE id = {escape_sql_value(task_id)}::uuid
            """)
            
            if task_id in self.current_tasks:
                del self.current_tasks[task_id]
            
            self.metrics.tasks_succeeded += 1
            logger.info(f"Task {task_id} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error completing task {task_id}: {e}")
            return False
    
    def fail_task(self, task_id: str, result: Dict[str, Any]) -> bool:
        """
        Mark task as failed with error details.
        
        Args:
            task_id: Task ID
            result: Execution result with error
            
        Returns:
            True if successfully updated
        """
        try:
            error = result.get("error", "Unknown error")
            
            query_db(f"""
                UPDATE tasks
                SET status = 'failed',
                    completed_at = NOW(),
                    output = {escape_sql_value(f"Error: {error}")}
                WHERE id = {escape_sql_value(task_id)}::uuid
            """)
            
            if task_id in self.current_tasks:
                del self.current_tasks[task_id]
            
            self.metrics.tasks_failed += 1
            logger.warning(f"Task {task_id} failed: {error}")
            return True
            
        except Exception as e:
            logger.error(f"Error failing task {task_id}: {e}")
            return False
    
    def check_limits(self) -> Dict[str, Any]:
        """
        Check if execution limits are being respected.
        
        Returns:
            Dict with limit status and reasons
        """
        now = datetime.now()
        
        # Reset hourly counters if hour has passed
        if now - self.metrics.hour_window_start > timedelta(hours=1):
            self.metrics.hourly_task_count = 0
            self.metrics.hourly_cost_cents = 0.0
            self.metrics.hour_window_start = now
        
        violations = []
        
        # Check concurrent tasks
        if len(self.current_tasks) >= self.limits.max_concurrent_tasks:
            violations.append(f"Max concurrent tasks reached ({self.limits.max_concurrent_tasks})")
        
        # Check hourly task limit
        if self.metrics.hourly_task_count >= self.limits.max_tasks_per_hour:
            violations.append(f"Hourly task limit reached ({self.limits.max_tasks_per_hour})")
        
        # Check hourly cost limit
        if self.metrics.hourly_cost_cents >= self.limits.max_cost_per_hour_cents:
            violations.append(f"Hourly cost limit reached (${self.limits.max_cost_per_hour_cents/100:.2f})")
        
        return {
            "within_limits": len(violations) == 0,
            "violations": violations,
            "current_concurrent": len(self.current_tasks),
            "hourly_tasks": self.metrics.hourly_task_count,
            "hourly_cost_cents": self.metrics.hourly_cost_cents,
        }
    
    def run_cycle(self) -> Dict[str, Any]:
        """
        Run one execution cycle.
        
        Returns:
            Dict with cycle results
        """
        if self.state != EngineState.RUNNING:
            return {"action": "skipped", "reason": f"Engine state: {self.state.value}"}
        
        # Check limits
        limit_check = self.check_limits()
        if not limit_check["within_limits"]:
            logger.warning(f"Execution limits violated: {limit_check['violations']}")
            return {
                "action": "limited",
                "reason": "Execution limits reached",
                "violations": limit_check["violations"],
            }
        
        # Poll for next task
        task = self.poll_next_task()
        if not task:
            return {"action": "idle", "reason": "No pending tasks"}
        
        task_id = task.get("id")
        
        # Claim task
        if not self.claim_task(task_id):
            return {"action": "claim_failed", "task_id": task_id}
        
        # Execute task
        result = self.execute_task(task)
        
        # Update hourly counters
        self.metrics.hourly_task_count += 1
        self.metrics.hourly_cost_cents += result.get("cost_cents", 0.0)
        
        # Update task status
        if result.get("success"):
            self.complete_task(task_id, result)
            return {
                "action": "executed",
                "task_id": task_id,
                "success": True,
                "cost_cents": result.get("cost_cents", 0.0),
                "duration_seconds": result.get("duration_seconds", 0.0),
            }
        else:
            self.fail_task(task_id, result)
            return {
                "action": "executed",
                "task_id": task_id,
                "success": False,
                "error": result.get("error"),
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current execution metrics."""
        return {
            "state": self.state.value,
            "worker_id": self.worker_id,
            "tasks_executed": self.metrics.tasks_executed,
            "tasks_succeeded": self.metrics.tasks_succeeded,
            "tasks_failed": self.metrics.tasks_failed,
            "success_rate": (
                self.metrics.tasks_succeeded / self.metrics.tasks_executed * 100
                if self.metrics.tasks_executed > 0 else 0.0
            ),
            "total_cost_cents": self.metrics.total_cost_cents,
            "average_task_duration": self.metrics.average_task_duration,
            "current_concurrent_tasks": len(self.current_tasks),
            "hourly_task_count": self.metrics.hourly_task_count,
            "hourly_cost_cents": self.metrics.hourly_cost_cents,
            "last_execution": (
                self.metrics.last_execution_time.isoformat()
                if self.metrics.last_execution_time else None
            ),
        }


def create_autonomous_engine(
    worker_id: str = "autonomous-engine",
    **limit_kwargs
) -> AutonomousEngine:
    """
    Create and configure an autonomous engine instance.
    
    Args:
        worker_id: Engine identifier
        **limit_kwargs: ExecutionLimits parameters
        
    Returns:
        Configured AutonomousEngine instance
    """
    limits = ExecutionLimits(**limit_kwargs) if limit_kwargs else ExecutionLimits()
    return AutonomousEngine(worker_id=worker_id, limits=limits)
