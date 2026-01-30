from __future__ import annotations

import argparse
import logging
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Protocol, runtime_checkable

LOGGER = logging.getLogger(__name__)

DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS: float = 5.0
DEFAULT_LOG_LEVEL: int = logging.INFO
HTTP_STATUS_OK_MIN: int = 200
HTTP_STATUS_OK_MAX: int = 299


class VerificationError(Exception):
    """Base exception for verification-related errors."""


class TaskNotFoundError(VerificationError):
    """Raised when a task cannot be found."""

    def __init__(self, task_id: str) -> None:
        """Initialize the exception.

        Args:
            task_id: Identifier of the missing task.
        """
        super().__init__(f"Task with id '{task_id}' not found.")
        self.task_id: str = task_id


class TaskVerificationFailed(VerificationError):
    """Raised when a task fails verification before completion."""

    def __init__(self, task_id: str, report: VerificationReport) -> None:  # type: ignore[name-defined]
        """Initialize the exception.

        Args:
            task_id: Identifier of the task that failed verification.
            report: Full verification report with step details.
        """
        message = (
            f"Task '{task_id}' failed verification. "
            f"Summary: {report.summary()}"
        )
        super().__init__(message)
        self.task_id: str = task_id
        self.report: VerificationReport = report


class VerificationStep(Enum):
    """Enumeration of verification steps in the chain."""

    PR_MERGED = auto()
    CI_PASSED = auto()
    DEPLOYMENT_SUCCEEDED = auto()
    HEALTHCHECK_PASSED = auto()


class StepStatus(Enum):
    """Status of an individual verification step."""

    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class VerificationStepResult:
    """Result of an individual verification step.

    Attributes:
        step: The verification step that was executed.
        status: Outcome of the step.
        message: Human-readable detail about the outcome.
    """

    step: VerificationStep
    status: StepStatus
    message: str


@dataclass
class VerificationReport:
    """Full verification report for a task.

    Attributes:
        task_id: Identifier of the verified task.
        is_successful: Overall verification status.
        step_results: Ordered list of results for each step.
    """

    task_id: str
    is_successful: bool
    step_results: List[VerificationStepResult] = field(default_factory=list)

    def summary(self) -> str:
        """Generate a one-line summary of the verification.

        Returns:
            Summary string describing the high-level outcome.
        """
        statuses = ", ".join(
            f"{result.step.name}={result.status.name}" for result in self.step_results
        )
        overall = "SUCCESS" if self.is_successful else "FAILED"
        return f"{overall} ({statuses})"


@dataclass
class PullRequestInfo:
    """Information about a pull request.

    Attributes:
        pr_id: Pull request identifier.
        exists: Whether the PR exists in the source control system.
        is_merged: Whether the PR has been merged into the target branch.
        ci_checks_passed: Whether all CI checks (lint, typecheck, tests) passed.
    """

    pr_id: int
    exists: bool
    is_merged: bool
    ci_checks_passed: bool


@dataclass
class DeploymentInfo:
    """Information about a deployment associated with a task.

    Attributes:
        pr_id: Pull request identifier associated with the deployment.
        succeeded: Whether the deployment completed successfully.
        logs_clean: Whether deployment logs are clean (no build errors).
        details: Optional descriptive details about the deployment.
    """

    pr_id: int
    succeeded: bool
    logs_clean: bool
    details: str = ""


@dataclass
class Task:
    """Represents a unit of work that must be verified before completion.

    Attributes:
        task_id: Unique identifier of the task.
        pr_id: Associated pull request number.
        service_url: URL used for the health check of the deployed service.
    """

    task_id: str
    pr_id: int
    service_url: str


@runtime_checkable
class PullRequestClient(Protocol):
    """Protocol for retrieving pull request information."""

    def get_pull_request(self, pr_id: int) -> PullRequestInfo:
        """Retrieve information about a pull request.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            PullRequestInfo describing the PR.

        Raises:
            VerificationError: If the PR cannot be retrieved.
        """
        ...


@runtime_checkable
class DeploymentClient(Protocol):
    """Protocol for retrieving deployment information."""

    def get_deployment_info(self, pr_id: int) -> DeploymentInfo:
        """Retrieve deployment information for a given PR.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            DeploymentInfo describing the deployment.

        Raises:
            VerificationError: If the deployment information cannot be retrieved.
        """
        ...


@runtime_checkable
class HealthCheckClient(Protocol):
    """Protocol for performing health checks against deployed services."""

    def check_health(self, url: str, timeout_seconds: float) -> bool:
        """Check the health of a service.

        Args:
            url: URL to send the health check request to.
            timeout_seconds: Timeout in seconds for the check.

        Returns:
            True if the service is healthy; False otherwise.
        """
        ...


class InMemoryPullRequestClient:
    """In-memory implementation of PullRequestClient for demonstration/testing."""

    def __init__(self, store: Dict[int, PullRequestInfo]) -> None:
        """Initialize the client with a PR store.

        Args:
            store: Mapping of PR id to PullRequestInfo.
        """
        self._store: Dict[int, PullRequestInfo] = store

    def get_pull_request(self, pr_id: int) -> PullRequest