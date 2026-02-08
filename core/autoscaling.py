"""
Worker Auto-Scaling Module for JUGGERNAUT.

This module implements automatic scaling of workers based on task queue depth.
It monitors queue metrics and spawns/terminates workers to maintain optimal throughput.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Queue depth thresholds
MIN_QUEUE_DEPTH_FOR_SCALE_UP: int = 5
MAX_QUEUE_DEPTH_FOR_SCALE_DOWN: int = 1
CRITICAL_QUEUE_DEPTH: int = 20

# Worker limits
MIN_WORKERS: int = 1
MAX_WORKERS: int = 10
DEFAULT_WORKERS: int = 2

# Timing constants (in seconds)
SCALE_CHECK_INTERVAL_SECONDS: int = 60
COOLDOWN_AFTER_SCALE_SECONDS: int = 300
WORKER_IDLE_TIMEOUT_SECONDS: int = 600
METRICS_WINDOW_SECONDS: int = 300

# Scale factors
SCALE_UP_FACTOR: float = 1.5
SCALE_DOWN_FACTOR: float = 0.5
TASKS_PER_WORKER: int = 3


class ScalingDecision(Enum):
    """Enum representing possible scaling decisions."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    MAINTAIN = "maintain"
    EMERGENCY_SCALE = "emergency_scale"


@dataclass
class QueueMetrics:
    """Data class for task queue metrics."""
    pending_count: int
    in_progress_count: int
    critical_count: int
    high_priority_count: int
    avg_wait_time_seconds: float
    oldest_task_age_seconds: float
    measured_at: datetime

    @property
    def total_active_tasks(self) -> int:
        """Return total number of active tasks requiring attention."""
        return self.pending_count + self.in_progress_count

    @property
    def priority_weighted_count(self) -> float:
        """Return priority-weighted task count (critical tasks count more)."""
        critical_weight: float = 3.0
        high_weight: float = 2.0
        normal_weight: float = 1.0
        weighted = (
            self.critical_count * critical_weight +
            self.high_priority_count * high_weight +
            (self.pending_count - self.critical_count - self.high_priority_count) * normal_weight
        )
        return max(weighted, 0.0)


@dataclass
class WorkerMetrics:
    """Data class for worker pool metrics."""
    active_count: int
    idle_count: int
    busy_count: int
    avg_tasks_per_worker: float
    measured_at: datetime

    @property
    def total_workers(self) -> int:
        """Return total number of workers."""
        return self.active_count

    @property
    def utilization_rate(self) -> float:
        """Return worker utilization rate (0.0 to 1.0)."""
        if self.active_count == 0:
            return 0.0
        return self.busy_count / self.active_count


@dataclass
class ScalingEvent:
    """Data class for scaling event records."""
    event_id: str
    decision: ScalingDecision
    previous_worker_count: int
    new_worker_count: int
    queue_depth: int
    reason: str
    timestamp: datetime


class AutoScaler:
    """
    Manages automatic scaling of workers based on queue metrics.
    
    This class monitors task queue depth and worker utilization to make
    intelligent scaling decisions. It implements cooldown periods to
    prevent thrashing and supports emergency scaling for critical situations.
    """

    def __init__(
        self,
        min_workers: int = MIN_WORKERS,
        max_workers: int = MAX_WORKERS,
        scale_up_threshold: int = MIN_QUEUE_DEPTH_FOR_SCALE_UP,
        scale_down_threshold: int = MAX_QUEUE_DEPTH_FOR_SCALE_DOWN,
        cooldown_seconds: int = COOLDOWN_AFTER_SCALE_SECONDS
    ) -> None:
        """
        Initialize the AutoScaler.
        
        Args:
            min_workers: Minimum number of workers to maintain.
            max_workers: Maximum number of workers allowed.
            scale_up_threshold: Queue depth that triggers scale up.
            scale_down_threshold: Queue depth that triggers scale down.
            cooldown_seconds: Seconds to wait between scaling operations.
        """
        self._min_workers = min_workers
        self._max_workers = max_workers
        self._scale_up_threshold = scale_up_threshold
        self._scale_down_threshold = scale_down_threshold
        self._cooldown_seconds = cooldown_seconds
        self._last_scale_time: Optional[datetime] = None
        self._scaling_history: List[ScalingEvent] = []
        self._current_worker_count = DEFAULT_WORKERS
        logger.info(
            "AutoScaler initialized: min=%d, max=%d, up_threshold=%d, down_threshold=%d",
            min_workers, max_workers, scale_up_threshold, scale_down_threshold
        )

    def evaluate_scaling(
        self,
        queue_metrics: QueueMetrics,
        worker_metrics: WorkerMetrics
    ) -> Tuple[ScalingDecision, int, str]:
        """
        Evaluate whether scaling is needed based on current metrics.
        
        Args:
            queue_metrics: Current task queue metrics.
            worker_metrics: Current worker pool metrics.
            
        Returns:
            Tuple of (decision, target_worker_count, reason).
        """
        current_workers = worker_metrics.active_count
        pending_tasks = queue_metrics.pending_count
        
        if queue_metrics.critical_count > 0 or pending_tasks >= CRITICAL_QUEUE_DEPTH:
            return self._evaluate_emergency_scaling(queue_metrics, current_workers)
        
        if not self._is_cooldown_complete():
            logger.debug("Scaling in cooldown period, maintaining current count")
            return ScalingDecision.MAINTAIN, current_workers, "In cooldown period"
        
        optimal_workers = self._calculate_optimal_workers(queue_metrics, worker_metrics)
        
        if optimal_workers > current_workers:
            target = min(optimal_workers, self._max_workers)
            if target > current_workers:
                reason = f"Queue depth {pending_tasks} exceeds threshold {self._scale_up_threshold}"
                return ScalingDecision.SCALE_UP, target, reason
        
        elif optimal_workers < current_workers:
            target = max(optimal_workers, self._min_workers)
            if target < current_workers and worker_metrics.utilization_rate < SCALE_DOWN_FACTOR:
                reason = f"Low utilization ({worker_metrics.utilization_rate:.2%}) and queue depth {pending_tasks}"
                return ScalingDecision.SCALE_DOWN, target, reason
        
        return ScalingDecision.MAINTAIN, current_workers, "Current capacity is optimal"

    def _evaluate_emergency_scaling(
        self,
        queue_metrics: QueueMetrics,
        current_workers: int
    ) -> Tuple[ScalingDecision, int, str]:
        """Evaluate emergency scaling for critical situations."""
        if queue_metrics.critical_count > 0:
            target = min(current_workers + queue_metrics.critical_count, self._max_workers)
            reason = f"Emergency: {queue_metrics.critical_count} critical tasks pending"
            logger.warning(reason)
            return ScalingDecision.EMERGENCY_SCALE, target, reason
        
        if queue_metrics.pending_count >= CRITICAL_QUEUE_DEPTH:
            target = self._max_workers
            reason = f"Emergency: Queue depth {queue_metrics.pending_count} at critical level"
            logger.warning(reason)
            return ScalingDecision.EMERGENCY_SCALE, target, reason
        
        return ScalingDecision.MAINTAIN, current_workers, "No emergency detected"

    def _calculate_optimal_workers(
        self,
        queue_metrics: QueueMetrics,
        worker_metrics: WorkerMetrics
    ) -> int:
        """Calculate optimal number of workers based on metrics."""
        base_workers = max(1, queue_metrics.pending_count // TASKS_PER_WORKER)
        priority_adjustment = int(queue_metrics.priority_weighted_count / TASKS_PER_WORKER)
        wait_time_adjustment = 0
        if queue_metrics.avg_wait_time_seconds > METRICS_WINDOW_SECONDS:
            wait_time_adjustment = 1
        optimal = base_workers + priority_adjustment + wait_time_adjustment
        return max(self._min_workers, min(optimal, self._max_workers))

    def _is_cooldown_complete(self) -> bool:
        """Check if the cooldown period has elapsed since last scaling."""
        if self._last_scale_time is None:
            return True
        elapsed = (datetime.utcnow() - self._last_scale_time).total_seconds()
        return elapsed >= self._cooldown_seconds

    def record_scaling_event(
        self,
        decision: ScalingDecision,
        previous_count: int,
        new_count: int,
        queue_depth: int,
        reason: str
    ) -> ScalingEvent:
        """Record a scaling event and update internal state."""
        event = ScalingEvent(
            event_id=f"scale_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            decision=decision,
            previous_worker_count=previous_count,
            new_worker_count=new_count,
            queue_depth=queue_depth,
            reason=reason,
            timestamp=datetime.utcnow()
        )
        self._scaling_history.append(event)
        self._last_scale_time = event.timestamp
        self._current_worker_count = new_count
        logger.info(
            "Scaling event recorded: %s from %d to %d workers (queue=%d)",
            decision.value, previous_count, new_count, queue_depth
        )
        return event

    def get_scaling_history(self, limit: int = 10) -> List[ScalingEvent]:
        """Get recent scaling events."""
        return self._scaling_history[-limit:]

    @property
    def current_worker_count(self) -> int:
        """Return the current tracked worker count."""
        return self._current_worker_count


class QueueDepthMonitor:
    """Monitors task queue depth and collects metrics for scaling decisions."""

    def __init__(self, db_executor: Any) -> None:
        """Initialize the QueueDepthMonitor."""
        self._db_executor = db_executor
        self._last_metrics: Optional[QueueMetrics] = None
        logger.info("QueueDepthMonitor initialized")

    async def collect_metrics(self) -> QueueMetrics:
        """Collect current queue metrics from the database."""
        query = """
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress_count,
                COUNT(*) FILTER (WHERE status = 'pending' AND priority = 'critical') as critical_count,
                COUNT(*) FILTER (WHERE status = 'pending' AND priority = 'high') as high_count,
                COALESCE(AVG(EXTRACT(EPOCH FROM (NOW() - created_at))) FILTER (WHERE status = 'pending'), 0) as avg_wait_seconds,
                COALESCE(MAX(EXTRACT(EPOCH FROM (NOW() - created_at))) FILTER (WHERE status = 'pending'), 0) as oldest_task_seconds
            FROM governance_tasks
            WHERE status IN ('pending', 'in_progress');
        """
        try:
            result = await self._db_executor.execute(query)
            row = result[0] if result else {}
            metrics = QueueMetrics(
                pending_count=int(row.get('pending_count', 0)),
                in_progress_count=int(row.get('in_progress_count', 0)),
                critical_count=int(row.get('critical_count', 0)),
                high_priority_count=int(row.get('high_count', 0)),
                avg_wait_time_seconds=float(row.get('avg_wait_seconds', 0.0)),
                oldest_task_age_seconds=float(row.get('oldest_task_seconds', 0.0)),
                measured_at=datetime.utcnow()
            )
            self._last_metrics = metrics
            logger.debug("Queue metrics collected: pending=%d, critical=%d", metrics.pending_count, metrics.critical_count)
            return metrics
        except Exception as exc:
            logger.error("Failed to collect queue metrics: %s", exc)
            raise RuntimeError(f"Database query failed: {exc}") from exc

    @property
    def last_metrics(self) -> Optional[QueueMetrics]:
        """Return the most recently collected metrics."""
        return self._last_metrics


class WorkerPoolManager:
    """Manages the pool of workers for task processing."""

    def __init__(self, db_executor: Any) -> None:
        """Initialize the WorkerPoolManager."""
        self._db_executor = db_executor
        self._registered_workers: Dict[str, datetime] = {}
        logger.info("WorkerPoolManager initialized")

    async def collect_metrics(self) -> WorkerMetrics:
        """Collect current worker pool metrics."""
        query = """
            SELECT assigned_worker, COUNT(*) as task_count, MAX(started_at) as last_active
            FROM governance_tasks
            WHERE status = 'in_progress' AND assigned_worker IS NOT NULL
            GROUP BY assigned_worker;
        """
        try:
            result = await self._db_executor.execute(query)
            active_workers = len(result) if result else 0
            busy_workers = sum(1 for r in (result or []) if r.get('task_count', 0) > 0)
            idle_workers = active_workers - busy_workers
            total_tasks = sum(r.get('task_count', 0) for r in (result or []))
            avg_tasks = total_tasks / active_workers if active_workers > 0 else 0.0
            metrics = WorkerMetrics(
                active_count=max(active_workers, MIN_WORKERS),
                idle_count=idle_workers,
                busy_count=busy_workers,
                avg_tasks_per_worker=avg_tasks,
                measured_at=datetime.utcnow()
            )
            logger.debug("Worker metrics collected: active=%d, busy=%d", metrics.active_count, metrics.busy_count)
            return metrics
        except Exception as exc:
            logger.error("Failed to collect worker metrics: %s", exc)
            return WorkerMetrics(
                active_count=MIN_WORKERS, idle_count=0, busy_count=MIN_WORKERS,
                avg_tasks_per_worker=0.0, measured_at=datetime.utcnow()
            )

    async def spawn_workers(self, count: int) -> List[str]:
        """Spawn additional workers."""
        spawned: List[str] = []
        for i in range(count):
            worker_id = f"worker-{datetime.utcnow().strftime('%H%M%S')}-{i:02d}"
            self._registered_workers[worker_id] = datetime.utcnow()
            spawned.append(worker_id)
            logger.info("Spawned worker: %s", worker_id)
        return spawned

    async def terminate_workers(self, count: int) -> List[str]:
        """Terminate idle workers."""
        terminated: List[str] = []
        query = """
            SELECT DISTINCT assigned_worker FROM governance_tasks
            WHERE status = 'in_progress' AND assigned_worker IS NOT NULL;
        """
        try:
            result = await self._db_executor.execute(query)
            active_worker_ids = {r.get('assigned_worker') for r in (result or [])}
            idle_workers = [wid for wid in self._registered_workers.keys() if wid not in active_worker_ids]
            for worker_id in idle_workers[:count]:
                del self._registered_workers[worker_id]
                terminated.append(worker_id)
                logger.info("Terminated worker: %s", worker_id)
        except Exception as exc:
            logger.error("Failed to terminate workers: %s", exc)
        return terminated

    @property
    def registered_worker_count(self) -> int:
        """Return count of registered workers."""
        return len(self._registered_workers)


async def run_autoscaling_cycle(
    autoscaler: AutoScaler,
    queue_monitor: QueueDepthMonitor,
    worker_manager: WorkerPoolManager
) -> Optional[ScalingEvent]:
    """Run a single auto-scaling evaluation cycle."""
    try:
        queue_metrics = await queue_monitor.collect_metrics()
        worker_metrics = await worker_manager.collect_metrics()
        decision, target_count, reason = autoscaler.evaluate_scaling(queue_metrics, worker_metrics)
        current_count = worker_metrics.active_count
        
        if decision in (ScalingDecision.SCALE_UP, ScalingDecision.EMERGENCY_SCALE):
            workers_to_add = target_count - current_count
            if workers_to_add > 0:
                await worker_manager.spawn_workers(workers_to_add)
                return autoscaler.record_scaling_event(
                    decision, current_count, target_count, queue_metrics.pending_count, reason
                )
        elif decision == ScalingDecision.SCALE_DOWN:
            workers_to_remove = current_count - target_count
            if workers_to_remove > 0:
                await worker_manager.terminate_workers(workers_to_remove)
                return autoscaler.record_scaling_event(
                    decision, current_count, target_count, queue_metrics.pending_count, reason
                )
        
        logger.debug("No scaling action taken: %s", reason)
        return None
    except Exception as exc:
        logger.error("Auto-scaling cycle failed: %s", exc)
        return None
