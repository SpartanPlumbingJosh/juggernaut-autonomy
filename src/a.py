import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Dict, List, Optional, Protocol, runtime_checkable
from urllib import error as urllib_error
from urllib import request as urllib_request


# =============================================================================
# Logging configuration
# =============================================================================

LOGGER_NAME: str = "task_verification"
DEFAULT_LOG_LEVEL: int = logging.INFO


def configure_logging(level: int = DEFAULT_LOG_LEVEL) -> logging.Logger:
    """Configure root logger for the verification module.

    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG).

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


logger = configure_logging()


# =============================================================================
# Constants
# =============================================================================

HEALTHCHECK_TIMEOUT_SECONDS: float = 5.0
HTTP_SUCCESS_MIN: int = 200
HTTP_SUCCESS_MAX: int = 299


# =============================================================================
# Exceptions
# =============================================================================

class VerificationError(Exception):
    """Base exception for all verification-related errors."""


class PRNotFoundError(VerificationError):
    """Raised when a pull request cannot be found."""

    def __init__(self, pr_id: str) -> None:
        """Initialize the exception.

        Args:
            pr_id: Identifier of the pull request.
        """
        super().__init__(f"Pull request '{pr_id}' not found")
        self.pr_id = pr_id


class PRServiceError(VerificationError):
    """Raised when there is a service error fetching PR information."""


class CIServiceError(VerificationError):
    """Raised when there is a service error fetching CI status."""


class DeploymentServiceError(VerificationError):
    """Raised when there is a service error fetching deployment status."""


class HealthCheckError(VerificationError):
    """Raised when there is an error performing the health check."""


# =============================================================================
# Enums and data models
# =============================================================================

class VerificationStep(Enum):
    """Enumeration of verification steps for a task."""

    PR_MERGED = auto()
    CI_PASSED = auto()
    DEPLOYMENT_SUCCEEDED = auto()
    HEALTHCHECK_PASSED = auto()


@dataclass
class PRInfo:
    """Information about a pull request.

    Attributes:
        pr_id: Identifier of the pull request (e.g., "#222").
        exists: Whether the PR exists.
        merged: Whether the PR has been merged.
        title: Optional title of the PR.
        url: Optional URL to the PR in the hosting system.
    """

    pr_id: str
    exists: bool
    merged: bool
    title: Optional[str] = None
    url: Optional[str] = None


@dataclass
class CICheckResult:
    """Result of CI checks for a pull request.

    Attributes:
        pr_id: Identifier of the pull request.
        all_passed: Whether all CI checks passed.
        checks: Mapping from check name to boolean pass/fail.
        details_url: Optional URL to CI details.
    """

    pr_id: str
    all_passed: bool
    checks: Dict[str, bool]
    details_url: Optional[str] = None


@dataclass
class DeploymentResult:
    """Result of a deployment associated with a pull request.

    Attributes:
        pr_id: Identifier of the pull request.
        succeeded: Whether deployment succeeded.
        logs_clean: Whether deployment logs are considered clean.
        deployment_id: Optional identifier of the deployment.
        provider: Optional deployment provider name (e.g., "Railway", "Vercel").
        logs_url: Optional URL to deployment logs.
    """

    pr_id: str
    succeeded: bool
    logs_clean: bool
    deployment_id: Optional[str] = None
    provider: Optional[str] = None
    logs_url: Optional[str] = None


@dataclass
class HealthCheckResult:
    """Result of a service health check.

    Attributes:
        service_url: URL of the service health endpoint.
        healthy: Whether the service is considered healthy.
        status_code: HTTP status code from the health check request.
        response_time_ms: Response time in milliseconds.
        error: Optional error message if the check failed.
    """

    service_url: str
    healthy: bool
    status_code: int
    response_time_ms: float
    error: Optional[str] = None


@dataclass
class TaskVerificationReport:
    """Full verification report for a task.

    Attributes:
        task_id: Identifier of the task being verified.
        timestamp: UTC timestamp when verification was performed.
        pr_info: Information about the associated pull request, if any.
        ci_result: CI check result, if available.
        deployment_result: Deployment result, if available.
        health_check_result: Health check result, if executed.
        failures: Human-readable list of failure reasons.
        can_mark_complete: Whether the task can be marked complete.
    """

    task_id: str
    timestamp: datetime
    pr_info: Optional[PRInfo]
    ci_result: Optional[CICheckResult]
    deployment_result: Optional[DeploymentResult]
    health_check_result: Optional[HealthCheckResult]
    failures: List[str]
    can_mark_complete: bool


# =============================================================================
# Provider protocols (interfaces)
# =============================================================================

@runtime_checkable
class PullRequestProvider(Protocol):
    """Protocol for a service that provides pull request information."""

    def get_pr_info(self, pr_id: str) -> PRInfo:
        """Fetch information about a pull request.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            PRInfo describing the pull request.

        Raises:
            PRNotFoundError: If the pull request does not exist.
            PRServiceError: If there is an error contacting the PR service.
        """
        ...


@runtime_checkable
class CIStatusProvider(Protocol):
    """Protocol for a service that provides CI status for pull requests."""

    def get_ci_status(self, pr_id: str) -> CICheckResult:
        """Fetch CI status for a pull request.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            CICheckResult describing CI checks and whether they all passed.

        Raises:
            CIServiceError: If there is an error contacting the CI service.
        """
        ...


@runtime_checkable
class DeploymentProvider(Protocol):
    """Protocol for a service that provides deployment status."""

    def get_deployment_result(self, pr_id: str) -> DeploymentResult:
        """Fetch deployment result associated with a pull request.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            DeploymentResult describing deployment success and logs cleanliness.

        Raises:
            DeploymentServiceError: If there is an error contacting deployment service.
        """
        ...


@runtime_checkable
class HealthCheckProvider(Protocol):
    """Protocol for performing a health check against a service."""

    def check(self, service_url: str) -> HealthCheckResult:
        """Perform a health check against the given service URL.

        Args:
            service_url: URL of the service health endpoint.

        Returns:
            HealthCheckResult describing health status.

        Raises:
            HealthCheckError: If there is an error performing the check.
        """
        ...


# =============================================================================
# Concrete implementations
# =============================================================================

class HttpHealthCheckProvider:
    """HTTP-based implementation of HealthCheckProvider using urllib."""

    def __init__(self, timeout_seconds: float = HEALTHCHECK_TIMEOUT_SECONDS) -> None:
        """Initialize the provider.

        Args:
            timeout_seconds: Maximum time to wait for a response before timing out.
        """
        self._timeout_seconds = timeout_seconds

    def check(self, service_url: str) -> HealthCheckResult:
        """Perform an HTTP GET health check.

        Args:
            service_url: URL to query.

        Returns:
            HealthCheckResult with details of the HTTP call.

        Raises:
            HealthCheckError: If there is a non-HTTP related error.
        """
        logger.debug("Starting health check for URL: %s", service_url)
        start = time.monotonic()
        try:
            req = urllib_request.Request(service_url, method="GET")
            with urllib_request.urlopen(req, timeout=self._timeout_seconds) as resp:
                status_code: int = int(resp.getcode())
                elapsed_ms: float = (time.monotonic() - start) * 1000.0
                healthy: bool = HTTP_SUCCESS_MIN <= status_code <= HTTP_SUCCESS_MAX
                logger.debug(
                    "Health check completed: status=%s, time_ms=%.2f, healthy=%s",
                    status_code,
                    elapsed_ms,
                    healthy,
                )
                return HealthCheckResult(
                    service_url=service_url,
                    healthy=healthy,
                    status_code=status_code,
                    response_time_ms=elapsed_ms,
                    error=None if healthy else f"Unhealthy HTTP status: {status_code}",
                )
        except urllib_error.HTTPError as exc:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            logger.warning(
                "HTTP error during health check: url=%s status=%s error=%s",
                service_url,
                exc.code,
                exc.reason,
            )
            return HealthCheckResult(
                service_url=service_url,
                healthy=False,
                status_code=int(exc.code),
                response_time_ms=elapsed_ms,
                error=f"HTTP error: {exc}",
            )
        except urllib_error.URLError as exc:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            logger.error(
                "URL error during health check: url=%s error=%s",
                service_url,
                exc.reason,
            )
            raise HealthCheckError(f"URL error during health check: {exc}") from exc
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            logger.exception(
                "Unexpected error during health check: url=%s time_ms=%.2f",
                service_url,
                elapsed_ms,
            )
            raise HealthCheckError(f"Unexpected health check error: {exc}") from exc


# =============================================================================
# Task verifier
# =============================================================================

class TaskVerifier:
    """Core verification orchestrator for tasks.

    The verifier enforces the full chain:

    1. PR exists and is merged.
    2. All CI checks passed.
    3. Deployment succeeded and logs are clean.
    4. Health check passes.

    Any failure in this chain means the task cannot be marked complete.
    """

    def __init__(
        self,
        pr_provider: PullRequestProvider,
        ci_provider: CIStatusProvider,
        deployment_provider: DeploymentProvider,
        healthcheck_provider: HealthCheckProvider,
    ) -> None:
        """Initialize the task verifier.

        Args:
            pr_provider: Provider used to fetch PR information.
            ci_provider: Provider used to fetch CI status.
            deployment_provider: Provider used to fetch deployment status.
            healthcheck_provider: Provider used to perform health checks.
        """
        self._pr_provider = pr_provider
        self._ci_provider = ci_provider
        self._deployment_provider = deployment_provider
        self._healthcheck_provider = healthcheck_provider

    def verify_task(
        self,
        task_id: str,
        pr_id: str,
        service_url: str,
    ) -> TaskVerificationReport:
        """Verify the full chain for a task.

        Args:
            task_id: Identifier of the task to verify.
            pr_id: Identifier of the associated pull request.
            service_url: URL of the deployed service for health checking.

        Returns:
            TaskVerificationReport describing the verification outcome.
        """
        logger.info(
            "Starting verification for task_id=%s pr_id=%s service_url=%s",
            task_id,
            pr_id,
            service_url