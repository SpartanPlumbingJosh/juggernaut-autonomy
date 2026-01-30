import datetime
import socket
from unittest import mock

import pytest

import a


# ---- Enums and constants ----


def test_verification_step_enum_values():
    assert a.VerificationStep.PR_MERGED.value == "pr_merged"
    assert a.VerificationStep.CI_PASSED.value == "ci_passed"
    assert a.VerificationStep.DEPLOYMENT_SUCCEEDED.value == "deployment_succeeded"
    assert a.VerificationStep.HEALTH_CHECK_PASSED.value == "health_check_passed"


def test_step_status_enum_values():
    assert a.StepStatus.SUCCESS.value == "success"
    assert a.StepStatus.FAILURE.value == "failure"
    assert a.StepStatus.SKIPPED.value == "skipped"
    assert a.StepStatus.ERROR.value == "error"


# ---- Dataclasses ----


def test_step_result_creation_and_defaults():
    step = a.StepResult(
        step=a.VerificationStep.PR_MERGED,
        status=a.StepStatus.SUCCESS,
        message="All good",
    )
    assert step.step is a.VerificationStep.PR_MERGED
    assert step.status is a.StepStatus.SUCCESS
    assert step.message == "All good