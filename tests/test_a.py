import logging
from datetime import datetime, timezone, timedelta
from io import BytesIO
from unittest.mock import Mock, MagicMock, patch

import pytest

import a


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_stage_results():
    return [
        a.StageResult(
            stage=a.VerificationStage.PR,
            status=a.VerificationStatus.SUCCESS,
            details="pr ok",
        ),
        a.StageResult(
            stage=a.VerificationStage.CI,
            status=a.VerificationStatus.FAILURE,
            details="ci failed",
        ),
        a.StageResult(
            stage=a.VerificationStage.DEPLOYMENT,
            status=a.VerificationStatus.SKIPPED,
            details="not deployed",
        ),
    ]


@pytest.fixture
def http_health_checker():
    return a.HttpHealthChecker(timeout_seconds=1)


# ---------------------------------------------------------------------------
# Logger and constants
# ---------------------------------------------------------------------------


def test_logger_is_configured_with_correct_name_and_level():
    assert a.logger.name == a.LOGGER_NAME
    # Level could be overridden externally; ensure at least default is not higher
    assert a.logger.level == a.DEFAULT_LOG_LEVEL


def test_constants_have_expected_values():
    assert isinstance(a.HEALTHCHECK_TIMEOUT_SECONDS, int)
    assert a.HEALTHCHECK_TIMEOUT_SECONDS > 0
    assert isinstance(a.EVIDENCE_MAX_LENGTH, int)
    assert a.EVIDENCE_MAX_LENGTH > 0
    assert isinstance(a.DEFAULT_USER_AGENT, str)
    assert "TaskVerification" in a.DEFAULT_USER_AGENT


# ---------------------------------------------------------------------------
# Enums and data models
# ---------------------------------------------------------------------------


def test_verification_stage_enum_members_and_values():
    assert a.VerificationStage.PR.value == "pr"
    assert a.VerificationStage.CI.value == "ci"
    assert a.VerificationStage.DEPLOYMENT.value == "deployment"
    assert a.VerificationStage.HEALTH.value == "health"


def test_verification_status_enum_members_and_values():
    assert a.VerificationStatus.SUCCESS.value == "success"
    assert a.VerificationStatus.FAILURE.value == "failure"
    assert a.VerificationStatus.SKIPPED.value == "skipped"


def test_stage_result_default_timestamp_is_utc_and_recent():
    before = datetime.now(timezone.utc)
    sr = a.StageResult(
        stage=a.VerificationStage.PR,
        status=a.VerificationStatus.SUCCESS,
        details="ok",
    )
    after = datetime.now(timezone.utc)

    assert isinstance(sr.timestamp, datetime)
    assert sr.timestamp.tzinfo == timezone.utc
    # Timestamp should be between before and after (with small tolerance)
    assert before - timedelta(seconds=1) <= sr.timestamp <= after + timedelta(
        seconds=1
    )


def test_verification_result_getters_filter_by_status(sample_stage_results):
    vr = a.VerificationResult(overall_success=False, stage_results=sample_stage_results)

    failed = vr.get_failed_stages()
    skipped = vr.get_skipped_stages()
    successful = vr.get_successful_stages()

    assert failed == [sample_stage_results[1]]
    assert skipped == [sample_stage_results[2]]
    assert successful == [sample_stage_results[0]]


def test_verification_result_getters_with_no_stages_return_empty_lists():
    vr = a.VerificationResult(overall_success=True, stage_results=[])

    assert vr.get_failed_stages() == []
    assert vr.get_skipped_stages() == []
    assert vr.get_successful_stages() == []


# ---------------------------------------------------------------------------
# InMemoryPRClient
# ---------------------------------------------------------------------------


def test_in_memory_pr_client_merged_returns_true_and_evidence():
    client = a.InMemoryPRClient()
    pr_id = "123"
    client.mark_merged(pr_id)

    merged, msg, evidence = client.is_pr_merged(pr_id)

    assert merged is True
    assert pr_id in msg
    assert evidence is not None
    assert evidence["pr_id"] == pr_id
    assert evidence["status"] == "merged"
    assert evidence["source"] == "in-memory"


def test_in_memory_pr_client_not_merged_returns_false_and_evidence():
    client = a.InMemoryPRClient(merged_pr_ids={"999"})
    pr_id = "123"

    merged, msg, evidence = client.is_pr_merged(pr_id)

    assert merged is False
    assert pr_id in msg
    assert "not merged" in msg
    assert evidence is not None
    assert evidence["pr_id"] == pr_id
    assert evidence["status"] == "not_merged"
    assert evidence["source"] == "in-memory"


# ---------------------------------------------------------------------------
# InMemoryCIClient
# ---------------------------------------------------------------------------


def test_in_memory_ci_client_passing_returns_true_and_evidence():
    client = a.InMemoryCIClient()
    pr_id = "42"
    client.mark_ci_passed(pr_id)

    ok, msg, evidence = client.have_all_checks_passed(pr_id)

    assert ok is True
    assert pr_id in msg
    assert "All CI checks passed" in msg
    assert evidence is not None
    assert evidence["pr_id"] == pr_id
    assert evidence["ci_status"] == "passed"
    assert evidence["source"] == "in-memory"


def test_in_memory_ci_client_not_passing_returns_false_and_evidence():
    client = a.InMemoryCIClient(passing_pr_ids={"99"})
    pr_id = "42"

    ok, msg, evidence = client.have_all_checks_passed(pr_id)

    assert ok is False
    assert pr_id in msg
    assert "have not passed" in msg
    assert evidence is not None
    assert evidence["pr_id"] == pr_id
    assert evidence["ci_status"] == "failed"
    assert evidence["source"] == "in-memory"


# ---------------------------------------------------------------------------
# InMemoryDeploymentClient
# ---------------------------------------------------------------------------


def test_in_memory_deployment_client_successful_returns_true_and_evidence():
    client = a.InMemoryDeploymentClient()
    deployment_id = "dep-1"
    client.mark_successful(deployment_id)

    ok, msg, evidence = client.is_deployment_successful(deployment_id)

    assert ok is True
    assert deployment_id in msg
    assert "succeeded" in msg
    assert evidence is not None
    assert evidence["deployment_id"] == deployment_id
    assert evidence["deployment_status"] == "successful"
    assert evidence["source"] == "in-memory"


def test_in_memory_deployment_client_unsuccessful_returns_false_and_evidence():
    client = a.InMemoryDeploymentClient(successful_deployments={"dep-99"})
    deployment_id = "dep-1"

    ok, msg, evidence = client.is_deployment_successful(deployment_id)

    assert ok is False
    assert deployment_id in msg
    assert "did not succeed" in msg
    assert evidence is not None
    assert evidence["deployment_id"] == deployment_id
    assert evidence["deployment_status"] == "failed"
    assert evidence["source"] == "in-memory"


# ---------------------------------------------------------------------------
# HttpHealthChecker - success and non-200 paths
# ---------------------------------------------------------------------------


@patch("a.request.urlopen")
def test_http_health_checker_success_200_returns_true_and_evidence(
    mock_urlopen, http_health_checker
):
    url = "http://example.com/health"
    body = b"OK"

    resp = MagicMock()
    resp.getcode.return_value = 200
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = None
    mock_urlopen.return_value = resp

    success, msg, evidence = http_health_checker.is_healthy(url)

    assert success is True
    assert "Health check passed" in msg
    assert url in msg
    assert evidence["url"] == url
    assert evidence["status_code"] == 200
    assert evidence["body_snippet"] == body.decode("utf-8")
    # Ensure read size is limited
    resp.read.assert_called_once_with(a.EVIDENCE_MAX_LENGTH)

    # Ensure User-Agent header is set and timeout used
    assert mock_urlopen.call_count == 1
    req_arg, = mock_urlopen.call_args[0]
    timeout_kw = mock_urlopen.call_args[1]["timeout"]
    assert timeout_kw == 1
    # Request object has get_header method
    assert req_arg.get_header("User-Agent") == a.DEFAULT_USER_AGENT


@patch("a.request