import pytest
from datetime import datetime, timezone

import escalationresolver as er


@pytest.fixture
def sample_datetime() -> datetime:
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_escalation(sample_datetime: datetime) -> er.Escalation:
    return er.Escalation(
        id="esc-123",
        created_at=sample_datetime,
        updated_at=sample_datetime,
        status=er.EscalationStatus.PENDING,
        risk_level=er.EscalationRiskLevel.MEDIUM,
        metadata={"key": "value"},
        retry_count=1,
        assigned_worker_id="worker-1",
        resolved_at=None,
        resolution_reason=None,
        manual_only=False,
    )


def test_logger_is_module_logger():
    assert isinstance(er.logger.name, str)
    # The logger should be named after the module
    assert er.logger.name.endswith("escalationresolver")


def test_constants_values():
    assert er.LOW_RISK_AUTO_APPROVAL_TIMEOUT_MINUTES == 15
    assert er.AUTO_RETRY_MAX_ATTEMPTS == 3
    assert er.AUTO_REASSIGN_TIMEOUT_MINUTES == 30
    assert er.SLA_TARGET_SECONDS == 60 * 60
    assert er.DASHBOARD_DEFAULT_LOOKBACK_HOURS == 24
    assert er.DEFAULT_RESOLUTION_LOOP_INTERVAL_SECONDS == 30


def test_escalation_status_enum_members_and_values():
    assert er.EscalationStatus.PENDING.value == "pending"
    assert er.EscalationStatus.APPROVED.value == "approved"
    assert er.EscalationStatus.REJECTED.value == "rejected"
    assert er.EscalationStatus.RESOLVED.value == "resolved"
    assert er.EscalationStatus.RETRYING.value == "retrying"
    assert er.EscalationStatus.CANCELLED.value == "cancelled"


def test_escalation_status_from_value_valid():
    assert er.EscalationStatus("pending") is er.EscalationStatus.PENDING
    assert er.EscalationStatus("approved") is er.EscalationStatus.APPROVED
    assert er.EscalationStatus("rejected") is er.EscalationStatus.REJECTED
    assert er.EscalationStatus("resolved") is er.EscalationStatus.RESOLVED
    assert er.EscalationStatus("retrying") is er.EscalationStatus.RETRYING
    assert er.EscalationStatus("cancelled") is er.EscalationStatus.CANCELLED


def test_escalation_status_from_value_invalid_raises_value_error():
    with pytest.raises(ValueError):
        er.EscalationStatus("nonexistent-status")


def test_escalation_risk_level_enum_members_and_values():
    assert er.EscalationRiskLevel.LOW.value == "low"
    assert er.EscalationRiskLevel.MEDIUM.value == "medium"
    assert er.EscalationRiskLevel.HIGH.value == "high"
    assert er.EscalationRiskLevel.CRITICAL.value == "critical"


def test_escalation_risk_level_from_value_valid():
    assert er.EscalationRiskLevel("low") is er.EscalationRiskLevel.LOW
    assert er.EscalationRiskLevel("medium") is er.EscalationRiskLevel.MEDIUM
    assert er.EscalationRiskLevel("high") is er.EscalationRiskLevel.HIGH
    assert er.EscalationRiskLevel("critical") is er.EscalationRiskLevel.CRITICAL


def test_escalation_risk_level_from_value_invalid_raises_value_error():
    with pytest.raises(ValueError):
        er.EscalationRiskLevel("invalid-risk")


def test_resolution_action_enum_has_expected_members():
    # These must exist as per the provided snippet
    assert hasattr(er.ResolutionAction, "NO_ACTION")
    assert hasattr(er.ResolutionAction, "APPROVED")
    assert hasattr(er.ResolutionAction, "REJECTED")
    assert hasattr(er.ResolutionAction, "RETRY_SCHEDULED")

    # Basic sanity on values (string enums)
    assert isinstance(er.ResolutionAction.NO_ACTION.value, str)
    assert isinstance(er.ResolutionAction.APPROVED.value, str)
    assert isinstance(er.ResolutionAction.REJECTED.value, str)
    assert isinstance(er.ResolutionAction.RETRY_SCHEDULED.value, str)


def test_escalation_dataclass_basic_initialization(sample_escalation: er.Escalation, sample_datetime: datetime):
    esc = sample_escalation
    assert esc.id == "esc-123"
    assert esc.created_at == sample_datetime
    assert esc.updated_at == sample_datetime
    assert esc.status is er.EscalationStatus.PENDING
    assert esc.risk_level is er.EscalationRiskLevel.MEDIUM
    assert esc.metadata == {"key": "value"}
    assert esc.retry_count == 1
    assert esc.assigned_worker_id == "worker-1"
    assert esc.resolved_at is None
    assert esc.resolution_reason is None
    assert esc.manual_only is False


def test_escalation_default_values_for_optional_fields(sample_datetime: datetime):
    esc = er.Escalation(
        id="esc-456",
        created_at=sample_datetime,
        updated_at=sample_datetime,
        status=er.EscalationStatus.APPROVED,
        risk_level=er.EscalationRiskLevel.HIGH,
    )

    assert esc.metadata == {}
    assert isinstance(esc.metadata, dict)
    assert esc.retry_count == 0
    assert esc.assigned_worker_id is None
    assert esc.resolved_at is None
    assert esc.resolution_reason is None
    assert esc.manual_only is False


def test_escalation_metadata_default_is_not_shared_between_instances(sample_datetime: datetime):
    esc1 = er.Escalation(
        id="esc-1",
        created_at=sample_datetime,
        updated_at=sample_datetime,
        status=er.EscalationStatus.PENDING,
        risk_level=er.EscalationRiskLevel.LOW,
    )
    esc2 = er.Escalation(
        id="esc-2",
        created_at=sample_datetime,
        updated_at=sample_datetime,
        status=er.EscalationStatus.PENDING,
        risk_level=er.EscalationRiskLevel.LOW,
    )

    esc1.metadata["a"] = 1
    assert esc1.metadata == {"a": 1}
    # Ensure the second instance has an independent metadata dict
    assert esc2.metadata == {}
    assert esc1.metadata is not esc2.metadata


def test_escalation_fields_are_mutable(sample_escalation: er.Escalation):
    esc = sample_escalation

    esc.status = er.EscalationStatus.APPROVED
    esc.risk_level = er.EscalationRiskLevel.HIGH
    esc.retry_count += 1
    esc.assigned_worker_id = "worker-2"
    esc.resolved_at = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
    esc.resolution_reason = "Resolved manually"
    esc.manual_only = True

    assert esc.status is er.EscalationStatus.APPROVED
    assert esc.risk_level is er.EscalationRiskLevel.HIGH
    assert esc.retry_count == 2
    assert esc.assigned_worker_id == "worker-2"
    assert esc.resolved_at == datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
    assert esc.resolution_reason == "Resolved manually"
    assert esc.manual_only is True


def test_escalation_allows_timezone_aware_datetimes(sample_datetime: datetime):
    esc = er.Escalation(
        id="esc-tz",
        created_at=sample_datetime,
        updated_at=sample_datetime,
        status=er.EscalationStatus.PENDING,
        risk_level=er.EscalationRiskLevel.LOW,
    )

    assert esc.created_at.tzinfo is not None
    assert esc.updated_at.tzinfo is not None
    assert esc.created_at.tzinfo == timezone.utc
    assert esc.updated_at.tzinfo == timezone.utc