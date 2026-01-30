import pytest
import logging
from types import SimpleNamespace

import a


@pytest.fixture
def sample_task() -> a.Task:
    return a.Task(
        task_id="task-1",
        repository="org/repo",
        pull_request_number=42,
        service_name="svc",
        healthcheck_url="http://example/health",
    )


@pytest.fixture
def in_memory_repo() -> a.InMemoryTaskRepository:
    return a.InMemoryTaskRepository()


def test_taskstatus_and_verificationstep_enum_values():
    assert a.TaskStatus.PENDING.value == "PENDING"
    assert a.TaskStatus.COMPLETED.value == "COMPLETED"
    assert a.TaskStatus.VERIFICATION_FAILED.value == "VERIFICATION_FAILED"

    assert a.VerificationStep.PR_MERGED.value == "PR_MERGED"
    assert a.VerificationStep.CI_CHECKS.value == "CI_CHECKS"
    assert a.VerificationStep.DEPLOYMENT.value == "DEPLOYMENT"
    assert a.VerificationStep.HEALTH_CHECK.value == "HEALTH_CHECK"


def test_dataclass_defaults_are_independent_for_tasks():
    t1 = a.Task(
        task_id="t1",
        repository="org/repo",
        pull_request_number=1,
        service_name="svc",
        healthcheck_url="u",
    )
    t2 = a.Task(
        task_id="t2",
        repository="org/repo",
        pull_request_number=2,
        service_name="svc",
        healthcheck_url="u",
    )

    # Mutate t1's lists/dicts and ensure t2 is unaffected
    t1.last_verification_evidence["foo"] = "bar"
    t1.last_verification_failures.append(
        a.VerificationFailure(step=a.VerificationStep.CI_CHECKS, reason="fail")
    )

    assert t2.last_verification_evidence == {}
    assert t2.last_verification_failures == []


def test_verificationfailure_default_details_are_independent():
    vf1 = a.VerificationFailure(step=a.VerificationStep.DEPLOYMENT, reason="r1")
    vf2 = a.VerificationFailure(step=a.VerificationStep.DEPLOYMENT, reason="r2")

    vf1.details["k"] = "v"
    assert vf2.details == {}
    assert vf1.details == {"k": "v"}


def test_verification_result_and_related_dataclasses_hold_values():
    failures = [a.VerificationFailure(step=a.VerificationStep.PR_MERGED, reason="not merged")]
    evidence = {"pr": {"number": 1}}
    vr = a.VerificationResult(task_id="tid", success=False, failures=failures, evidence=evidence)

    assert vr.task_id == "tid"
    assert not vr.success
    assert vr.failures is failures
    assert vr.evidence is evidence


def test_constants_have_expected_types_and_values():
    assert isinstance(a.HEALTHCHECK_DEFAULT_TIMEOUT_SECONDS, float)
    assert a.HEALTHCHECK_DEFAULT_TIMEOUT_SECONDS == 5.0

    assert isinstance(a.LOG_SNIPPET_MAX_LENGTH, int)
    assert a.LOG_SNIPPET_MAX_LENGTH == 500


def test_task_not_found_error_message_and_attribute():
    ex = a.TaskNotFoundError("missing-id")
    assert "missing-id" in str(ex)
    assert getattr(ex, "task_id") == "missing-id"
    assert isinstance(ex, a.TaskVerificationError)


def test_external_service_error_preserves_original_exception_and_service_name():
    original = ValueError("boom")
    ex = a.ExternalServiceError  # intentionally get class to construct below
    err = a.ExternalServiceError("MyService", original)
    assert "MyService" in str(err)
    assert "boom" in str(err)
    assert err.service_name == "MyService"
    assert err.original_exception is original
    assert isinstance(err, a.TaskVerificationError)


def test_abstract_service_methods_raise_not_implemented_error():
    # These classes are intended as interfaces that raise NotImplementedError if called.
    with pytest.raises(NotImplementedError):
        a.PullRequestService().get_pull_request("repo", 1)

    with pytest.raises(NotImplementedError):
        a.CIService().get_ci_result("repo", 1)

    with pytest.raises(NotImplementedError):
        a.DeploymentService().get_latest_deployment_status("svc")

    with pytest.raises(NotImplementedError):
        a.HealthCheckService().run_health_check("http://x", 1.0)

    with pytest.raises(NotImplementedError):
        a.TaskRepository().get_task("id")

    with pytest.raises(NotImplementedError):
        a.TaskRepository().save_task(a.Task(
            task_id="t",
            repository="r",
            pull_request_number=1,
            service_name="s",
            healthcheck_url="u"
        ))


def test_inmemory_repository_add_get_and_save_behaviour(in_memory_repo, sample_task):
    # Add a task and retrieve it
    in_memory_repo.add_task(sample_task)
    retrieved = in_memory_repo.get_task("task-1")
    assert retrieved is sample_task

    # Update status and save
    sample_task.status = a.TaskStatus.COMPLETED
    in_memory_repo.save_task(sample_task)
    retrieved2 = in_memory_repo.get_task("task-1")
    assert retrieved2.status == a.TaskStatus.COMPLETED

    # Ensure saving replaces stored instance
    sample_task2 = a.Task(
        task_id="task-1",
        repository="org/repo",
        pull_request_number=42,
        service_name="svc",
        healthcheck_url="http://example/health",
        status=a.TaskStatus.VERIFICATION_FAILED,
    )
    in_memory_repo.save_task(sample_task2)
    assert in_memory_repo.get_task("task-1") is sample_task2


def test_inmemory_repository_get_task_raises_and_logs_missing(caplog, in_memory_repo):
    caplog.set_level(logging.WARNING)
    missing_id = "does-not-exist"
    with pytest.raises(a.TaskNotFoundError) as excinfo:
        in_memory_repo.get_task(missing_id)

    # Exception carries the id
    assert excinfo.value.task_id == missing_id

    # A warning was logged
    assert any(
        missing_id in rec.getMessage() and rec.levelno == logging.WARNING for rec in caplog.records
    )


def test_fake_pull_request_service_returns_entry_and_none_for_missing():
    pr_info = a.PullRequestInfo(number=10, is_merged=True, state="merged", url="http://pr")
    svc = a.FakePullRequestService({("org/repo", 10): pr_info})

    got = svc.get_pull_request("org/repo", 10)
    assert got is pr_info

    none = svc.get_pull_request("org/repo", 11)
    assert none is None


def test_fake_ci_service_returns_entry_and_none_for_missing():
    ci_result = a.CICheckResult(all_passed=True, failing_checks=[], raw_status={"ok": True})
    svc = a.FakeCIService({("org/repo", 5): ci_result})

    assert svc.get_ci_result("org/repo", 5) is ci_result
    assert svc.get_ci_result("org/repo", 6) is None


def test_fake_deployment_service_returns_entry_and_none_for_missing():
    d = a.DeploymentStatus(service_name="svc", success=True, provider="P", logs_snippet="log")
    svc = a.FakeDeploymentService({"svc": d})

    assert svc.get_latest_deployment_status("svc") is d
    assert svc.get_latest_deployment_status("unknown") is None


def test_fake_healthcheck_service_has_stored_mapping_and_run_returns_none_by_default():
    # Note: The implementation in the module contains only a docstring for run_health_check,
    # therefore calling it will return None. The test documents that current behavior.
    health_map = {
        "http://ok": a.HealthCheckStatus(is_healthy=True, status_code=200, error_message=None),
        "http://bad": a.HealthCheckStatus(is_healthy=False, status_code=500, error_message="err"),
    }
    svc = a.FakeHealthCheckService(health_map)

    # The mapping should be stored
    assert svc._health is health_map

    # The current implementation's run_health_check contains only a docstring and returns None.
    assert svc.run_health_check("http://ok", a.HEALTHCHECK_DEFAULT_TIMEOUT_SECONDS) is None
    assert svc.run_health_check("http://not-in-map", a.HEALTHCHECK_DEFAULT_TIMEOUT_SECONDS) is None


def test_dataclass_equality_and_repr_examples():
    pr1 = a.PullRequestInfo(number=1, is_merged=False, state="open", url="u1")
    pr2 = a.PullRequestInfo(number=1, is_merged=False, state="open", url="u1")
    assert pr1 == pr2
    # repr should contain class name and field
    r = repr(pr1)
    assert "PullRequestInfo" in r and "number=1" in r


def test_task_defaults_and_custom_fields():
    t = a.Task(
        task_id="tid",
        repository="r",
        pull_request_number=7,
        service_name="s",
        healthcheck_url="http://h",
        status=a.TaskStatus.PENDING,
        last_verification_evidence={"a": 1},
        last_verification_failures=[a.VerificationFailure(step=a.VerificationStep.CI_CHECKS, reason="r")],
    )

    assert t.task_id == "tid"
    assert t.status == a.TaskStatus.PENDING
    assert t.last_verification_evidence == {"a": 1}
    assert len(t.last_verification_failures) == 1
    assert isinstance(t.last_verification_failures[0], a.VerificationFailure)