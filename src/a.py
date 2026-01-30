import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional

import requests

# Constants
DEFAULT_HTTP_TIMEOUT_SECONDS: float = 5.0
DEFAULT_HEALTH_CHECK_EXPECTED_STATUS: int = 200

# Configure module-level logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


class VerificationError(Exception):
    """Exception raised when a task fails verification."""

    def __init__(self, message: str, report: "TaskVerificationReport") -> None:
        """Initialize VerificationError.

        Args:
            message: Human-readable error message.
            report: Detailed verification report.
        """
        super().__init__(message)
        self.report = report


class CheckStatus(Enum):
    """Enumeration of possible check outcomes."""

    PASSED = auto()
    FAILED = auto()
    SKIPPED = auto()


class CheckType(Enum):
    """Enumeration of check types in the verification chain."""

    PR_MERGED = auto()
    CI_PASSED = auto()
    DEPLOY_SUCCEEDED = auto()
    HEALTHY = auto()


@dataclass(frozen=True)
class CheckResult:
    """Result of a single verification check."""

    check_type: CheckType
    status: CheckStatus
    message: str


@dataclass(frozen=True)
class TaskVerificationReport:
    """Aggregated verification report for a task."""

    task_id: str
    overall_passed: bool
    check_results: List[CheckResult]

    def failed_checks(self) -> List[CheckResult]:
        """Get all failed checks.

        Returns:
            List of CheckResult objects that have status FAILED.
        """
        return [c for c in self.check_results if c.status == CheckStatus.FAILED]

    def to_human_readable(self) -> str:
        """Render the report as a human-readable multi-line string.

        Returns:
            Human-readable string representation of the report.
        """
        lines: List[str] = [
            f"Task '{self.task_id}' verification: "
            f"{'PASSED' if self.overall_passed else 'FAILED'}"
        ]
        for result in self.check_results:
            lines.append(
                f"- {result.check_type.name}: {result.status.name} - {result.message}"
            )
        return "\n".join(lines)


@dataclass(frozen=True)
class Task:
    """Representation of a task that must be verified before completion."""

    id: str
    repository: str
    pr_number: int
    ci_pipeline_id: Optional[str] = None
    deployment_id: Optional[str] = None
    health_check_url: Optional[str] = None


class PullRequestStatus(Enum):
    """Status of a pull request in a VCS provider."""

    OPEN = auto()
    MERGED = auto()
    CLOSED = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class PullRequest:
    """Representation of a pull request."""

    repository: str
    number: int
    title: str
    status: PullRequestStatus


class CIStatus(Enum):
    """Status of a CI pipeline."""

    PASSED = auto()
    FAILED = auto()
    RUNNING = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class CIPipeline:
    """Representation of a CI pipeline."""

    pipeline_id: str
    status: CIStatus
    url: Optional[str] = None
    description: Optional[str] = None


class DeploymentStatus(Enum):
    """Status of a deployment process."""

    SUCCEEDED = auto()
    FAILED = auto()
    RUNNING = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class Deployment:
    """Representation of a deployment."""

    deployment_id: str
    status: DeploymentStatus
    logs_url: Optional[str] = None
    description: Optional[str] = None


class PRService(ABC):
    """Abstract interface for interacting with pull requests."""

    @abstractmethod
    def get_pull_request(self, repository: str, pr_number: int) -> Optional[PullRequest]:
        """Retrieve a pull request.

        Args:
            repository: Fully qualified repository name (e.g., 'org/repo').
            pr_number: Pull request number.

        Returns:
            PullRequest instance if found, otherwise None.

        Raises:
            Exception: Implementations may raise more specific exceptions.
        """
        raise NotImplementedError


class CIService(ABC):
    """Abstract interface for interacting with CI pipelines."""

    @abstractmethod
    def get_pipeline(self, pipeline_id: str) -> Optional[CIPipeline]:
        """Retrieve CI pipeline information.

        Args:
            pipeline_id: Unique identifier of the CI pipeline.

        Returns:
            CIPipeline instance if found, otherwise None.

        Raises:
            Exception: Implementations may raise more specific exceptions.
        """
        raise NotImplementedError


class DeploymentService(ABC):
    """Abstract interface for interacting with deployments."""

    @abstractmethod
    def get_deployment(self, deployment_id: str) -> Optional[Deployment]:
        """Retrieve deployment information.

        Args:
            deployment_id: Unique identifier of the deployment.

        Returns:
            Deployment instance if found, otherwise None.

        Raises:
            Exception: Implementations may raise more specific exceptions.
        """
        raise NotImplementedError


class HealthCheckService(ABC):
    """Abstract interface for performing health checks on services."""

    @abstractmethod
    def check(self, url: str) -> CheckResult:
        """Perform a health check on a given URL.

        Args:
            url: Health check endpoint URL.

        Returns:
            CheckResult representing the outcome of the health check.
        """
        raise NotImplementedError


class HttpHealthCheckService(HealthCheckService):
    """HTTP-based implementation of HealthCheckService."""

    def __init__(
        self,
        expected_status: int = DEFAULT_HEALTH_CHECK_EXPECTED_STATUS,
        timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize HttpHealthCheckService.

        Args:
            expected_status: HTTP status code considered as a passing health check.
            timeout_seconds: Request timeout in seconds.
        """
        self._expected_status = expected_status
        self._timeout_seconds = timeout_seconds

    def check(self, url: str) -> CheckResult:
        """Perform an HTTP GET health check.

        Args:
            url: Health check endpoint URL.

        Returns:
            CheckResult representing the outcome of the health check.
        """
        logger.info("Performing health check for URL '%s'", url)
        try:
            response = requests.get(url, timeout=self._timeout_seconds)
            if response.status_code == self._expected_status:
                return CheckResult(
                    check_type=CheckType.HEALTHY,
                    status=CheckStatus.PASSED,
                    message=f"Health check successful (status {response.status_code}).",
                )
            return CheckResult(
                check_type=CheckType.HEALTHY,
                status=CheckStatus.FAILED,
                message=(
                    f"Health check failed: expected status "
                    f"{self._expected_status}, got {response.status_code}."
                ),
            )
        except requests.exceptions.Timeout as exc:
            logger.warning("Health check timeout for URL '%s': %s", url, exc)
            return CheckResult(
                check_type=CheckType.HEALTHY,
                status=CheckStatus.FAILED,
                message="Health check timed out.",
            )
        except requests.exceptions.RequestException as exc:
            logger.warning("Health check error for URL '%s': %s", url, exc)
            return CheckResult(
                check_type=CheckType.HEALTHY,
                status=CheckStatus.FAILED,
                message=f"Health check error: {exc}",
            )


class InMemoryPRService(PRService):
    """In-memory PR service for testing and local usage."""

    def __init__(self, prs: Optional[Dict[str, PullRequest]] = None) -> None:
        """Initialize InMemoryPRService.

        Args:
            prs: Optional dictionary keyed by 'repo#number' with PullRequest values.
        """
        self._prs: Dict[str, PullRequest] = prs or {}

    @staticmethod
    def _key(repository: str, pr_number: int) -> str:
        """Build a storage key for a PR.

        Args:
            repository: Repository name.
            pr_number: Pull request number.

        Returns:
            Composite key string.
        """
        return f"{repository}#{pr_number}"

    def add_pull_request(self, pr: PullRequest) -> None:
        """Store a pull request in memory.

        Args:
            pr: PullRequest to store.
        """
        key = self._key(pr.repository, pr.number)
        logger.debug("Adding PR to in-memory store: %s", key)
        self._prs[key] = pr

    def get_pull_request(self, repository: str, pr_number: int) -> Optional[PullRequest]:
        """Retrieve a pull request from memory.

        Args:
            repository: Repository name.
            pr_number: Pull request number.

        Returns:
            PullRequest instance if found, otherwise None.
        """
        key = self._key(repository, pr_number)
        pr = self._prs.get(key)
        logger.info("Fetching PR %s -> %s", key, "FOUND" if pr else "NOT FOUND")
        return pr


class InMemoryCIService(CIService):
    """In-memory CI service for testing and local usage."""

    def __init__(self, pipelines: Optional[Dict[str, CIPipeline]] = None) -> None:
        """Initialize InMemoryCIService.

        Args:
            pipelines: Optional dictionary keyed by pipeline_id with CIPipeline values.
        """
        self._pipelines: Dict[str, CIPipeline] = pipelines or {}

    def add_pipeline(self, pipeline: CIPipeline) -> None:
        """Store a CI pipeline in memory.

        Args:
            pipeline: CIPipeline to store.
        """
        logger.debug("Adding CI pipeline to in-memory store: %s", pipeline.pipeline_id)
        self._pipelines[pipeline.pipeline_id] = pipeline

    def get_pipeline(self, pipeline_id: str) -> Optional[CIPipeline]:
        """Retrieve a CI pipeline from memory.

        Args:
            pipeline_id: Unique identifier of the CI pipeline.

        Returns:
            CIPipeline instance if found, otherwise None.
        """
        pipeline = self._pipelines.get(pipeline_id)
        logger.info(
            "Fetching CI pipeline %s -> %s",
            pipeline_id,
            "FOUND" if pipeline else "NOT FOUND",
        )
        return pipeline


class InMemoryDeploymentService(DeploymentService):
    """In-memory deployment service for testing and local usage."""

    def __init__(self, deployments: Optional[Dict[str, Deployment]] = None) -> None:
        """Initialize InMemoryDeploymentService.

        Args:
            deployments: Optional dictionary keyed by deployment_id with Deployment values.
        """
        self._deployments: Dict[str, Deployment] = deployments or {}

    def add_deployment(self, deployment: Deployment) -> None:
        """Store a deployment in memory.

        Args:
            deployment: Deployment to store.
        """
        logger.debug(
            "Adding deployment to in-memory store: %s", deployment.deployment_id
        )
        self._deployments[deployment.deployment_id] = deployment

    def get_deployment(self, deployment_id: str) -> Optional[Deployment]:
        """Retrieve a deployment from memory.

        Args:
            deployment_id: Unique identifier of the deployment.

        Returns:
            Deployment instance if found, otherwise None.
        """
        deployment = self._deployments.get(deployment_id)
        logger.info(
            "Fetching deployment %s -> %s",
            deployment_id,
            "FOUND" if deployment else "NOT FOUND",
        )
        return deployment


class TaskVerificationService:
    """Service responsible for verifying the full completion chain of a task."""

    def __init__(
        self,
        pr_service: PRService,
        ci_service: CIService,
        deployment_service: DeploymentService,
        health_check_service: HealthCheckService,
    ) -> None:
        """Initialize TaskVerificationService.

        Args:
            pr_service: Service to query pull request status.
            ci_service: Service to query CI pipeline status.
            deployment_service: Service to query deployment status.
            health_check_service: Service to perform health checks.
        """
        self._pr_service = pr_service
        self._ci_service = ci_service
        self._deployment_service = deployment_service
        self._health_check_service = health_check_service

    def verify(self, task: Task) -> TaskVerificationReport:
        """Run the full verification chain for a task.

        The chain is:

        1. PR exists and is MERGED.
        2. All CI checks PASSED.
        3. Deployment SUCCEEDED.
        4. Health check PASSES.

        If an early step fails, subsequent steps are skipped to avoid
        confusing/invalid results.

        Args:
            task: Task to verify.

        Returns:
            TaskVerificationReport with detailed status for each check.
        """
        logger.info("Starting verification for task '%s'", task.id)
        check_results: List[CheckResult] = []

        # 1. PR exists and is MERGED
        pr_result = self._check_pr_merged(task)
        check_results.append(pr_result)

        if pr_result.status is not CheckStatus.PASSED:
            # Abort chain: cannot progress without a merged PR
            logger.info(
                "