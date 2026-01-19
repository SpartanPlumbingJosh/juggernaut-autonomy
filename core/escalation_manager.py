"""Automated escalation system for JUGGERNAUT L5 capabilities.

This module implements automated escalation including:
- Escalation rules based on risk, cost, time
- Multiple escalation levels (worker -> orchestrator -> Josh)
- Auto-escalation on timeout
- Escalation chain tracking for audit
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class EscalationLevel(Enum):
    """Levels of escalation in the approval chain."""
    WORKER = 1
    ORCHESTRATOR = 2
    OWNER = 3


class RiskLevel(Enum):
    """Risk levels that affect escalation behavior."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class EscalationRule:
    """Configuration for when and how to escalate."""
    risk_level: RiskLevel
    max_cost_cents: int
    timeout_minutes: int
    auto_approve_below_cost: int
    requires_level: EscalationLevel


@dataclass
class EscalationResult:
    """Result of an escalation check or action."""
    escalated: bool
    new_level: EscalationLevel
    escalated_to: str
    reason: str
    timeout_at: Optional[datetime] = None


@dataclass
class ApprovalRequest:
    """An approval request with escalation state."""
    approval_id: UUID
    task_id: Optional[UUID]
    action_type: str
    risk_level: RiskLevel
    estimated_cost_cents: int
    current_level: EscalationLevel
    created_at: datetime
    expires_at: Optional[datetime]
    escalation_history: list[dict] = field(default_factory=list)


class EscalationManager:
    """Manages automated escalation for approval requests.
    
    Implements L5 requirement: Automated Escalation & Approval - 
    Handles exceptions without bottlenecks.
    """

    DEFAULT_TIMEOUT_MINUTES = {
        EscalationLevel.WORKER: 30,
        EscalationLevel.ORCHESTRATOR: 60,
        EscalationLevel.OWNER: 1440,
    }

    LEVEL_HANDLERS = {
        EscalationLevel.WORKER: "system",
        EscalationLevel.ORCHESTRATOR: "juggernaut",
        EscalationLevel.OWNER: "josh",
    }

    DEFAULT_RULES = [
        EscalationRule(
            risk_level=RiskLevel.LOW,
            max_cost_cents=1000,
            timeout_minutes=30,
            auto_approve_below_cost=500,
            requires_level=EscalationLevel.WORKER,
        ),
        EscalationRule(
            risk_level=RiskLevel.MEDIUM,
            max_cost_cents=5000,
            timeout_minutes=60,
            auto_approve_below_cost=0,
            requires_level=EscalationLevel.ORCHESTRATOR,
        ),
        EscalationRule(
            risk_level=RiskLevel.HIGH,
            max_cost_cents=50000,
            timeout_minutes=120,
            auto_approve_below_cost=0,
            requires_level=EscalationLevel.ORCHESTRATOR,
        ),
        EscalationRule(
            risk_level=RiskLevel.CRITICAL,
            max_cost_cents=999999999,
            timeout_minutes=240,
            auto_approve_below_cost=0,
            requires_level=EscalationLevel.OWNER,
        ),
    ]

    def __init__(self, db_client: Any, rules: Optional[list[EscalationRule]] = None) -> None:
        """Initialize the escalation manager."""
        self._db = db_client
        self._rules = rules or self.DEFAULT_RULES
        logger.info("EscalationManager initialized with %d rules", len(self._rules))

    def get_rule_for_request(
        self, risk_level: RiskLevel, cost_cents: int
    ) -> EscalationRule:
        """Get the appropriate escalation rule for a request."""
        for rule in self._rules:
            if rule.risk_level == risk_level and cost_cents <= rule.max_cost_cents:
                return rule
        return self._rules[-1]

    def calculate_timeout(
        self, level: EscalationLevel, from_time: Optional[datetime] = None
    ) -> datetime:
        """Calculate when a request should timeout at a given level."""
        base_time = from_time or datetime.now(timezone.utc)
        timeout_minutes = self.DEFAULT_TIMEOUT_MINUTES.get(level, 60)
        return base_time + timedelta(minutes=timeout_minutes)

    async def check_auto_approve(
        self, risk_level: RiskLevel, cost_cents: int
    ) -> tuple[bool, str]:
        """Check if a request can be auto-approved based on rules."""
        rule = self.get_rule_for_request(risk_level, cost_cents)
        if cost_cents <= rule.auto_approve_below_cost:
            logger.info(
                "Auto-approving: cost %d <= threshold %d",
                cost_cents, rule.auto_approve_below_cost
            )
            return True, f"Auto-approved: cost {cost_cents} <= {rule.auto_approve_below_cost} cents"
        return False, "Requires manual approval"

    async def get_initial_level(
        self, risk_level: RiskLevel, cost_cents: int
    ) -> EscalationLevel:
        """Determine the initial escalation level for a new request."""
        rule = self.get_rule_for_request(risk_level, cost_cents)
        return rule.requires_level

    async def escalate(
        self, approval_id: UUID, reason: str
    ) -> EscalationResult:
        """Escalate an approval request to the next level."""
        query = """
        SELECT escalation_level, risk_level, action_data->>'estimated_cost_cents' as cost
        FROM approvals WHERE id = $1
        """
        result = await self._db.fetch_one(query, [str(approval_id)])
        if not result:
            logger.error("Approval %s not found", approval_id)
            return EscalationResult(
                escalated=False,
                new_level=EscalationLevel.WORKER,
                escalated_to="",
                reason="Approval not found",
            )

        current_level = result.get("escalation_level", 1)
        next_level_value = min(current_level + 1, EscalationLevel.OWNER.value)
        next_level = EscalationLevel(next_level_value)
        escalated_to = self.LEVEL_HANDLERS.get(next_level, "josh")
        timeout_at = self.calculate_timeout(next_level)

        update_query = """
        UPDATE approvals 
        SET escalation_level = $1,
            escalated_to = $2,
            escalation_reason = $3,
            expires_at = $4
        WHERE id = $5
        """
        await self._db.execute(update_query, [
            next_level.value,
            escalated_to,
            reason,
            timeout_at,
            str(approval_id),
        ])

        logger.info(
            "Escalated approval %s: level %d -> %d, to %s",
            approval_id, current_level, next_level.value, escalated_to
        )

        return EscalationResult(
            escalated=True,
            new_level=next_level,
            escalated_to=escalated_to,
            reason=reason,
            timeout_at=timeout_at,
        )

    async def check_timeouts(self) -> list[EscalationResult]:
        """Check for timed-out approvals and escalate them."""
        query = """
        SELECT id, escalation_level, created_at, expires_at
        FROM approvals
        WHERE decision = 'pending'
          AND expires_at IS NOT NULL
          AND expires_at < NOW()
          AND escalation_level < $1
        """
        results: list[EscalationResult] = []
        pending = await self._db.fetch_all(query, [EscalationLevel.OWNER.value])
        
        for approval in pending:
            approval_id = UUID(approval["id"])
            result = await self.escalate(
                approval_id,
                reason=f"Timeout: no response within {self.DEFAULT_TIMEOUT_MINUTES.get(EscalationLevel(approval['escalation_level']), 60)} minutes"
            )
            results.append(result)
            logger.info("Auto-escalated timed-out approval %s", approval_id)

        if results:
            logger.info("Processed %d timeout escalations", len(results))
        return results

    async def create_approval_request(
        self,
        action_type: str,
        action_description: str,
        risk_level: RiskLevel,
        estimated_cost_cents: int,
        task_id: Optional[UUID] = None,
        worker_id: Optional[str] = None,
        action_data: Optional[dict] = None,
    ) -> tuple[UUID, bool, str]:
        """Create a new approval request with appropriate escalation level.
        
        Returns (approval_id, auto_approved, message).
        """
        auto_approve, msg = await self.check_auto_approve(risk_level, estimated_cost_cents)
        initial_level = await self.get_initial_level(risk_level, estimated_cost_cents)
        escalated_to = self.LEVEL_HANDLERS.get(initial_level, "system")
        timeout_at = self.calculate_timeout(initial_level)
        approval_id = uuid4()

        decision = "approved" if auto_approve else "pending"
        decided_by = "system" if auto_approve else None
        decided_at = datetime.now(timezone.utc) if auto_approve else None

        data = action_data or {}
        data["estimated_cost_cents"] = estimated_cost_cents

        query = """
        INSERT INTO approvals (
            id, task_id, worker_id, action_type, action_description,
            action_data, risk_level, decision, decided_by, decided_at,
            created_at, expires_at, escalation_level, escalated_to
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            NOW(), $11, $12, $13
        )
        """
        await self._db.execute(query, [
            str(approval_id),
            str(task_id) if task_id else None,
            worker_id,
            action_type,
            action_description,
            data,
            risk_level.value,
            decision,
            decided_by,
            decided_at,
            timeout_at if not auto_approve else None,
            initial_level.value,
            escalated_to,
        ])

        logger.info(
            "Created approval %s: level=%s, auto_approved=%s",
            approval_id, initial_level.name, auto_approve
        )
        return approval_id, auto_approve, msg

    async def get_escalation_chain(self, approval_id: UUID) -> list[dict]:
        """Get the escalation history for an approval request."""
        query = """
        SELECT escalation_level, escalated_to, escalation_reason,
               created_at, expires_at, decided_at, decided_by, decision
        FROM approvals WHERE id = $1
        """
        result = await self._db.fetch_one(query, [str(approval_id)])
        if not result:
            return []

        chain = [{
            "level": result.get("escalation_level", 1),
            "handler": result.get("escalated_to", "system"),
            "reason": result.get("escalation_reason"),
            "timeout_at": result.get("expires_at"),
            "decision": result.get("decision"),
            "decided_by": result.get("decided_by"),
            "decided_at": result.get("decided_at"),
        }]
        return chain

    async def process_decision(
        self,
        approval_id: UUID,
        decision: str,
        decided_by: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Process a decision on an approval request."""
        valid_decisions = ["approved", "rejected", "deferred"]
        if decision not in valid_decisions:
            logger.error("Invalid decision: %s", decision)
            return False

        query = """
        UPDATE approvals
        SET decision = $1,
            decided_by = $2,
            decided_at = NOW(),
            decision_notes = $3
        WHERE id = $4 AND decision = 'pending'
        """
        result = await self._db.execute(query, [
            decision, decided_by, notes, str(approval_id)
        ])
        
        if result:
            logger.info(
                "Decision recorded for %s: %s by %s",
                approval_id, decision, decided_by
            )
            return True
        return False


async def create_escalation_manager(
    db_client: Any,
    rules: Optional[list[EscalationRule]] = None
) -> EscalationManager:
    """Factory function to create an EscalationManager."""
    return EscalationManager(db_client, rules)
