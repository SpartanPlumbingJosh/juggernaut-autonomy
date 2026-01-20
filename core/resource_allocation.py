"""
Resource Allocation System for JUGGERNAUT Autonomy.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources that can be allocated."""
    BUDGET = "budget"
    TIME = "time"
    WORKER = "worker"
    API_CALLS = "api_calls"


@dataclass
class BudgetStatus:
    """Current budget status for a goal or experiment."""
    entity_id: UUID
    entity_type: str
    budget_limit_cents: int
    spent_cents: int
    remaining_cents: int
    utilization_percent: float
    is_exceeded: bool
    alert_triggered: bool


@dataclass
class PriorityScore:
    """Calculated priority score with breakdown."""
    task_id: UUID
    base_priority: int
    roi_multiplier: float
    urgency_multiplier: float
    budget_penalty: float
    final_score: float
    recommendation: str


class ResourceAllocator:
    """Manages resource allocation across goals, experiments, and tasks."""

    PRIORITY_VALUES = {"critical": 100, "high": 75, "medium": 50, "low": 25}
    DEFAULT_ALERT_THRESHOLD = 80

    def __init__(self, db_executor: Any) -> None:
        """Initialize the resource allocator."""
        self.db = db_executor

    async def get_budget_status(
        self, entity_id: UUID, entity_type: str = "goal"
    ) -> BudgetStatus:
        """Get current budget status for a goal or experiment."""
        table = "goals" if entity_type == "goal" else "experiments"
        budget_query = f"SELECT max_cost_cents as budget_limit FROM {table} WHERE id = %s"
        budget_result = await self.db.execute(budget_query, (str(entity_id),))
        budget_limit = (budget_result[0]["budget_limit"] if budget_result else 0) or 0
        spent = 0
        remaining = max(0, budget_limit - spent)
        utilization = (spent / budget_limit * 100) if budget_limit > 0 else 0.0
        return BudgetStatus(
            entity_id=entity_id, entity_type=entity_type,
            budget_limit_cents=budget_limit, spent_cents=spent,
            remaining_cents=remaining, utilization_percent=round(utilization, 2),
            is_exceeded=spent > budget_limit if budget_limit > 0 else False,
            alert_triggered=utilization >= self.DEFAULT_ALERT_THRESHOLD,
        )

    async def calculate_priority_score(self, task_id: UUID) -> PriorityScore:
        """Calculate dynamic priority score for a task based on ROI."""
        query = """SELECT t.priority, t.goal_id FROM governance_tasks t WHERE t.id = %s"""
        result = await self.db.execute(query, (str(task_id),))
        if not result:
            return PriorityScore(
                task_id=task_id, base_priority=0, roi_multiplier=1.0,
                urgency_multiplier=1.0, budget_penalty=0.0, final_score=0.0,
                recommendation="Task not found",
            )
        row = result[0]
        base_priority = self.PRIORITY_VALUES.get(row.get("priority", "medium"), 50)
        roi_multiplier = 1.0
        urgency_multiplier = 1.0
        budget_penalty = 0.0
        goal_id = row.get("goal_id")
        if goal_id:
            budget_status = await self.get_budget_status(UUID(goal_id), "goal")
            if budget_status.is_exceeded:
                budget_penalty = 0.5
            elif budget_status.alert_triggered:
                budget_penalty = 0.2
        final_score = base_priority * roi_multiplier * urgency_multiplier * (1 - budget_penalty)
        if budget_penalty >= 0.5:
            recommendation = "DEPRIORITIZE: Goal budget exceeded"
        else:
            recommendation = "NORMAL: Process in order"
        return PriorityScore(
            task_id=task_id, base_priority=base_priority,
            roi_multiplier=round(roi_multiplier, 2),
            urgency_multiplier=round(urgency_multiplier, 2),
            budget_penalty=round(budget_penalty, 2),
            final_score=round(final_score, 2),
            recommendation=recommendation,
        )

    async def check_budget_before_execution(
        self, task_id: UUID, estimated_cost_cents: int
    ) -> Tuple[bool, str]:
        """Check if a task can be executed within budget constraints."""
        query = "SELECT goal_id FROM governance_tasks WHERE id = %s"
        result = await self.db.execute(query, (str(task_id),))
        if not result or not result[0].get("goal_id"):
            return True, "No budget constraints"
        goal_id = UUID(result[0]["goal_id"])
        budget_status = await self.get_budget_status(goal_id, "goal")
        if budget_status.is_exceeded:
            return False, "Goal budget exceeded"
        if budget_status.remaining_cents < estimated_cost_cents:
            return False, "Insufficient budget"
        return True, "Budget check passed"

    async def resolve_resource_conflict(
        self, task_ids: List[UUID], resource_type: ResourceType
    ) -> UUID:
        """Resolve a conflict between tasks competing for the same resource."""
        if not task_ids:
            raise ValueError("No tasks provided")
        if len(task_ids) == 1:
            return task_ids[0]
        scores = []
        for tid in task_ids:
            score = await self.calculate_priority_score(tid)
            scores.append((tid, score.final_score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[0][0]
