"""
Auto-scaling module for Juggernaut worker management.

This module monitors task queue depth and automatically scales workers
up or down based on configurable thresholds and policies.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_MIN_WORKERS = 1
DEFAULT_MAX_WORKERS = 10
SCALE_UP_THRESHOLD = 5
SCALE_DOWN_THRESHOLD = 0
SCALE_UP_COOLDOWN_SECONDS = 300
SCALE_DOWN_COOLDOWN_SECONDS = 600
HEARTBEAT_STALE_SECONDS = 120


class ScalingAction(Enum):
    """Types of scaling actions."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_ACTION = "no_action"


@dataclass
class ScalingConfig:
    """Configuration for auto-scaling behavior."""
    min_workers: int = DEFAULT_MIN_WORKERS
    max_workers: int = DEFAULT_MAX_WORKERS
    scale_up_threshold: int = SCALE_UP_THRESHOLD
    scale_down_threshold: int = SCALE_DOWN_THRESHOLD
    scale_up_cooldown_seconds: int = SCALE_UP_COOLDOWN_SECONDS
    scale_down_cooldown_seconds: int = SCALE_DOWN_COOLDOWN_SECONDS
    enabled: bool = True


@dataclass
class ScalingDecision:
    """Result of a scaling evaluation."""
    action: ScalingAction
    reason: str
    current_workers: int
    current_queue_depth: int
    target_workers: Optional[int] = None
    workers_to_add: int = 0
    workers_to_remove: int = 0


@dataclass
class QueueMetrics:
    """Metrics about the task queue."""
    pending_count: int
    in_progress_count: int
    waiting_approval_count: int
    total_actionable: int


@dataclass
class WorkerMetrics:
    """Metrics about active workers."""
    active_count: int
    idle_count: int
    stale_count: int
    total_capacity: int


class AutoScaler:
    """
    Manages automatic scaling of Juggernaut workers based on queue depth.
    
    The auto-scaler monitors task queue depth and active worker count,
    making scaling decisions based on configurable thresholds.
    """
    
    def __init__(
        self,
        db_endpoint: str,
        connection_string: str,
        config: Optional[ScalingConfig] = None
    ) -> None:
        """
        Initialize the auto-scaler.
        
        Args:
            db_endpoint: Neon database HTTP endpoint
            connection_string: PostgreSQL connection string
            config: Optional scaling configuration
        """
        self.db_endpoint = db_endpoint
        self.connection_string = connection_string
        self.config = config or ScalingConfig()
        self._last_scale_up: Optional[datetime] = None
        self._last_scale_down: Optional[datetime] = None
        self._http_client: Optional[httpx.Client] = None
    
    @property
    def http_client(self) -> httpx.Client:
        """Lazy-initialize HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=30.0)
        return self._http_client
    
    def _execute_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a SQL query against the database.
        
        Args:
            query: SQL query to execute
            
        Returns:
            Query result as dictionary
            
        Raises:
            RuntimeError: If query execution fails
        """
        try:
            response = self.http_client.post(
                self.db_endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Neon-Connection-String": self.connection_string
                },
                json={"query": query}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.error("Database query failed: %s", exc)
            raise RuntimeError(f"Database query failed: {exc}") from exc
    
    def get_queue_metrics(self) -> QueueMetrics:
        """
        Get current task queue metrics.
        
        Returns:
            QueueMetrics with current queue state
        """
        query = """
            SELECT 
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
                COUNT(*) FILTER (WHERE status = 'waiting_approval') as waiting
            FROM governance_tasks
        """
        result = self._execute_query(query)
        rows = result.get("rows", [])
        
        if not rows:
            return QueueMetrics(0, 0, 0, 0)
        
        row = rows[0]
        pending = int(row.get("pending", 0) or 0)
        in_progress = int(row.get("in_progress", 0) or 0)
        waiting = int(row.get("waiting", 0) or 0)
        
        return QueueMetrics(
            pending_count=pending,
            in_progress_count=in_progress,
            waiting_approval_count=waiting,
            total_actionable=pending + in_progress
        )
    
    def get_worker_metrics(self) -> WorkerMetrics:
        """
        Get current worker metrics.
        
        Returns:
            WorkerMetrics with active worker state
        """
        stale_threshold = datetime.now(timezone.utc) - timedelta(
            seconds=HEARTBEAT_STALE_SECONDS
        )
        
        query = f"""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'active') as active,
                COUNT(*) FILTER (
                    WHERE status = 'active' 
                    AND last_heartbeat < '{stale_threshold.isoformat()}'
                ) as stale,
                COALESCE(SUM(max_concurrent_tasks), 0) as capacity
            FROM worker_registry
            WHERE status = 'active'
        """
        result = self._execute_query(query)
        rows = result.get("rows", [])
        
        if not rows:
            return WorkerMetrics(0, 0, 0, 0)
        
        row = rows[0]
        active = int(row.get("active", 0) or 0)
        stale = int(row.get("stale", 0) or 0)
        capacity = int(row.get("capacity", 0) or 0)
        
        in_progress_query = """
            SELECT COUNT(DISTINCT assigned_worker) as busy_workers
            FROM governance_tasks
            WHERE status = 'in_progress'
        """
        in_progress_result = self._execute_query(in_progress_query)
        in_progress_rows = in_progress_result.get("rows", [])
        busy = int(in_progress_rows[0].get("busy_workers", 0) or 0) if in_progress_rows else 0
        
        idle = max(0, active - stale - busy)
        
        return WorkerMetrics(
            active_count=active - stale,
            idle_count=idle,
            stale_count=stale,
            total_capacity=capacity
        )
    
    def _is_cooldown_active(self, action: ScalingAction) -> bool:
        """Check if cooldown period is active for an action."""
        now = datetime.now(timezone.utc)
        
        if action == ScalingAction.SCALE_UP:
            if self._last_scale_up is None:
                return False
            elapsed = (now - self._last_scale_up).total_seconds()
            return elapsed < self.config.scale_up_cooldown_seconds
        
        if action == ScalingAction.SCALE_DOWN:
            if self._last_scale_down is None:
                return False
            elapsed = (now - self._last_scale_down).total_seconds()
            return elapsed < self.config.scale_down_cooldown_seconds
        
        return False
    
    def evaluate_scaling(self) -> ScalingDecision:
        """
        Evaluate whether scaling is needed.
        
        Returns:
            ScalingDecision with recommended action
        """
        if not self.config.enabled:
            return ScalingDecision(
                action=ScalingAction.NO_ACTION,
                reason="Auto-scaling is disabled",
                current_workers=0,
                current_queue_depth=0
            )
        
        queue = self.get_queue_metrics()
        workers = self.get_worker_metrics()
        
        queue_depth = queue.pending_count
        active_workers = workers.active_count
        
        if queue_depth > self.config.scale_up_threshold:
            if active_workers >= self.config.max_workers:
                return ScalingDecision(
                    action=ScalingAction.NO_ACTION,
                    reason=f"At max workers ({self.config.max_workers})",
                    current_workers=active_workers,
                    current_queue_depth=queue_depth
                )
            
            if self._is_cooldown_active(ScalingAction.SCALE_UP):
                return ScalingDecision(
                    action=ScalingAction.NO_ACTION,
                    reason="Scale-up cooldown active",
                    current_workers=active_workers,
                    current_queue_depth=queue_depth
                )
            
            workers_needed = min(
                queue_depth // self.config.scale_up_threshold,
                self.config.max_workers - active_workers
            )
            
            return ScalingDecision(
                action=ScalingAction.SCALE_UP,
                reason=f"Queue depth {queue_depth} exceeds threshold {self.config.scale_up_threshold}",
                current_workers=active_workers,
                current_queue_depth=queue_depth,
                target_workers=active_workers + workers_needed,
                workers_to_add=workers_needed
            )
        
        if queue_depth <= self.config.scale_down_threshold and workers.idle_count > 0:
            if active_workers <= self.config.min_workers:
                return ScalingDecision(
                    action=ScalingAction.NO_ACTION,
                    reason=f"At min workers ({self.config.min_workers})",
                    current_workers=active_workers,
                    current_queue_depth=queue_depth
                )
            
            if self._is_cooldown_active(ScalingAction.SCALE_DOWN):
                return ScalingDecision(
                    action=ScalingAction.NO_ACTION,
                    reason="Scale-down cooldown active",
                    current_workers=active_workers,
                    current_queue_depth=queue_depth
                )
            
            workers_to_remove = min(
                workers.idle_count,
                active_workers - self.config.min_workers
            )
            
            return ScalingDecision(
                action=ScalingAction.SCALE_DOWN,
                reason=f"Queue empty with {workers.idle_count} idle workers",
                current_workers=active_workers,
                current_queue_depth=queue_depth,
                target_workers=active_workers - workers_to_remove,
                workers_to_remove=workers_to_remove
            )
        
        return ScalingDecision(
            action=ScalingAction.NO_ACTION,
            reason="Queue depth within normal range",
            current_workers=active_workers,
            current_queue_depth=queue_depth
        )
    
    def spawn_worker(self, worker_type: str = "claude-worker") -> Optional[str]:
        """
        Spawn a new worker instance.
        
        Args:
            worker_type: Type of worker to spawn
            
        Returns:
            Worker ID if spawned successfully, None otherwise
        """
        import uuid
        worker_id = f"{worker_type}-{uuid.uuid4().hex[:8]}"
        
        query = f"""
            INSERT INTO worker_registry (
                worker_id, name, description, status, 
                max_concurrent_tasks, last_heartbeat, created_at
            ) VALUES (
                '{worker_id}',
                'Auto-scaled Worker',
                'Spawned by auto-scaler',
                'active',
                5,
                NOW(),
                NOW()
            )
            RETURNING worker_id
        """
        
        try:
            result = self._execute_query(query)
            rows = result.get("rows", [])
            if rows:
                self._last_scale_up = datetime.now(timezone.utc)
                logger.info("Spawned worker: %s", worker_id)
                return worker_id
        except RuntimeError as exc:
            logger.error("Failed to spawn worker: %s", exc)
        
        return None
    
    def terminate_worker(self, worker_id: str) -> bool:
        """
        Terminate an idle worker.
        
        Args:
            worker_id: ID of worker to terminate
            
        Returns:
            True if terminated successfully
        """
        query = f"""
            UPDATE worker_registry
            SET status = 'offline', updated_at = NOW()
            WHERE worker_id = '{worker_id}'
            AND status = 'active'
            RETURNING worker_id
        """
        
        try:
            result = self._execute_query(query)
            if result.get("rowCount", 0) > 0:
                self._last_scale_down = datetime.now(timezone.utc)
                logger.info("Terminated worker: %s", worker_id)
                return True
        except RuntimeError as exc:
            logger.error("Failed to terminate worker %s: %s", worker_id, exc)
        
        return False
    
    def get_idle_workers(self) -> List[str]:
        """
        Get list of idle worker IDs.
        
        Returns:
            List of worker IDs that are idle
        """
        query = """
            SELECT wr.worker_id
            FROM worker_registry wr
            WHERE wr.status = 'active'
            AND NOT EXISTS (
                SELECT 1 FROM governance_tasks gt
                WHERE gt.assigned_worker = wr.worker_id
                AND gt.status = 'in_progress'
            )
            ORDER BY wr.last_heartbeat ASC
        """
        
        result = self._execute_query(query)
        rows = result.get("rows", [])
        return [row["worker_id"] for row in rows]
    
    def execute_scaling(self) -> Dict[str, Any]:
        """
        Evaluate and execute scaling decision.
        
        Returns:
            Dict with scaling action results
        """
        decision = self.evaluate_scaling()
        
        result = {
            "action": decision.action.value,
            "reason": decision.reason,
            "current_workers": decision.current_workers,
            "queue_depth": decision.current_queue_depth,
            "workers_added": [],
            "workers_removed": []
        }
        
        if decision.action == ScalingAction.SCALE_UP:
            for _ in range(decision.workers_to_add):
                worker_id = self.spawn_worker()
                if worker_id:
                    result["workers_added"].append(worker_id)
        
        elif decision.action == ScalingAction.SCALE_DOWN:
            idle_workers = self.get_idle_workers()
            for worker_id in idle_workers[:decision.workers_to_remove]:
                if self.terminate_worker(worker_id):
                    result["workers_removed"].append(worker_id)
        
        logger.info(
            "Scaling executed: action=%s, added=%d, removed=%d",
            decision.action.value,
            len(result["workers_added"]),
            len(result["workers_removed"])
        )
        
        return result
    
    def log_scaling_event(self, decision: ScalingDecision) -> None:
        """
        Log scaling event to database for tracking.
        
        Args:
            decision: The scaling decision made
        """
        query = f"""
            INSERT INTO scaling_events (
                action, reason, workers_before, workers_after,
                queue_depth, created_at
            ) VALUES (
                '{decision.action.value}',
                '{decision.reason}',
                {decision.current_workers},
                {decision.target_workers or decision.current_workers},
                {decision.current_queue_depth},
                NOW()
            )
        """
        
        try:
            self._execute_query(query)
        except RuntimeError:
            logger.warning("Failed to log scaling event (table may not exist)")


def create_auto_scaler(
    db_endpoint: str,
    connection_string: str,
    config: Optional[ScalingConfig] = None
) -> AutoScaler:
    """
    Factory function to create an AutoScaler.
    
    Args:
        db_endpoint: Neon database HTTP endpoint
        connection_string: PostgreSQL connection string
        config: Optional scaling configuration
        
    Returns:
        Configured AutoScaler instance
    """
    return AutoScaler(db_endpoint, connection_string, config)
