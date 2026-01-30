import logging
from typing import Dict, Tuple

import pytest

import a


@pytest.fixture
def sample_verification_failures() -> list[a.VerificationFailure]:
    return [
        a.VerificationFailure(
            step=a.VerificationStep.PR_MERGED,
            message="PR is not merged",
            details={"pr_number": 123},
        ),
        a.VerificationFailure(
            step=a.VerificationStep.CI_PASSED,
            message="CI failed",
            details={"job": "build", "status": "failed"},
        ),
    ]


@pytest.fixture
def sample_verification_result(sample_verification_failures: list[a.VerificationFailure]) -> a.VerificationResult:
    return a.VerificationResult(
        task_id="task-123",
        success=False,
        failures=sample_verification_failures,
    )


@pytest.fixture
def sample_task() -> a.Task:
    return a.Task(
        id="task-1",
        repository="example/repo",
        pr_number=42,
        deployment_environment="prod",
        healthcheck_url="https://example.com/health",
    )


@pytest.fixture
def in_memory_repo() -> a.InMemoryTaskRepository:
    return a.InMemoryTaskRepository()


@pytest.fixture
def sample_pr_mapping() -> Dict[Tuple[str, int], a.PullRequestStatus]:
    return {
        ("example/repo", 1): a.PullRequestStatus.OPEN,
        ("example/repo", 2): a.PullRequestStatus.MERGED,
    }


@pytest.fixture
def dummy_pr_provider(sample_pr_mapping: Dict[Tuple[str, int], a.PullRequestStatus]) -> a.DummyPullRequestProvider:
    return a.DummyPullRequestProvider(sample_pr_mapping)


def test_verification_result_to_dict_with_failures(sample_verification_result: a.VerificationResult) -> None:
    result_dict = sample_verification_result.to_dict()

    assert result_dict["task_id"] == "task-123"
    assert result_dict["success"] is False
    assert isinstance(result_dict["failures"], list)
    assert len(result_dict["failures"]) == 2

    first_failure = result_dict["failures"][0]
    assert first_failure["step"] == a.VerificationStep.PR_MERGED.name
    assert first_failure["message"] == "PR is not merged"
    assert first_failure["details"] == {"pr_number": 123}


def test_verification_result_to_dict_without_failures() -> None:
    vr = a.VerificationResult(task_id="t-1", success=True)
    result_dict = vr.to_dict()

    assert result_dict == {
        "task_id": "t-1",
        "success": True,
        "failures": [],
    }


def test_verification_result_from_dict_round_trip(sample_verification_result: a.VerificationResult) -> None:
    as_dict = sample_verification_result.to_dict()
    reconstructed = a.VerificationResult.from_dict(as_dict)

    assert reconstructed.task_id == sample_verification_result.task_id
    assert reconstructed.success == sample_verification_result.success
    assert len(reconstructed.failures) == len(sample_verification_result.failures)

    for orig, recon in zip(sample_verification_result.failures, reconstructed.failures):
        assert recon.step == orig.step
        assert recon.message == orig.message
        assert recon.details == orig.details


def test_verification_result_from_dict_with_empty_failures() -> None:
    data = {
        "task_id": "task-xyz",
        "success": True,
        "failures": [],
    }
    result = a.VerificationResult.from_dict(data)

    assert result.task_id == "task-xyz"
    assert result.success is True
    assert result.failures == []


def test_verification_result_from_dict_missing_details_defaults_to_empty_dict() -> None:
    data = {
        "task_id": "task-xyz",
        "success": False,
        "failures": [
            {
                "step": a.VerificationStep.HEALTHY.name,
                "message": "Health check failed",
            }
        ],
    }

    result = a.VerificationResult.from_dict(data)

    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.step == a.VerificationStep.HEALTHY
    assert failure.message == "Health check failed"
    assert failure.details == {}


def test_verification_result_from_dict_invalid_step_raises_key_error() -> None:
    data = {
        "task_id": "task-xyz",
        "success": False,
        "failures": [
            {
                "step": "NON_EXISTENT_STEP",
                "message": "Invalid",
                "details": {},
            }
        ],
    }

    with pytest.raises(KeyError):
        a.VerificationResult.from_dict(data)


def test_verification_result_from_dict_missing_required_fields_raises_key_error() -> None:
    data_missing_task_id = {
        "success": True,
        "failures": [],
    }

    with pytest.raises(KeyError):
        a.VerificationResult.from_dict(data_missing_task_id)


def test_task_defaults_and_fields(sample_task: a.Task) -> None:
    assert sample_task.status == a.TaskStatus.PENDING
    assert sample_task.last_verification is None
    assert sample_task.repository == "example/repo"
    assert sample_task.pr_number == 42
    assert sample_task.deployment_environment == "prod"
    assert sample_task.healthcheck_url == "https://example.com/health"


def test_in_memory_task_repository_add_and_get_task(in_memory_repo: a.InMemoryTaskRepository, sample_task: a.Task) -> None:
    in_memory_repo.add_task(sample_task)

    retrieved = in_memory_repo.get_task(sample_task.id)

    assert retrieved is sample_task
    assert retrieved.id == "task-1"


def test_in_memory_task_repository_add_task_duplicate_id_raises_value_error(
    in_memory_repo: a.InMemoryTaskRepository, sample_task: a.Task
) -> None:
    in_memory_repo.add_task(sample_task)

    with pytest.raises(ValueError) as exc_info:
        in_memory_repo.add_task(sample_task)

    assert "already exists" in str(exc_info.value)


def test_in_memory_task_repository_get_nonexistent_task_raises_task_not_found(
    in_memory_repo: a.InMemoryTaskRepository, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR, logger=a.logger.name)

    with pytest.raises(a.TaskNotFoundError) as exc_info:
        in_memory_repo.get_task("missing-id")

    assert "not found" in str(exc_info.value)
    assert any("Task not found" in record.getMessage() for record in caplog.records)


def test_in_memory_task_repository_update_existing_task(
    in_memory_repo: a.InMemoryTaskRepository, sample_task: a.Task
) -> None:
    in_memory_repo.add_task(sample_task)
    sample_task.status = a.TaskStatus.IN_PROGRESS

    in_memory_repo.update_task(sample_task)

    updated = in_memory_repo.get_task(sample_task.id)
    assert updated.status == a.TaskStatus.IN_PROGRESS


def test_in_memory_task_repository_update_nonexistent_task_raises_task_not_found(
    in_memory_repo: a.InMemoryTaskRepository, sample_task: a.Task, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR, logger=a.logger.name)

    with pytest.raises(a.TaskNotFoundError) as exc_info:
        in_memory_repo.update_task(sample_task)

    assert "not found" in str(exc_info.value)
    assert any("Attempted to update non-existent task" in record.getMessage() for record in caplog.records)


def test_in_memory_task_repository_accepts_arbitrary_task_ids(in_memory_repo: a.InMemoryTaskRepository) -> None:
    task = a.Task(
        id="",
        repository="repo",
        pr_number=1,
        deployment_environment="env",
        healthcheck_url="url",
    )

    in_memory_repo.add_task(task)
    retrieved = in_memory_repo.get_task("")

    assert retrieved.id == ""


def test_dummy_pull_request_provider_returns_existing_pr(
    dummy_pr_provider: a.DummyPullRequestProvider, sample_pr_mapping: Dict[Tuple[str, int], a.PullRequestStatus]
) -> None:
    pr = dummy_pr_provider.get_pull_request("example/repo", 1)

    assert isinstance(pr, a.PullRequest)
    assert pr.repository == "example/repo"
    assert pr.number == 1
    assert pr.status == sample_pr_mapping[("example/repo", 1)]


def test_dummy_pull_request_provider_unknown_pr_raises_provider_error(
    dummy_pr_provider: a.DummyPullRequestProvider, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR, logger=a.logger.name)

    with pytest.raises(a.ProviderError) as exc_info:
        dummy_pr_provider.get_pull_request("unknown/repo", 999)

    assert "not found" in str(exc_info.value)
    assert any("Pull request not found" in record.getMessage() for record in caplog.records)


def test_dummy_pull_request_provider_implements_pull_request_provider_protocol(
    dummy_pr_provider: a.DummyPullRequestProvider,
) -> None:
    assert isinstance(dummy_pr_provider, a.PullRequestProvider)


def test_in_memory_task_repository_implements_task_repository_protocol(
    in_memory_repo: a.InMemoryTaskRepository,
) -> None:
    assert isinstance(in_memory_repo, a.TaskRepository)


def test_enums_have_expected_members() -> None:
    assert "PENDING" in [member.name for member in a.TaskStatus]
    assert "IN_PROGRESS" in [member.name for member in a.TaskStatus]
    assert "COMPLETED" in [member.name for member in a.TaskStatus]
    assert "FAILED_VERIFICATION" in [member.name for member in a.TaskStatus]

    assert "OPEN" in [member.name for member in a.PullRequestStatus]
    assert "MERGED" in [member.name for member in a.PullRequestStatus]
    assert "CLOSED" in [member.name for member in a.PullRequestStatus]

    assert "PR_MERGED" in [member.name for member in a.VerificationStep]
    assert "CI_PASSED" in [member.name for member in a.VerificationStep]
    assert "DEPLOYMENT_SUCCEEDED" in [member.name for member in a.VerificationStep]
    assert "HEALTHY" in [member.name for member in a.VerificationStep]


def test_verification_failure_dataclass_fields(sample_verification_failures: list[a.VerificationFailure]) -> None:
    failure = sample_verification_failures[0]

    assert failure.step == a.VerificationStep.PR_MERGED
    assert failure.message == "PR is not merged"
    assert failure.details == {"pr_number": 123}


def test_pull_request_dataclass_fields() -> None:
    pr = a.PullRequest(number=10, repository="example/repo", status=a.PullRequestStatus.CLOSED)

    assert pr.number == 10
    assert pr.repository == "example/repo"
    assert pr.status == a.PullRequestStatus.CLOSED


def test_provider_and_repository_errors_are_exceptions() -> None:
    assert issubclass(a.ProviderError, Exception)
    assert issubclass(a.TaskNotFoundError, Exception)


def test_constants_have_expected_values() -> None:
    assert isinstance(a.LOGGER_NAME, str)
    assert a.LOGGER_NAME == "task_verification"

    assert isinstance(a.DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS, float)
    assert a.DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS == 5.0

    assert isinstance(a.DEFAULT_HEALTHCHECK_METHOD, str)
    assert a.DEFAULT_HEALTHCHECK_METHOD == "GET"

    assert isinstance(a.HTTP_OK, int)
    assert a.HTTP_OK == 200