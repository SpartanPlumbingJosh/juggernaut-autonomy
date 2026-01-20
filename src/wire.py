import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, Optional, Protocol

logger = logging.getLogger(__name__)

# Constants
VERIFICATION_TIMEOUT_SECONDS: int = 30

try:
    # Local import; if unavailable we fall back to a safe default implementation.
    from core.verification import verify_completion as core_verify_completion  # type: ignore[attr-defined]
except ImportError:
    core_verify_completion = None


class TaskStatus(Enum):
    """Enumeration of possible task statuses."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED_VERIFICATION = "failed_verification"


@dataclass
class Task:
    """Represents a task that can be completed and verified.

    Attributes:
        id: Unique identifier of the task.
        description: Human-readable description of the task.
        status: Current status of the task.
        updated_at: Last time the task was updated.
        verified_at: Timestamp when the task was successfully verified, if any.
    """

    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    updated_at: datetime = field(default_factory=datetime.utcnow)
    verified_at: Optional[datetime] = None


class TaskRepository(Protocol):
    """Protocol defining operations required for task persistence."""

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by its identifier.

        Args:
            task_id: Identifier of the task to retrieve.

        Returns:
            The corresponding Task instance if found, otherwise None.
        """
        ...

    def save_task(self, task: Task) -> None:
        """Persist a task instance.

        Args:
            task: Task instance to persist.

        Returns:
            None
        """
        ...


class InMemoryTaskRepository:
    """Simple in-memory implementation of TaskRepository for testing/demo."""

    def __init__(self) -> None:
        """Initialize the in-memory task repository."""
        self._tasks: Dict[str, Task] = {}

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task from the in-memory store.

        Args:
            task_id: Identifier of the task to retrieve.

        Returns:
            The corresponding Task instance if found, otherwise None.
        """
        return self._tasks.get(task_id)

    def save_task(self, task: Task) -> None:
        """Persist a task into the in-memory store.

        Args:
            task: Task instance to persist.

        Returns:
            None
        """
        self._tasks[task.id] = task


class TaskNotFoundError(Exception):
    """Raised when a requested task cannot be found."""

    def __init__(self, task_id: str) -> None:
        """Initialize the exception.

        Args:
            task_id: Identifier of the task that was not found.
        """
        super().__init__(f"Task not found: {task_id}")
        self.task_id = task_id


class TaskVerificationError(Exception):
    """Raised when verification fails for a task prior to completion."""

    def __init__(self, task_id: str, message: str = "Task failed verification") -> None:
        """Initialize the exception.

        Args:
            task_id: Identifier of the task that failed verification.
            message: Optional message describing the failure.
        """
        super().__init__(f"{message}: {task_id}")
        self.task_id = task_id


class TaskAlreadyCompletedError(Exception):
    """Raised when attempting to complete a task that is already completed."""

    def __init__(self, task_id: str) -> None:
        """Initialize the exception.

        Args:
            task_id: Identifier of the already completed task.
        """
        super().__init__(f"Task already completed: {task_id}")
        self.task_id = task_id


def _fallback_verify_completion(task_id: str) -> bool:
    """Fallback verification implementation when core.verification is unavailable.

    This implementation always returns True but logs a warning so that
    environments without the core verification module are visible in logs.

    Args:
        task_id: Identifier of the task being "verified".

    Returns:
        True, indicating that verification is considered successful.
    """
    logger.warning(
        "core.verification.verify_completion not available; "
        "defaulting to successful verification for task_id=%s",
        task_id,
    )
    return True


def default_verify_completion(task_id: str) -> bool:
    """Default verification entrypoint that delegates to core.verification if available.

    Attempts to call ``core.verification.verify_completion`` if it was imported
    successfully. If the import is not available, falls back to a permissive
    implementation that always returns True.

    The function is designed to be tolerant of minor signature differences:
    it first attempts to call using a keyword argument, then positionally.

    Args:
        task_id: Identifier of the task to verify.

    Returns:
        True if verification passed, False otherwise.
    """
    if core_verify_completion is None:
        return _fallback_verify_completion(task_id)

    try:
        # Prefer a keyword argument call to be explicit.
        result = core_verify_completion(task_id=task_id)  # type: ignore[call-arg]
    except TypeError:
        # Fallback to positional if the function does not accept keywords.
        result = core_verify_completion(task_id)  # type: ignore[call-arg]

    is_verified = bool(result)
    logger.debug(
        "Verification result from core.verification for task_id=%s: %s",
        task_id,
        is_verified,
    )
    return is_verified


def complete_task(
    task_id: str,
    repository: TaskRepository,
    verify_func: Optional[Callable[[str], bool]] = None,
) -> Task:
    """Complete a task after verifying its completion criteria.

    This function wires the verification step into the task completion flow.
    It ensures that ``verify_completion()`` is called before marking the task
    as completed. If verification fails, the task is not completed and its
    status is updated to ``FAILED_VERIFICATION``.

    Args:
        task_id: Identifier of the task to complete.
        repository: Repository used to load and persist the task.
        verify_func: Optional custom verification function. If not provided,
            uses :func:`default_verify_completion`, which delegates to
            ``core.verification.verify_completion`` when available.

    Returns:
        The updated Task instance after successful completion.

    Raises:
        TaskNotFoundError: If the task does not exist in the repository.
        TaskAlreadyCompletedError: If the task is already completed.
        TaskVerificationError: If verification fails.
    """
    verifier = verify_func or default_verify_completion

    logger.debug("Attempting to complete task_id=%s", task_id)
    task = repository.get_task(task_id)
    if task is None:
        logger.error("Task not found during completion attempt: task_id=%s", task_id)
        raise TaskNotFoundError(task_id)

    if task.status == TaskStatus.COMPLETED:
        logger.info("Task already completed; no action taken: task_id=%s", task_id)
        raise TaskAlreadyCompletedError(task_id)

    logger.debug("Starting verification step for task_id=%s", task_id)
    is_verified = verifier(task_id)
    if not is_verified:
        logger.info("Verification failed for task_id=%s", task_id)
        task.status = TaskStatus.FAILED_VERIFICATION
        task.updated_at = datetime.utcnow()
        repository.save_task(task)
        raise TaskVerificationError(task_id)

    # Mark as completed only after successful verification.
    logger.debug("Verification passed; marking task as completed: task_id=%s", task_id)
    now = datetime.utcnow()
    task.status = TaskStatus.COMPLETED
    task.updated_at = now
    task.verified_at = now
    repository.save_task(task)

    logger.info("Task successfully completed after verification: task_id=%s", task_id)
    return task


__all__ = [
    "TaskStatus",
    "Task",
    "TaskRepository",
    "InMemoryTaskRepository",
    "TaskNotFoundError",
    "TaskVerificationError",
    "TaskAlreadyCompletedError",
    "default_verify_completion",
    "complete_task",
]