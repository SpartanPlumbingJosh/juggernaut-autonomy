import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple

try:
    # Local import from the same package; this module is expected to exist.
    from core import learning_application as _learning_application_module  # type: ignore[import]
except ImportError:  # pragma: no cover - defensive in case the module is not present
    _learning_application_module = None  # type: ignore[assignment]

# Configure module-level logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_BASE_BACKOFF_SECONDS: float = 1.0
DEFAULT_BACKOFF_MULTIPLIER: float = 2.0

LEARNING_PHASE_BEFORE_TASK: str = "before_task"
LEARNING_PHASE_AFTER_TASK: str = "after_task"

LEARNING_KEY_TASK_ROUTING_BIAS: str = "task_routing_bias"
LEARNING_KEY_WORKER_SCORE_ADJUSTMENTS: str = "worker_score_adjustments"
LEARNING_KEY_RETRY_POLICY_OVERRIDES: str = "retry_policy_overrides"


class LearningFunction(Protocol):
    """Protocol for a learning application function.

    The function receives a context mapping and returns a mapping of learning
    updates that can influence task routing, worker selection, and retry strategies.
    """

    def __call__(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        """Apply learnings to the given context.

        Args:
            context: Execution context containing task, worker, and strategy state.

        Returns:
            A mapping of learning updates.
        """
        ...


class TransientWorkerError(Exception):
    """Represents a transient failure when executing a task on a worker."""


class PermanentWorkerError(Exception):
    """Represents a non-retryable failure when executing a task on a worker."""


@dataclass
class Task:
    """Represents a unit of work to be executed.

    Attributes:
        task_id: Unique identifier for the task.
        task_type: Logical type/category of the task.
        payload: Arbitrary payload for the task.
        metadata: Optional metadata associated with the task.
    """

    task_id: str
    task_type: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the task to a serializable dictionary.

        Returns:
            A dictionary representation of the task.
        """
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "metadata": self.metadata,
        }


@dataclass
class Worker:
    """Represents a worker capable of executing tasks.

    Attributes:
        worker_id: Unique identifier for the worker.
        capabilities: List of task types this worker can handle.
        reliability_score: A score representing reliability (higher is better).
        current_load: Approximate measure of current load on the worker.
    """

    worker_id: str
    capabilities: List[str]
    reliability_score: float = 1.0
    current_load: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert the worker to a serializable dictionary.

        Returns:
            A dictionary representation of the worker.
        """
        return {
            "worker_id": self.worker_id,
            "capabilities": self.capabilities,
            "reliability_score": self.reliability_score,
            "current_load": self.current_load,
        }


@dataclass
class TaskExecutionResult:
    """Represents the result of executing a task.

    Attributes:
        task: The task that was executed.
        worker: The worker that executed the task.
        success: Whether the task execution succeeded.
        result: The return value from the worker, if any.
        error: The exception raised during execution, if any.
        attempts: Number of execution attempts made for this task.
    """

    task: Task
    worker: Optional[Worker]
    success: bool
    result: Any
    error: Optional[BaseException]
    attempts: int


class TaskRouter:
    """Strategy for routing tasks to candidate workers."""

    def route(
        self,
        task: Task,
        workers: Sequence[Worker],
        learning_state: Mapping[str, Any],
    ) -> List[Worker]:
        """Select candidate workers for a given task.

        This implementation:
        - Filters workers by capability matching the task_type.
        - Applies optional routing bias from learning_state to prioritize workers.

        Args:
            task: The task to be routed.
            workers: Available workers.
            learning_state: Current learning-derived state.

        Returns:
            A list of candidate workers, ordered by preference.
        """
        capable_workers = [
            worker for worker in workers if task.task_type in worker.capabilities
        ]

        if not capable_workers:
            logger.warning(
                "No capable workers found for task_type=%s; using all workers as fallback.",
                task.task_type,
            )
            capable_workers = list(workers)

        routing_bias_raw = learning_state.get(LEARNING_KEY_TASK_ROUTING_BIAS, {})
        routing_bias: Dict[str, Dict[str, float]] = (
            routing_bias_raw if isinstance(routing_bias_raw, dict) else {}
        )

        task_bias = routing_bias.get(task.task_type, {})

        def worker_priority(worker: Worker) -> float:
            """Compute priority for a worker based on routing bias and load."""
            bias = float(task_bias.get(worker.worker_id, 0.0))
            # Lower load and higher bias preferred; subtract load as penalty.
            priority_score = bias - worker.current_load
            logger.debug(
                "Routing priority for worker=%s bias=%s load=%s score=%s",
                worker.worker_id,
                bias,
                worker.current_load,
                priority_score,
            )
            return priority_score

        sorted_workers = sorted(
            capable_workers,
            key=worker_priority,
            reverse=True,
        )

        logger.info(
            "Routed task_id=%s task_type=%s to %d candidate workers.",
            task.task_id,
            task.task_type,
            len(sorted_workers),
        )
        return sorted_workers


class WorkerSelector:
    """Strategy for selecting a single worker from candidate workers."""

    def select(
        self,
        task: Task,
        candidates: Sequence[Worker],
        learning_state: Mapping[str, Any],
    ) -> Worker:
        """Select a worker from candidates using learning-informed scores.

        Selection is based on:
        - Base reliability_score per worker.
        - Optional score adjustments from learning_state.
        - Current load (as a negative factor).

        Args:
            task: The task to be executed.
            candidates: Candidate workers for this task.
            learning_state: Current learning-derived state.

        Returns:
            The selected worker.

        Raises:
            ValueError: If no candidate workers are provided.
        """
        if not candidates:
            raise ValueError("No candidate workers available for selection.")

        adjustments_raw = learning_state.get(LEARNING_KEY_WORKER_SCORE_ADJUSTMENTS, {})
        adjustments: Dict[str, float] = (
            adjustments_raw if isinstance(adjustments_raw, dict) else {}
        )

        scored_candidates: List[Tuple[Worker, float]] = []
        for worker in candidates:
            adjustment = float(adjustments.get(worker.worker_id, 0.0))
            score = worker.reliability_score + adjustment - worker.current_load
            scored_candidates.append((worker, score))
            logger.debug(
                "Worker selection score for worker=%s base=%s adj=%s load=%s total=%s",
                worker.worker_id,
                worker.reliability_score,