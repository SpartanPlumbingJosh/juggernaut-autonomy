from __future__ import annotations

import datetime
import enum
import json
import logging
import socket
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
from urllib import error as url_error
from urllib import request as url_request

# Constants
DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS: float = 5.0
DEFAULT_MAX_DEPLOYMENT_LOG_LINES: int = 1000
HTTP_SUCCESS_MIN: int = 200
HTTP_SUCCESS_MAX: int = 299

DEPLOYMENT_SUCCESS_KEYWORDS: Tuple[str, ...] = (
    "build succeeded",
    "deployment completed",
    "successfully deployed",
)

DEPLOYMENT_FAILURE_KEYWORDS: Tuple[str, ...] = (
    "error",
    "failed",
    "exception",
    "traceback",
    "panic",
)


class VerificationStep(enum.Enum):
    """Enumeration of the verification steps in the completion chain."""

    PR_MERGED = "pr_merged"
    CI_PASSED = "ci_passed"
    DEPLOYMENT_SUCCEEDED = "deployment_succeeded"
    HEALTH_CHECK_PASSED = "health_check_passed"


class StepStatus(enum.Enum):
    """Enumeration of the status of a single verification step."""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class StepResult:
    """Result of a single verification step.

    Attributes:
        step: The verification step that was executed.
        status: Outcome status of the step.
        message: Human-readable explanation of the outcome.
        details: Optional structured details for the step.
    """

    step: VerificationStep
    status: StepStatus
    message: str
    details: Optional[Mapping[str, Any]] = None


@dataclass
class VerificationResult:
    """Aggregate result of verifying a task's completion chain.

    Attributes:
        task_id: Identifier of the task that was verified.
        success: True if all steps succeeded, False otherwise.
        step_results: Detailed results for each verification step.
    """

    task_id: str
    success: bool
    step_results: List[StepResult] = field(default_factory=list)

    def failed_steps(self) -> List[StepResult]:
        """Return all steps that did not succeed.

        Returns:
            List of StepResult objects where status is not SUCCESS.
        """
        return [r for r in self.step_results if r.status is not StepStatus.SUCCESS]


@dataclass
class Task:
    """Represents a unit of work that depends on a PR and deployment chain.

    Attributes:
        id: Unique identifier for the task.
        repository: Repository identifier (e.g., 'owner/repo').
        pr_id: Identifier of the associated pull request.
        ci_pipeline_id: Identifier of the CI pipeline for the PR.
        deployment_id: Identifier of the deployment artifact or instance.
        healthcheck_url: URL used to perform runtime health checks.
        completed: Whether the task has been marked as completed.
        completed_at: Timestamp when the task was marked as completed.
    """

    id: str
    repository: str
    pr_id: str
    ci_pipeline_id: str
    deployment_id: str
    healthcheck_url: str
    completed: bool = False
    completed_at: Optional[datetime.datetime] = None


class TaskVerificationError(Exception):
    """Base exception for errors during task verification."""


class PullRequestServiceError(TaskVerificationError):
    """Exception raised when the pull request service fails."""


class CIServiceError(TaskVerificationError):
    """Exception raised when the CI service fails."""


class DeploymentServiceError(TaskVerificationError):
    """Exception raised when the deployment service fails."""


class HealthCheckServiceError(TaskVerificationError):
    """Exception raised when the health check service fails."""


class PullRequestService:
    """Abstract interface for querying pull request state."""

    def is_pr_merged(self, repository: str, pr_id: str) -> bool:
        """Check if the given pull request is merged.

        Args:
            repository: Repository identifier (e.g., 'owner/repo').
            pr_id: Pull request identifier.

        Returns:
            True if the PR is merged, False otherwise.

        Raises:
            PullRequestServiceError: If the service cannot determine PR state.
        """
        raise NotImplementedError


class CIService:
    """Abstract interface for querying CI pipeline state."""

    def are_checks_successful(self, pipeline_id: str) -> bool:
        """Check if all CI checks for a pipeline have passed.

        Args:
            pipeline_id: Identifier of the CI pipeline.

        Returns:
            True if all required checks passed, False otherwise.

        Raises:
            CIServiceError: If the service cannot determine CI state.
        """
        raise NotImplementedError


class DeploymentService:
    """Abstract interface for querying deployment state and logs."""

    def is_deployment_successful(self, deployment_id: str) -> bool:
        """Check if the deployment completed successfully.

        Args:
            deployment_id: Identifier of the deployment.

        Returns:
            True if the deployment is successful, False otherwise.

        Raises:
            DeploymentServiceError: If the service cannot determine deployment state.
        """
        raise NotImplementedError

    def get_build_logs(self, deployment_id: str, max_lines: int) -> Sequence[str]:
        """Retrieve build or deployment logs for analysis.

        Args:
            deployment_id: Identifier of the deployment.
            max_lines: Maximum number of log lines to return.

        Returns:
            A sequence of log lines in chronological order.

        Raises:
            DeploymentServiceError: If logs cannot be retrieved.
        """
        raise NotImplementedError


class HealthCheckService:
    """Abstract interface for performing health checks against a service."""

    def is_healthy(self, url: str, timeout_seconds: float) -> bool:
        """Perform a health check against a URL.

        Args:
            url: Health check endpoint URL.
            timeout_seconds: Timeout in seconds for the request.

        Returns:
            True if the health check passes, False otherwise.

        Raises:
            HealthCheckServiceError: If the health check could not be performed.
        """
        raise NotImplementedError


class InMemoryPullRequestService(PullRequestService):
    """In-memory implementation of PullRequestService for testing or demos."""

    def __init__(self, merged_prs: Optional[Iterable[Tuple[str, str]]] = None) -> None:
        """Initialize the service.

        Args:
            merged_prs: Optional iterable of (repository, pr_id) pairs that are merged.
        """
        self._merged_prs: Set[Tuple[str, str]] = set(merged_prs or [])

    def is_pr_merged(self, repository: str, pr_id: str) -> bool:
        """See base class."""
        try:
            return (repository, pr_id) in self._merged_prs
        except Exception as exc:
            raise PullRequestServiceError(f"Failed to check PR merge state: {exc}") from exc


class InMemoryCIService(CIService):
    """In-memory implementation of CIService for testing or demos."""

    def __init__(self, successful_pipelines: Optional[Iterable[str]] = None) -> None:
        """Initialize the service.

        Args:
            successful_pipelines: Optional iterable of CI pipeline IDs that passed.
        """
        self._successful_pipelines: Set[str] = set(successful_pipelines or [])

    def are_checks_successful(self, pipeline_id: str) -> bool:
        """See base class."""
        try:
            return pipeline_id in self._successful_pipelines
        except Exception as exc:
            raise CIServiceError(f"Failed to check CI pipeline state: {exc}") from exc


class InMemoryDeploymentService(DeploymentService):
    """In-memory implementation of DeploymentService for testing or demos."""

    def __init__(
        self,
        successful_deployments: Optional[Iterable[str]] = None,
        logs_by_deployment: Optional[Mapping[str, Sequence[str]]] = None,
    ) -> None:
        """Initialize the service.

        Args:
            successful_deployments: Optional iterable of deployment IDs that succeeded.
            logs_by_deployment: Optional mapping of deployment IDs to log lines.
        """
        self._successful_deployments: Set[str] = set(successful_deployments or [])
        self._logs_by_deployment: Dict[str, Sequence[str]] = dict(logs_by_deployment or {})

    def is_deployment_successful(self, deployment_id: str) -> bool:
        """See base class."""
        try:
            return deployment_id in self._successful_deployments
        except Exception as exc:
            raise DeploymentServiceError(f"Failed to check deployment state: {exc}") from exc

    def get_build_logs(self, deployment_id: str, max_lines: int) -> Sequence[str]:
        """See base class."""
        try:
            logs = self._logs_by_deployment.get(deployment_id, [])
            if max_lines <= 0:
                return []
            return logs[-max_lines:]
        except Exception as exc:
            raise DeploymentServiceError(f"Failed to fetch deployment logs: {exc}") from exc


class HttpHealthCheckService(HealthCheckService):
    """HTTP-based implementation of HealthCheckService."""

    def is_healthy(self, url: str, timeout_seconds: float) -> bool:
        """See base class."""
        request = url_request.Request(url, method="GET")
        try:
            with url_request.urlopen(request, timeout=timeout_seconds) as response:
                status_code = response.getcode()
                content_type = response.headers.get("Content-Type", "")
                if HTTP