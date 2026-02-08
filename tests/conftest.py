"""
Pytest fixtures for JUGGERNAUT L1-L5 integration tests.

Provides database connection, test run tracking, and cleanup utilities.
"""

import os
import uuid
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Generator, Optional

import httpx
import pytest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


repo_root = Path(__file__).resolve().parent.parent
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


# =============================================================================
# CONSTANTS
# =============================================================================

DATABASE_URL = os.environ.get("DATABASE_URL", "")
NEON_HTTP_ENDPOINT = os.environ.get("NEON_HTTP_ENDPOINT", "")

TEST_SUITE_NAME = "l1_l5_integration"
TEST_WORKER_PREFIX = "test-worker"


# =============================================================================
# DATABASE HELPER
# =============================================================================

def execute_sql(query: str, params: Optional[list[Any]] = None) -> dict[str, Any]:
    """
    Execute SQL query against Neon database via HTTP.
    
    Args:
        query: SQL query string with $1, $2 style placeholders
        params: List of parameter values
        
    Returns:
        Query result with fields, rows, rowCount
        
    Raises:
        httpx.HTTPStatusError: If request fails
    """
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL,
    }
    
    body: dict[str, Any] = {"query": query}
    if params:
        body["params"] = params
    
    with httpx.Client(timeout=30.0) as client:
        response = client.post(NEON_HTTP_ENDPOINT, json=body, headers=headers)
        response.raise_for_status()
        return response.json()


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def run_id() -> str:
    """Generate unique run ID for this test session."""
    return str(uuid.uuid4())


@pytest.fixture(scope="session")
def test_worker_id() -> str:
    """Generate unique test worker ID."""
    return f"{TEST_WORKER_PREFIX}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="function")
def db() -> Generator[dict[str, Any], None, None]:
    """
    Database connection fixture.
    
    Yields execute_sql function and provides cleanup.
    """
    yield {"execute": execute_sql}


@pytest.fixture(scope="function")
def record_test_result(run_id: str):
    """
    Factory fixture to record test results to database.
    
    Returns callable that records test outcome.
    """
    def _record(
        test_name: str,
        level: str,
        status: str,
        duration_ms: int,
        error_message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Record test result to test_results table.
        
        Args:
            test_name: Name of the test
            level: Autonomy level (L1-L5)
            status: passed, failed, skipped
            duration_ms: Test duration in milliseconds
            error_message: Error message if failed
            details: Additional test details as JSON
        """
        query = """
            INSERT INTO test_results 
            (id, test_name, test_suite, level, status, duration_ms, error_message, details, run_id, created_at)
            VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, NOW())
        """
        params = [
            test_name,
            TEST_SUITE_NAME,
            level,
            status,
            duration_ms,
            error_message,
            json.dumps(details) if details else None,
            run_id,
        ]
        try:
            execute_sql(query, params)
            logger.info("Recorded test result: %s - %s", test_name, status)
        except Exception as exc:
            logger.error("Failed to record test result: %s", exc)
    
    return _record


@pytest.fixture(scope="function")
def cleanup_test_data(test_worker_id: str):
    """
    Cleanup fixture for test data created during tests.
    
    Yields list to collect entity IDs for cleanup.
    """
    cleanup_items: list[tuple[str, str, str]] = []  # (table, column, value)
    
    yield cleanup_items
    
    # Cleanup after test
    for table, column, value in cleanup_items:
        try:
            query = f"DELETE FROM {table} WHERE {column} = $1"
            execute_sql(query, [value])
            logger.debug("Cleaned up %s.%s = %s", table, column, value)
        except Exception as exc:
            logger.warning("Cleanup failed for %s: %s", table, exc)


@pytest.fixture(scope="session", autouse=True)
def log_test_run_start(run_id: str):
    """Log test run start."""
    logger.info("=" * 60)
    logger.info("JUGGERNAUT L1-L5 Integration Test Suite")
    logger.info("Run ID: %s", run_id)
    logger.info("Started: %s", datetime.utcnow().isoformat())
    logger.info("=" * 60)
    
    yield
    
    logger.info("=" * 60)
    logger.info("Test run complete: %s", run_id)
    logger.info("=" * 60)


# =============================================================================
# HELPER FUNCTIONS FOR TESTS
# =============================================================================

def generate_unique_id(prefix: str = "test") -> str:
    """Generate unique ID for test entities."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def wait_for_condition(
    check_fn: callable,
    timeout_seconds: int = 10,
    poll_interval: float = 0.5
) -> bool:
    """
    Wait for condition to become true.
    
    Args:
        check_fn: Callable that returns True when condition is met
        timeout_seconds: Maximum wait time
        poll_interval: Time between checks
        
    Returns:
        True if condition met, False if timeout
    """
    import time
    start = time.time()
    while time.time() - start < timeout_seconds:
        if check_fn():
            return True
        time.sleep(poll_interval)
    return False
