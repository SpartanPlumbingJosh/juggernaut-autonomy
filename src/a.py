import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import socket
import json


# Constants
LOGGER_NAME: str = "task_verification"
DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS: float = 5.0
DEFAULT_HEALTHCHECK_METHOD: str = "GET"
HTTP_OK: int = 200


logger = logging.getLogger(LOGGER_NAME)


class TaskStatus(Enum):
    """Enumeration of task lifecycle statuses."""

    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED_VERIFICATION = auto()


class PullRequestStatus(Enum):
    """Enumeration of pull request statuses."""

    OPEN = auto()
    MERGED = auto()
    CLOSED = auto()


class VerificationStep(Enum):
    """Enumeration of verification steps in the completion chain."""

    PR_MERGED = auto()
    CI_PASSED = auto()
    DEPLOYMENT_SUCCEEDED = auto()
    HEALTHY = auto()


@dataclass
class VerificationFailure:
    """Represents a failure in a specific verification step.

    Attributes:
        step: The verification step that failed.
        message: Human-readable explanation of the failure.
        details: Optional structured details for debugging or UI display.
    """

    step: VerificationStep
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Represents the result of verifying a task's completion chain.

    Attributes:
        task_id: Identifier of the task that was verified.
        success: True if all verification steps passed, False otherwise.
        failures: List of verification failures. Empty if success is True.
    """

    task_id: str
    success: bool
    failures: List[VerificationFailure] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the verification result into a JSON-serializable dictionary.

        Returns:
            Dictionary representation of the verification result.
        """
        return {
            "task_id": self.task_id,
            "success": self.success,
            "failures": [
                {
                    "step": failure.step.name,
                    "message": failure.message,
                    "details": failure.details,
                }
                for failure in self.failures
            ],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "VerificationResult":
        """Create a VerificationResult from its dictionary representation.

        Args:
            data: Dictionary representation of a verification result.

        Returns:
            VerificationResult instance.
        """
        failures: List[VerificationFailure] = []
        for item in data.get("failures", []):
            failures.append(
                VerificationFailure(
                    step=VerificationStep[item["step"]],
                    message=item["message"],
                    details=item.get("details", {}),
                )
            )
        return VerificationResult(
            task_id=data["task_id"],
            success=data["success"],
            failures=failures,
        )


@dataclass
class PullRequest:
    """Represents a pull request in a source code repository.

    Attributes:
        number: Numeric identifier of the PR.
        repository: Repository name or slug.
        status: Current status of the PR.
    """

    number: int
    repository: str
    status: PullRequestStatus


@dataclass
class Task:
    """Represents a unit of work that must be verified before completion.

    Attributes:
        id: Unique identifier for the task.
        repository: Repository associated with the task's pull request.
        pr_number: Pull request number associated with this task.
        deployment_environment: Name of the target deployment environment.
        healthcheck_url: URL used to verify service health after deployment.
        status: Current status of the task in its lifecycle.
        last_verification: The last verification result for this task, if any.
    """

    id: str
    repository: str
    pr_number: int
    deployment_environment: str
    healthcheck_url: str
    status: TaskStatus = TaskStatus.PENDING
    last_verification: Optional[VerificationResult] = None


class ProviderError(Exception):
    """Base exception for provider-related failures."""


class TaskNotFoundError(Exception):
    """Raised when a task cannot be found in the repository."""


@runtime_checkable
class PullRequestProvider(Protocol):
    """Protocol for retrieving pull request information from a VCS provider."""

    def get_pull_request(self, repository: str, pr_number: int) -> PullRequest:
        """Fetch pull request metadata.

        Args:
            repository: Repository name or slug.
            pr_number: Pull request number.

        Returns:
            PullRequest instance.

        Raises:
            ProviderError: If the pull request cannot be retrieved.
        """
        ...


@runtime_checkable
class CIProvider(Protocol):
    """Protocol for querying CI status related to a pull request."""

    def have_checks_passed(self, repository: str, pr_number: int) -> Tuple[bool, str]:
        """Check whether all CI checks for the PR have passed.

        Args:
            repository: Repository name or slug.
            pr_number: Pull request number.

        Returns:
            Tuple where the first element indicates success, and the second
            element contains a human-readable summary or failure reason.

        Raises:
            ProviderError: If CI status cannot be determined.
        """
        ...


@runtime_checkable
class DeploymentProvider(Protocol):
    """Protocol for querying deployment status for a given build."""

    def is_deployment_successful(
        self, repository: str, pr_number: int, environment: str
    ) -> Tuple[bool, str]:
        """Check whether deployment for the PR to the environment succeeded.

        Args:
            repository: Repository name or slug.
            pr_number: Pull request number.
            environment: Target deployment environment name.

        Returns:
            Tuple where the first element indicates success, and the second
            element contains a human-readable summary or failure reason.

        Raises:
            ProviderError: If deployment status cannot be determined.
        """
        ...


@runtime_checkable
class HealthCheckProvider(Protocol):
    """Protocol for performing runtime health checks on deployed services."""

    def is_healthy(self, url: str) -> Tuple[bool, str]:
        """Check whether the service at the given URL is healthy.

        Args:
            url: Health check endpoint URL.

        Returns:
            Tuple where the first element indicates success, and the second
            element contains a human-readable summary or failure reason.

        Raises:
            ProviderError: If health status cannot be determined.
        """
        ...


@runtime_checkable
class TaskRepository(Protocol):
    """Protocol for storing and retrieving tasks and their verification status."""

    def add_task(self, task: Task) -> None:
        """Add a new task to the repository.

        Args:
            task: Task to add.

        Raises:
            ValueError: If a task with the same id already exists.
        """
        ...

    def get_task(self, task_id: str) -> Task:
        """Retrieve a task by its identifier.

        Args:
            task_id: Identifier of the task.

        Returns:
            Task instance.

        Raises:
            TaskNotFoundError: If the task does not exist.
        """
        ...

    def update_task(self, task: Task) -> None:
        """Persist changes to a task.

        Args:
            task: Task instance with updated fields.

        Raises:
            TaskNotFoundError: If the task does not exist.
        """
        ...


class InMemoryTaskRepository(TaskRepository):
    """In-memory implementation of TaskRepository for simple deployments and tests."""

    def __init__(self) -> None:
        """Initialize an empty in-memory task store."""
        self._tasks: Dict[str, Task] = {}

    def add_task(self, task: Task) -> None:
        """Add a new task to the repository.

        Args:
            task: Task to add.

        Raises:
            ValueError: If a task with the same id already exists.
        """
        if task.id in self._tasks:
            raise ValueError(f"Task with id '{task.id}' already exists")
        self._tasks[task.id] = task
        logger.debug("Task added: %s", task)

    def get_task(self, task_id: str) -> Task:
        """Retrieve a task by its identifier.

        Args:
            task_id: Identifier of the task.

        Returns:
            Task instance.

        Raises:
            TaskNotFoundError: If the task does not exist.
        """
        try:
            task = self._tasks[task_id]
            logger.debug("Task retrieved: %s", task)
            return task
        except KeyError as exc:
            logger.error("Task not found: %s", task_id)
            raise TaskNotFoundError(f"Task with id '{task_id}' not found") from exc

    def update_task(self, task: Task) -> None:
        """Persist changes to a task.

        Args:
            task: Task instance with updated fields.

        Raises:
            TaskNotFoundError: If the task does not exist.
        """
        if task.id not in self._tasks:
            logger.error("Attempted to update non-existent task: %s", task.id)
            raise TaskNotFoundError(f"Task with id '{task.id}' not found")
        self._tasks[task.id] = task
        logger.debug("Task updated: %s", task)


class DummyPullRequestProvider(PullRequestProvider):
    """Simple in-memory PR provider for demonstration and testing.

    The provider maintains a mapping from (repository, pr_number) to PR status.
    """

    def __init__(self, prs: Dict[Tuple[str, int], PullRequestStatus]) -> None:
        """Initialize the provider with predefined PR statuses.

        Args:
            prs: Mapping from (repository, pr_number) to pull request status.
        """
        self._prs = prs

    def get_pull_request(self, repository: str, pr_number: int) -> PullRequest:
        """Fetch pull request metadata from the in-memory store.

        Args:
            repository: Repository name or slug.
            pr_number: Pull request number.

        Returns:
            PullRequest instance.

        Raises:
            ProviderError: If the PR is unknown.
        """
        key = (repository, pr_number)
        if key not in self._prs:
            logger.error("Pull request not found: %s #%s", repository, pr_number)
            raise ProviderError(f"Pull request {repository}#{pr_number} not found")
        status = self._prs[key]
        pr = PullRequest(number=pr_number, repository=repository,