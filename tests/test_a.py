import pytest
from unittest.mock import MagicMock

import a


@pytest.fixture
def sample_task() -> a.Task:
    return a.Task(task_id="task-123", pr_id="42", service_url="http://service.test")


@pytest.fixture
def mock_clients():
    vc = MagicMock(spec=a.VersionControlClient)
    ci = MagicMock(spec=a.CIChecksClient)
    deploy = MagicMock(spec=a.DeploymentClient)
    health = MagicMock(spec=a.HealthCheckClient)
    return vc, ci, deploy, health


@pytest.fixture
def task_verifier(mock_clients) -> a.TaskVerifier:
    vc, ci, deploy, health = mock_clients
    return a.TaskVerifier(
        version_control_client=vc,
        ci_checks_client=ci,
        deployment_client=deploy,
        health_check_client=health,
    )


def test_constants_values():
    assert a.DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS == 5.0
    assert a.DEFAULT_HTTP_RETRY_DELAY_SECONDS == 0.5
    assert a.MAX_HTTP_RETRIES == 3


def test_failure_detail_dataclass_fields():
    detail = a.FailureDetail(
        code=a.VerificationErrorCode.CI_CHECKS_FAILED,
        message="Some CI checks failed",
    )
    assert detail.code is a.VerificationErrorCode.CI_CHECKS_FAILED
    assert detail.message == "Some CI checks failed"


def test_verification_exception_stores_failures():
    failures = [
        a.FailureDetail(a.VerificationErrorCode.PR_NOT_FOUND, "No PR"),
        a.FailureDetail(a.VerificationErrorCode.CI_CHECKS_FAILED, "CI failed"),
    ]
    exc = a.VerificationException("summary", failures)
    assert isinstance(exc, Exception)
    assert exc.failures == failures
    assert str(exc) == "summary"


def test_verification_exception_default_failures_is_empty_list():
    exc = a.VerificationException("msg")
    assert exc.failures == []
    # ensure it's a real list that can be mutated independently
    exc.failures.append(
        a.FailureDetail(a.VerificationErrorCode.UNKNOWN_ERROR, "error")
    )
    exc2 = a.VerificationException("msg2")
    assert exc2.failures == []


def test_verification_result_require_success_no_failures():
    result = a.VerificationResult(is_success=True)
    # Should not raise
    result.require_success()


def test_verification_result_require_success_raises_with_message_and_failures():
    failures = [
        a.FailureDetail(
            a.VerificationErrorCode.CI_CHECKS_FAILED, "CI failed for PR 1"
        ),
        a.FailureDetail(
            a.VerificationErrorCode.DEPLOYMENT_FAILED,
            "Deployment failed for PR 1",
        ),
    ]
    result = a.VerificationResult(is_success=False, failures=failures)

    with pytest.raises(a.VerificationException) as excinfo:
        result.require_success()

    exc = excinfo.value
    # Message should contain both codes and messages joined by semicolon
    msg = str(exc)
    assert "CI_CHECKS_FAILED: CI failed for PR 1" in msg
    assert "DEPLOYMENT_FAILED: Deployment failed for PR 1" in msg
    assert "; " in msg
    assert exc.failures == failures


def test_task_dataclass_fields():
    task = a.Task(task_id="t1", pr_id="123", service_url="http://svc")
    assert task.task_id == "t1"
    assert task.pr_id == "123"
    assert task.service_url == "http://svc"


def test_task_verifier_all_checks_pass(task_verifier, mock_clients, sample_task):
    vc, ci, deploy, health = mock_clients
    vc.pr_exists.return_value = True
    vc.is_pr_merged.return_value = True
    ci.all_checks_passed.return_value = True
    deploy.deployment_succeeded.return_value = True
    health.check_health.return_value = True

    result = task_verifier.verify_task(sample_task)

    assert result.is_success is True
    assert result.failures == []
    vc.pr_exists.assert_called_once_with(sample_task.pr_id)
    vc.is_pr_merged.assert_called_once_with(sample_task.pr_id)
    ci.all_checks_passed.assert_called_once_with(sample_task.pr_id)
    deploy.deployment_succeeded.assert_called_once_with(sample_task.pr_id)
    health.check_health.assert_called_once_with(sample_task.service_url)


def test_task_verifier_pr_not_found_only_failure(task_verifier, mock_clients, sample_task):
    vc, ci, deploy, health = mock_clients
    vc.pr_exists.return_value = False
    ci.all_checks_passed.return_value = True
    deploy.deployment_succeeded.return_value = True
    health.check_health.return_value = True

    result = task_verifier.verify_task(sample_task)

    assert result.is_success is False
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.code is a.VerificationErrorCode.PR_NOT_FOUND
    assert "does not exist" in failure.message
    vc.pr_exists.assert_called_once_with(sample_task.pr_id)
    vc.is_pr_merged.assert_not_called()


def test_task_verifier_pr_not_merged_only_failure(task_verifier, mock_clients, sample_task):
    vc, ci, deploy, health = mock_clients
    vc.pr_exists.return_value = True
    vc.is_pr_merged.return_value = False
    ci.all_checks_passed.return_value = True
    deploy.deployment_succeeded.return_value = True
    health.check_health.return_value = True

    result = task_verifier.verify_task(sample_task)

    assert result.is_success is False
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.code is a.VerificationErrorCode.PR_NOT_MERGED
    assert "is not merged" in failure.message


def test_task_verifier_ci_checks_failed_only_failure(task_verifier, mock_clients, sample_task):
    vc, ci, deploy, health = mock_clients
    vc.pr_exists.return_value = True
    vc.is_pr_merged.return_value = True
    ci.all_checks_passed.return_value = False
    deploy.deployment_succeeded.return_value = True
    health.check_health.return_value = True

    result = task_verifier.verify_task(sample_task)

    assert result.is_success is False
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.code is a.VerificationErrorCode.CI_CHECKS_FAILED
    assert "CI checks failed" in failure.message


def test_task_verifier_deployment_failed_with_logs_snippet(task_verifier, mock_clients, sample_task):
    vc, ci, deploy, health = mock_clients
    vc.pr_exists.return_value = True
    vc.is_pr_merged.return_value = True
    ci.all_checks_passed.return_value = True
    deploy.deployment_succeeded.return_value = False
    long_logs = "x" * 600
    deploy.get_deployment_logs.return_value = long_logs
    health.check_health.return_value = True

    result = task_verifier.verify_task(sample_task)

    assert result.is_success is False
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.code is a.VerificationErrorCode.DEPLOYMENT_FAILED
    assert "Deployment failed for PR" in failure.message
    assert "Logs snippet:" in failure.message
    # Ensure logs are truncated to 500 characters
    prefix = "Logs snippet: "
    start = failure.message.index(prefix) + len(prefix)
    end = failure.message.rindex("...")
    snippet = failure.message[start:end]
    assert len(snippet) == 500
    assert snippet == long_logs[:500]


def test_task_verifier_deployment_failed_logs_unavailable(task_verifier, mock_clients, sample_task):
    vc, ci, deploy, health = mock_clients
    vc.pr_exists.return_value = True
    vc.is_pr_merged.return_value = True
    ci.all_checks_passed.return_value = True
    deploy.deployment_succeeded.return_value = False
    deploy.get_deployment_logs.side_effect = RuntimeError("log fetch error")
    health.check_health.return_value = True

    result = task_verifier.verify_task(sample_task)

    assert result.is_success is False
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.code is a.VerificationErrorCode.DEPLOYMENT_FAILED
    assert "<unable to fetch logs: log fetch error>" in failure.message


def test_task_verifier_health_check_failed_only_failure(task_verifier, mock_clients, sample_task):
    vc, ci, deploy, health = mock_clients
    vc.pr_exists.return_value = True
    vc.is_pr_merged.return_value = True
    ci.all_checks_passed.return_value = True
    deploy.deployment_succeeded.return_value = True
    health.check_health.return_value = False

    result = task_verifier.verify_task(sample_task)

    assert result.is_success is False
    assert len(result.failures) == 1