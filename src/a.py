from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# Constants
HEALTHCHECK_DEFAULT_TIMEOUT_SECONDS: float = 5.0
LOG_SNIPPET_MAX_LENGTH: int = 500


logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Represents the lifecycle state of a task."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"


class VerificationStep(str, Enum):
    """Represents the individual steps in the verification chain."""

    PR_MERGED = "PR_MERGED"
    CI_CHECKS = "CI_CHECKS"
    DEPLOYMENT = "DEPLOYMENT"
    HEALTH_CHECK = "HEALTH_CHECK"


@dataclass
class Task:
    """Domain entity representing a unit of work that must be verified.

    Attributes:
        task_id: Unique identifier for the task.
        repository: Full name of the repository (e.g., "org/repo").
        pull_request_number: Associated pull request number.
        service_name: Name of the deployed service (for deployment checks).
        healthcheck_url: URL used to perform the runtime health check.
        status: Current status of the task.
        last_verification_evidence: Evidence data from the last verification attempt.
        last_verification_failures: List of failures from the last verification attempt.
    """

    task_id: str
    repository: str
    pull_request_number: int
    service_name: str
    healthcheck_url: str
    status: TaskStatus = TaskStatus.PENDING
    last_verification_evidence: Dict[str, Any] = field(default_factory=dict)
    last_verification_failures: List["VerificationFailure"] = field(default_factory=list)


@dataclass
class PullRequestInfo:
    """Represents essential information about a pull request.

    Attributes:
        number: Pull request number.
        is_merged: Whether the PR has been merged.
        state: Current state of the PR (e.g., 'open', 'closed', 'merged').
        url: URL to the pull request.
    """

    number: int
    is_merged: bool
    state: str
    url: str


@dataclass
class CICheckResult:
    """Represents the CI status associated with a pull request.

    Attributes:
        all_passed: Whether all CI checks have passed.
        failing_checks: Names of failing checks, if any.
        raw_status: Raw status payload or summary for evidence.
    """

    all_passed: bool
    failing_checks: List[str]
    raw_status: Dict[str, Any]


@dataclass
class DeploymentStatus:
    """Represents the status of the latest deployment of a service.

    Attributes:
        service_name: Name of the deployed service.
        success: Whether the latest deployment succeeded.
        provider: Name of the deployment provider (e.g., 'Railway', 'Vercel').
        logs_snippet: Tail of deploy logs for evidence/diagnostics.
    """

    service_name: str
    success: bool
    provider: str
    logs_snippet: str


@dataclass
class HealthCheckStatus:
    """Represents the outcome of a service health check.

    Attributes:
        is_healthy: Whether the service responded as healthy.
        status_code: HTTP status code, if available.
        error_message: Error description if the check failed.
    """

    is_healthy: bool
    status_code: Optional[int]
    error_message: Optional[str]


@dataclass
class VerificationFailure:
    """Represents a specific failure in the verification chain.

    Attributes:
        step: Which verification step failed.
        reason: Human-readable short reason for the failure.
        details: Optional additional structured data.
    """

    step: VerificationStep
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Represents the aggregate result of verifying a task.

    Attributes:
        task_id: Identifier of the verified task.
        success: Whether the task passed all verification steps.
        failures: List of failures; empty if success is True.
        evidence: Collected evidence across all steps.
    """

    task_id: str
    success: bool
    failures: List[VerificationFailure]
    evidence: Dict[str, Any]


class TaskVerificationError(Exception):
    """Base exception for task verification related errors."""


class TaskNotFoundError(TaskVerificationError):
    """Raised when a requested task cannot be found."""

    def __init__(self, task_id: str) -> None:
        """Initialize the exception.

        Args:
            task_id: Identifier of the task that was not found.
        """
        super().__init__(f"Task with id '{task_id}' not found")
        self.task_id = task_id


class ExternalServiceError(TaskVerificationError):
    """Raised when an external service cannot be queried properly."""

    def __init__(self, service_name: str, original_exception: Exception) -> None:
        """Initialize the exception.

        Args:
            service_name: Name of the external service.
            original_exception: The underlying exception.
        """
        message = f"Error while communicating with external service '{service_name}': {original_exception}"
        super().__init__(message)
        self.service_name = service_name
        self.original_exception = original_exception


class PullRequestService:
    """Abstract interface for retrieving pull request information."""

    def get_pull_request(self, repository: str, pr_number: int) -> Optional[PullRequestInfo]:
        """Retrieve PR information.

        Args:
            repository: Repository full name (e.g., 'org/repo').
            pr_number: Pull request number.

        Returns:
            PullRequestInfo if found, otherwise None.

        Raises:
            ExternalServiceError: If the underlying service call fails.
        """
        raise NotImplementedError


class CIService:
    """Abstract interface for retrieving CI results."""

    def get_ci_result(self, repository: str, pr_number: int) -> Optional[CICheckResult]:
        """Retrieve the CI status for a particular PR.

        Args:
            repository: Repository full name (e.g., 'org/repo').
            pr_number: Pull request number.

        Returns:
            CICheckResult if CI information is available, otherwise None.

        Raises:
            ExternalServiceError: If the underlying service call fails.
        """
        raise NotImplementedError


class DeploymentService:
    """Abstract interface for retrieving deployment status."""

    def get_latest_deployment_status(self, service_name: str) -> Optional[DeploymentStatus]:
        """Retrieve the latest deployment status for a service.

        Args:
            service_name: Name of the deployed service.

        Returns:
            DeploymentStatus if available, otherwise None.

        Raises:
            ExternalServiceError: If the underlying service call fails.
        """
        raise NotImplementedError


class HealthCheckService:
    """Abstract interface for performing health checks on services."""

    def run_health_check(self, url: str, timeout_seconds: float) -> HealthCheckStatus:
        """Perform a health check against the target URL.

        Args:
            url: URL to check.
            timeout_seconds: Maximum time to wait for a response.

        Returns:
            HealthCheckStatus describing the outcome.

        Raises:
            ExternalServiceError: If the underlying service call fails.
        """
        raise NotImplementedError


class TaskRepository:
    """Abstract interface for persisting and retrieving tasks."""

    def get_task(self, task_id: str) -> Task:
        """Retrieve a task by its identifier.

        Args:
            task_id: Identifier of the task.

        Returns:
            The corresponding Task instance.

        Raises:
            TaskNotFoundError: If the task cannot be found.
        """
        raise NotImplementedError

    def save_task(self, task: Task) -> None:
        """Persist updates to a task.

        Args:
            task: The task instance to persist.
        """
        raise NotImplementedError


class InMemoryTaskRepository(TaskRepository):
    """In-memory implementation of the TaskRepository for demonstration/testing."""

    def __init__(self) -> None:
        """Initialize the repository."""
        self._tasks: Dict[str, Task] = {}

    def add_task(self, task: Task) -> None:
        """Add a new task into the repository.

        Args:
            task: Task to be added.
        """
        logger.debug("Adding task to repository: %s", task)
        self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Task:
        """Retrieve a task from the in-memory store.

        Args:
            task_id: Identifier of the task.

        Returns:
            Task associated with the given identifier.

        Raises:
            TaskNotFoundError: If the task does not exist.
        """
        try:
            task = self._tasks[task_id]
            logger.debug("Retrieved task '%s' from repository", task_id)
            return task
        except KeyError as exc:
            logger.warning("Task '%s' not found in repository", task_id)
            raise TaskNotFoundError(task_id) from exc

    def save_task(self, task: Task) -> None:
        """Persist a task in the in-memory store.

        Args:
            task: Task instance to persist.
        """
        logger.debug("Saving task '%s' with status '%s'", task.task_id, task.status)
        self._tasks[task.task_id] = task


class FakePullRequestService(PullRequestService):
    """Fake pull request service using in-memory data for demonstration."""

    def __init__(self, prs: Dict[Tuple[str, int], PullRequestInfo]) -> None:
        """Initialize the service.

        Args:
            prs: Mapping from (repository, pr_number) to PullRequestInfo.
        """
        self._prs = prs

    def get_pull_request(self, repository: str, pr_number: int) -> Optional[PullRequestInfo]:
        """Retrieve PR information from the in-memory map.

        Args:
            repository: Repository name.
            pr_number: Pull request number.

        Returns:
            PullRequestInfo if found, otherwise None.
        """
        key = (repository, pr_number)
        pr = self._prs.get(key)
        logger.debug("Queried PR for %s#%s: %s", repository, pr_number, pr)
        return pr


class FakeCIService(CIService):
    """Fake CI service that uses in-memory data."""

    def __init__(self, results: Dict[Tuple[str, int], CICheckResult]) -> None:
        """Initialize the service.

        Args:
            results: Mapping from (repository, pr_number) to CICheckResult.
        """
        self._results = results

    def get_ci_result(self, repository: str, pr_number: int) -> Optional[CICheckResult]:
        """Retrieve CI result from the in-memory map.

        Args:
            repository: Repository name.
            pr_number: Pull request number.

        Returns:
            CICheckResult if found, otherwise None.
        """
        key = (repository, pr_number)
        result = self._results.get(key)
        logger.debug("Queried CI result for %s#%s: %s", repository, pr_number, result)
        return result


class FakeDeploymentService(DeploymentService):
    """Fake deployment service that uses in-memory data."""

    def __init__(self, statuses: Dict[str, DeploymentStatus]) -> None:
        """Initialize the service.

        Args:
            statuses: Mapping from service_name to DeploymentStatus.
        """
        self._statuses = statuses

    def get_latest_deployment_status(self, service_name: str) -> Optional[DeploymentStatus]:
        """Retrieve the deployment status from the in-memory map.

        Args:
            service_name: Name of the deployed service.

        Returns:
            DeploymentStatus if found, otherwise None.
        """
        status = self._statuses.get(service_name)
        logger.debug("Queried deployment status for '%s': %s", service_name, status)
        return status


class FakeHealthCheckService(HealthCheckService):
    """Fake health check service that uses static responses."""

    def __init__(self, health: Dict[str, HealthCheckStatus]) -> None:
        """Initialize the service.

        Args:
            health: Mapping from URL to HealthCheckStatus.
        """
        self._health = health

    def run_health_check(self, url: str, timeout_seconds: float) -> HealthCheckStatus:
        """Return a static health check result from the in-memory map.

        Args:
            url: URL to check.
            timeout_seconds: Timeout for the health check (ignored in fake).

        Returns:
            HealthCheckStatus describing the outcome.

        Raises:
            ExternalServiceError: If the URL is unknown.