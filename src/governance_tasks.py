from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure module-level logger
LOGGER = logging.getLogger(__name__)

# Constants
DEFAULT_DB_PATH = "governance_tasks.db"
STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_DRY_RUN_COMPLETED = "dry_run_completed"
ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"
SQLITE_BOOLEAN_TRUE = 1
SQLITE_BOOLEAN_FALSE = 0


@dataclass
class GovernanceTask:
    """Represents a governance task record.

    Attributes:
        id: Unique identifier of the task.
        name: Logical name of the task (e.g., 'send_email', 'sync_permissions').
        parameters: Arbitrary parameters for the task, stored as JSON.
        dry_run: Whether this task should execute in dry-run mode.
        dry_run_result: Simulated result for dry-run executions, if any.
        status: Current status of the task.
        created_at: UTC timestamp of creation.
        updated_at: UTC timestamp of the last update.
    """

    id: int
    name: str
    parameters: Dict[str, Any]
    dry_run: bool
    dry_run_result: Optional[Dict[str, Any]]
    status: str
    created_at: datetime
    updated_at: datetime


class GovernanceTaskManager:
    """Manages governance tasks, including dry-run aware execution.

    This manager is responsible for:

    * Creating governance_tasks records in an SQLite database.
    * Executing tasks with or without dry-run mode.
    * Storing simulated results for dry-run executions in dry_run_result.
    * Ensuring that dry-run tasks produce no external side effects.

    Typical usage:

        manager = GovernanceTaskManager()
        task_id = manager.create_task(
            name="send_email",
            parameters={"recipients": ["a@example.com"]},
            dry_run=True,
        )
        manager.execute_task(task_id)
        task = manager.get_task(task_id)
        print(task.dry_run_result)

    To enable dry-run for a task, set `dry_run=True` at creation time or ensure
    that the `governance_tasks.dry_run` column is true (1) for the task before
    execution. During execution:

    * Dry-run tasks:
        - Skip any real external API calls.
        - Compute a simulated outcome based solely on task input.
        - Persist the simulated outcome into `dry_run_result`.
        - Set status to `dry_run_completed`.
    * Non-dry-run tasks:
        - Perform the "real" execution path (where actual side effects would be).
        - Record side-effect descriptions into the `external_side_effects` table.
        - Set status to `completed`.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        """Initialize the task manager and ensure database schema exists.

        Args:
            db_path: Path to the SQLite database file. Use ':memory:' for tests.
        """
        self._db_path = db_path
        try:
            self._connection = sqlite3.connect(self._db_path)
            self._connection.row_factory = sqlite3.Row
            # Enable foreign key enforcement
            self._connection.execute("PRAGMA foreign_keys = ON")
        except sqlite3.Error as exc:
            LOGGER.exception("Failed to connect to SQLite database at %s", db_path)
            raise
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create required tables if they do not exist."""
        create_tasks_sql = """
        CREATE TABLE IF NOT EXISTS governance_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parameters TEXT NOT NULL,
            dry_run INTEGER NOT NULL DEFAULT 0,
            dry_run_result TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
        create_effects_sql = """
        CREATE TABLE IF NOT EXISTS external_side_effects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            effect TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES governance_tasks(id)
        )
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(create_tasks_sql)
            cursor.execute(create_effects_sql)
            self._connection.commit()
        except sqlite3.Error as exc:
            LOGGER.exception("Failed to ensure database schema: %s", exc)
            raise

    def create_task(
        self,
        name: str,
        parameters: Dict[str, Any],
        dry_run: bool = False,
    ) -> int:
        """Create a new governance task.

        Args:
            name: Logical name of the task.
            parameters: Task parameters to be serialized as JSON.
            dry_run: If True, mark this task to be executed in dry-run mode.

        Returns:
            The ID of the newly created task.
        """
