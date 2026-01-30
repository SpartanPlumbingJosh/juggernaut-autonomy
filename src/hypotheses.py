import collections
import datetime
import hashlib
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple

# Constants
DEFAULT_DB_TIMEOUT_SECONDS: float = 30.0
DEFAULT_SCHEDULE_INTERVAL_SECONDS: int = 4 * 60 * 60  # 4 hours
MIN_LEARNINGS_PER_HYPOTHESIS: int = 3
MIN_EXPERIMENT_SUCCESSES_PER_HYPOTHESIS: int = 2
MIN_OPPORTUNITY_SCANS_PER_HYPOTHESIS: int = 2
OPPORTUNITY_IMPACT_THRESHOLD: float = 0.7
HYPOTHESIS_STATUS_NEW: str = "new"
SOURCE_LEARNINGS: str = "learnings"
SOURCE_EXPERIMENTS: str = "experiments"
SOURCE_OPPORTUNITY_SCANS: str = "opportunity_scans"

logger = logging.getLogger(__name__)


class ExperimentsAPI(Protocol):
    """Protocol for experiment-related operations used by hypothesis generation."""

    def suggest_hypotheses_from_results(
        self, experiments: Iterable[Dict[str, Any]]
    ) -> List[Tuple[str, str]]:
        """Suggest hypotheses from experiment results.

        Args:
            experiments: Iterable of experiment rows as dictionaries.

        Returns:
            A list of (title, description) tuples for suggested hypotheses.
        """


@dataclass
class HypothesisCandidate:
    """Represents a hypothesis candidate before persistence."""

    title: str
    description: str
    source: str
    evidence: List[Tuple[str, int]]  # List of (evidence_type, evidence_id)


def _get_connection(db_path: str) -> sqlite3.Connection:
    """Create a SQLite connection with appropriate settings.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        SQLite connection.
    """
    conn = sqlite3.connect(db_path, timeout=DEFAULT_DB_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    """Initialize required tables if they do not exist.

    This is idempotent and safe to call multiple times.

    Args:
        db_path: Path to the SQLite database file.
    """
    conn = _get_connection(db_path)
    try:
        cur = conn.cursor()

        # Core tables (simplified schemas, adapt as needed)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS learnings (
                id INTEGER PRIMARY KEY,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                result TEXT NOT NULL,
                metric_name TEXT,
                metric_value REAL,
                created_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunity_scans (
                id INTEGER PRIMARY KEY,
                area TEXT NOT NULL,
                description TEXT NOT NULL,
                impact_score REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        # Hypotheses and linking tables
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS hypotheses (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS hypothesis_evidence (
                id INTEGER PRIMARY KEY,
                hypothesis_id INTEGER NOT NULL,
                evidence_type TEXT NOT NULL,
                evidence_id INTEGER NOT NULL,
                FOREIGN KEY (hypothesis_id) REFERENCES hypotheses (id)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS hypothesis_experiments (
                id INTEGER PRIMARY KEY,
                hypothesis_id INTEGER NOT NULL,
                experiment_id INTEGER NOT NULL,
                FOREIGN KEY (hypothesis_id) REFERENCES hypotheses (id),
                FOREIGN KEY (experiment_id) REFERENCES experiments (id)
            )
            """
        )

        conn.commit()
        logger.debug("Database initialized for hypotheses module at %s", db_path)
    except sqlite3.Error as exc:
        logger.exception("Error initializing database: %s", exc)
        raise
    finally:
        conn.close()


class HypothesisGenerator:
    """Generates hypotheses from learnings, experiments, and opportunity scans."""

    def __init__(
        self,
        db_path: str,
        experiments_api: Optional[ExperimentsAPI] = None,
    ) -> None:
        """Initialize the hypothesis generator.

        Args:
            db_path: Path to the SQLite database file.
            experiments_api: Optional experiments API instance for advanced
                hypothesis generation from experiments.
        """
        self._db_path = db_path
        self._experiments_api = experiments_api

    def generate_hypotheses(self) -> List[int]:
        """Generate hypotheses from available data.

        This method orchestrates hypothesis generation from learnings,
        experiments, and opportunity scans, persists them, and creates
        links to supporting evidence and validating experiments.

        Returns:
            List of IDs of newly created hypotheses.
        """
        init_db(self._db_path)
        conn = _get_connection(self._db_path)
        new_ids: List[int] = []

        try:
            candidates: List[HypothesisCandidate] = []

            candidates.extend(self._generate_from_learnings(conn))
            candidates.extend(self._generate_from_experiments(conn))
            candidates.extend(self._generate_from_opportunity_scans(conn))

            if not candidates:
                logger.info("No new hypothesis candidates generated")
                return []

            for candidate in candidates:
                hypothesis_id = self._persist_hypothesis(conn, candidate)
                if hypothesis_id is not None:
                    new_ids.append(hypothesis_id)

            self._link_hypotheses_to_experiments(conn, new_ids)

            conn.commit()
            logger.info("Generated %d new hypotheses", len(new_ids))
            return new_ids
        except sqlite3.Error as exc:
            conn.rollback()
            logger.exception("Database error during hypothesis generation: %s", exc)
            raise
        finally:
            conn.close()

    def _generate_from_learnings(
        self, conn: sqlite3.Connection
    ) -> List[HypothesisCandidate]:
        """Generate hypothesis candidates by finding patterns in learnings.

        Args:
            conn: Active SQLite connection.

        Returns:
            List of hypothesis candidates derived from learnings.
        """
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, topic, content, created_at
                FROM learnings
                """
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            logger.exception("Failed to fetch learnings: %s", exc)
            raise

        if not rows:
            return []

        learnings_by_topic: Dict[str, List[sqlite3.Row]] = collections.defaultdict(list)
        for row in rows:
            learnings_by_topic[row["topic"]].append(row)

        candidates: List[HypothesisCandidate] = []
        now = datetime.datetime.utcnow().isoformat()

        for topic, topic_learnings in learnings_by_topic.items():
            if len(topic_learnings) < MIN_LEARNINGS_PER_HYPOTHESIS:
                continue

            title = f"Pattern observed in learnings about '{topic}'"
            description = (
                f"Based on {len(topic_learnings)} learnings about '{topic}', "
                "there appears to be a consistent pattern that may indicate a "
                "causal relationship or opportunity for improvement. "
                "This hypothesis should be validated with targeted experiments."
            )

            evidence = [("learning", int(row["id"])) for row in topic_learnings]

            candidates.append(
                HypothesisCandidate(
                    title=title,
                    description=description,
                    source=SOURCE_LEARNINGS,
                    evidence=evidence,
                )
            )

        logger.debug(
            "Generated %d hypothesis candidates from learnings at %s",
            len(candidates),
            now,
        )
        return candidates

    def _generate_from_experiments(
        self, conn: sqlite3.Connection
    ) -> List[HypothesisCandidate]:
        """Generate hypothesis candidates from experiment results.

        If an external experiments API with smarter logic is provided,
        it will be used; otherwise, a basic grouping by metric is applied.

        Args:
            conn: Active SQLite connection.

        Returns:
            List of hypothesis candidates derived from experiment results.
        """
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, name, result, metric_name, metric_value, created_at
                FROM experiments
                """
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            logger.exception("Failed to fetch experiments: %s", exc)
            raise

        if not rows:
            return []

        experiments: List[Dict[str, Any]] = [dict(row) for row in rows]

        if self._experiments_api is not None:
            try:
                suggestions = self._experiments_api.suggest_hypotheses_from_results(
                    experiments
                )
                candidates: List[HypothesisCandidate] = []