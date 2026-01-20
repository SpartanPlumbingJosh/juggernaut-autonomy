import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from statistics import mean
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Protocol, Tuple, runtime_checkable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUTO_RESOLVE_RISK_THRESHOLD_DEFAULT: float = 0.6
RESOLUTION_TIMEOUT_SECONDS_DEFAULT: int = 300  # 5 minutes
PRIORITY_HIGHEST_VALUE: int = 100
WORKER_MAX_LOAD_THRESHOLD: float = 0.9
RISK_SCORE_MIN: float = 0.0
RISK_SCORE_MAX: float = 1.0

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain Models
# ---------------------------------------------------------------------------


class ConflictType(str, Enum):
    """Enumeration of supported conflict types."""

    RESOURCE_CONTENTION = "resource_contention"
    TASK_DEPENDENCY = "task_dependency"
    WORKER_AVAILABILITY = "worker_availability"
    BUDGET = "budget"


class ConflictStatus(str, Enum):
    """Enumeration of conflict lifecycle statuses."""

    PENDING = "pending"
    AUTO_RESOLVED = "auto_resolved"
    ESCALATED = "escalated"
    MANUAL_RESOLVED = "manual_resolved"
    FAILED = "failed"


@dataclass
class Conflict:
    """Represents a conflict that needs to be resolved.

    Attributes:
        conflict_id: Unique identifier for the conflict.
        type: The type of conflict.
        risk_score: A normalized risk score between 0.0 and 1.0.
        created_at: Timestamp when the conflict was created.
        last_updated_at: Timestamp when the conflict was last updated.
        status: Current status of the conflict.
        payload: Arbitrary payload describing the conflict details,
            structure depends on the conflict type.
    """

    conflict_id: str
    type: ConflictType
    risk_score: float
    created_at: datetime
    last_updated_at: datetime
    status: ConflictStatus
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize and validate attributes after initialization."""
        if self.risk_score < RISK_SCORE_MIN:
            logger.debug("Normalizing risk_score below minimum for conflict %s", self.conflict_id)
            self.risk_score = RISK_SCORE_MIN
        elif self.risk_score > RISK_SCORE_MAX:
            logger.debug("Normalizing risk_score above maximum for conflict %s", self.conflict_id)
            self.risk_score = RISK_SCORE_MAX

        # Ensure timestamps are timezone-aware (UTC)
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.last_updated_at.tzinfo is None:
            self.last_updated_at = self.last_updated_at.replace(tzinfo=timezone.utc)


@dataclass
class ConflictResolutionResult:
    """Represents the result of attempting to resolve a conflict.

    Attributes:
        success: Whether the resolution strategy executed without internal errors.
        resolved: Whether the conflict has been successfully resolved.
        escalated: Whether the conflict should be escalated for manual handling.
        resolution_type: A short code describing the resolution outcome.
        message: Human-readable description of the resolution.
        risk_score: The resulting risk score after resolution attempt.
        strategy_name: The name of the strategy used.
        metadata: Arbitrary data about the resolution (for audit).
        resolution_time_ms: Time taken to attempt resolution, in milliseconds.
    """

    success: bool
    resolved: bool
    escalated: bool
    resolution_type: str
    message: str
    risk_score: float
    strategy_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolution_time_ms: int = 0


@dataclass
class ConflictResolutionMetricsSnapshot:
    """Immutable snapshot of conflict resolution metrics.

    Attributes:
        total_conflicts: Total number of conflicts processed.
        auto_resolved: Number of conflicts automatically resolved.
        escalated: Number of conflicts escalated to manual handling.
        failed: Number of conflicts whose resolution attempts failed.
        avg_resolution_time_ms: Average resolution time in milliseconds.
        by_type: Per-type aggregates of metrics.
    """

    total_conflicts: int
    auto_resolved: int
    escalated: int
    failed: int
    avg_resolution_time_ms: float
    by_type: Dict[ConflictType, Dict[str, Any]]


@dataclass
class ConflictContext:
    """Context container passed to strategies during resolution.

    Attributes:
        conflict_manager: Optional integration with the core conflict manager.
        resources: Mapping of resource_id to resource details.
        tasks: Mapping of task_id to task details.
        workers: Mapping of worker_id to worker details.
        budget: Budget-related information.
        timeout_seconds: Maximum time allowed for resolution attempt.
    """

    conflict_manager: Optional["ConflictManagerProtocol"] = None
    resources: MutableMapping[str, Any] = field(default_factory=dict)
    tasks: MutableMapping[str, Any] = field(default_factory=dict)
    workers: MutableMapping[str, Any] = field(default_factory=dict)
    budget: MutableMapping[str, Any] = field(default_factory=dict)
    timeout_seconds: int = RESOLUTION_TIMEOUT_SECONDS_DEFAULT


# ---------------------------------------------------------------------------
# Conflict Manager Integration (Protocol)
# ---------------------------------------------------------------------------


@runtime_checkable
class ConflictManagerProtocol(Protocol):
    """Protocol describing the expected interface of core.conflict_manager.

    This allows the ConflictResolver to integrate with an existing conflict
    manager implementation without a hard dependency on its concrete type.
    """

    def get_conflict(self, conflict_id: str) -> Conflict:
        """Retrieve a conflict by its identifier.

        Args:
            conflict_id: Unique identifier of the conflict.

        Returns:
            The corresponding Conflict instance.
        """

    def update_conflict(self, conflict: Conflict) -> None:
        """Persist updates to a conflict.

        Args:
            conflict: Conflict instance with updated fields.
        """

    def log_resolution(self, conflict_id: str, resolution: ConflictResolutionResult) -> None:
        """Log the resolution details for auditing.

        Args:
            conflict_id: Unique identifier of the conflict.
            resolution: Result of the resolution attempt.
        """

    def escalate_conflict(self, conflict_id: str, reason: str) -> None:
        """Escalate the conflict for manual intervention.

        Args:
            conflict_id: Unique identifier of the conflict.
            reason: Description of why the conflict was escalated.
        """


# ---------------------------------------------------------------------------
# Strategy Pattern for Conflict Resolution
# ---------------------------------------------------------------------------


class ConflictResolutionStrategy(ABC):
    """Abstract base class for conflict resolution strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of the strategy."""

    @abstractmethod
    def resolve(self, conflict: Conflict, context: ConflictContext) -> ConflictResolutionResult:
        """Attempt to resolve the given conflict.

        Args:
            conflict: The conflict to resolve.
            context: Additional context required to resolve the conflict.

        Returns:
            A ConflictResolutionResult describing the outcome.
        """


# ---------------------------------------------------------------------------
# Concrete Strategies
# ---------------------------------------------------------------------------


class ResourceContentionStrategy(ConflictResolutionStrategy):
    """Resolve resource contention conflicts using priority-based allocation.

    Expected payload structure:
        {
            "resource_id": str,
            "total_units": int,
            "requests": [
                {
                    "task_id": str,
                    "priority": int,  # higher is more important
                    "requested_units": int
                },
                ...
            ]
        }

    Strategy:
        - Sort requests by priority descending.
        - Allocate units to highest priority tasks first.
        - Defer or partially fulfill lower priority tasks when capacity is exhausted.
    """

    @property
    def name(self) -> str:
        """Return the strategy name."""
        return "resource_contention_priority"

    def resolve(self, conflict: Conflict, context: ConflictContext) -> ConflictResolutionResult:
        """Resolve resource contention via priority-based allocation."""
        start_time = time.monotonic()
        payload = conflict.payload

        resource_id = payload.get("resource_id")
        total_units = payload.get("total_units")
        requests = payload.get("requests", [])

        if resource_id is None or total_units is None:
            msg = "Invalid payload: 'resource_id' and 'total_units' are required."
            logger.error("%s Conflict ID: %s", msg, conflict.conflict_id)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return ConflictResolutionResult(
                success=False,
                resolved=False,
                escalated=True,
                resolution_type="invalid_payload",
                message=msg,
                risk_score=conflict.risk_score,
                strategy_name=self.name,