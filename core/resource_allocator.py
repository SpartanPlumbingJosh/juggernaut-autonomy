"""Resource allocation system for JUGGERNAUT L5 capabilities.

This module implements dynamic resource allocation including:
- Budget tracking per goal/experiment
- Time allocation across competing tasks
- Priority adjustment based on ROI
- Automatic resource conflict resolution
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class AllocationStatus(Enum):
    """Status of a resource allocation request."""
    APPROVED = "approved"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIME_EXCEEDED = "time_exceeded"
    CONFLICT = "conflict"
    DEPRIORITIZED = "deprioritized"


@dataclass
class BudgetCheck:
    """Result of a budget check operation."""
    allowed: bool
    status: AllocationStatus
    budget_remaining_cents: int
    budget_used_cents: int
    budget_limit_cents: int
    message: str


@dataclass
class TimeCheck:
    """Result of a time allocation check."""
    allowed: bool
    status: AllocationStatus
    time_remaining_minutes: int
    time_spent_minutes: int
    time_budget_minutes: int
    message: str


@dataclass
class PriorityAdjustment:
    """Result of a priority recalculation."""
    task_id: str
    old_priority: str
    new_priority: str
    reason: str
    roi_score: float


class ResourceAllocator:
    """Manages resource allocation for tasks and goals.
    
    Implements L5 requirement: Resource Allocation - Dynamically assigns
    time, budget, priority across competing tasks.
    """

    PRIORITY_ORDER = ["critical", "high", "medium", "low"]
    DEFAULT_ALERT_THRESHOLD = 80

    def __init__(self, db_client: Any) -> None:
        """Initialize the resource allocator.
        
        Args:
            db_client: Database client for executing queries.
        """
        self._db = db_client
        logger.info("ResourceAllocator initialized")

    async def check_budget(
        self,
        goal_id: Optional[UUID] = None,
        experiment_id: Optional[UUID] = None,
        requested_cents: int = 0
    ) -> BudgetCheck:
        """Check if a budget allocation is allowed.
        
        Args:
            goal_id: Optional goal to check budget for.
            experiment_id: Optional experiment to check budget for.
            requested_cents: Amount requested in cents.
            
        Returns:
            BudgetCheck with allocation decision.
        """
        if not goal_id and not experiment_id:
            return BudgetCheck(
                allowed=True,
                status=AllocationStatus.APPROVED,
                budget_remaining_cents=0,
                budget_used_cents=0,
                budget_limit_cents=0,
                message="No goal or experiment specified, no budget constraints"
            )

        query = """
        SELECT 
            COALESCE(g.max_cost_cents, 0) as budget_limit,
            COALESCE(SUM(ce.amount_cents), 0) as spent
        FROM goals g
        LEFT JOIN cost_events ce ON ce.goal_id = g.id
        WHERE g.id = $1
        GROUP BY g.id, g.max_cost_cents
        """
        
        target_id = goal_id if goal_id else experiment_id
        result = await self._db.fetch_one(query, [str(target_id)])
        
        if not result:
            return BudgetCheck(
                allowed=True,
                status=AllocationStatus.APPROVED,
                budget_remaining_cents=0,
                budget_used_cents=0,
                budget_limit_cents=0,
                message="No budget limit configured"
            )

        budget_limit = result.get("budget_limit", 0)
        spent = result.get("spent", 0)
        remaining = budget_limit - spent
        
        if budget_limit > 0 and (spent + requested_cents) > budget_limit:
            logger.warning(
                "Budget exceeded for goal %s: spent=%d, requested=%d, limit=%d",
                target_id, spent, requested_cents, budget_limit
            )
            return BudgetCheck(
                allowed=False,
                status=AllocationStatus.BUDGET_EXCEEDED,
                budget_remaining_cents=max(0, remaining),
                budget_used_cents=spent,
                budget_limit_cents=budget_limit,
                message=f"Budget exceeded: {spent + requested_cents} > {budget_limit} cents"
            )

        return BudgetCheck(
            allowed=True,
            status=AllocationStatus.APPROVED,
            budget_remaining_cents=remaining - requested_cents,
            budget_used_cents=spent,
            budget_limit_cents=budget_limit,
            message="Budget allocation approved"
        )

    async def check_time_budget(
        self,
        goal_id: UUID,
        requested_minutes: int = 0
    ) -> TimeCheck:
        """Check if time allocation is allowed for a goal.
        
        Args:
            goal_id: Goal to check time budget for.
            requested_minutes: Additional minutes requested.
            
        Returns:
            TimeCheck with allocation decision.
        """
        query = """
        SELECT 
            COALESCE(time_budget_minutes, 0) as time_budget,
            COALESCE(time_spent_minutes, 0) as time_spent
        FROM goals
        WHERE id = $1
        """
        
        result = await self._db.fetch_one(query, [str(goal_id)])
        
        if not result:
            return TimeCheck(
                allowed=True,
                status=AllocationStatus.APPROVED,
                time_remaining_minutes=0,
                time_spent_minutes=0,
                time_budget_minutes=0,
                message="Goal not found, no time constraints"
            )

        time_budget = result.get("time_budget", 0)
        time_spent = result.get("time_spent", 0)
        remaining = time_budget - time_spent
        
        if time_budget > 0 and (time_spent + requested_minutes) > time_budget:
            logger.warning(
                "Time budget exceeded for goal %s: spent=%d, requested=%d, limit=%d",
                goal_id, time_spent, requested_minutes, time_budget
            )
            return TimeCheck(
                allowed=False,
                status=AllocationStatus.TIME_EXCEEDED,
                time_remaining_minutes=max(0, remaining),
                time_spent_minutes=time_spent,
                time_budget_minutes=time_budget,
                message=f"Time budget exceeded: {time_spent + requested_minutes} > {time_budget} minutes"
            )

        return TimeCheck(
            allowed=True,
            status=AllocationStatus.APPROVED,
            time_remaining_minutes=remaining - requested_minutes,
            time_spent_minutes=time_spent,
            time_budget_minutes=time_budget,
            message="Time allocation approved"
        )

    async def record_cost(
        self,
        amount_cents: int,
        cost_type: str,
        category: str,
        description: str,
        goal_id: Optional[UUID] = None,
        experiment_id: Optional[UUID] = None,
        source: str = "system",
        metadata: Optional[dict] = None
    ) -> bool:
        """Record a cost event for tracking.
        
        Args:
            amount_cents: Cost amount in cents.
            cost_type: Type of cost (e.g., 'api_call', 'compute').
            category: Category (e.g., 'openai', 'railway').
            description: Human-readable description.
            goal_id: Optional associated goal.
            experiment_id: Optional associated experiment.
            source: Source of the cost.
            metadata: Additional metadata.
            
        Returns:
            True if recorded successfully.
        """
        query = """
        INSERT INTO cost_events (
            cost_type, category, description, amount_cents,
            currency, source, goal_id, experiment_id, metadata,
            occurred_at, recorded_at, recorded_by
        ) VALUES (
            $1, $2, $3, $4, 'USD', $5, $6, $7, $8, NOW(), NOW(), $9
        )
        """
        
        try:
            await self._db.execute(query, [
                cost_type,
                category,
                description,
                amount_cents,
                source,
                str(goal_id) if goal_id else None,
                str(experiment_id) if experiment_id else None,
                metadata or {},
                "resource_allocator"
            ])
            logger.info(
                "Recorded cost: %d cents for %s/%s",
                amount_cents, cost_type, category
            )
            return True
        except Exception as exc:
            logger.error("Failed to record cost: %s", str(exc))
            return False

    async def update_time_spent(
        self,
        goal_id: UUID,
        minutes_spent: int
    ) -> bool:
        """Update time spent on a goal.
        
        Args:
            goal_id: Goal to update.
            minutes_spent: Additional minutes to add.
            
        Returns:
            True if updated successfully.
        """
        query = """
        UPDATE goals 
        SET time_spent_minutes = COALESCE(time_spent_minutes, 0) + $1,
            updated_at = NOW()
        WHERE id = $2
        """
        
        try:
            await self._db.execute(query, [minutes_spent, str(goal_id)])
            logger.info(
                "Updated time spent for goal %s: +%d minutes",
                goal_id, minutes_spent
            )
            return True
        except Exception as exc:
            logger.error("Failed to update time spent: %s", str(exc))
            return False

    async def calculate_roi(self, task_id: str) -> float:
        """Calculate ROI score for a task.
        
        ROI is calculated as: expected_value / (estimated_cost + time_cost)
        Higher ROI = higher priority.
        
        Args:
            task_id: Task to calculate ROI for.
            
        Returns:
            ROI score (0.0 to 1.0).
        """
        query = """
        SELECT 
            t.estimated_cost_cents,
            t.priority,
            g.max_cost_cents as goal_budget,
            g.progress as goal_progress
        FROM governance_tasks t
        LEFT JOIN goals g ON t.goal_id = g.id
        WHERE t.id = $1
        """
        
        result = await self._db.fetch_one(query, [task_id])
        
        if not result:
            return 0.5
        
        priority_values = {
            "critical": 1.0,
            "high": 0.75,
            "medium": 0.5,
            "low": 0.25
        }
        priority_score = priority_values.get(
            result.get("priority", "medium"), 0.5
        )
        
        estimated_cost = result.get("estimated_cost_cents", 0) or 0
        cost_factor = 1.0 / (1.0 + estimated_cost / 1000)
        
        goal_progress = float(result.get("goal_progress", 0) or 0)
        progress_factor = 0.5 + (goal_progress / 200)
        
        roi = (
            priority_score * 0.4
            + cost_factor * 0.3
            + progress_factor * 0.3
        )
        
        return min(1.0, max(0.0, roi))

    async def recalculate_priorities(
        self,
        scope: str = "pending"
    ) -> list[PriorityAdjustment]:
        """Recalculate priorities for tasks based on ROI.
        
        Tasks with budget-exceeded goals get deprioritized.
        
        Args:
            scope: Task status to recalculate ('pending', 'all').
            
        Returns:
            List of priority adjustments made.
        """
        adjustments: list[PriorityAdjustment] = []
        
        query = """
        SELECT 
            t.id,
            t.priority,
            t.goal_id,
            g.max_cost_cents as budget_limit,
            COALESCE(
                (SELECT SUM(amount_cents) FROM cost_events WHERE goal_id = g.id),
                0
            ) as budget_spent
        FROM governance_tasks t
        LEFT JOIN goals g ON t.goal_id = g.id
        WHERE t.status = $1
        ORDER BY t.created_at
        """
        
        status = scope if scope != "all" else "pending"
        tasks = await self._db.fetch_all(query, [status])
        
        for task in tasks:
            task_id = task.get("id")
            current_priority = task.get("priority", "medium")
            budget_limit = task.get("budget_limit", 0) or 0
            budget_spent = task.get("budget_spent", 0) or 0
            
            if budget_limit > 0 and budget_spent >= budget_limit:
                new_priority = self._deprioritize(current_priority)
                if new_priority != current_priority:
                    await self._update_task_priority(task_id, new_priority)
                    roi = await self.calculate_roi(task_id)
                    adjustments.append(PriorityAdjustment(
                        task_id=task_id,
                        old_priority=current_priority,
                        new_priority=new_priority,
                        reason="Goal budget exceeded",
                        roi_score=roi
                    ))
                    logger.info(
                        "Deprioritized task %s: %s -> %s (budget exceeded)",
                        task_id, current_priority, new_priority
                    )
            else:
                roi = await self.calculate_roi(task_id)
                suggested_priority = self._priority_from_roi(roi)
                
                if suggested_priority != current_priority:
                    if self._is_higher_priority(
                        suggested_priority, current_priority
                    ):
                        await self._update_task_priority(
                            task_id, suggested_priority
                        )
                        adjustments.append(PriorityAdjustment(
                            task_id=task_id,
                            old_priority=current_priority,
                            new_priority=suggested_priority,
                            reason=f"ROI score {roi:.2f} justifies upgrade",
                            roi_score=roi
                        ))
        
        logger.info(
            "Recalculated priorities: %d adjustments",
            len(adjustments)
        )
        return adjustments

    def _deprioritize(self, current: str) -> str:
        """Get the next lower priority level."""
        try:
            idx = self.PRIORITY_ORDER.index(current)
            if idx < len(self.PRIORITY_ORDER) - 1:
                return self.PRIORITY_ORDER[idx + 1]
        except ValueError:
            pass
        return current

    def _priority_from_roi(self, roi: float) -> str:
        """Convert ROI score to priority level."""
        if roi >= 0.8:
            return "high"
        elif roi >= 0.5:
            return "medium"
        return "low"

    def _is_higher_priority(self, new: str, old: str) -> bool:
        """Check if new priority is higher than old."""
        try:
            new_idx = self.PRIORITY_ORDER.index(new)
            old_idx = self.PRIORITY_ORDER.index(old)
            return new_idx < old_idx
        except ValueError:
            return False

    async def _update_task_priority(
        self,
        task_id: str,
        priority: str
    ) -> None:
        """Update a task's priority in the database."""
        query = """
        UPDATE governance_tasks 
        SET priority = $1::priority_level
        WHERE id = $2
        """
        await self._db.execute(query, [priority, task_id])

    async def allocate_resources(
        self,
        task_id: str,
        estimated_cost_cents: int = 0,
        estimated_minutes: int = 0
    ) -> tuple[bool, str]:
        """Attempt to allocate resources for a task.
        
        Checks both budget and time constraints before allowing
        task execution.
        
        Args:
            task_id: Task requesting resources.
            estimated_cost_cents: Estimated cost of the task.
            estimated_minutes: Estimated time for the task.
            
        Returns:
            Tuple of (allowed, reason).
        """
        query = "SELECT goal_id FROM governance_tasks WHERE id = $1"
        result = await self._db.fetch_one(query, [task_id])
        
        if not result or not result.get("goal_id"):
            return True, "No goal constraints"
        
        goal_id = UUID(result["goal_id"])
        
        budget_check = await self.check_budget(
            goal_id=goal_id,
            requested_cents=estimated_cost_cents
        )
        
        if not budget_check.allowed:
            await self.recalculate_priorities()
            return False, budget_check.message
        
        time_check = await self.check_time_budget(
            goal_id=goal_id,
            requested_minutes=estimated_minutes
        )
        
        if not time_check.allowed:
            return False, time_check.message
        
        return True, "Resources allocated"

    async def resolve_conflict(
        self,
        task_ids: list[str],
        resource_type: str
    ) -> Optional[str]:
        """Resolve resource conflict between tasks.
        
        Uses ROI-based resolution: highest ROI task wins.
        
        Args:
            task_ids: Tasks competing for the resource.
            resource_type: Type of resource being contested.
            
        Returns:
            Task ID that wins the resource, or None.
        """
        if not task_ids:
            return None
        
        best_task = None
        best_roi = -1.0
        
        for task_id in task_ids:
            roi = await self.calculate_roi(task_id)
            if roi > best_roi:
                best_roi = roi
                best_task = task_id
        
        if best_task:
            logger.info(
                "Resolved %s conflict: task %s wins with ROI %.2f",
                resource_type, best_task, best_roi
            )
        
        return best_task


async def create_resource_allocator(db_client: Any) -> ResourceAllocator:
    """Factory function to create a ResourceAllocator.
    
    Args:
        db_client: Database client instance.
        
    Returns:
        Configured ResourceAllocator instance.
    """
    return ResourceAllocator(db_client)
