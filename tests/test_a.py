import logging

import pytest

from a import (
    DEFAULT_DEPLOYMENT_LOG_CLEAN_INDICATOR,
    DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS,
    CIStatusVerifier,
    DeploymentVerifier,
    HealthCheckVerifier,
    InMemoryCIStatusVerifier,
    InMemoryDeploymentVerifier,
    InMemoryHealthCheckVerifier,
    InMemoryPullRequestVerifier,
    PullRequestVerifier,
    StageVerificationResult,
    Task,
    TaskStatus,
    TaskVerificationResult,
    VerificationError,
    VerificationStage,
)


@pytest.fixture
def sample_stage_success():
    return StageVerificationResult(
        stage=VerificationStage.PR_MERGED,
        success=True,
        detail="ok",
    )


@pytest.fixture
def sample_stage_failure():
    return StageVerificationResult(
        stage=VerificationStage.CI_CHECKS_PASSED,
        success=False,
        detail="failed",
    )


@pytest.fixture
def sample_stage_skipped():
    return StageVerificationResult(
        stage=VerificationStage.DEPLOYMENT_SUCCEEDED,
        success=False,
        detail="skipped reason",
        skipped=True,
    )


def test_constants_values():
    assert isinstance(DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS, float)
    assert DEFAULT_HEALTHCHECK_TIMEOUT_SECONDS == 5.0
    assert DEFAULT_DEPLOYMENT_LOG_CLEAN_INDICATOR == "BUILD_SUCCEEDED"


def test_task_status_enum_values():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.IN_PROGRESS.value == "in_progress"
    assert TaskStatus.COMPLETED.value == "completed"
    assert TaskStatus.BLOCKED.value == "blocked"


def test_verification_stage_enum_values():
    assert VerificationStage.PR_MERGED.value == "pr_merged"
    assert VerificationStage.CI_CHECKS_PASSED.value == "ci_checks_passed"
    assert VerificationStage.DEPLOYMENT_SUCCEEDED.value == "deployment_succeeded"
    assert VerificationStage.HEALTHCHECK_PASSED.value == "healthcheck_passed"


def test_stage_verification_result_human_readable_success(sample_stage_success):
    result = sample_stage_success
    text = result.human_readable()
    assert text == f"[{result.stage.name}] OK: {result.detail}"


def test_stage_verification_result_human_readable_failure(sample_stage_failure):
    result = sample_stage_failure
    text = result.human_readable()
    assert text == f"[{result.stage.name}] FAILED: {result.detail}"


def test_stage_verification_result_human_readable_skipped_overrides_success():
    result = StageVerificationResult(
        stage=VerificationStage.HEALTHCHECK_PASSED,
        success=True,
        detail="irrelevant",
        skipped=True,
    )
    text = result.human_readable()
    assert text == f"[{result.stage.name}] SKIPPED: {result.detail}"


def test_task_verification_result_success_all_pass(sample_stage_success):
    tvr = TaskVerificationResult(
        task_id="t1",
        stage_results={
            sample_stage_success.stage: sample_stage_success,
        },
    )
    assert tvr.success is True
    assert tvr.failures() == {}


def test_task_verification_result_success_ignores_skipped(sample_stage_success, sample_stage_skipped):
    tvr = TaskVerificationResult(
        task_id="t2",
        stage_results={
            sample_stage_success.stage: sample_stage_success,
            sample_stage_skipped.stage: sample_stage_skipped,
        },
    )
    assert tvr.success is True
    assert tvr.failures() == {}


def test_task_verification_result_failure_when_any_non_skipped_fails(
    sample_stage_success, sample_stage_failure, sample_stage_skipped
):
    tvr = TaskVerificationResult(
        task_id="t3",
        stage_results={
            sample_stage_success.stage: sample_stage_success,
            sample_stage_failure.stage: sample_stage_failure,
            sample_stage_skipped.stage: sample_stage_skipped,
        },
    )
    assert tvr.success is False
    failures = tvr.failures()
    assert list(failures.keys()) == [sample_stage_failure.stage]
    assert failures[sample_stage_failure.stage] is sample_stage_failure


def test_task_verification_result_success_with_no_stages():
    tvr = TaskVerificationResult(task_id="empty")
    assert tvr.stage_results == {}
    assert tvr.success is True
    assert tvr.failures() == {}


def test_task_verification_result_summary_joins_human_readable_lines(
    sample_stage_success, sample_stage_failure
):
    tvr = TaskVerificationResult(
        task_id="t4",
        stage_results={
            sample_stage_success.stage: sample_stage_success,
            sample_stage_failure.stage: sample_stage_failure,
        },
    )
    summary = tvr.summary()
    expected_lines = [
        sample_stage_success.human_readable(),
        sample_stage_failure.human_readable(),
    ]
    assert summary == "\n".join(expected_lines)


def test_task_dataclass_defaults_and_fields():
    task = Task(
        id="1",
        repository="org/repo",
        pr_number=42,
        environment="staging",
        healthcheck_url="https://example.com/hc",
    )
    assert task.status == TaskStatus.PENDING
    assert task.last_verification is None
    assert task.id == "1"
    assert task.repository == "org/repo"
    assert task.pr_number == 42
    assert task.environment == "staging"
    assert task.healthcheck_url == "https://example.com/hc"


def test_task_can_store_last_verification(sample_stage_success):
    tvr = TaskVerificationResult(
        task_id="1", stage_results={sample_stage_success.stage: sample_stage_success}
    )
    task = Task(
        id="1",
        repository="org/repo",
        pr_number=1,
        environment="prod",
        healthcheck_url="url",
        last_verification=tvr,
    )
    assert task.last_verification is tvr
    assert task.last_verification.success is True


def test_verification_error_builds_message_and_attributes():
    failure_reasons = {
        VerificationStage.PR_MERGED: "not merged",
        VerificationStage.CI_CHECKS_PASSED: "ci failed",
    }
    err = VerificationError(task_id="t1", failure_reasons=failure_reasons)
    assert err.task_id == "t1"
    assert err.failure_reasons is failure_reasons
    message = str(err)
    assert "Task 't1' failed verification and cannot be marked complete." in message
    assert "- PR_MERGED: not merged" in message
    assert "- CI_CHECKS_PASSED: ci failed" in message


def test_pull_request_verifier_is_abstract():
    with pytest.raises(TypeError):
        PullRequestVerifier()  # type: ignore[abstract]


def test_ci_status_verifier_is_abstract():
    with pytest.raises(TypeError):
        CIStatusVerifier()  # type: ignore[abstract]


def test_deployment_verifier_is_abstract():
    with pytest.raises(TypeError):
        DeploymentVerifier()  # type: ignore[abstract]


def test_healthcheck_verifier_is_abstract():
    with pytest.raises(TypeError):
        HealthCheckVerifier()  # type: ignore[abstract]


def test_in_memory_pull_request_verifier_reports_merged(caplog):
    repo = "org/repo"
    pr = 123
    verifier = InMemoryPullRequestVerifier(merged_prs=[(repo, pr)])

    caplog.set_level(logging.DEBUG)
    result = verifier.verify_merged(repo, pr)

    assert result.stage == VerificationStage.PR_MERGED
    assert result.success is True
    assert result.detail == "Pull request is marked as merged."
    assert any(
        "Verifying PR merged status" in rec.getMessage() for rec in caplog.records
    )


def test_in_memory_pull_request_verifier_reports_not_merged(caplog):
    repo = "org/repo"
    pr = 123
    verifier = InMemoryPullRequestVerifier()

    caplog.set_level(logging.DEBUG)
    result = verifier.verify_merged(repo, pr)

    assert result.stage == VerificationStage.PR_MERGED
    assert result.success is False
    assert result.detail == "Pull request is not merged."
    assert any(
        "Verifying PR merged status" in rec.getMessage() for rec in caplog.records
    )


def test_in_memory_ci_status_verifier_reports_passing(caplog):
    repo = "org/repo"
    pr = 10
    verifier = InMemoryCIStatusVerifier(passing_prs=[(repo, pr)])

    caplog.set_level(logging.DEBUG)
    result = verifier.verify_checks_passed(repo, pr)

    assert result.stage == VerificationStage.CI_CHECKS_PASSED
    assert result.success is True
    assert (
        result.detail
        == "All CI checks (lint, typecheck, tests) have passed."
    )
    assert any("Verifying CI checks" in rec.getMessage() for rec in caplog.records)


def test_in_memory_ci_status_verifier_reports_not_passing():
    repo = "org/repo"
    pr = 10
    verifier = InMemoryCIStatusVerifier()

    result = verifier.verify_checks_passed(repo, pr)

    assert result.stage == VerificationStage.CI_CHECKS_PASSED
    assert result.success is False
    assert result.detail == "CI checks have not all passed."


def test_in_memory_deployment_verifier_reports_deployed(caplog):
    env = "prod"
    repo = "org/repo"
    pr = 1
    verifier = InMemoryDeploymentVerifier(
        successful_deployments=[(env, repo, pr)]
    )

    caplog.set_level(logging.DEBUG)
    result = verifier.verify_deployment_succeeded(env, repo, pr)

    assert result.stage == VerificationStage.DEPLOY