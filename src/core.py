import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

LOGGER = logging.getLogger(__name__)

# Constants
IMPACT_SIMULATIONS_TABLE_NAME = "impact_simulations"
DEFAULT_SIMULATION_TYPE = "default"
ISO_8601_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
DEFAULT_MIN_ACCURACY_FOR_PROMOTION = 0.6
ACCURACY_MINIMUM_DATA_POINTS = 1


@dataclass
class ExperimentConfig:
    """Configuration for an experiment used as input to the impact simulation.

    Attributes:
        experiment_id: Unique identifier for the experiment.
        simulation_type: The type of simulation to run.
        parameters: Arbitrary configuration parameters for the experiment.
    """

    experiment_id: str
    simulation_type: str = DEFAULT_SIMULATION_TYPE
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentOutcome:
    """Actual observed outcome for a completed experiment.

    Attributes:
        experiment_id: Unique identifier for the experiment.
        observed_metrics: Observed metrics keyed by metric name.
        completed_at: Datetime when the experiment completed.
    """

    experiment_id: str
    observed_metrics: Dict[str, float]
    completed_at: datetime


@dataclass
class ImpactSimulationRecord:
    """Represents a stored impact simulation record.

    Attributes:
        id: Primary key of the simulation record.
        experiment_id: Associated experiment identifier.
        simulation_type: Type of simulation executed.
        input_params: Input parameters used for the simulation.
        predicted_outcomes: Predicted outcomes from the simulation.
        confidence_scores: Confidence scores for each predicted outcome.
        actual_outcomes: Actual outcomes after experiment completion.
        accuracy_score: Accuracy of the simulation vs actual outcomes.
        created_at: Datetime when the simulation was created.
        completed_at: Datetime when the experiment was completed (if any).
    """

    id: Optional[int]
    experiment_id: str
    simulation_type: str
    input_params: Dict[str, Any]
    predicted_outcomes: Dict[str, float]
    confidence_scores: Dict[str, float]
    actual_outcomes: Optional[Dict[str, float]]
    accuracy_score: Optional[float]
    created_at: datetime
    completed_at: Optional[datetime]


@dataclass
class ExperimentResult:
    """Result wrapper for an experiment run with impact simulation.

    Attributes:
        outcome: Actual observed experiment outcome.
        simulation: Impact simulation record, including accuracy if completed.
        should_promote: Decision flag indicating if experiment should be promoted.
    """

    outcome: ExperimentOutcome
    simulation: Optional[ImpactSimulationRecord]
    should_promote: bool


def _datetime_to_str(value: datetime) -> str:
    """Convert a datetime to an ISO 8601 string.

    Args:
        value: Datetime value.

    Returns:
        ISO 8601 formatted string.
    """
    return value.strftime(ISO_8601_FORMAT)


def _str_to_datetime(value: str) -> datetime:
    """Convert an ISO 8601 string to a datetime.

    Args:
        value: ISO 8601 formatted string.

    Returns:
        Parsed datetime.
    """
    return datetime.strptime(value, ISO_8601_FORMAT)


class ImpactSimulationRepository:
    """Repository for persisting and querying impact simulation records."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Initialize the repository.

        Args:
            connection: SQLite database connection.
        """
        self._connection = connection
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure that the impact_simulations table exists."""
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {IMPACT_SIMULATIONS_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT NOT NULL,
            simulation_type TEXT NOT NULL,
            input_params TEXT NOT NULL,
            predicted_outcomes TEXT NOT NULL,
            confidence_scores TEXT NOT NULL,
            actual_outcomes TEXT,
            accuracy_score REAL,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
        """
        create_index_sql = f"""
        CREATE INDEX IF NOT EXISTS idx_{IMPACT_SIMULATIONS_TABLE_NAME}_experiment_id
        ON {IMPACT_SIMULATIONS_TABLE_NAME} (experiment_id);
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(create_table_sql)
            cursor.execute(create_index_sql)
            self._connection.commit()
            LOGGER.debug("Ensured impact_simulations table and indices exist.")
        except sqlite3.Error as exc:
            LOGGER.exception("Failed to ensure impact_simulations schema: %s", exc)
            raise

    def _row_to_record(self, row: Tuple[Any, ...]) -> ImpactSimulationRecord:
        """Convert a database row tuple to an ImpactSimulationRecord.

        Args:
            row: Database row tuple with columns in SELECT order:
                (id, experiment_id, simulation_type, input_params,
                 predicted_outcomes, confidence_scores, actual_outcomes,
                 accuracy_score, created_at, completed_at)

        Returns:
            ImpactSimulationRecord instance with parsed JSON and datetime fields.
        """
        return ImpactSimulationRecord(
            id=row[0],
            experiment_id=row[1],
            simulation_type=row[2],
            input_params=json.loads(row[3]),
            predicted_outcomes=json.loads(row[4]),
            confidence_scores=json.loads(row[5]),
            actual_outcomes=json.loads(row[6]) if row[6] is not None else None,
            accuracy_score=row[7],
            created_at=_str_to_datetime(row[8]),
            completed_at=_str_to_datetime(row[9]) if row[9] is not None else None,
        )

    def insert_simulation(self, record: ImpactSimulationRecord) -> int:
        """Insert a new simulation record into the database.

        Args:
            record: ImpactSimulationRecord to insert. The id field is ignored.

        Returns:
            The generated primary key ID.
        """
        sql = f"""
        INSERT INTO {IMPACT_SIMULATIONS_TABLE_NAME} (
            experiment_id,
            simulation_type,
            input_params,
            predicted_outcomes,
            confidence_scores,
            actual_outcomes,
            accuracy_score,
            created_at,
            completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            record.experiment_id,
            record.simulation_type,
            json.dumps(record.input_params),
            json.dumps(record.predicted_outcomes),
            json.dumps(record.confidence_scores),
            json.dumps(record.actual_outcomes) if record.actual_outcomes is not None else None,
            record.accuracy_score,
            _datetime_to_str(record.created_at),
            _datetime_to_str(record.completed_at) if record.completed_at is not None else None,
        )
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, params)
            self._connection.commit()
            simulation_id = int(cursor.lastrowid)
            LOGGER.debug("Inserted impact simulation record with id=%d", simulation_id)
            return simulation_id
        except sqlite3.Error as exc:
            LOGGER.exception("Failed to insert impact simulation: %s", exc)
            raise

    def update_with_actuals(
        self,
        experiment_id: str,
        actual_outcomes: Dict[str, float],
        accuracy: float,
        completed_at: datetime,
    ) -> Optional[ImpactSimulationRecord]:
        """Update the latest simulation for an experiment with actual outcomes.

        Args:
            experiment_id: Experiment identifier.
            actual_outcomes: Observed outcomes for the experiment.
            accuracy: Computed accuracy of the simulation.
            completed_at: Datetime when the experiment completed.

        Returns:
            Updated ImpactSimulationRecord, or None if no simulation exists.
        """
        latest = self.get_latest_for_experiment(experiment_id)
        if latest is None:
            LOGGER.warning(
                "No impact simulation found for experiment_id=%s to update with actuals.",
                experiment_id,
            )
            return None

        sql = f"""
        UPDATE {IMPACT_SIMULATIONS_TABLE_NAME}
        SET actual_outcomes = ?, accuracy_score = ?, completed_at = ?
        WHERE id = ?
        """
        params = (
            json.dumps(actual_outcomes),
            accuracy,
            _datetime_to_str(completed_at),
            latest.id,
        )
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, params)
            self._connection.commit()
            LOGGER.debug(
                "Updated impact simulation id=%d for experiment_id=%s with actuals and accuracy=%f",
                latest.id,
                experiment_id,
                accuracy,
            )
        except sqlite3.Error as exc:
            LOGGER.exception("Failed to update impact simulation with actuals: %s", exc)
            raise

        # Return refreshed record
        return self.get_by_id(latest.id)

    def get_by_id(self, simulation_id: int) -> Optional[ImpactSimulationRecord]:
        """Retrieve a simulation record by its primary key.

        Args:
            simulation_id: Primary key of the simulation record.

        Returns:
            ImpactSimulationRecord if found, otherwise None.
        """
        sql = f"""
        SELECT
            id,
            experiment_id,
            simulation_type,
            input_params,
            predicted_outcomes,
            confidence_scores,
            actual_outcomes,
            accuracy_score,
            created_at,
            completed_at
        FROM {IMPACT_SIMULATIONS_TABLE_NAME}
        WHERE id = ?
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (simulation_id,))
            row = cursor.fetchone()
        except sqlite3.Error as exc:
            LOGGER.exception("Failed to query impact simulation by id: %s", exc)
            raise

        if row is None:
            return None
        return self._row_to_record(row)

    def get_latest_for_experiment(self, experiment_id: str) -> Optional[ImpactSimulationRecord]:
        """Retrieve the latest simulation record for an experiment.

        Args:
            experiment_id: Experiment identifier.

        Returns:
            ImpactSimulationRecord if found, otherwise None.
        """
        sql = f"""
        SELECT
            id,
            experiment_id,
            simulation_type,
            input_params,
            predicted_outcomes,
            confidence_scores,
            actual_outcomes,
            accuracy_score,
            created_at,
            completed_at
        FROM {IMPACT_SIMULATIONS_TABLE_NAME}
        WHERE experiment_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (experiment_id,))
            row = cursor.fetchone()
        except sqlite3.Error as exc:
            LOGGER.exception(
                "Failed to query latest impact simulation for experiment_id=%s: %s",
                experiment_id,
                exc,
            )
            raise

        if row is None:
            return None
        return self._row_to_record(row)
