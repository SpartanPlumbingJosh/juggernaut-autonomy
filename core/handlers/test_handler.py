"""
Test Task Handler
=================
Runs verification queries and validates expected results.
"""

import json
import urllib.request
import urllib.error
import os
from typing import Dict, Any, Tuple, List
from datetime import datetime, timezone


DATABASE_URL = os.getenv("DATABASE_URL", "")
NEON_ENDPOINT = os.getenv(
    "NEON_ENDPOINT",
    "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
)


def _execute_sql(sql: str) -> Dict[str, Any]:
    """Execute SQL via Neon HTTP API."""
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL
    }
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
    
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def _run_single_test(test: Dict, log_action_fn, task_id: str) -> Dict:
    """
    Run a single verification test.
    
    Test structure:
    {
        "name": "Test name",
        "sql": "SELECT count(*) as cnt FROM table",
        "expect": {"cnt": 1}  # Expected result
        OR
        "expect_min_rows": 1  # Minimum rows expected
        OR
        "expect_max_rows": 100  # Maximum rows expected
    }
    """
    test_name = test.get("name", "Unnamed test")
    sql = test.get("sql") or test.get("query")
    
    if not sql:
        return {
            "name": test_name,
            "passed": False,
            "error": "No SQL provided for test"
        }
    
    try:
        result = _execute_sql(sql)
        rows = result.get("rows", [])
        row_count = len(rows)
        
        passed = True
        failure_reason = None
        
        # Check expectations
        if "expect" in test:
            expected = test["expect"]
            if rows and isinstance(expected, dict):
                # Compare first row against expected values
                actual = rows[0]
                for key, expected_value in expected.items():
                    actual_value = actual.get(key)
                    if actual_value != expected_value:
                        passed = False
                        failure_reason = f"Expected {key}={expected_value}, got {actual_value}"
                        break
            elif not rows:
                passed = False
                failure_reason = "No rows returned but expected specific values"
        
        if "expect_min_rows" in test:
            min_rows = test["expect_min_rows"]
            if row_count < min_rows:
                passed = False
                failure_reason = f"Expected at least {min_rows} rows, got {row_count}"
        
        if "expect_max_rows" in test:
            max_rows = test["expect_max_rows"]
            if row_count > max_rows:
                passed = False
                failure_reason = f"Expected at most {max_rows} rows, got {row_count}"
        
        log_action_fn(
            "task.test_result",
            f"Test '{test_name}': {'PASSED' if passed else 'FAILED'}",
            level="info" if passed else "warn",
            task_id=task_id,
            output_data={
                "test_name": test_name,
                "passed": passed,
                "row_count": row_count,
                "failure_reason": failure_reason
            }
        )
        
        return {
            "name": test_name,
            "passed": passed,
            "row_count": row_count,
            "failure_reason": failure_reason,
            "first_row": rows[0] if rows else None
        }
        
    except Exception as e:
        log_action_fn(
            "task.test_error",
            f"Test '{test_name}' error: {str(e)}",
            level="error",
            task_id=task_id
        )
        return {
            "name": test_name,
            "passed": False,
            "error": str(e)
        }


def handle_test_task(task_id: str, payload: Dict[str, Any], log_action_fn) -> Tuple[bool, Dict[str, Any]]:
    """
    Run verification queries/tests from payload.
    
    Args:
        task_id: Task identifier for logging
        payload: Task payload containing:
            - 'tests': List of test objects with 'sql' and optional 'expect'
            OR
            - 'sql': Single SQL query (simple mode)
            - 'queries': List of SQL queries (simple mode)
        log_action_fn: Function to log actions
    
    Returns:
        Tuple of (success: bool, result: dict)
    """
    tests = payload.get("tests", [])
    
    # Support simple mode with single SQL or list of queries
    if not tests:
        if "sql" in payload:
            tests = [{"name": "Query 1", "sql": payload["sql"], "expect_min_rows": 0}]
        elif "queries" in payload:
            tests = [
                {"name": f"Query {i+1}", "sql": q, "expect_min_rows": 0}
                for i, q in enumerate(payload["queries"])
            ]
    
    if not tests:
        log_action_fn(
            "task.test_handler",
            "No tests provided in payload (expected 'tests', 'sql', or 'queries' key)",
            level="error",
            task_id=task_id
        )
        return False, {"error": "No tests provided in payload"}
    
    try:
        log_action_fn(
            "task.test_starting",
            f"Running {len(tests)} verification test(s)",
            level="info",
            task_id=task_id,
            input_data={"test_count": len(tests)}
        )
        
        results = []
        passed_count = 0
        failed_count = 0
        
        for test in tests:
            result = _run_single_test(test, log_action_fn, task_id)
            results.append(result)
            if result.get("passed"):
                passed_count += 1
            else:
                failed_count += 1
        
        all_passed = failed_count == 0
        
        log_action_fn(
            "task.test_completed",
            f"Tests completed: {passed_count} passed, {failed_count} failed",
            level="info" if all_passed else "warn",
            task_id=task_id,
            output_data={
                "total": len(tests),
                "passed": passed_count,
                "failed": failed_count,
                "all_passed": all_passed
            }
        )
        
        return True, {
            "executed": True,
            "tests_run": len(tests),
            "passed": passed_count,
            "failed": failed_count,
            "all_passed": all_passed,
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        log_action_fn(
            "task.test_error",
            f"Test exception: {str(e)}",
            level="error",
            task_id=task_id,
            error_data={"exception": str(e)}
        )
        return False, {"error": str(e)}
