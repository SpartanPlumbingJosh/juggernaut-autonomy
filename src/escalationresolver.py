from __future__ import annotations

import logging
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)

# Constants
LOW_RISK_AUTO_APPROVAL_TIMEOUT_MINUTES: int = 15
AUTO_RETRY_MAX_ATTEMPTS: int = 3
AUTO_REASSIGN_TIMEOUT_MINUTES: int = 30
SLA_TARGET_SECONDS: int = 60 * 60  # 1 hour
DASHBOARD_DEFAULT_LOOKBACK_HOURS: int = 24
DEFAULT_RESOLUTION_LOOP_INTERVAL_SECONDS: int = 30


class EscalationStatus(Enum):
    """Enumeration of escalation lifecycle states."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESOLVED = "resolved"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class EscalationRiskLevel(Enum):
    """Enumeration of escalation risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Escalation:
    """Represents an escalation item in the system.

    Attributes:
        id: Unique identifier for the escalation.
        created_at: UTC timestamp when escalation was created.
        updated_at: UTC timestamp of the last modification.
        status: Current status of the escalation.
        risk_level: Risk classification of the escalation.
        metadata: Arbitrary metadata describing the escalation context.
        retry_count: Number of automatic retries already performed.
        assigned_worker_id: Identifier of the currently assigned worker, if any.
        resolved_at: UTC timestamp when the escalation was resolved (if resolved).
        resolution_reason: Human-readable explanation of the resolution.
        manual_only: Whether the escalation must always be handled manually.
    """

    id: str
    created_at: datetime
    updated_at: datetime
    status: EscalationStatus
    risk_level: EscalationRiskLevel
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    assigned_worker_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_reason: Optional[str] = None
    manual_only: bool = False


class ResolutionAction(Enum):
    """Enumeration of rule engine actions for escalations."""

    NO_ACTION = "no_action"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETRY_SCHEDULED = "retry