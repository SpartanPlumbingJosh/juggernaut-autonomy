import copy
import logging
from typing import Any, Dict

import pytest

import automatic


@pytest.fixture
def experiment() -> automatic.Experiment:
    return automatic.Experiment(id="exp-123", name="Test Experiment")


@pytest.fixture
def manager() -> automatic.AutomaticCheckpointManager:
    return automatic.AutomaticCheckpointManager()


@pytest.fixture
def initial_parameters() -> Dict[str, Any]:
    # Nested structure to validate deep copy behavior
    return {
        "learning_rate": 0.01,
        "layers": [64, 64],
        "config": {"dropout": 0.5, "activation": "relu"},
    }


def test_experiment_state_defaults_are_set():
    state = automatic.ExperimentState()

    assert state.parameters == {}
    assert state.metrics == {}
    assert state.system_health == automatic.INITIAL_SYSTEM_HEALTH
    assert state.status == "initialized"


def test_experiment_state_custom_values():
    params = {"lr": 0.1}
    metrics = {"loss": 0.5}
    state = automatic.ExperimentState(
        parameters=params, metrics=metrics, system_health=0.9, status="running"
    )

    assert state.parameters is params
    assert state.metrics is metrics
    assert state.system_health == 0.9
    assert state.status == "running"


def test_checkpoint_dataclass_fields(experiment):
    state = automatic.ExperimentState(parameters={"a": 1})
    cp = automatic.Checkpoint(
        id="cp-1",
        experiment_id=experiment.id,
        created_at=automatic.datetime.utcnow(),
        state=state,
        reason=automatic.CHECKPOINT_REASON_MILESTONE,
        index=3,
    )

    assert cp.id == "cp-1"
    assert cp.experiment_id == experiment.id
    assert isinstance(cp.created_at, automatic.datetime)
    assert cp.state is state
    assert cp.reason == automatic.CHECKPOINT_REASON_MILESTONE
    assert cp.index == 3


def test_rollback_event_dataclass_fields(experiment):
    rb = automatic.RollbackEvent(
        id="rb-1",
        experiment_id=experiment.id,
        created_at=automatic.datetime.utcnow(),
        from_checkpoint_id="cp-3",
        to_checkpoint_id="cp-2",
        reason=automatic.ROLLBACK_REASON_THRESHOLD,
    )

    assert rb.id == "rb-1"
    assert rb.experiment_id == experiment.id
    assert isinstance(rb.created_at, automatic.datetime)
    assert rb.from_checkpoint_id == "cp-3"
    assert rb.to_checkpoint_id == "cp-2"
    assert rb.reason == automatic.ROLLBACK_REASON_THRESHOLD


def test_experiment_defaults():
    exp = automatic.Experiment(id="exp-1", name="My Experiment")

    assert exp.id == "exp-1"
    assert exp.name == "My Experiment"
    assert exp.checkpoints == []
    assert exp.rollback_history == []
    assert exp.current_state is None


def test_experiment_collections_are_independent():
    exp1 = automatic.Experiment(id="exp-1", name="E1")
    exp2 = automatic.Experiment(id="exp-2", name="E2")

    exp1.checkpoints.append("dummy-checkpoint")
    exp1.rollback_history.append("dummy-rollback")

    assert exp2.checkpoints == []
    assert exp2.rollback_history == []


def test_automatic_checkpoint_manager_uses_default_thresholds():
    manager = automatic.AutomaticCheckpointManager()

    assert manager._failure_metric_name == automatic.DEFAULT_FAILURE_METRIC_NAME
    assert manager._failure_metric_threshold == automatic.DEFAULT_FAILURE_METRIC_THRESHOLD
    assert manager._health_degradation_threshold == automatic.DEFAULT_HEALTH_DEGRADATION_THRESHOLD


def test_automatic_checkpoint_manager_allows_custom_thresholds():
    manager = automatic.AutomaticCheckpointManager(
        failure_metric_name="accuracy",
        failure_metric_threshold=0.2,
        health_degradation_threshold=0.3,
    )

    assert manager._failure_metric_name == "accuracy"
    assert manager._failure_metric_threshold == 0.2
    assert manager._health_degradation_threshold == 0.3


def test_start_experiment_sets_initial_state_with_deep_copied_parameters(
    manager, experiment, initial_parameters
):
    manager.start_experiment(experiment, initial_parameters)

    assert isinstance(experiment.current_state, automatic.ExperimentState)

    # Parameters are equal but not the same object (deep copy)
    assert experiment.current_state.parameters == initial_parameters
    assert experiment.current_state.parameters is not initial_parameters

    # Nested objects should also be deep-copied
    assert experiment.current_state.parameters["layers"] == initial_parameters["layers"]
    assert experiment.current_state.parameters["layers"] is not initial_parameters["layers"]

    assert experiment.current_state.parameters["config"] == initial_parameters["config"]
    assert experiment.current_state.parameters["config"] is not initial_parameters["config"]

    # System health should start at the defined initial health
    assert experiment.current_state.system_health == automatic.INITIAL_SYSTEM_HEALTH


def test_start_experiment_creates_baseline_checkpoint(manager, experiment, initial_parameters):
    manager.start_experiment(experiment, initial_parameters)

    # A baseline checkpoint should be created when the experiment starts
    assert len(experiment.checkpoints) == 1
    checkpoint = experiment.checkpoints[0]

    assert checkpoint.experiment_id == experiment.id
    assert checkpoint.reason == automatic.CHECKPOINT