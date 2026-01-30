import logging

import pytest

import a


@pytest.fixture
def sample_step_results():
    return [
        a.VerificationStepResult(
            step=a.VerificationStep.PR_MERGED,
            status=a.StepStatus.SUCCESS,
            message="PR was merged",
        ),
        a.VerificationStepResult(
            step=a.VerificationStep.CI_PASSED,
            status=a.StepStatus.FAILED,
            message="CI failed",
        ),
    ]


@pytest.fixture
def successful_report(sample_step_results):
    return a.VerificationReport(
        task_id="task-123",
        is_successful=True,
        step_results=sample_step_results,
    )


@pytest.fixture
def failed_report(sample_step_results):
    return a.VerificationReport(
        task_id="task-456",
        is_successful=False,
        step_results=sample_step_results,
    )


@pytest.fixture
def pr_store():
    return {
        1: a.PullRequestInfo(
            pr_id=1,
            exists=True,
            is_merged=True,
            ci_checks_passed=True,
        ),
        2: a.PullRequestInfo(
            pr_id=2,
            exists=True,
            is_merged=False,
            ci_checks_passed=False,
        ),
    }


# --- Constants -----------------------------------------------------------------


def test_default_constants_have_expected_values():
    assert isinstance(a.DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS, float)
    assert a.DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS == 5.0

    assert a.DEFAULT_LOG_LEVEL == logging.INFO
    assert a.HTTP_STATUS_OK_MIN == 200
    assert a.HTTP_STATUS_OK_MAX == 299
    assert a.HTTP_STATUS_OK_MIN < a.HTTP_STATUS_OK_MAX


# --- Exceptions ----------------------------------------------------------------


def test_task_not_found_error_has_informative_message_and_attribute():
    task_id = "abc-123"

    exc = a.TaskNotFoundError(task_id)

    assert exc.task_id == task_id
    assert str(exc) == f"Task with id '{task_id}' not found."
    assert isinstance(exc, a.VerificationError)


def test_task_verification_failed_includes_summary_in_message(successful_report):
    task_id = "task-xyz"

    exc = a.TaskVerificationFailed(task_id, successful_report)

    assert exc.task_id == task_id
    assert exc.report is successful_report
    assert isinstance(exc, a.VerificationError)

    # Message should include both the task id and the report summary
    msg = str(exc)
    assert f"Task '{task_id}' failed verification." in msg
    assert successful_report.summary() in msg


# --- Enums ---------------------------------------------------------------------


def test_verification_step_enum_members_and_order():
    steps = list(a.VerificationStep)
    assert steps == [
        a.VerificationStep.PR_MERGED,
        a.VerificationStep.CI_PASSED,
        a.VerificationStep.DEPLOYMENT_SUCCEEDED,
        a.VerificationStep.HEALTHCHECK_PASSED,
    ]


def test_step_status_enum_members_and_order():
    statuses = list(a.StepStatus)
    assert statuses == [
        a.StepStatus.SUCCESS,
        a.StepStatus.FAILED,
        a.StepStatus.SKIPPED,
    ]


# --- Dataclasses ---------------------------------------------------------------


def test_verification_step_result_stores_given_data():
    result = a.VerificationStepResult(
        step=a.VerificationStep.DEPLOYMENT_SUCCEEDED,
        status=a.StepStatus.SKIPPED,
        message="Deployment not required",
    )

    assert result.step is a.VerificationStep.DEPLOYMENT_SUCCEEDED
    assert result.status is a.StepStatus.SKIPPED
    assert result.message == "Deployment not required"


def test_verification_report_summary_success_with_steps(successful_report, sample_step_results):
    summary = successful_report.summary()

    assert summary.startswith("SUCCESS (")
    # All steps and their statuses should appear
    for r in sample_step_results:
        assert f"{r.step.name}={r.status.name}" in summary


def test_verification_report_summary_failure_with_steps(failed_report, sample_step_results):
    summary = failed_report.summary()

    assert summary.startswith("FAILED (")
    for r in sample_step_results:
        assert f"{r.step.name}={r.status.name}" in summary


def test_verification_report_summary_with_no_steps_success():
    report = a.VerificationReport(task_id="no-steps", is_successful=True, step_results=[])

    summary = report.summary()

    assert summary == "SUCCESS ()"


def test_verification_report_summary_with_no_steps_failure():
    report = a.VerificationReport(task_id="no-steps", is_successful=False, step_results=[])

    summary = report.summary()

    assert summary == "FAILED ()"


def test_pull_request_info_dataclass_fields():
    pr_info = a.PullRequestInfo(
        pr_id=42,
        exists=True,
        is_merged=False,
        ci_checks_passed=True,
    )

    assert pr_info.pr_id == 42
    assert pr_info.exists is True
    assert pr_info.is_merged is False
    assert pr_info.ci_checks_passed is True


def test_deployment_info_dataclass_fields_and_default_details():
    deployment = a.DeploymentInfo(
        pr_id=10,
        succeeded=True,
        logs_clean=False,
    )

    assert deployment.pr_id == 10
    assert deployment.succeeded is True
    assert deployment.logs_clean is False
    # default value
    assert deployment.details == ""


def test_task_dataclass_fields():
    task = a.Task(
        task_id="task-1",
        pr_id=5,
        service_url="https://example.com/health",
    )

    assert task.task_id == "task-1"
    assert task.pr_id == 5
    assert task.service_url == "https://example.com/health"


# --- Protocols (runtime_checkable behavior) ------------------------------------


class DummyPullRequestClient:
    def __init__(self, info: a.PullRequestInfo):
        self._info = info

    def get_pull_request(self, pr_id: int) -> a.PullRequestInfo:
        return self._info


class DummyDeploymentClient:
    def __init__(self, info: a.DeploymentInfo):
        self._info = info

    def get_deployment_info(self, pr_id: int) -> a.DeploymentInfo:
        return self._info


class DummyHealthCheckClient:
    def __init__(self, result: bool):
        self._result = result

    def check_health(self, url: str, timeout_seconds: float) -> bool:
        return self._result


def test_pull_request_client_protocol_runtime_checkable():
    dummy = DummyPullRequestClient(
        a.PullRequestInfo(
            pr_id=1,
            exists=True,
            is_merged=True,
            ci_checks_passed=True,
        )
    )

    assert isinstance(dummy, a.PullRequestClient)


def test_deployment_client_protocol_runtime_checkable():
    dummy = DummyDeploymentClient(
        a.DeploymentInfo(
            pr_id=1,
            succeeded=True,
            logs_clean=True,
            details="ok",
        )
    )

    assert isinstance(dummy, a.DeploymentClient)


def test_health_check_client_protocol_runtime_checkable():
    dummy = DummyHealthCheckClient(result=True)

    assert isinstance(dummy, a.HealthCheckClient)


# --- InMemoryPullRequestClient -------------------------------------------------


@pytest.fixture
def in_memory_pr_client(pr_store):
    return a.InMemoryPullRequestClient(pr_store)


def test_in_memory_pull_request_client_returns_existing_pr(in_memory_pr_client, pr_store):
    pr_id = 1

    result = in_memory_pr_client.get_pull_request(pr_id)

    # Should return semantically the same object as stored
    assert result == pr_store[pr_id]
    # Ensure returned object has expected fields
    assert result.pr_id == pr_id
    assert result.exists is True
    assert result.is_merged is True
    assert result.ci_checks_passed is True


def test_in_memory_pull_request_client_missing_pr_raises_verification_error(in_memory_pr_client, pr_store):
    missing_pr_id = max(pr_store.keys()) + 1

    with pytest.raises(a.VerificationError):
        in_memory_pr_client.get_pull_request(missing_pr_id)