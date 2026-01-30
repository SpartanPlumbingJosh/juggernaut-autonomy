from __future__ import annotations

import dataclasses
import enum
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol, Sequence, Tuple
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

# Configure module-level logger
LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    # Basic configuration; in a real application, configure logging centrally.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )

# Constants
DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS: int = 5
DEFAULT_MAX_HEALTHCHECK_BODY_SNIPPET: int = 512
BUILD_LOG_ERROR_KEYWORDS: Tuple[str, ...] = ("ERROR", "FATAL", "EXCEPTION", "FAIL", "FAILED")
HTTP_SUCCESS_MIN: int = 200
HTTP_SUCCESS_MAX: int = 299


class TaskStatus(enum.Enum):
    """Enumeration of possible task lifecycle states."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED_VERIFICATION = "failed_verification"


class VerificationStage(enum.Enum):
    """Enumeration of verification stages in the completion chain."""

    PULL_REQUEST = "pull_request"
    CI_CHECKS = "ci_checks"
    DEPLOYMENT = "deployment"
    HEALTH_CHECK = "health_check"


@dataclass(frozen=True)
class StageVerificationResult:
    """Result of a single verification stage.

    Attributes:
        stage: The verification stage this result pertains to.
        success: Whether the stage passed successfully.
        details: Human-readable explanation of the outcome.
        evidence: Additional machine-readable evidence for auditing.
    """

    stage: VerificationStage
    success: bool
    details: str
    evidence: Dict[str, object]


@dataclass(frozen=True)
class VerificationReport:
    """Aggregated verification report for a task completion attempt.

    Attributes:
        task_id: Identifier of the task that was verified.
        all_passed: Whether all verification stages passed.
        results: Collection of per-stage verification results.
        verified_at: Timestamp when the verification was executed.
    """

    task_id: str
    all_passed: bool
    results: Sequence[StageVerificationResult]
    verified_at: datetime


@dataclass
class TaskRecord:
    """Represents a unit of work that can be completed.

    Attributes:
        task_id: Unique identifier of the task.
        pr_number: Associated pull request number for the task.
        service_url: Base URL or health endpoint for the deployed service.
        deployment_id: Identifier of the deployment/build (e.g., Railway/Vercel ID).
        status: Current lifecycle state of the task.
        last_verification_report: Most recent verification report, if any.
    """

    task_id: str
    pr_number: int
    service_url: str
    deployment_id: Optional[str]
    status: TaskStatus = TaskStatus.PENDING
    last_verification_report: Optional[VerificationReport] = None


@dataclass(frozen=True)
class PullRequestInfo:
    """Information about a pull request.

    Attributes:
        number: Pull request number.
        title: Title of the pull request.
        is_merged: Whether the PR has been merged.
        merged_at: When the PR was merged (if merged).
        html_url: URL to view the PR in a browser.
    """

    number: int
    title: str
    is_merged: bool
    merged_at: Optional[datetime]
    html_url: Optional[str]


@dataclass(frozen=True)
class CIStatus:
    """Information about CI status for a given PR.

    Attributes:
        all_checks_passed: True if all CI checks (lint, typecheck, tests) passed.
        failed_checks: Names of checks that failed, if any.
        details_url: Link to CI run/details.
    """

    all_checks_passed: bool
    failed_checks: Sequence[str]
    details_url: Optional[str]


@dataclass(frozen=True)
class DeploymentStatus:
    """Information about deployment/build status.

    Attributes:
        deployment_id: Identifier of the deployment.
        succeeded: Whether the deployment completed successfully.
        build_logs: Build logs for inspection.
        platform: Name of the deployment platform (e.g., Railway, Vercel).
        url: URL of deployment logs or dashboard.
    """

    deployment_id: str
    succeeded: bool
    build_logs: Sequence[str]
    platform: str
    url: Optional[str]


@dataclass(frozen=True)
class HealthCheckResult:
    """Result of a health check against a running service.

    Attributes:
        url: URL that was checked.
        ok: True if the health check passed.
        status_code: HTTP status code received, or None if unavailable.
        body_snippet: Short snippet of the response body for debugging.
        elapsed_seconds: Time taken to complete the health check.
    """

    url: str
    ok: bool
    status_code: Optional[int]
    body_snippet: str
    elapsed_seconds: float


class TaskVerificationError(Exception):
    """Raised when a task fails verification and cannot be completed."""

    def __init__(self, task_id: str, report: VerificationReport) -> None:
        """Initialize the TaskVerificationError.

        Args:
            task_id: Identifier of the task that failed verification.
            report: Detailed verification report for the failure.
        """
        self.task_id = task_id
        self.report = report
        super().__init__(f"Task '{task_id}' failed verification and cannot be completed.")


class ExternalServiceError(Exception):
    """Raised when an external integration cannot be contacted or returns invalid data."""

    def __init__(self, service_name: str, message: str) -> None:
        """Initialize the ExternalServiceError.

        Args:
            service_name: Name of the external service.
            message: Description of the failure.
        """
        self.service_name = service_name
        self.message = message
        super().__init__(f"{service_name} error: {message}")


class TaskRepository(Protocol):
    """Protocol for persisting and retrieving tasks."""

    def get_task(self, task_id: str) -> TaskRecord:
        """Retrieve a task record by identifier.

        Args:
            task_id: Identifier of the task.

        Returns:
            The corresponding TaskRecord.

        Raises:
            KeyError: If the task does not exist.
        """
        ...

    def save_task(self, task: TaskRecord) -> None:
        """Persist a task record.

        Args:
            task: The task record to save.

        Returns:
            None.
        """
        ...


class PullRequestService(Protocol):
    """Protocol for interacting with a pull request hosting service."""

    def get_pull_request(self, pr_number: int) -> PullRequestInfo:
        """Retrieve pull request information.

        Args:
            pr_number: Number of the pull request.

        Returns:
            PullRequestInfo for the given PR.

        Raises:
            ExternalServiceError: If the PR cannot be fetched.
        """
        ...


class CIService(Protocol):
    """Protocol for interacting with CI systems."""

    def get_ci_status(self, pr_number: int) -> CIStatus:
        """Retrieve CI status for a pull request.

        Args:
            pr_number: Pull request number.

        Returns:
            CIStatus representing the outcome of CI checks.

        Raises:
            ExternalServiceError: If CI status cannot be fetched.
        """
        ...


class DeploymentService(Protocol):
    """Protocol for interacting with deployment/build systems."""

    def get_deployment_status(self, deployment_id: str) -> DeploymentStatus:
        """Retrieve deployment status and logs.

        Args:
            deployment_id: Identifier for the deployment.

        Returns:
            DeploymentStatus representing the outcome and logs.

        Raises:
            ExternalServiceError: If deployment status cannot be fetched.
        """
        ...


class HealthCheckService(Protocol):
    """Protocol for performing health checks against running services."""

    def perform_health_check(self, url: str, timeout_seconds: int) -> HealthCheckResult:
        """Perform a health check on the given URL.

        Args:
            url: Full URL to the health endpoint.
            timeout_seconds: Maximum number of seconds to wait.

        Returns:
            HealthCheckResult describing the outcome.

        Raises:
            ExternalServiceError: If the health check fails unexpectedly.
        """
        ...


class InMemoryTaskRepository:
    """In-memory implementation of TaskRepository for testing or lightweight usage."""

    def __init__(self) -> None:
        """Initialize an empty in-memory task repository."""
        self._tasks: Dict[str, TaskRecord] = {}

    def add_task(self, task: TaskRecord) -> None:
        """Add a new task to the repository.

        Args:
            task: Task record to add.

        Returns:
            None.
        """
        LOGGER.debug("Adding task to repository: %s", task.task_id)
        self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> TaskRecord:
        """Retrieve a task record by identifier.

        Args:
            task_id: Identifier of the task.

        Returns:
            The corresponding TaskRecord.

        Raises:
            KeyError: If the task does not exist.
        """
        try:
            task = self._tasks[task_id]
            LOGGER.debug("Retrieved task '%s' from repository", task_id)
            return task
        except KeyError as exc: