import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


LOGGER = logging.getLogger(__name__)


# Constants
DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS: float = 5.0
DEFAULT_DEPLOYMENT_LOG_CLEAN_INDICATOR: str = "BUILD_SUCCEEDED"


class TaskStatus(Enum):
    """Represents the lifecycle state of a task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class VerificationStage(Enum):
    """Represents each step in the verification chain."""

    PR_MERGED = "pr_merged"
    CI_CHECKS_PASSED = "ci_checks_passed"
    DEPLOYMENT_SUCCEEDED = "deployment_succeeded"
    HEALTHCHECK_PASSED = "healthcheck_passed"


class VerificationError(Exception):
    """Raised when a task fails verification and cannot be marked complete."""

    def __init__(self, task_id: str, failure_reasons: Dict[VerificationStage, str]) -> None:
        """Initialize the VerificationError.

        Args:
            task_id: Identifier of the task that failed verification.
            failure_reasons: Mapping from verification stage to human-readable failure reason.
        """
        self.task_id: str = task_id
        self.failure_reasons: Dict[VerificationStage, str] = failure_reasons
        message = self._build_message(task_id, failure_reasons)
        super().__init__(message)

    @staticmethod
    def _build_message(task_id: str, failure_reasons: Dict[VerificationStage, str]) -> str:
        """Build a descriptive error message.

        Args:
            task_id: Identifier of the task.
            failure_reasons: Mapping from verification stage to failure reason.

        Returns:
            Error message string.
        """
        reason_lines = [
            f"- {stage.name}: {reason}" for stage, reason in failure_reasons.items()
        ]
        joined_reasons = "\n".join(reason_lines)
        return (
            f"Task '{task_id}' failed verification and cannot be marked complete.\n"
            f"Failures:\n{joined_reasons}"
        )


@dataclass
class StageVerificationResult:
    """Represents the outcome of a single verification stage."""

    stage: VerificationStage
    success: bool
    detail: str
    skipped: bool = False

    def human_readable(self) -> str:
        """Return a human-readable summary of this stage result.

        Returns:
            String describing the outcome of the stage.
        """
        status = "SKIPPED" if self.skipped else ("OK" if self.success else "FAILED")
        return f"[{self.stage.name}] {status}: {self.detail}"


@dataclass
class TaskVerificationResult:
    """Aggregated verification results for a task."""

    task_id: str
    stage_results: Dict[VerificationStage, StageVerificationResult] = field(
        default_factory=dict
    )

    @property
    def success(self) -> bool:
        """Determine whether all non-skipped stages succeeded.

        Returns:
            True if all non-skipped stages succeeded, otherwise False.
        """
        for result in self.stage_results.values():
            if not result.skipped and not result.success:
                return False
        return True

    def failures(self) -> Dict[VerificationStage, StageVerificationResult]:
        """Return all failed stages (excluding skipped).

        Returns:
            Mapping of failed stage to its result.
        """
        return {
            stage: result
            for stage, result in self.stage_results.items()
            if not result.skipped and not result.success
        }

    def summary(self) -> str:
        """Produce a multi-line human-readable summary.

        Returns:
            Summary string across all stages.
        """
        lines = [result.human_readable() for result in self.stage_results.values()]
        return "\n".join(lines)


@dataclass
class Task:
    """Represents a unit of work tied to a pull request and deployment."""

    id: str
    repository: str
    pr_number: int
    environment: str
    healthcheck_url: str
    status: TaskStatus = TaskStatus.PENDING
    last_verification: Optional[TaskVerificationResult] = None


class PullRequestVerifier(ABC):
    """Interface for verifying pull request state."""

    @abstractmethod
    def verify_merged(self, repository: str, pr_number: int) -> StageVerificationResult:
        """Verify that the given pull request is merged.

        Args:
            repository: Repository identifier (e.g., 'org/repo').
            pr_number: Pull request number.

        Returns:
            StageVerificationResult for the PR_MERGED stage.
        """
        raise NotImplementedError


class CIStatusVerifier(ABC):
    """Interface for verifying CI status of a pull request."""

    @abstractmethod
    def verify_checks_passed(
        self, repository: str, pr_number: int
    ) -> StageVerificationResult:
        """Verify that all CI checks for the pull request have passed.

        Args:
            repository: Repository identifier.
            pr_number: Pull request number.

        Returns:
            StageVerificationResult for the CI_CHECKS_PASSED stage.
        """
        raise NotImplementedError


class DeploymentVerifier(ABC):
    """Interface for verifying deployment success."""

    @abstractmethod
    def verify_deployment_succeeded(
        self, environment: str, repository: str, pr_number: int
    ) -> StageVerificationResult:
        """Verify that the deployment associated with the PR succeeded.

        Args:
            environment: Target environment (e.g., 'production', 'staging').
            repository: Repository identifier.
            pr_number: Pull request number.

        Returns:
            StageVerificationResult for the DEPLOYMENT_SUCCEEDED stage.
        """
        raise NotImplementedError


class HealthCheckVerifier(ABC):
    """Interface for verifying service health."""

    @abstractmethod
    def verify_healthcheck(self, url: str) -> StageVerificationResult:
        """Verify that the service healthcheck passes.

        Args:
            url: Healthcheck endpoint URL.

        Returns:
            StageVerificationResult for the HEALTHCHECK_PASSED stage.
        """
        raise NotImplementedError


class InMemoryPullRequestVerifier(PullRequestVerifier):
    """Simple in-memory pull request verifier for testing or demos.

    This implementation treats any PR listed in `merged_prs` as merged.
    """

    def __init__(self, merged_prs: Optional[List[Tuple[str, int]]] = None) -> None:
        """Initialize the verifier.

        Args:
            merged_prs: Optional list of (repository, pr_number) tuples considered merged.
        """
        self._merged_prs: List[Tuple[str, int]] = merged_prs or []

    def verify_merged(self, repository: str, pr_number: int) -> StageVerificationResult:
        """Verify whether a PR is merged using the in-memory list.

        Args:
            repository: Repository identifier.
            pr_number: Pull request number.

        Returns:
            StageVerificationResult indicating success if the PR is marked merged.
        """
        LOGGER.debug(
            "Verifying PR merged status (repo=%s, pr_number=%d)", repository, pr_number
        )
        merged = (repository, pr_number) in self._merged_prs
        if merged:
            detail = "Pull request is marked as merged."
        else:
            detail = "Pull request is not merged."
        return StageVerificationResult(
            stage=VerificationStage.PR_MERGED,
            success=merged,
            detail=detail,
        )


class InMemoryCIStatusVerifier(CIStatusVerifier):
    """Simple in-memory CI status verifier for testing or demos.

    This implementation treats any PR listed in `passing_prs` as having passing checks.
    """

    def __init__(self, passing_prs: Optional[List[Tuple[str, int]]] = None) -> None:
        """Initialize the verifier.

        Args:
            passing_prs: Optional list of (repository, pr_number) tuples with passing CI.
        """
        self._passing_prs: List[Tuple[str, int]] = passing_prs or []

    def verify_checks_passed(
        self, repository: str, pr_number: int
    ) -> StageVerificationResult:
        """Verify CI checks using the in-memory list.

        Args:
            repository: Repository identifier.
            pr_number: Pull request number.

        Returns:
            StageVerificationResult indicating whether CI checks are considered passed.
        """
        LOGGER.debug(
            "Verifying CI checks (repo=%s, pr_number=%d)", repository, pr_number
        )
        passed = (repository, pr_number) in self._passing_prs
        if passed:
            detail = "All CI checks (lint, typecheck, tests) have passed."
        else:
            detail = "CI checks have not all passed."
        return StageVerificationResult(
            stage=VerificationStage.CI_CHECKS_PASSED,
            success=passed,
            detail=detail,
        )


class InMemoryDeploymentVerifier(DeploymentVerifier):
    """Simple in-memory deployment verifier for testing or demos.

    This implementation treats any (environment, repository, pr_number) listed in
    `successful_deployments` as successfully deployed.
    """

    def __init__(
        self,
        successful_deployments: Optional[List[Tuple[str, str, int]]] = None,
    ) -> None:
        """Initialize the verifier.

        Args:
            successful_deployments: Optional list of
                (environment, repository, pr_number) tuples considered successfully deployed.
        """
        self._successful_deployments: List[Tuple[str, str, int]] = (
            successful_deployments or []
        )

    def verify_deployment_succeeded(
        self, environment: str, repository: str, pr_number: int
    ) -> StageVerificationResult:
        """Verify deployment success using the in-memory list.

        Args:
            environment: Target environment.
            repository: Repository identifier.
            pr_number: Pull request number.

        Returns:
            StageVerificationResult indicating whether deployment is considered successful.
        """
        LOGGER.debug(
            "Verifying deployment (env=%s, repo=%s, pr_number=%d)",
            environment,
            repository,
            pr_number,
        )
        deployed = (environment, repository, pr_number) in self._successful_deployments
        if deployed:
            detail = "Deployment succeeded and build logs are clean."
        else:
            detail = "Deployment not found or did not succeed."
        return StageVerificationResult(
            stage=VerificationStage.DEPLOYMENT_SUCCEEDED,
            success=deployed,
            detail=detail,
        )


class InMemoryHealthCheckVerifier(HealthCheckVerifier):
    """Simple in-memory healthcheck verifier for testing or demos.