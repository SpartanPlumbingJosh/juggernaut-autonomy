import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


# Constants
DEFAULT_TOTAL_TIME_BUDGET: float = 300.0  # seconds
MIN_TASK_TIME: float = 1.0  # seconds
MAX_TASK_TIME: float = 120.0  # seconds

PRIORITY_WEIGHT: float = 2.0
COMPLEXITY_WEIGHT: float = 1.0

CRITICAL_PRIORITY_MULTIPLIER: float = 2.0
HIGH_PRIORITY_MULTIPLIER: float = 1.5
MEDIUM_PRIORITY_MULTIPLIER: float = 1.0
LOW_PRIORITY_MULTIPLIER: float = 0.7

SMALL_EPSILON: float = 1e-9


# Logging configuration
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Priority(Enum):
    """Task priority levels for resource allocation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TaskSpec:
    """Specification for a single task requiring a time budget.

    Attributes:
        task_id: Unique identifier for the task.
        priority: Priority level of the task.
        estimated_complexity: Relative complexity (e.g., 1.0 simple, 10.0 very complex).
        min_time: Minimum allowable time budget for the task.
        max_time: Maximum allowable time budget for the task.
    """

    task_id: str
    priority: Priority
    estimated_complexity: float
    min_time: float = MIN_TASK_TIME
    max_time: float = MAX_TASK_TIME


class ResourceAllocationError(Exception):
    """Domain-specific exception for resource allocation errors."""


class ResourceAllocator:
    """Allocator that computes dynamic time budgets for tasks.

    The allocator distributes a global time budget across multiple tasks
    based on priority and estimated complexity, enforcing per-task min/max
    constraints.
    """

    def __init__(self, total_time_budget: float) -> None:
        """Initialize the resource allocator.

        Args:
            total_time_budget: Total time budget in seconds to be allocated.

        Raises:
            ValueError: If total_time_budget is non-positive.
        """
        if total_time_budget <= 0:
            raise ValueError("Total time budget must be positive.")
        self.total_time_budget = total_time_budget

    def _priority_multiplier(self, priority: Priority) -> float:
        """Get weighting multiplier for a given priority.

        Args:
            priority: Task priority.

        Returns:
            Multiplier used to scale the task weight.
        """
        if priority == Priority.CRITICAL:
            return CRITICAL_PRIORITY_MULTIPLIER
        if priority == Priority.HIGH:
            return HIGH_PRIORITY_MULTIPLIER
        if priority == Priority.MEDIUM:
            return MEDIUM_PRIORITY_MULTIPLIER
        return LOW_PRIORITY_MULTIPLIER

    def _compute_weights(self, tasks: List[TaskSpec]) -> Dict[str, float]:
        """Compute relative allocation weights for each task.

        Args:
            tasks: List of task specifications.

        Returns:
            Mapping of task_id to computed weight.
        """
        weights: Dict[str, float] = {}
        for task in tasks:
            priority_component = PRIORITY_WEIGHT * self._priority_multiplier(task.priority)
            complexity_component = COMPLEXITY_WEIGHT * max(task.estimated_complexity, SMALL_EPSILON)
            weight = priority_component * complexity_component
            weights[task.task_id] = max(weight, SMALL_EPSILON)
        return weights

    def allocate(self, tasks: List[TaskSpec]) -> Dict[str, float]:
        """Allocate time budgets dynamically across tasks.

        Args:
            tasks: List of task specifications to allocate time for.

        Returns:
            Mapping of task_id to allocated time in seconds.

        Raises:
            ResourceAllocationError: If constraints cannot be satisfied.
            ValueError: If tasks list is empty.
        """
        if not tasks:
            raise ValueError("At least one task is required for allocation.")

        logger.debug("Starting allocation for %d tasks with total budget %.3f", len(tasks), self.total_time_budget)

        min_time_sum = sum(task.min_time for task in tasks)
        if min_time_sum > self.total_time_budget:
            message = (
                "Total minimum time requirements exceed available budget: "
                f"required={min_time_sum:.3f}, available={self.total_time_budget:.3f}"
            )
            logger.error(message)
            raise ResourceAllocationError(message)

        # Reserve the minimum time for each task first
        remaining_budget = self.total_time_budget - min_time_sum
        logger.debug("Reserved minimum times (%.3f), remaining budget: %.3f", min_time_sum, remaining_budget)

        weights = self._compute_weights(tasks)
        total_weight = sum(weights.values())
        if total_weight <= SMALL_EPSILON:
            # In pathological case, distribute remaining budget evenly
            logger.warning("Total weight is extremely small; distributing remaining budget evenly.")
            even_share = remaining_budget / len(tasks) if tasks else 0.0
            return {task.task_id: task.min_time + even_share for task in tasks}

        # Initial allocation proportional to weights
        allocations: Dict[str, float] = {}
        for task in tasks:
            extra_share = remaining_budget * (weights[task.task_id] / total_weight)
            allocated = task.min_time + extra_share
            clamped = max(task.min_time, min(allocated, task.max_time))
            allocations[task.task_id] = clamped
            logger.debug(
                "Task %s: weight=%.3f, extra_share=%.3f, raw_alloc=%.3f, clamped_alloc=%.3f",
                task.task_id,
                weights[task.task_id],
                extra_share,
                allocated,
                clamped,
            )

        # Check if clamping caused unused budget, and redistribute if significant
        used_budget = sum(allocations.values())
        unallocated_budget = self.total_time_budget - used_budget
        logger.debug("Initial allocations used %.3f of %.3f (unallocated: %.3f)", used_budget, self.total_time_budget, unallocated_budget)

        if unallocated_budget > SMALL_EPSILON:
            # Redistribute remaining budget among tasks that are not at max_time
            adjustable_tasks = [task for task in tasks if allocations[task.task_id] < task.max_time - SMALL_EPSILON]
            if adjustable_tasks:
                logger.debug(
                    "Redistributing %.3f additional budget among %d adjustable tasks",
                    unallocated_budget,
                    len(adjustable_tasks),
                )
                adjustable_weights = {t.task_id: weights[t.task_id] for t in adjustable_tasks}
                adjustable_total_weight = sum(adjustable_weights.values())
                if adjustable_total_weight <= SMALL_EPSILON:
                    even_extra = unallocated_budget / len(adjustable_tasks)
                    for t in adjustable_tasks:
                        allocations[t.task_id] = min(allocations[t.task_id] + even_extra, t.max_time)
                else:
                    for t in adjustable_tasks:
                        extra = unallocated_budget * (adjustable_weights[t.task_id] / adjustable_total_weight)
                        allocations[t.task_id] = min(allocations[t.task_id] + extra, t.max_time)

        final_total = sum(allocations.values())
        logger.info(
            "Resource allocation completed. Allocated %.3f seconds out of %.3f available.",
            final_total,
            self.total_time_budget,
        )

        return allocations


def allocate_resources(tasks: List[TaskSpec], total_time_budget: float) -> Dict[str, float]:
    """Public API for dynamic time-budget allocation.

    This function should be used by the system wherever time budgets for
    tasks need to be determined dynamically, replacing any hardcoded
    allocation decisions.

    Args:
        tasks: List of task specifications for which to allocate resources.
        total_time_budget: Total time budget in seconds to be distributed
            across all tasks.

    Returns:
        Mapping of task_id to allocated time in seconds.

    Raises:
        ResourceAllocationError: If allocation constraints cannot be satisfied.
        ValueError: If invalid parameters are provided.
    """
    allocator = ResourceAllocator(total_time_budget=total_time_budget)
    return allocator.allocate(tasks)


def _configure_root_logger() -> None:
    """Configure the root logger if it has no handlers.

    This ensures that logging output is visible when this module is executed
    as a script, but does not interfere with applications that configure
    logging on their own.
    """
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)


def main() -> None:
    """Example entrypoint demonstrating dynamic resource allocation.

    This function is purely illustrative and can be removed or adapted
    when integrating into the larger system.
    """
    _configure_root_logger()

    example_tasks = [
        TaskSpec(task_id="planning", priority=Priority.CRITICAL, estimated_complexity=8.0),
        TaskSpec(task_id="analysis", priority=Priority.HIGH, estimated_complexity=6.0),
        TaskSpec(task_id="retrieval", priority=Priority.MEDIUM, estimated_complexity=3.0),
        TaskSpec(task_id="logging", priority=Priority.LOW, estimated_complexity=1.0, max_time=20.0),
    ]

    total_budget = DEFAULT_TOTAL_TIME_BUDGET

    try:
        allocations = allocate_resources(example_tasks, total_budget)
    except (ResourceAllocationError, ValueError) as exc:
        logger.error("Failed to allocate resources: %s", exc)
        return

    for task in example_tasks:
        allocated_time = allocations.get(task.task_id, 0.0)
        logger.info(
            "Task '%s' (priority=%s, complexity=%.2f): allocated %.3f seconds",
            task.task_id,
            task.priority.value,
            task.estimated_complexity,
            allocated_time,
        )


if __name__ == "__main__":
    main()