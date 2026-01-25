import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from core import (
    ACCURACY_MINIMUM_DATA_POINTS,
    DEFAULT_MIN_ACCURACY_FOR_PROMOTION,
    DEFAULT_SIMULATION_TYPE,
    IMPACT_SIMULATIONS_TABLE_NAME,
    ExperimentConfig,
    ExperimentOutcome,
    ExperimentResult,
    ImpactSimulationRecord,
    ImpactSimulationRepository,
    _datetime_to_str,
    _str_to_datetime,
)


@pytest.fixture
def db_connection():
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def repository(db_connection):
    return ImpactSimulationRepository(db_connection)


@pytest.fixture
def sample_datetime():
    # Fixed datetime with microseconds to test round trips
    return datetime(2024, 1, 2, 3, 4, 5, 123456)


@pytest.fixture
def sample_experiment_id():
    return "exp-123"


@pytest.fixture
def sample_simulation_record(sample_experiment_id, sample_datetime):
    return ImpactSimulationRecord(
        id=None,
        experiment_id=sample_experiment_id,
        simulation_type="sim-type",
        input_params={"a": 1, "b": "x"},
        predicted_outcomes={"metric1": 1.23},
        confidence_scores={"metric1": 0.9},
        actual_outcomes=None,
        accuracy_score=None,
        created_at=sample_datetime,
        completed_at=None,
    )


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


def test_experiment_config_defaults_and_mutability():
    cfg1 = ExperimentConfig(experiment_id="exp-1")
    cfg2 = ExperimentConfig(experiment_id="exp-2")

    assert cfg1.simulation_type == DEFAULT_SIMULATION_TYPE
    assert cfg1.parameters == {}
    assert cfg2.parameters == {}
    assert cfg1.parameters is not cfg2.parameters

    cfg1.parameters["k"] = "v"
    assert "k" not in cfg2.parameters


def test_experiment_outcome_initialization(sample_experiment_id, sample_datetime):
    outcome = ExperimentOutcome(
        experiment_id=sample_experiment_id,
        observed_metrics={"m1": 1.0},
        completed_at=sample_datetime,
    )

    assert outcome.experiment_id == sample_experiment_id
    assert outcome.observed_metrics == {"m1": 1.0}
    assert outcome.completed_at == sample_datetime


def test_impact_simulation_record_initialization(sample_simulation_record, sample_datetime):
    rec = sample_simulation_record
    assert rec.id is None
    assert rec.experiment_id == "exp-123"
    assert rec.simulation_type == "sim-type"
    assert rec.input_params == {"a": 1, "b": "x"}
    assert rec.predicted_outcomes == {"metric1": 1.23}
    assert rec.confidence_scores == {"metric1": 0.9}
    assert rec.actual_outcomes is None
    assert rec.accuracy_score is None
    assert rec.created_at == sample_datetime
    assert rec.completed_at is None


def test_experiment_result_initialization(sample_experiment_id, sample_datetime, sample_simulation_record):
    outcome = ExperimentOutcome(
        experiment_id=sample_experiment_id,
        observed_metrics={"m": 2.0},
        completed_at=sample_datetime,
    )
    result = ExperimentResult(outcome=outcome, simulation=sample_simulation_record, should_promote=True)

    assert result.outcome is outcome
    assert result.simulation is sample_simulation_record
    assert result.should_promote is True


# ---------------------------------------------------------------------------
# Datetime helper tests
# ---------------------------------------------------------------------------


def test_datetime_to_str_and_back_round_trip(sample_datetime):
    s = _datetime_to_str(sample_datetime)
    parsed = _str_to_datetime(s)
    assert parsed == sample_datetime


def test_str_to_datetime_invalid_format_raises():
    with pytest.raises(ValueError):
        _str_to_datetime("not-a-timestamp")


# ---------------------------------------------------------------------------
# Repository schema tests
# ---------------------------------------------------------------------------


def test_repository_initialization_creates_table_and_index(db_connection):
    ImpactSimulationRepository(db_connection)

    cursor = db_connection.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (IMPACT_SIMULATIONS_TABLE_NAME,),
    )
    assert cursor.fetchone() is not None

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (f"idx_{IMPACT_SIMULATIONS_TABLE_NAME}_experiment_id",),
    )
    assert cursor.fetchone() is not None


def test_ensure_schema_db_error_is_propagated_and_logged(caplog):
    class FailingCursor:
        def execute(self, *args, **kwargs):
            raise sqlite3.Error("schema failure")

    class FailingConnection:
        def cursor(self):
            return FailingCursor()

        def commit(self):
            pass

    caplog.set_level(logging.ERROR)
    with pytest.raises(sqlite3.Error):
        ImpactSimulationRepository(FailingConnection())

    assert any("Failed to ensure impact_simulations schema" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Repository insert and retrieval tests
# ---------------------------------------------------------------------------


def test_insert_simulation_persists_record_and_returns_generated_id(repository, sample_simulation_record):
    simulation_id = repository.insert_simulation(sample_simulation_record)
    assert isinstance(simulation_id, int)
    assert simulation_id > 0

    fetched = repository.get_by_id(simulation_id)
    assert fetched is not None
    assert fetched.id == simulation_id
    assert fetched.experiment_id == sample_simulation_record.experiment_id
    assert fetched.simulation_type == sample_simulation_record.simulation_type
    assert fetched.input_params == sample_simulation_record.input_params
    assert fetched.predicted_outcomes == sample_simulation_record.predicted_outcomes
    assert fetched.confidence_scores == sample_simulation_record.confidence_scores
    assert fetched.actual_outcomes is None
    assert fetched.accuracy_score is None


def test_get_by_id_missing_returns_none(repository):
    assert repository.get_by_id(999999) is None


def test_get_latest_for_experiment_returns_latest(repository, sample_simulation_record, sample_datetime):
    rec1 = ImpactSimulationRecord(
        id=None,
        experiment_id=sample_simulation_record.experiment_id,
        simulation_type='t1',
        input_params={'x': 1},
        predicted_outcomes={'m': 1.0},
        confidence_scores={'m': 0.5},
        actual_outcomes=None,
        accuracy_score=None,
        created_at=sample_datetime,
        completed_at=None,
    )
    rec2 = ImpactSimulationRecord(
        id=None,
        experiment_id=sample_simulation_record.experiment_id,
        simulation_type='t2',
        input_params={'x': 2},
        predicted_outcomes={'m': 2.0},
        confidence_scores={'m': 0.6},
        actual_outcomes=None,
        accuracy_score=None,
        created_at=sample_datetime + timedelta(seconds=1),
        completed_at=None,
    )
    id1 = repository.insert_simulation(rec1)
    id2 = repository.insert_simulation(rec2)

    latest = repository.get_latest_for_experiment(sample_simulation_record.experiment_id)
    assert latest is not None
    assert latest.id == id2
    assert latest.simulation_type == 't2'
    assert latest.input_params == {'x': 2}
    assert id2 != id1


def test_update_with_actuals_updates_latest_record(repository, sample_simulation_record, sample_datetime):
    repository.insert_simulation(sample_simulation_record)
    updated = repository.update_with_actuals(
        experiment_id=sample_simulation_record.experiment_id,
        actual_outcomes={'metric1': 1.0},
        accuracy=0.75,
        completed_at=sample_datetime + timedelta(minutes=5),
    )

    assert updated is not None
    assert updated.actual_outcomes == {'metric1': 1.0}
    assert updated.accuracy_score == 0.75
    assert updated.completed_at == sample_datetime + timedelta(minutes=5)