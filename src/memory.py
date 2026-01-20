import json
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from math import exp, log1p
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    # Optional integration with existing learning components if present
    from core.learning import LearningEngine  # type: ignore
except (ImportError, ModuleNotFoundError):
    LearningEngine = None  # type: ignore

try:
    from core.learning_capture import LearningCapture  # type: ignore
except (ImportError, ModuleNotFoundError):
    LearningCapture = None  # type: ignore


LOGGER = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.getenv("JUGGERNAUT_MEMORY_DB_PATH", "memory.db")

TABLE_MEMORIES = "memories"
TABLE_SHARED_MEMORIES = "shared_memory"

DEFAULT_INITIAL_IMPORTANCE = 1.0
MAX_IMPORTANCE = 10.0
IMPORTANCE_INCREMENT_ON_ACCESS = 0.2
IMPORTANCE_INCREMENT_ON_CREATION = 0.5

# Half-life of memory importance in days (for decay scoring)
IMPORTANCE_HALF_LIFE_DAYS = 14.0

# Limits
MAX_CONTENT_LENGTH = 8000
DEFAULT_LIMIT_PER_CATEGORY = 10

# Stats window default (hours)
DEFAULT_STATS_WINDOW_HOURS = 24


class MemoryCategory(str, Enum):
    """Enumeration of supported memory categories."""

    WORKER_SPECIFIC = "worker_specific"
    TASK_TYPE_PATTERN = "task_type_pattern"
    SYSTEM_WIDE = "system_wide"
    CROSS_DEPARTMENT = "cross_department"


@dataclass
class Memory:
    """Represents a single memory entity.

    Attributes:
        id: Primary key in the underlying storage table.
        table_name: Name of the table that stores this memory.
        category: Memory category indicating its scope.
        worker_id: Optional identifier of the worker this memory relates to.
        department: Optional department context.
        task_type: Optional task type associated with the memory.
        content: Textual content of the memory.
        importance: Raw importance score (before decay).
        created_at: Creation timestamp (UTC).
        updated_at: Last update timestamp (UTC).
        last_accessed_at: Last time this memory was accessed (UTC).
        access_count: Number of times this memory has been accessed.
        is_active: Whether this memory is active and retrievable.
        tags: Optional tags associated with the memory.
    """

    id: Optional[int]
    table_name: str
    category: MemoryCategory
    worker_id: Optional[str]
    department: Optional[str]
    task_type: Optional[str]
    content: str
    importance: float
    created_at: datetime
    updated_at: datetime
    last_accessed_at: Optional[datetime]
    access_count: int
    is_active: bool
    tags: Optional[List[str]]


class MemoryRepository:
    """Repository responsible for persistence and retrieval of memories.

    This implementation uses SQLite as a backing store and manages both
    worker-specific and shared memories.

    Attributes:
        db_path: Filesystem path to the SQLite database.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize the MemoryRepository.

        Args:
            db_path: Optional path to the SQLite database. Defaults to
                `DEFAULT_DB_PATH` if not provided.
        """
        self._db_path: str = db_path or DEFAULT_DB_PATH
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self._db_path, check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES
        )
        self._connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Initialize database schema for memories and shared memories."""
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {{table_name}} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            worker_id TEXT,
            department TEXT,
            task_type TEXT,
            content TEXT NOT NULL,
            importance REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_accessed_at TEXT,
            access_count INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            tags TEXT
        );
        """

        with self._lock:
            try