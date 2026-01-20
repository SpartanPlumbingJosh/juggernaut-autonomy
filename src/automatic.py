import copy
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_FAILURE_METRIC_NAME: str = "loss"
DEFAULT_FAILURE_METRIC_THRESHOLD: float = 0.8
DEFAULT_HEALTH_DEGRADATION_THRESHOLD: float = 0.5
INITIAL_SYSTEM_HEALTH: float = 1.0

CHECKPOINT_REASON_BASELINE: str = "baseline"
CHECKPOINT_REASON_MILESTONE: str = "milestone"
CHECKPOINT_REASON_PRE_RISK: str = "pre-risk"
CHECKPOINT_REASON_FINAL: str = "final"

ROLLBACK_REASON_THRESHOLD: str = "threshold-exceeded"
ROLLBACK_REASON_HEALTH_DEGRADATION: str = "health-degradation"
ROLLBACK_REASON_EXPLICIT: str = "explicit-failure"
ROLLBACK_REASON_OPERATION_ERROR: str = "operation-error"


@dataclass
class ExperimentState:
    """Represents the mutable state of an experiment.

    Attributes:
        parameters: Hyperparameters or config for the experiment.
        metrics: Collected metrics (e.g., loss, accuracy).
        system_health: Synthetic health indicator for the system (0.0-1.0).
        status: Human-readable status string.
    """

    parameters: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    system_health: float = INITIAL_SYSTEM_HEALTH
    status: str = "initialized"


@dataclass
class Checkpoint:
    """Represents a saved checkpoint for an experiment.

    Attributes:
        id: Unique identifier for the checkpoint.
        experiment_id: Identifier of the experiment this checkpoint belongs to.
        created_at: Timestamp of when the checkpoint was created.
        state: Deep copy of the experiment state at checkpoint time.
        reason: Human-readable reason/category for the checkpoint.
        index: Monotonic index within the experiment's checkpoint sequence.
    """

    id: str
    experiment_id: str
    created_at: datetime
    state: ExperimentState
    reason: str
    index: int


@dataclass
class RollbackEvent:
    """Represents a rollback occurrence for an experiment.

    Attributes:
        id: Unique identifier for the rollback event.
        experiment_id: Identifier of the experiment this rollback belongs to.
        created_at: Timestamp of when the rollback completed.
        from_checkpoint_id: Identifier of the checkpoint we rolled back from.
        to_checkpoint_id: Identifier of the checkpoint we rolled back to.
        reason: Human-readable reason for the rollback.
    """

    id: str
    experiment_id: str
    created_at: datetime
    from_checkpoint_id: Optional[str]
    to_checkpoint_id: str
    reason: str


@dataclass
class Experiment:
    """Container for experiment data, checkpoints, and rollback history.

    Attributes:
        id: Unique identifier for the experiment.
        name: Human-readable experiment name.
        checkpoints: Ordered list of checkpoints taken for the experiment.
        rollback_history: Ordered list of rollback events for the experiment.
        current_state: The current mutable state of the experiment.
    """

    id: str
    name: str
    checkpoints: List[Checkpoint] = field(default_factory=list)
    rollback_history: List[RollbackEvent] = field(default_factory=list)
    current_state: Optional[ExperimentState] = None


class AutomaticCheckpointManager:
    """Manages automatic checkpoints and rollbacks for experiments.

    This class encapsulates the logic that would typically live in
    core/experiments.py related to checkpointing and rollback behavior.

    It guarantees:
        - A baseline checkpoint is created when the experiment starts.
        - Checkpoints can be created at milestones and before risky operations.
        - Automatic rollback triggers based on metrics, health, or explicit failure.
    """

    def __init__(
        self,
        failure_metric_name: str = DEFAULT_FAILURE_METRIC_NAME,
        failure_metric_threshold: float = DEFAULT_FAILURE_METRIC_THRESHOLD,
        health_degradation_threshold: float = DEFAULT_HEALTH_DEGRADATION_THRESHOLD,
    ) -> None:
        """Initialize the checkpoint manager.

        Args:
            failure_metric_name: Name of the metric used for failure detection.
            failure_metric_threshold: Threshold above which the experiment fails.
            health_degradation_threshold: Threshold below which system health fails.
        """
        self._failure_metric_name = failure_metric_name
        self._failure_metric_threshold = failure_metric_threshold
        self._health_degradation_threshold = health_degradation_threshold

    def start_experiment(self, experiment: Experiment, initial_parameters: Dict[str, Any]) -> None:
        """Initialize and create a baseline checkpoint for an experiment.

        Args:
            experiment: The experiment to start.
            initial_parameters: Initial configuration/parameters for the experiment.

        Raises:
            ValueError: If the experiment already has a current state.
        """
        if experiment.current_state is not None:
            raise ValueError(f"Experiment {experiment.id} has already been started.")

        logger.info("Starting experiment '%s' (%s)", experiment.name, experiment.id)
        initial_state = ExperimentState(
            parameters=copy.deepcopy