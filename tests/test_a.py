import dataclasses
import logging
from datetime import datetime, timezone

import pytest

import a


@pytest.fixture
def task_repository() -> a.InMemoryTaskRepository:
    return a.InMemoryTaskRepository()


@pytest.fixture
def sample_verification_results() -> list[a.StageVerificationResult]:
    return [
        a.StageVerificationResult(
            stage=a.VerificationStage.PULL_REQUEST,
            success=True,
            details="PR merged successfully",
            evidence={"merged": True},
        ),
        a.StageVerificationResult(
            stage=a.VerificationStage.CI_CHECKS,
            success=True,
            details="All CI checks passed",
            evidence={"checks": ["lint", "tests"], "status": "success"},
        ),
    ]


@pytest.fixture
def sample_verification_report(sample_verification_results: list[a.StageVerificationResult]) -> a.VerificationReport:
    return a.VerificationReport(
        task_id="task-123",
        all_passed=True,
        results=sample_verification_results,
        verified_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_task(sample_verification_report: a.VerificationReport) -> a.TaskRecord:
    return a.TaskRecord(
        task_id="task-123",
        pr_number=42,
        service_url="https://service.example.com/health",
        deployment_id="deploy-abc",
        status=a.TaskStatus.PENDING,
        last_verification_report=sample_verification_report,
    )


def test_task_status_enum_values_are_unique_and_strings():
    values = [status.value for status in a.TaskStatus]
    assert len(values) == len(set(values))
    assert all(isinstance(v, str) for v in values)


def test_verification_stage_enum_values_are_unique_and_strings():
    values = [stage.value for stage in a.VerificationStage]
    assert len(values) == len(set(values))
    assert all(isinstance(v, str) for v in values)


def test_stage_verification_result_is_frozen_and_immutable():
    result = a.StageVerificationResult(
        stage=a.VerificationStage.CI_CHECKS,
        success=False,
        details="Checks failed",
        evidence={"failed_checks": ["lint"]},
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.success = True  # type: ignore[attr-defined]


def test_verification_report_is_frozen_and_contains_results(sample_verification_report: a.VerificationReport):
    report = sample_verification_report
    assert report.task_id == "task-123"
    assert report.all_passed is True
    assert isinstance(report.results, (list, tuple))
    assert all(isinstance(r, a.StageVerificationResult) for r in report.results)

    # Frozen dataclass should not allow modification
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.task_id = "other"  # type: ignore[attr-defined]


def test_task_record_defaults_and_mutability():
    task = a.TaskRecord(
        task_id="t1",
        pr_number=1,
        service_url="https://example.com",
        deployment_id=None,
    )

    # Defaults
    assert task.status == a.TaskStatus.PENDING
    assert task.last_verification_report is None

    # Non-frozen: can be modified
    task.status = a.TaskStatus.IN_PROGRESS
    assert task.status == a.TaskStatus.IN_PROGRESS


def test_pull_request_info_is_frozen():
    pr = a.PullRequestInfo(
        number=10,
        title="Add feature X",
        is_merged=True,
        merged_at=datetime.now(timezone.utc),
        html_url="https://example.com/pr/10",
    )
    assert pr.number == 10
    assert pr.is_merged is True

    with pytest.raises(dataclasses.FrozenInstanceError):
        pr.number = 11  # type: ignore[attr-defined]


def test_ci_status_is_frozen():
    ci = a.CIStatus(
        all_checks_passed=False,
        failed_checks=["tests", "lint"],
        details_url="https://ci.example.com/run/1",
    )
    assert ci.all_checks_passed is False
    assert "tests" in ci.failed_checks

    with pytest.raises(dataclasses.FrozenInstanceError):
        ci.all_checks_passed = True  # type: ignore[attr-defined]


def test_deployment_status_is_frozen():
    deployment = a.DeploymentStatus(
        deployment_id="dep-1",
        succeeded=True,
        build_logs=["Build started", "Build finished"],
        platform="ExamplePlatform",
        url="https://deploy.example.com/dep-1",
    )
    assert deployment.deployment_id == "dep-1"
    assert deployment.succeeded is True

    with pytest.raises(dataclasses.FrozenInstanceError):
        deployment.succeeded = False  # type: ignore[attr-defined]


def test_health_check_result_is_frozen():
    hc = a.HealthCheckResult(
        url="https://service.example.com/health",
        ok=True,
        status_code=200,
        body_snippet="OK",
        elapsed_seconds=0.123,
    )
    assert hc.ok is True
    assert hc.status_code == 200

    with pytest.raises(dataclasses.FrozenInstanceError):
        hc.ok = False  # type: ignore[attr-defined]


def test_task_verification_error_contains_task_id_and_report(sample_verification_report: a.VerificationReport):
    err = a.TaskVerificationError(task_id="task-123", report=sample_verification_report)
    assert err.task_id == "task-123"
    assert err.report is sample_verification_report
    assert "task-123" in str(err)
    assert "failed verification" in str(err).lower()


def test_external_service_error_contains_service_name_and_message():
    err = a.ExternalServiceError(service_name="GitHub", message="Rate limit exceeded")
    assert err.service_name == "GitHub"
    assert err.message == "Rate limit exceeded"
    text = str(err)
    assert "GitHub" in text
    assert "Rate limit exceeded" in text


def test_in_memory_task_repository_add_and_get_task_success(
    task_repository: a.InMemoryTaskRepository,
    sample_task: a.TaskRecord,
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.DEBUG, logger=a.LOGGER.name)

    task_repository.add_task(sample_task)
    assert "Adding task to repository" in caplog.text

    caplog.clear()
    retrieved = task_repository.get_task(sample_task.task_id)

    assert retrieved is sample_task
    assert f"Retrieved task '{sample_task.task_id}' from repository" in caplog.text


def test_in_memory_task_repository_get_task_raises_keyerror_for_missing_task(
    task_repository: a.InMemoryTaskRepository,
):
    with pytest.raises(KeyError):
        task_repository.get_task("non-existent-task-id")


def test_in_memory_task_repository_add_task_overwrites_existing(
    task_repository: a.InMemoryTaskRepository,
):
    original = a.TaskRecord(
        task_id="task-1",
        pr_number=1,
        service_url="https://example.com",
        deployment_id="dep-1",
    )
    updated = a.TaskRecord(
        task_id="task-1",
        pr_number=2,
        service_url="https://other.example.com",
        deployment_id="dep-2",
    )

    task_repository.add_task(original)
    task_repository.add_task(updated)

    retrieved = task_repository.get_task("task-1")
    # Confirm it was overwritten with the updated record
    assert retrieved is updated
    assert retrieved.pr_number == 2
    assert retrieved.service_url == "https://other.example.com"
    assert retrieved.deployment_id == "dep-2"


def test_default_healthcheck_constants_are_positive_and_reasonable():
    assert isinstance(a.DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS, int)
    assert a.DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS > 0

    assert isinstance(a.DEFAULT_MAX_HEALTHCHECK_BODY_SNIPPET, int)
    assert a.DEFAULT_MAX_HEALTHCHECK_BODY_SNIPPET > 0
    assert a.DEFAULT_MAX_HEALTHCHECK_BODY_SNIPPET >= 128


def test_build_log_error_keywords_is_non_empty_tuple_of_strings():
    assert isinstance(a.BUILD_LOG_ERROR_KEYWORDS, tuple)
    assert len(a.BUILD_LOG_ERROR_KEYWORDS) > 0
    assert all(isinstance(k, str) for k in a.BUILD_LOG_ERROR_KEYWORDS)
    # Expect some common error indicators to be present
    assert "ERROR" in a.BUILD_LOG_ERROR_KEYWORDS
    assert "FAIL" in a.BUILD_LOG_ERROR_KEYWORDS or "FAILED" in a.BUILD_LOG_ERROR_KEYWORDS


def test_http_success_range_is_valid_and_in_2xx_range():
    assert isinstance(a.HTTP_SUCCESS_MIN, int)
    assert isinstance(a.HTTP_SUCCESS_MAX, int)
    assert 200 <= a.HTTP_SUCCESS_MIN <= a.HTTP_SUCCESS_MAX < 400


def test_protocols_cannot_be_instantiated_directly():
    # Protocol classes from typing should not be directly instantiable
    with pytest.raises(TypeError):
        a.TaskRepository()  # type: ignore[abstract]
    with pytest.raises(TypeError):
        a.PullRequestService()  # type: ignore[abstract]
    with pytest.raises(TypeError):
        a.CIService()  # type: ignore[abstract]
    with pytest.raises(TypeError):
        a.DeploymentService()  # type: ignore[abstract]
    with pytest.raises(TypeError):
        a.HealthCheckService()  # type: ignore[abstract]


def test_logger_is_configured_with_module_name():
    assert isinstance(a.LOGGER, logging.Logger)
    assert a.LOGGER.name == a.__name__