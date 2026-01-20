from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import (
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Protocol,
    Sequence,
    runtime_checkable,
)

try:
    import psutil  # type: ignore[import]
except ImportError:
    psutil = None  # type: ignore[assignment]

# Constants
HEARTBEAT_WARNING_THRESHOLD_MINUTES: int = 5
HEARTBEAT_FAILOVER_THRESHOLD_MINUTES: int = 15
MAX_WORKER_RECOVERY_MINUTES: int = 5

CPU_USAGE_THRESHOLD_PERCENT: float = 95.0
MEMORY_USAGE_THRESHOLD_PERCENT: float = 95.0

DEFAULT_HEALTH_CHECK_INTERVAL_SECONDS: int = 30

LOGGER = logging.getLogger(__name__)


class WorkerHealthStatus(Enum):
    """Represents the heartbeat health status of a worker."""

    HEALTHY = auto()
    WARNING = auto()
    FAILED = auto()


class FailureType(Enum):
    """Represents different types of failover scenarios."""

    HEARTBEAT_STALE = auto()
    DB_UNAVAILABLE = auto()
    API_UNAVAILABLE = auto()
    RESOURCE_EXHAUSTION = auto()


@dataclass
class Worker:
    """Represents a worker or orchestrator process in the system.

    Attributes:
        worker_id: Unique identifier for the worker.
        role: Logical role of the worker (e.g., "worker", "orchestrator").
        last_heartbeat: Timestamp of the last heartbeat from this worker.
        active: Indicates whether the worker is considered active.
        metadata: Arbitrary key-value data associated with the worker.
    """

    worker_id: str
    role: str
    last_heartbeat: datetime
    active: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class Task:
    """Represents a unit of work assigned to a worker.

    Attributes:
        task_id: Unique task identifier.
        worker_id: Identifier of the worker currently assigned to the task.
        payload: Arbitrary key-value data for the task.
    """

    task_id: str
    worker_id: Optional[str]
    payload: Dict[str, str] = field(default_factory=dict)


@dataclass
class FailoverEvent:
    """Represents a failover event and its recovery details.

    Attributes:
        worker_id: Identifier of the affected worker, if applicable.
        failure_type: Type of failure that triggered failover.
        detected_at: Time the failure was detected.
        recovered_at: Time the system recovered from the failure.
        details: Human-readable description of the failure and recovery.
        recovery_duration: Time in seconds between detection and recovery.
    """

    worker_id: Optional[str]
    failure_type: FailureType
    detected_at: datetime
    recovered_at: Optional[datetime] = None
    details: str = ""
    recovery_duration: Optional[float] = None


@runtime_checkable
class WorkerRepository(Protocol):
    """Protocol for accessing and mutating worker state."""

    def get_all_workers(self) -> Sequence[Worker]:
        """Return all known workers.

        Returns:
            A sequence of Worker instances.
        """
        ...

    def get_worker(self, worker_id: str) -> Optional[Worker]:
        """Return a single worker by ID, or None if not found.

        Args:
            worker_id: Identifier of the worker.

        Returns:
            The Worker or None.
        """
        ...

    def save_worker(self, worker: Worker) -> None:
        """Create or update a worker record.

        Args:
            worker: Worker instance