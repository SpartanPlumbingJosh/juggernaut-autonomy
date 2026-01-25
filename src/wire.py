import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:
    from core.conflict_manager import ConflictManager as ConflictManager  # type: ignore
except Exception:  # pragma: no cover
    ConflictManager = Any  # type: ignore

# Constants
DEFAULT_MAX_CONCURRENT_TASKS: int = 8
DEFAULT_LOG_LEVEL: int = logging.INFO

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """Represents a unit of work assigned to an agent.

    Attributes:
        task_id: Unique identifier of the task.
        agent_id: Identifier of the agent responsible for the task.
        payload: Arbitrary data representing the task specifics.
        priority: Priority of the task; lower numbers can represent higher priority.
        resources: Collection of resource identifiers the task needs.
    """

    task_id: str
    agent_id: str
    payload: Dict[str, Any]
    priority: int = 0
    resources: Sequence[str] = field(default_factory=list)


@dataclass
class TaskResult:
    """Represents the result of an executed task.

    Attributes:
        task_id: Identifier of the completed task.
        agent_id: Identifier of the agent that executed the task.
        success: Whether the task completed successfully.
        result: Optional payload with the result of the task.
        error: Optional error message if execution failed.
    """

    task_id: str
    agent_id: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MultiAgentExecutor:
    """Executes tasks for multiple agents with L5 conflict detection and resolution.

    This executor integrates with the `core.conflict_manager.ConflictManager`
    to provide Level 5 multi-agent conflict detection and resolution before
    executing tasks.
    """

    def __init__(
        self,
        conflict_manager: Optional[Any] = None,
        max_concurrent_tasks: int = DEFAULT_MAX_CONCURRENT_TASKS,
    ) -> None:
        """Initializes the multi-agent executor.

        Args:
            conflict_manager: Optional externally provided ConflictManager instance.
                If not provided, a new instance is created.
            max_concurrent_tasks: Maximum number of tasks to execute concurrently.
        """
        self.conflict_manager: Optional[Any] = conflict_manager
        self.max_concurrent_tasks: int = max_concurrent_tasks
        logger.debug(
            "MultiAgentExecutor initialized with max_concurrent_tasks=%d",
            self.max_concurrent_tasks,
        )

    def _apply_conflict_resolution(self, tasks: Sequence[Task]) -> List[Task]:
        """Detects and resolves conflicts among a collection of tasks.

        This method wires into the `core.conflict_manager.ConflictManager`
        by calling its conflict detection and resolution methods. It is
        intentionally defensive to support different underlying implementations
        of the conflict manager.

        The expected API of ConflictManager is one of:
          - detect_conflicts(tasks) -> conflicts
            resolve_conflicts(conflicts, tasks) -> resolved_tasks
          - detect_and_resolve_conflicts(tasks) -> resolved_tasks

        Args:
            tasks: Collection of tasks to analyze.

        Returns:
            A list of tasks after conflict resolution.
        """
        task_list: List[Task] = list(tasks)

        if self.conflict_manager is None:
            return task_list

        logger.debug("Starting conflict detection for %d tasks", len(tasks))

        try:
            # Preferred combined API: detect_and_resolve_conflicts
            if hasattr(self.conflict_manager, "detect_and_resolve_conflicts"):
                logger.debug(
                    "Using ConflictManager.detect_and_resolve_conflicts API for conflict handling"
                )
                resolved_tasks: Any = self.conflict_manager.detect_and_resolve_conflicts(
                    task_list
                )  # type: ignore[attr-defined]
                resolved_list: List[Task] = list(resolved_tasks)
                logger.info(
                    "Conflict detection and resolution completed; %d tasks after resolution",
                    len(resolved_list),
                )
                return resolved_list

            conflicts: Any = None
            resolved: Any = None

            # Fallback: separate detect_conflicts and resolve_conflicts APIs
            if hasattr(self.conflict_manager, "detect_conflicts"):
                logger.debug("Using ConflictManager.detect_conflicts API")
                conflicts = self.conflict_manager.detect_conflicts(
                    task_list
                )  # type: ignore[attr-defined]
                logger.info("Detected %d conflicts", len(conflicts) if conflicts is not None else 0)
            else:
                logger.warning(
                    "ConflictManager has no 'detect_conflicts' method; skipping detection"
                )

            if conflicts and hasattr(self.conflict_manager, "resolve_conflicts"):
                logger.debug("Using ConflictManager.resolve_conflicts API")
                resolved = self.conflict_manager.resolve_conflicts(
                    conflicts, task_list
                )  # type: ignore[attr-defined]
                resolved_list = list(resolved)
                logger.info(
                    "Conflict resolution completed; %d tasks after resolution",
                    len(resolved_list),
                )
                return resolved_list

            if conflicts and not hasattr(self.conflict_manager, "resolve_conflicts"):
                logger.warning(
                    "Conflicts were detected but ConflictManager has no "
                    "'resolve_conflicts' method; continuing with original tasks"
                )

        except (TypeError, ValueError, RuntimeError) as exc:
            logger.exception("Conflict resolution failed due to an error: %s", exc)
            # In case of any error, fall back to original tasks.
            return task_list

        logger.debug(
            "No conflict resolution API used; proceeding with %d original tasks",
            len(task_list),
        )
        return task_list

    def execute_task(self, task: Task) -> TaskResult:
        """Executes a single task.

        In a production system, this would dispatch work to the appropriate agent.
        Here, it simulates execution with logging.

        Args:
            task: Task to execute.

        Returns:
            TaskResult describing the outcome of the execution.
        """
        logger.debug(
            "Executing task %s for agent %s with priority %d",
            task.task_id,
            task.agent_id,
            task.priority,
        )
        try:
            # Placeholder for real execution logic.
            simulated_result: Dict[str, Any] = {
                "echo_payload": task.payload,
                "resources_used": list(task.resources),
            }
            logger.info(
                "Task %s executed successfully for agent %s",
                task.task_id,
                task.agent_id,
            )
            return TaskResult(
                task_id=task.task_id,
                agent_id=task.agent_id,
                success=True,
                result=simulated_result,
            )
        except (RuntimeError, ValueError) as exc:
            logger.exception(
                "Task %s execution failed for agent %s: %s",
                task.task_id,
                task.agent_id,
                exc,
            )
            return TaskResult(
                task_id=task.task_id,
                agent_id=task.agent_id,
                success=False,
                error=str(exc),
            )

    def run_multi_agent_tasks(self, tasks: Iterable[Task]) -> List[TaskResult]:
        """Runs a collection of tasks across multiple agents with L5 conflict handling.

        This method performs:
          1. Conflict detection and resolution using ConflictManager.
          2. Concurrent execution of the resulting, conflict-free task set.

        Args:
            tasks: Iterable of tasks to run.

        Returns:
            List of TaskResult for each completed task.
        """
        original_tasks: List[Task] = list(tasks)
        logger.info(
            "Starting multi-agent execution for %d tasks (pre-resolution)",
            len(original_tasks),
        )

        # Step 1: Detect and resolve conflicts with the ConflictManager.
        resolved_tasks: List[Task] = self._apply_conflict_resolution(original_tasks)

        # Step 2: Execute resolved tasks concurrently using ThreadPoolExecutor.
        results: List[TaskResult] = []
        with ThreadPoolExecutor(max_workers=self.max_concurrent_tasks) as executor:
            future_to_task = {
                executor.submit(self.execute_task, task): task
                for task in resolved_tasks
            }
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    logger.exception(
                        "Task %s raised an exception: %s", task.task_id, exc
                    )
                    results.append(
                        TaskResult(
                            task_id=task.task_id,
                            agent_id=task.agent_id,
                            success=False,
                            error=str(exc),
                        )
                    )

        logger.info(
            "Multi-agent execution finished; %d results produced", len(results)
        )
        return results


def configure_logging(level: int = DEFAULT_LOG_LEVEL) -> None:
    """Configures logging for the application.

    Args:
        level: Logging level to use for the root logger.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    logger.debug("Logging configured with level %s", logging.getLevelName(level))


def main() -> None:
    """Entry point for running a sample multi-agent execution with conflict handling.

    This demonstrates wiring the `core.conflict_manager.ConflictManager`
    into the main execution path to enable L5 multi-agent conflict resolution.
    """
    configure_logging()

    # Create a sample set of tasks for multiple agents.
    sample_tasks: List[Task] = [
        Task(
            task_id="task-1",
            agent_id="agent-A",
            payload={"operation": "read", "target": "resource-1"},
            priority=1,
            resources=["resource-1"],
        ),
        Task(
            task_id="task-2",
            agent_id="agent-B",
            payload={"operation": "write", "target": "resource-1"},
            priority=0,
            resources=["resource-1"],
        ),
        Task(
            task_id="task-3",
            agent_id="agent-C",
            payload={"operation": "compute", "target": "resource-2"},
            priority=2,
            resources=["resource-2"],
        ),
    ]

    executor = MultiAgentExecutor()
    results: List[TaskResult] = executor.run_multi_agent_tasks(sample_tasks)

    # Results are available for further processing; we only log summaries here.
    for result in results:
        if result.success:
            logger.info(
                "Result - task_id=%s agent_id=%s success=%s",
                result.task_id,
                result.agent_id,
                result.success,
            )
        else:
            logger.warning(
                "Result - task_id=%s agent_id=%s success=%s error=%s",
                result.task_id,
                result.agent_id,
                result.success,
                result.error,
            )


if __name__ == "__main__":
    main()
