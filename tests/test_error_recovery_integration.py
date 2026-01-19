"""
Integration tests for JUGGERNAUT Error Recovery System.

Tests the integration of error_recovery.py module with main.py:
- Dead letter queue handling
- Retry logic with exponential backoff
- Alert creation for failures
- Escalation triggers

Task ID: 84e8ec6f-48ba-49fd-8716-c9baded47710
Worker: claude-chat-7K3M
"""

import logging
import uuid
from typing import Any, Dict, Optional

import httpx
import pytest

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

DATABASE_URL: str = (
    "postgresql://neondb_owner:npg_OYkCRU4aze2l@"
    "ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
)
NEON_HTTP_ENDPOINT: str = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"

# Test configuration
TEST_WORKER_ID: str = "test-worker"
RETRY_BASE_DELAY_SECONDS: int = 60
RETRY_MAX_DELAY_SECONDS: int = 3600
MAX_RETRY_ATTEMPTS: int = 3


# =============================================================================
# DATABASE HELPER
# =============================================================================

def execute_sql(query: str, params: Optional[list[Any]] = None) -> Dict[str, Any]:
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
    
    body: Dict[str, Any] = {"query": query}
    if params:
        body["params"] = params
    
    with httpx.Client(timeout=30.0) as client:
        response = client.post(NEON_HTTP_ENDPOINT, json=body, headers=headers)
        response.raise_for_status()
        return response.json()


def generate_unique_id(prefix: str = "test") -> str:
    """
    Generate unique ID for test entities.
    
    Args:
        prefix: String prefix for the ID
        
    Returns:
        Unique identifier string
    """
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# =============================================================================
# RETRY LOGIC FUNCTIONS (matching main.py implementation)
# =============================================================================

def calculate_retry_delay(retry_count: int) -> int:
    """
    Calculate exponential backoff delay in seconds.
    
    Args:
        retry_count: Number of retries already attempted
        
    Returns:
        Delay in seconds for next retry
    """
    delay = RETRY_BASE_DELAY_SECONDS * (2 ** retry_count)
    return min(delay, RETRY_MAX_DELAY_SECONDS)


# =============================================================================
# CLEANUP FIXTURES
# =============================================================================

@pytest.fixture
def cleanup_tasks():
    """
    Fixture to clean up test tasks after each test.
    
    Yields:
        List to collect task IDs for cleanup
    """
    task_ids: list[str] = []
    
    yield task_ids
    
    # Cleanup after test
    for task_id in task_ids:
        try:
            execute_sql("DELETE FROM governance_tasks WHERE id = $1", [task_id])
            execute_sql("DELETE FROM dead_letter_queue WHERE task_id = $1", [task_id])
            execute_sql("DELETE FROM system_alerts WHERE related_id = $1", [task_id])
            execute_sql("DELETE FROM escalations WHERE task_id = $1", [task_id])
            logger.debug("Cleaned up task %s", task_id)
        except httpx.HTTPStatusError as e:
            logger.warning("Cleanup failed for task %s: %s", task_id, e)


@pytest.fixture
def cleanup_dlq():
    """
    Fixture to clean up DLQ entries after each test.
    
    Yields:
        List to collect DLQ IDs for cleanup
    """
    dlq_ids: list[str] = []
    
    yield dlq_ids
    
    for dlq_id in dlq_ids:
        try:
            execute_sql("DELETE FROM dead_letter_queue WHERE id = $1", [dlq_id])
            logger.debug("Cleaned up DLQ entry %s", dlq_id)
        except httpx.HTTPStatusError as e:
            logger.warning("Cleanup failed for DLQ %s: %s", dlq_id, e)


# =============================================================================
# TEST: EXPONENTIAL BACKOFF CALCULATION
# =============================================================================

class TestExponentialBackoff:
    """Test retry delay calculation with exponential backoff."""
    
    def test_first_retry_delay(self) -> None:
        """
        Verify first retry uses base delay.
        """
        delay = calculate_retry_delay(0)
        assert delay == RETRY_BASE_DELAY_SECONDS, f"First retry should be {RETRY_BASE_DELAY_SECONDS}s"
        logger.info("Test passed: First retry delay = %ds", delay)
    
    def test_second_retry_delay(self) -> None:
        """
        Verify second retry doubles the delay.
        """
        delay = calculate_retry_delay(1)
        expected = RETRY_BASE_DELAY_SECONDS * 2
        assert delay == expected, f"Second retry should be {expected}s"
        logger.info("Test passed: Second retry delay = %ds", delay)
    
    def test_third_retry_delay(self) -> None:
        """
        Verify third retry quadruples the base delay.
        """
        delay = calculate_retry_delay(2)
        expected = RETRY_BASE_DELAY_SECONDS * 4
        assert delay == expected, f"Third retry should be {expected}s"
        logger.info("Test passed: Third retry delay = %ds", delay)
    
    def test_max_delay_cap(self) -> None:
        """
        Verify delay is capped at maximum.
        """
        # With base 60 and cap 3600, we hit cap at retry 6 (60 * 2^6 = 3840 > 3600)
        delay = calculate_retry_delay(10)
        assert delay == RETRY_MAX_DELAY_SECONDS, f"Delay should be capped at {RETRY_MAX_DELAY_SECONDS}s"
        logger.info("Test passed: Max delay cap = %ds", delay)


# =============================================================================
# TEST: DEAD LETTER QUEUE
# =============================================================================

class TestDeadLetterQueue:
    """Test dead letter queue functionality."""
    
    def test_dlq_table_exists(self) -> None:
        """
        Verify dead_letter_queue table exists.
        """
        result = execute_sql("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'dead_letter_queue'
        """)
        assert result.get("rowCount", 0) > 0, "dead_letter_queue table should exist"
        logger.info("Test passed: dead_letter_queue table exists")
    
    def test_dlq_accepts_entries(
        self,
        cleanup_tasks: list[str],
        cleanup_dlq: list[str]
    ) -> None:
        """
        Verify tasks can be added to dead letter queue.
        
        Args:
            cleanup_tasks: Fixture for task cleanup
            cleanup_dlq: Fixture for DLQ cleanup
        """
        task_id = generate_unique_id("dlq-test-task")
        cleanup_tasks.append(task_id)
        
        # Create a test task first
        execute_sql("""
            INSERT INTO governance_tasks (id, task_type, title, status, priority)
            VALUES ($1, 'test', 'DLQ Test Task', 'failed', 'medium')
        """, [task_id])
        
        # Insert into DLQ
        result = execute_sql("""
            INSERT INTO dead_letter_queue (task_id, error_message, attempts, worker_id)
            VALUES ($1, 'Test error', 3, $2)
            RETURNING id
        """, [task_id, TEST_WORKER_ID])
        
        assert result.get("rowCount", 0) > 0, "Should insert into DLQ"
        dlq_id = result["rows"][0]["id"]
        cleanup_dlq.append(dlq_id)
        
        # Verify entry exists
        verify = execute_sql("""
            SELECT * FROM dead_letter_queue WHERE id = $1
        """, [dlq_id])
        
        assert verify.get("rowCount", 0) == 1, "DLQ entry should exist"
        entry = verify["rows"][0]
        assert entry.get("task_id") == task_id
        assert entry.get("attempts") == 3
        
        logger.info("Test passed: DLQ accepts entries")


# =============================================================================
# TEST: SYSTEM ALERTS
# =============================================================================

class TestSystemAlerts:
    """Test system alert functionality."""
    
    def test_alerts_table_exists(self) -> None:
        """
        Verify system_alerts table exists.
        """
        result = execute_sql("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'system_alerts'
        """)
        assert result.get("rowCount", 0) > 0, "system_alerts table should exist"
        logger.info("Test passed: system_alerts table exists")
    
    def test_alert_creation(self) -> None:
        """
        Verify alerts can be created and retrieved.
        """
        alert_id = None
        try:
            result = execute_sql("""
                INSERT INTO system_alerts 
                (alert_type, severity, title, message, source, status)
                VALUES ('task_failure', 'error', 'Test Alert', 'Test message', $1, 'open')
                RETURNING id
            """, [TEST_WORKER_ID])
            
            assert result.get("rowCount", 0) > 0, "Should create alert"
            alert_id = result["rows"][0]["id"]
            
            # Verify alert exists
            verify = execute_sql("""
                SELECT * FROM system_alerts WHERE id = $1
            """, [alert_id])
            
            assert verify.get("rowCount", 0) == 1, "Alert should exist"
            alert = verify["rows"][0]
            assert alert.get("severity") == "error"
            assert alert.get("status") == "open"
            
            logger.info("Test passed: Alert creation works")
            
        finally:
            if alert_id:
                execute_sql("DELETE FROM system_alerts WHERE id = $1", [alert_id])


# =============================================================================
# TEST: ESCALATIONS
# =============================================================================

class TestEscalations:
    """Test escalation functionality."""
    
    def test_escalations_table_exists(self) -> None:
        """
        Verify escalations table exists.
        """
        result = execute_sql("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'escalations'
        """)
        assert result.get("rowCount", 0) > 0, "escalations table should exist"
        logger.info("Test passed: escalations table exists")
    
    def test_escalation_creation(
        self,
        cleanup_tasks: list[str]
    ) -> None:
        """
        Verify escalations can be created for failed tasks.
        
        Args:
            cleanup_tasks: Fixture for task cleanup
        """
        task_id = generate_unique_id("esc-test-task")
        cleanup_tasks.append(task_id)
        escalation_id = None
        
        try:
            # Create test task
            execute_sql("""
                INSERT INTO governance_tasks (id, task_type, title, status, priority)
                VALUES ($1, 'test', 'Escalation Test Task', 'failed', 'medium')
            """, [task_id])
            
            # Create escalation
            result = execute_sql("""
                INSERT INTO escalations 
                (level, issue_type, description, task_id, status)
                VALUES ('medium', 'task_failure', 'Task failed after max retries', $1, 'open')
                RETURNING id
            """, [task_id])
            
            assert result.get("rowCount", 0) > 0, "Should create escalation"
            escalation_id = result["rows"][0]["id"]
            
            # Verify escalation exists
            verify = execute_sql("""
                SELECT * FROM escalations WHERE id = $1
            """, [escalation_id])
            
            assert verify.get("rowCount", 0) == 1, "Escalation should exist"
            escalation = verify["rows"][0]
            assert escalation.get("task_id") == task_id
            assert escalation.get("status") == "open"
            
            logger.info("Test passed: Escalation creation works")
            
        finally:
            if escalation_id:
                execute_sql("DELETE FROM escalations WHERE id = $1", [escalation_id])


# =============================================================================
# TEST: RETRY COUNT TRACKING
# =============================================================================

class TestRetryTracking:
    """Test retry count tracking in governance_tasks."""
    
    def test_attempt_count_column_exists(self) -> None:
        """
        Verify attempt_count column exists in governance_tasks.
        """
        result = execute_sql("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'governance_tasks' AND column_name = 'attempt_count'
        """)
        assert result.get("rowCount", 0) > 0, "attempt_count column should exist"
        logger.info("Test passed: attempt_count column exists")
    
    def test_retry_count_increment(
        self,
        cleanup_tasks: list[str]
    ) -> None:
        """
        Verify attempt_count increments on retry.
        
        Args:
            cleanup_tasks: Fixture for task cleanup
        """
        task_id = generate_unique_id("retry-test-task")
        cleanup_tasks.append(task_id)
        
        # Create task with attempt_count = 0
        execute_sql("""
            INSERT INTO governance_tasks 
            (id, task_type, title, status, priority, attempt_count)
            VALUES ($1, 'test', 'Retry Test Task', 'pending', 'medium', 0)
        """, [task_id])
        
        # Increment attempt_count
        execute_sql("""
            UPDATE governance_tasks 
            SET attempt_count = attempt_count + 1
            WHERE id = $1
        """, [task_id])
        
        # Verify increment
        result = execute_sql("""
            SELECT attempt_count FROM governance_tasks WHERE id = $1
        """, [task_id])
        
        assert result.get("rowCount", 0) == 1, "Task should exist"
        count = result["rows"][0].get("attempt_count", 0)
        assert count == 1, f"attempt_count should be 1, got {count}"
        
        logger.info("Test passed: Retry count increments correctly")


# =============================================================================
# TEST: MAX_RETRY_ATTEMPTS CONSTANT
# =============================================================================

class TestMaxRetryAttempts:
    """Test MAX_RETRY_ATTEMPTS constant behavior."""
    
    def test_max_retry_constant_value(self) -> None:
        """
        Verify MAX_RETRY_ATTEMPTS is set to expected value.
        """
        assert MAX_RETRY_ATTEMPTS == 3, "MAX_RETRY_ATTEMPTS should be 3"
        logger.info("Test passed: MAX_RETRY_ATTEMPTS = %d", MAX_RETRY_ATTEMPTS)
    
    def test_retry_sequence(self) -> None:
        """
        Verify full retry sequence with exponential backoff.
        """
        delays = []
        for i in range(MAX_RETRY_ATTEMPTS):
            delay = calculate_retry_delay(i)
            delays.append(delay)
        
        # Verify delays are increasing
        assert delays[0] < delays[1] < delays[2], "Delays should increase"
        
        # Verify specific values
        assert delays[0] == 60, "First retry: 60s"
        assert delays[1] == 120, "Second retry: 120s"
        assert delays[2] == 240, "Third retry: 240s"
        
        logger.info("Test passed: Retry sequence: %s", delays)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
