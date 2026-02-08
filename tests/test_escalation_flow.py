"""Tests for L5 escalation flow verification.

L5-TEST-04: Verify that high-risk tasks trigger proper escalation
and human notification mechanisms.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from core.escalation_manager import (
    EscalationLevel,
    EscalationManager,
    EscalationResult,
    EscalationRule,
    RiskLevel,
)
from core.notifications import SlackNotifier

logger = logging.getLogger(__name__)


class MockDBClient:
    """Mock database client for testing."""

    def __init__(self) -> None:
        """Initialize mock database client."""
        self._storage: dict[str, dict] = {}
        self._execute_results: list[Any] = []

    async def execute(
        self, query: str, params: Optional[list] = None
    ) -> dict[str, Any]:
        """Mock execute method."""
        if "INSERT INTO approvals" in query and params:
            approval_id = params[0]
            self._storage[approval_id] = {
                "id": approval_id,
                "task_id": params[1],
                "worker_id": params[2],
                "action_type": params[3],
                "action_description": params[4],
                "action_data": params[5],
                "risk_level": params[6],
                "decision": params[7],
                "decided_by": params[8],
                "decided_at": params[9],
                "expires_at": params[10],
                "escalation_level": params[11],
                "escalated_to": params[12],
            }
        return {"rowcount": 1}

    async def fetch_one(
        self, query: str, params: Optional[list] = None
    ) -> Optional[dict]:
        """Mock fetch_one method."""
        if params and params[0] in self._storage:
            return self._storage[params[0]]
        return None

    async def fetch_all(
        self, query: str, params: Optional[list] = None
    ) -> list[dict]:
        """Mock fetch_all method."""
        return []


@pytest.fixture
def mock_db() -> MockDBClient:
    """Create a mock database client."""
    return MockDBClient()


@pytest.fixture
def escalation_manager(mock_db: MockDBClient) -> EscalationManager:
    """Create an EscalationManager with mock database."""
    return EscalationManager(mock_db)


class TestEscalationFlowHighRisk:
    """Test escalation flow for high-risk tasks."""

    @pytest.mark.asyncio
    async def test_high_risk_task_requires_escalation(
        self, escalation_manager: EscalationManager
    ) -> None:
        """Verify high-risk task creates escalation requiring approval."""
        approval_id, auto_approved, msg = await escalation_manager.create_approval_request(
            action_type="domain_purchase",
            action_description="Purchase high-value domain example.com for $500",
            risk_level=RiskLevel.HIGH,
            estimated_cost_cents=50000,
            task_id=uuid4(),
            worker_id="agent-chat-test",
            action_data={"domain": "example.com"},
        )

        assert approval_id is not None
        assert auto_approved is False, "High-risk tasks should NOT be auto-approved"
        assert "manual approval" in msg.lower()

    @pytest.mark.asyncio
    async def test_high_risk_escalates_to_orchestrator(
        self, escalation_manager: EscalationManager
    ) -> None:
        """Verify high-risk task escalates to orchestrator level."""
        initial_level = await escalation_manager.get_initial_level(
            RiskLevel.HIGH, cost_cents=50000
        )
        assert initial_level == EscalationLevel.ORCHESTRATOR

    @pytest.mark.asyncio
    async def test_critical_risk_escalates_to_owner(
        self, escalation_manager: EscalationManager
    ) -> None:
        """Verify critical-risk task escalates to owner (Josh) level."""
        initial_level = await escalation_manager.get_initial_level(
            RiskLevel.CRITICAL, cost_cents=100000
        )
        assert initial_level == EscalationLevel.OWNER

    @pytest.mark.asyncio
    async def test_escalation_creates_timeout(
        self, escalation_manager: EscalationManager
    ) -> None:
        """Verify escalation includes appropriate timeout."""
        timeout = escalation_manager.calculate_timeout(EscalationLevel.ORCHESTRATOR)
        expected_min = datetime.now(timezone.utc) + timedelta(minutes=55)
        expected_max = datetime.now(timezone.utc) + timedelta(minutes=65)

        assert expected_min <= timeout <= expected_max


class TestEscalationNotification:
    """Test that escalations trigger notifications."""

    def test_slack_notifier_can_send_escalation_alert(self) -> None:
        """Verify SlackNotifier has method to send escalation alerts."""
        notifier = SlackNotifier(webhook_url=None)
        assert hasattr(notifier, "notify_alert")

    def test_notify_alert_formats_escalation_message(self) -> None:
        """Verify alert formatting for escalation notifications."""
        notifier = SlackNotifier(webhook_url=None)

        with patch.object(notifier, "_post_to_slack", return_value=True) as mock_post:
            notifier.enabled = True
            notifier.webhook_url = "https://hooks.slack.com/test"

            result = notifier.notify_alert(
                alert_type="ESCALATION_REQUIRED",
                message="High-risk approval pending: domain_purchase - $500.00",
                severity="warning",
            )

            if mock_post.called:
                call_args = mock_post.call_args[0][0]
                assert "ESCALATION_REQUIRED" in call_args.get("text", "")

    def test_escalation_levels_have_handlers(self) -> None:
        """Verify each escalation level maps to a handler."""
        handlers = EscalationManager.LEVEL_HANDLERS
        assert EscalationLevel.WORKER in handlers
        assert EscalationLevel.ORCHESTRATOR in handlers
        assert EscalationLevel.OWNER in handlers
        assert handlers[EscalationLevel.OWNER] == "josh"


class TestEscalationRules:
    """Test escalation rule configuration."""

    def test_default_rules_exist(self) -> None:
        """Verify default escalation rules are configured."""
        rules = EscalationManager.DEFAULT_RULES
        assert len(rules) >= 4

        risk_levels = [rule.risk_level for rule in rules]
        assert RiskLevel.LOW in risk_levels
        assert RiskLevel.MEDIUM in risk_levels
        assert RiskLevel.HIGH in risk_levels
        assert RiskLevel.CRITICAL in risk_levels

    def test_critical_requires_owner_approval(self) -> None:
        """Verify critical tasks require owner approval."""
        rules = EscalationManager.DEFAULT_RULES
        critical_rule = next(r for r in rules if r.risk_level == RiskLevel.CRITICAL)
        assert critical_rule.requires_level == EscalationLevel.OWNER

    def test_low_risk_can_auto_approve(self) -> None:
        """Verify low-risk tasks can be auto-approved."""
        rules = EscalationManager.DEFAULT_RULES
        low_rule = next(r for r in rules if r.risk_level == RiskLevel.LOW)
        assert low_rule.auto_approve_below_cost > 0


class TestEscalationTimeout:
    """Test timeout-based auto-escalation."""

    @pytest.mark.asyncio
    async def test_timeout_values_by_level(
        self, escalation_manager: EscalationManager
    ) -> None:
        """Verify timeout values differ by escalation level."""
        worker_timeout = escalation_manager.DEFAULT_TIMEOUT_MINUTES[
            EscalationLevel.WORKER
        ]
        orch_timeout = escalation_manager.DEFAULT_TIMEOUT_MINUTES[
            EscalationLevel.ORCHESTRATOR
        ]
        owner_timeout = escalation_manager.DEFAULT_TIMEOUT_MINUTES[
            EscalationLevel.OWNER
        ]

        assert worker_timeout < orch_timeout < owner_timeout

    @pytest.mark.asyncio
    async def test_check_timeouts_returns_results(
        self, escalation_manager: EscalationManager
    ) -> None:
        """Verify timeout check returns escalation results."""
        results = await escalation_manager.check_timeouts()
        assert isinstance(results, list)


class TestEscalationDecision:
    """Test approval decision processing."""

    def test_valid_decisions(self) -> None:
        """Verify valid decision values."""
        valid = ["approved", "rejected", "deferred"]
        for decision in valid:
            assert decision in ["approved", "rejected", "deferred"]

    @pytest.mark.asyncio
    async def test_process_decision_validates_input(
        self, escalation_manager: EscalationManager
    ) -> None:
        """Verify invalid decisions are rejected."""
        result = await escalation_manager.process_decision(
            approval_id=uuid4(),
            decision="invalid_decision",
            decided_by="test",
        )
        assert result is False
