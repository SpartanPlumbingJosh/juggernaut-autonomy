from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Protocol


# Constants
DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS: float = 5.0
DEFAULT_HTTP_RETRY_DELAY_SECONDS: float = 0.5
MAX_HTTP_RETRIES: int = 3


logger: logging.Logger = logging.getLogger(__name__)


class VerificationErrorCode(Enum):
    """Enumerates the possible verification failure codes."""

    PR_NOT_FOUND = auto()
    PR_NOT_MERGED = auto()
    CI_CHECKS_FAILED = auto()
    DEPLOYMENT_FAILED = auto()
    HEALTH_CHECK_FAILED = auto()
    UNKNOWN_ERROR = auto()


@dataclass
class FailureDetail:
    """Represents a single failure within the verification chain.

    Attributes:
        code: Machine-readable error code describing the failure.
        message: Human-readable message describing what went wrong.
    """

    code: VerificationErrorCode
    message: str


@dataclass
class VerificationResult:
    """Result of verifying whether a task can be marked complete.

    Attributes:
        is_success: True if all checks in the chain passed; False otherwise.
        failures: List of failure details explaining what failed.
    """

    is_success: bool
    failures: List[FailureDetail] = field(default_factory=list)

    def require_success(self) -> None:
        """Raise an exception if verification did not succeed.

        Raises:
            VerificationException: If the verification failed.
        """
        if not self.is_success:
            messages = "; ".join(f"{failure.code.name}: {failure.message}" for failure in self.failures)
            raise VerificationException(messages, self.failures)


@dataclass
class Task:
    """Represents a unit of work that is backed by a pull request and deployment.

    Attributes:
        task_id: Unique identifier for the task.
        pr_id: Identifier of the pull request associated with this task.
        service_url: URL of the deployed service for health checks.
    """

    task_id: str
    pr_id: str
    service_url: str


class VerificationException(Exception):
    """Raised when verification fails and completion is not allowed."""

    def __init__(self, message: str, failures: Optional[List[FailureDetail]] = None) -> None:
        """Initialize the VerificationException.

        Args:
            message: Summary message for the exception.
            failures: Optional list of failure details.
        """
        super().__init__(message)
        self.failures: List[FailureDetail] = failures or []


class VersionControlClient(Protocol):
    """Protocol for interacting with a version control system (e.g., GitHub)."""

    def pr_exists(self, pr_id: str) -> bool:
        """Check whether a pull request exists.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            True if the pull request exists; False otherwise.
        """
        ...

    def is_pr_merged(self, pr_id: str) -> bool:
        """Check whether a pull request has been merged.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            True if the pull request is merged; False otherwise.
        """
        ...


class CIChecksClient(Protocol):
    """Protocol for interacting with a CI system (lint, typecheck, tests)."""

    def all_checks_passed(self, pr_id: str) -> bool:
        """Check whether all CI checks associated with a PR have passed.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            True if all checks passed; False otherwise.
        """
        ...


class DeploymentClient(Protocol):
    """Protocol for checking deployment status and fetching logs."""

    def deployment_succeeded(self, pr_id: str) -> bool:
        """Check whether deployment associated with a PR has succeeded.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            True if deployment succeeded; False otherwise.
        """
        ...

    def get_deployment_logs(self, pr_id: str) -> str:
        """Retrieve deployment logs for a pull request.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            Text logs for the deployment.
        """
        ...


class HealthCheckClient(Protocol):
    """Protocol for performing health checks on deployed services."""

    def check_health(self, service_url: str) -> bool:
        """Run a health check against the deployed service.

        Args:
            service_url: URL of the service to check.

        Returns:
            True if the health check passes; False otherwise.
        """
        ...


class TaskVerifier:
    """Orchestrates the verification chain for marking tasks complete.

    The verification chain enforces:

    1. PR exists and is merged.
    2. All CI checks passed.
    3. Deployment succeeded with clean logs.
    4. Health check passes.

    Any failure in this chain disallows task completion.
    """

    def __init__(
        self,
        version_control_client: VersionControlClient,
        ci_checks_client: CIChecksClient,
        deployment_client: DeploymentClient,
        health_check_client: HealthCheckClient,
    ) -> None:
        """Initialize the TaskVerifier.

        Args:
            version_control_client: Client used to interact with version control.
            ci_checks_client: Client used to query CI status.
            deployment_client: Client used to check deployment state.
            health_check_client: Client used to perform health checks.
        """
        self._vc = version_control_client
        self._ci = ci_checks_client
        self._deploy = deployment_client
        self._health = health_check_client

    def verify_task(self, task: Task) -> VerificationResult:
        """Verify whether a task can be safely marked as complete.

        This method executes the full verification chain and accumulates all
        failures. If any step fails, `is_success` will be False.

        Args:
            task: Task instance representing the unit of work.

        Returns:
            VerificationResult indicating whether all checks passed, along
            with detailed failure information.
        """
        logger.debug("Starting verification for task_id=%s, pr_id=%s", task.task_id, task.pr_id)
        failures: List[FailureDetail] = []

        # 1. Verify PR exists and is merged.
        try:
            logger.debug("Checking whether PR %s exists", task.pr_id)
            if not self._vc.pr_exists(task.pr_id):
                message = f"PR {task.pr_id} does not exist."
                logger.info(message)
                failures.append(FailureDetail(VerificationErrorCode.PR_NOT_FOUND, message))
            else:
                logger.debug("PR %s exists; checking merged status", task.pr_id)
                if not self._vc.is_pr_merged(task.pr_id):
                    message = f"PR {task.pr_id} is not merged."
                    logger.info(message)
                    failures.append(FailureDetail(VerificationErrorCode.PR_NOT_MERGED, message))
                else:
                    logger.debug("PR %s is merged", task.pr_id)
        except Exception as exc:
            message = f"Error verifying PR {task.pr_id}: {exc}"
            logger.exception(message)
            failures.append(FailureDetail(VerificationErrorCode.UNKNOWN_ERROR, message))

        # 2. Verify all CI checks passed.
        try:
            logger.debug("Checking CI status for PR %s", task.pr_id)
            if not self._ci.all_checks_passed(task.pr_id):
                message = f"One or more CI checks failed for PR {task.pr_id}."
                logger.info(message)
                failures.append(FailureDetail(VerificationErrorCode.CI_CHECKS_FAILED, message))
            else:
                logger.debug("All CI checks passed for PR %s", task.pr_id)
        except Exception as exc:
            message = f"Error checking CI status for PR {task.pr_id}: {exc}"
            logger.exception(message)
            failures.append(FailureDetail(VerificationErrorCode.UNKNOWN_ERROR, message))

        # 3. Verify deployment succeeded and logs are clean.
        try:
            logger.debug("Checking deployment status for PR %s", task.pr_id)
            if not self._deploy.deployment_succeeded(task.pr_id):
                logs = ""
                try:
                    logs = self._deploy.get_deployment_logs(task.pr_id)
                except Exception as logs_exc:
                    logs = f"<unable to fetch logs: {logs_exc}>"
                    logger.exception("Error fetching deployment logs for PR %s", task.pr_id)
                message = (
                    f"Deployment failed for PR {task.pr_id}. "
                    f"Logs snippet: {logs[:500]}..."
                )
                logger.info(message)
                failures.append(FailureDetail(VerificationErrorCode.DEPLOYMENT_FAILED, message))
            else:
                logger.debug("Deployment succeeded for PR %s", task.pr_id)
        except Exception as exc:
            message = f"Error checking deployment for PR {task.pr_id}: {exc}"
            logger.exception(message)
            failures.append(FailureDetail(VerificationErrorCode.UNKNOWN_ERROR, message))

        # 4. Verify service health.
        try:
            logger.debug("Performing health check for service_url=%s", task.service_url)
            if not self._health.check_health(task.service_url):
                message = (
                    f"Health check failed for service {task.service_url} "
                    f"(PR {task.pr_id}, task {task.task_id})."
                )
                logger.info(message)
                failures.append(FailureDetail(VerificationErrorCode.HEALTH_CHECK_FAILED, message))
            else:
                logger.debug("Health check passed for service_url=%s", task.service_url)
        except Exception as exc:
            message = f"Error performing health check for {task.service_url}: {exc}"
            logger.exception(message)
            failures.append(FailureDetail(VerificationErrorCode.UNKNOWN_ERROR, message))

        is_success: bool = len(failures) == 0
        logger.debug(
            "Verification completed for task_id=%s, pr_id=%s, success=%s, failures=%d",
            task.task_id,
            task.pr_id,
            is_success,
            len(failures),
        )
        return VerificationResult(is_success=is_success, failures=failures)


class InMemoryVersionControlClient:
    """Simple in-memory implementation of VersionControlClient for testing.

    This client is suitable for unit tests and local development where
    integrating with a real VCS provider is not required.
    """

    def __init__(self, merged_prs: Optional[Dict[str, bool]] = None) -> None:
        """Initialize the in-memory version control client.

        Args:
            merged_prs: Mapping of PR IDs to a boolean indicating whether
                each PR is merged. Presence in the dict implies existence.
        """
        self._merged_prs: Dict[str, bool] = merged_prs or {}

    def pr_exists(self, pr_id: str) -> bool:
        """Check whether a PR exists in the in-memory store.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            True if the PR exists; False otherwise.
        """
        exists = pr_id in self._merged_prs
        logger.debug("InMemoryVersionControlClient.pr_exists(%s) -> %s", pr_id, exists)
        return exists

    def is_pr_merged(self, pr_id: str) -> bool:
        """Check whether a PR is marked as merged.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            True if the PR is merged; False if it exists but is not merged.
        """
        merged = self._merged_prs.get(pr_id, False)
        logger.debug("InMemoryVersionControlClient.is_pr_merged(%s) -> %s", pr_id, merged)
        return merged