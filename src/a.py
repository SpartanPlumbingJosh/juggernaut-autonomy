import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Sequence, Set, Tuple

from urllib import request, error as url_error


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

LOGGER_NAME: str = "task_verification"
DEFAULT_LOG_LEVEL: int = logging.INFO

logger = logging.getLogger(LOGGER_NAME)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(DEFAULT_LOG_LEVEL)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEALTHCHECK_TIMEOUT_SECONDS: int = 10
DEFAULT_USER_AGENT: str = "TaskVerification/1.0"
EVIDENCE_MAX_LENGTH: int = 4096


# ---------------------------------------------------------------------------
# Enums and Data Models
# ---------------------------------------------------------------------------


class VerificationStage(Enum):
    """Stages of the verification chain."""

    PR = "pr"
    CI = "ci"
    DEPLOYMENT = "deployment"
    HEALTH = "health"


class VerificationStatus(Enum):
    """Result status for a verification stage."""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """Result for a single verification stage.

    Attributes:
        stage: Name of the verification stage.
        status: Outcome of the stage.
        details: Human-readable explanation of what happened.
        evidence: Optional structured evidence (e.g., logs, response snippets).
        timestamp: When this stage was evaluated.
    """

    stage: VerificationStage
    status: VerificationStatus
    details: str
    evidence: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class VerificationResult:
    """Aggregated verification result for a task.

    Attributes:
        overall_success: True if all mandatory stages passed.
        stage_results: List of detailed results per stage, in order.
    """

    overall_success: bool
    stage_results: List[StageResult]

    def get_failed_stages(self) -> List[StageResult]:
        """Return all stages that failed.

        Returns:
            List of StageResult instances with FAILURE status.
        """
        return [s for s in self.stage_results if s.status == VerificationStatus.FAILURE]

    def get_skipped_stages(self) -> List[StageResult]:
        """Return all stages that were skipped.

        Returns:
            List of StageResult instances with SKIPPED status.
        """
        return [s for s in self.stage_results if s.status == VerificationStatus.SKIPPED]

    def get_successful_stages(self) -> List[StageResult]:
        """Return all stages that succeeded.

        Returns:
            List of StageResult instances with SUCCESS status.
        """
        return [s for s in self.stage_results if s.status == VerificationStatus.SUCCESS]


# ---------------------------------------------------------------------------
# Client Protocols (Interfaces)
# ---------------------------------------------------------------------------


class PRClient(Protocol):
    """Interface for pull request verification."""

    def is_pr_merged(self, pr_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Check whether a pull request exists and is merged.

        Args:
            pr_id: Identifier of the pull request (e.g., "#222" or a numeric ID).

        Returns:
            A tuple of:
                - bool: True if PR exists and is merged.
                - str: Explanatory message.
                - Optional[Dict[str, Any]]: Evidence such as PR metadata.

        Raises:
            Exception: Implementations may raise specific exceptions for
                unrecoverable issues (e.g., network failures).
        """
        ...


class CIClient(Protocol):
    """Interface for CI (lint, typecheck, tests) verification."""

    def have_all_checks_passed(
        self, pr_id: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Check whether all CI checks passed for a given PR.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            A tuple of:
                - bool: True if all CI checks have passed.
                - str: Explanatory message.
                - Optional[Dict[str, Any]]: Evidence such as CI run summary.
        """
        ...


class DeploymentClient(Protocol):
    """Interface for deployment verification."""

    def is_deployment_successful(
        self, deployment_id: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Check whether a deployment succeeded.

        Args:
            deployment_id: Deployment identifier (e.g., Railway/Vercel deployment id).

        Returns:
            A tuple of:
                - bool: True if deployment succeeded.
                - str: Explanatory message.
                - Optional[Dict[str, Any]]: Evidence such as logs or metadata.
        """
        ...


class HealthChecker(Protocol):
    """Interface for service health verification."""

    def is_healthy(self, url: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Check whether a service is healthy.

        Args:
            url: Health check URL to query.

        Returns:
            A tuple of:
                - bool: True if the service is healthy.
                - str: Explanatory message.
                - Optional[Dict[str, Any]]: Evidence such as HTTP status code and body.
        """
        ...


# ---------------------------------------------------------------------------
# In-memory / Simple Implementations
# ---------------------------------------------------------------------------


class InMemoryPRClient:
    """In-memory implementation of PRClient for demonstration and testing.

    This client treats a PR as "merged" if its ID is present in `merged_pr_ids`.

    Attributes:
        merged_pr_ids: Set of PR identifiers considered merged.
    """

    def __init__(self, merged_pr_ids: Optional[Set[str]] = None) -> None:
        """Initialize the client.

        Args:
            merged_pr_ids: Initial set of merged PR identifiers.
        """
        self._merged_pr_ids: Set[str] = merged_pr_ids or set()

    def mark_merged(self, pr_id: str) -> None:
        """Mark a PR as merged in the in-memory store.

        Args:
            pr_id: Identifier of the pull request.
        """
        logger.debug("Marking PR %s as merged in in-memory client.", pr_id)
        self._merged_pr_ids.add(pr_id)

    def is_pr_merged(self, pr_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Check if a PR is considered merged in-memory.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            Tuple indicating whether the PR is merged, a message, and evidence.
        """
        logger.debug("Checking if PR %s is merged in in-memory client.", pr_id)
        if pr_id in self._merged_pr_ids:
            evidence = {"pr_id": pr_id, "status": "merged", "source": "in-memory"}
            return True, f"PR {pr_id} is marked as merged.", evidence

        evidence = {"pr_id": pr_id, "status": "not_merged", "source": "in-memory"}
        return False, f"PR {pr_id} is not merged or does not exist.", evidence


class InMemoryCIClient:
    """In-memory implementation of CIClient for demonstration and testing.

    Attributes:
        passing_pr_ids: Set of PR identifiers whose CI checks have passed.
    """

    def __init__(self, passing_pr_ids: Optional[Set[str]] = None) -> None:
        """Initialize the client.

        Args:
            passing_pr_ids: Initial set of PR identifiers with passing CI.
        """
        self._passing_pr_ids: Set[str] = passing_pr_ids or set()

    def mark_ci_passed(self, pr_id: str) -> None:
        """Mark CI checks as passed for a PR.

        Args:
            pr_id: Identifier of the pull request.
        """
        logger.debug("Marking CI as passed for PR %s in in-memory client.", pr_id)
        self._passing_pr_ids.add(pr_id)

    def have_all_checks_passed(
        self, pr_id: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Check if all CI checks passed for a PR in-memory.

        Args:
            pr_id: Identifier of the pull request.

        Returns:
            Tuple indicating whether CI checks passed, a message, and evidence.
        """
        logger.debug("Checking CI status for PR %s in in-memory client.", pr_id)
        if pr_id in self._passing_pr_ids:
            evidence = {"pr_id": pr_id, "ci_status": "passed", "source": "in-memory"}
            return True, f"All CI checks passed for PR {pr_id}.", evidence

        evidence = {"pr_id": pr_id, "ci_status": "failed", "source": "in-memory"}
        return (
            False,
            f"CI checks have not passed for PR {pr_id}.",
            evidence,
        )


class InMemoryDeploymentClient:
    """In-memory implementation of DeploymentClient for demonstration and testing.

    Attributes:
        successful_deployments: Set of deployment identifiers considered successful.
    """

    def __init__(self, successful_deployments: Optional[Set[str]] = None) -> None:
        """Initialize the client.

        Args:
            successful_deployments: Initial set of successful deployment identifiers.
        """
        self._successful_deployments: Set[str] = successful_deployments or set()

    def mark_successful(self, deployment_id: str) -> None:
        """Mark a deployment as successful.

        Args:
            deployment_id: Identifier of the deployment.
        """
        logger.debug(
            "Marking deployment %s as successful in in-memory client.", deployment_id
        )
        self._successful_deployments.add(deployment_id)

    def is_deployment_successful(
        self, deployment_id: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Check if a deployment is considered successful in-memory.

        Args:
            deployment_id: Identifier of the deployment.

        Returns:
            Tuple indicating whether deployment succeeded, a message, and evidence.
        """
        logger.debug(
            "Checking deployment status for %s in in-memory client.", deployment_id
        )
        if deployment_id in self._successful_deployments:
            evidence = {
                "deployment_id": deployment_id,
                "deployment_status": "successful",
                "source": "in-memory",
            }
            return True, f"Deployment {deployment_id} succeeded.", evidence

        evidence = {
            "deployment_id": deployment_id,
            "deployment_status": "failed",
            "source": "in-memory",
        }
        return False, f"Deployment {deployment_id} did not succeed.", evidence


class HttpHealthChecker:
    """HTTP-based implementation of HealthChecker.

    This checker performs a GET request to the provided URL and considers
    the service healthy if the response code is 200.

    Attributes:
        timeout_seconds: Timeout to use for HTTP requests.
    """

    def __init__(self, timeout_seconds: int = HEALTHCHECK_TIMEOUT_SECONDS) -> None:
        """Initialize the health checker.

        Args:
            timeout_seconds: Maximum number of seconds to wait for a response.
        """
        self._timeout_seconds: int = timeout_seconds

    def is_healthy(self, url: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Check service health via HTTP GET.

        Args:
            url: Health check URL.

        Returns:
            Tuple indicating whether the service is healthy, a message, and evidence.
        """
        logger.debug("Performing health check for URL: %s", url)
        req = request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as resp:
                status_code = resp.getcode()
                body_snippet_bytes = resp.read(EVIDENCE_MAX_LENGTH)
                body_snippet = body_snippet_bytes.decode("utf-8", errors="replace")
                evidence = {
                    "url": url,
                    "status_code": status_code,
                    "body_snippet": body_snippet,
                }

                if status_code == 200:
                    return True, f"Health check passed for {url}.", evidence
                return (
                    False,
                    f"Health check failed for {url} with status {status_code}.",
                    evidence,
                )
        except url_error.HTTPError as exc:
            evidence = {
                "url": url,
                "status_code": exc.code,
                "reason": exc.reason,
                "body": exc.read(EVIDENCE_MAX_LENGTH).decode(
                    "utf-8", errors="replace"
                ),
            }
            logger.warning(
                "HTTPError during health check for %s: %s", url, exc, exc_info=True
            )
            return (
                False,
                f"Health check HTTP error for {url}: {exc.code} {exc.reason}.",
                evidence,
            )
        except url_error.URLError as exc:
            evidence = {
                "url": url,
                "reason": str(exc.reason),
            }
            logger.warning(
                "URLError during health check for %s: %s", url, exc, exc_info=True
            )
            return (
                False,
                f"Health check URL error for {url}: {exc.reason}.",
                evidence,
            )
        except TimeoutError as exc:
            evidence = {
                "url": url,
                "reason": "timeout",
            }
            logger.warning(
                "Timeout during health check for %s: %s", url, exc, exc_info=True
            )
            return (
                False,
                f"Health check timed out for {url}.",
                evidence,
            )
        except Exception as exc:
            evidence = {
                "url": url,
                "reason": f"unexpected error: {exc!r}",
            }
            logger.error(
                "Unexpected error during health check for %s: %s",
                url,
                exc,
                exc_info=True,
            )
            return (
                False,
                f"Unexpected error during health check for {url}: {exc}.",
                evidence,
            )


# ---------------------------------------------------------------------------
# Core Verification Service
#