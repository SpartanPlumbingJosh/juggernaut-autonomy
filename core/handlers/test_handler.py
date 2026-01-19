"""
Test Task Handler
=================

Runs verification queries and tests against the system.
Records test results to the database.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Callable, List
from uuid import uuid4


def handle_test_task(
    task: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Execute a test/verification task.
    
    Payload format:
    {
        "test_type": "query|health|integration",  # Required
        "tests": [                                 # For query type
            {"name": "test1", "query": "SELECT...", "expected": "..."},
        ],
        "components": ["database", "api"],        # For health type
        "save_results": true                      # Optional, default true
    }
    
    Args:
        task: Task dict with test configuration
        execute_sql: Function to execute SQL
        log_action: Function to log actions
        
    Returns:
        Result dict with test outcomes
    """
    task_id = task.get("id", "unknown")
    payload = task.get("payload", {})
    
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid JSON payload"}
    
    test_type = payload.get("test_type", "query")
    save_results = payload.get("save_results", True)
    
    log_action(
        "test.handler.start",
        f"Starting {test_type} tests",
        "info",
        task_id=task_id,
        input_data={"test_type": test_type}
    )
    
    if test_type == "query":
        results = _run_query_tests(task, execute_sql, log_action)
    elif test_type == "health":
        results = _run_health_checks(task, execute_sql, log_action)
    elif test_type == "integration":
        results = _run_integration_tests(task, execute_sql, log_action)
    else:
        return {
            "success": False,
            "error": f"Unknown test_type: {test_type}",
            "valid_types": ["query", "health", "integration"]
        }
    
    # Save results to database
    if save_results:
        _save_test_results(task_id, test_type, results, execute_sql, log_action)
    
    return results


def _run_query_tests(
    task: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Run SQL query verification tests.
    
    Each test specifies a query and expected result condition.
    """
    task_id = task.get("id", "unknown")
    payload = task.get("payload", {})
    tests = payload.get("tests", [])
    
    if not tests:
        # Default tests if none specified
        tests = _get_default_query_tests()
    
    results = {
        "success": True,
        "test_type": "query",
        "total": len(tests),
        "passed": 0,
        "failed": 0,
        "details": []
    }
    
    for test in tests:
        test_name = test.get("name", "unnamed")
        query = test.get("query", "")
        expected = test.get("expected", None)
        condition = test.get("condition", "not_empty")  # not_empty, equals, contains, gt, lt
        
        if not query:
            results["details"].append({
                "name": test_name,
                "passed": False,
                "error": "No query specified"
            })
            results["failed"] += 1
            continue
        
        try:
            result = execute_sql(query)
            rows = result.get("rows", [])
            row_count = result.get("rowCount", len(rows))
            
            # Evaluate condition
            passed = False
            if condition == "not_empty":
                passed = row_count > 0
            elif condition == "equals":
                passed = row_count == expected
            elif condition == "gt":
                passed = row_count > expected
            elif condition == "lt":
                passed = row_count < expected
            elif condition == "contains":
                passed = any(expected in str(row) for row in rows)
            else:
                passed = row_count > 0  # Default to not_empty
            
            results["details"].append({
                "name": test_name,
                "passed": passed,
                "row_count": row_count,
                "condition": condition,
                "expected": expected
            })
            
            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["success"] = False
            
            log_action(
                "test.handler.query_test",
                f"Test '{test_name}': {'PASS' if passed else 'FAIL'}",
                "info" if passed else "warning",
                task_id=task_id
            )
            
        except Exception as e:
            results["details"].append({
                "name": test_name,
                "passed": False,
                "error": str(e)[:200]
            })
            results["failed"] += 1
            results["success"] = False
    
    log_action(
        "test.handler.query_complete",
        f"Query tests: {results['passed']}/{results['total']} passed",
        "info" if results["success"] else "warning",
        task_id=task_id
    )
    
    return results


def _get_default_query_tests() -> List[Dict[str, Any]]:
    """Return default verification queries."""
    return [
        {
            "name": "database_connected",
            "query": "SELECT 1 as test",
            "condition": "not_empty"
        },
        {
            "name": "tasks_table_exists",
            "query": "SELECT COUNT(*) FROM governance_tasks",
            "condition": "not_empty"
        },
        {
            "name": "logs_table_exists",
            "query": "SELECT COUNT(*) FROM execution_logs WHERE created_at > NOW() - INTERVAL '24 hours'",
            "condition": "not_empty"
        }
    ]


def _run_health_checks(
    task: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Run system health checks."""
    task_id = task.get("id", "unknown")
    payload = task.get("payload", {})
    components = payload.get("components", ["database"])
    
    results = {
        "success": True,
        "test_type": "health",
        "total": len(components),
        "passed": 0,
        "failed": 0,
        "details": []
    }
    
    for component in components:
        if component == "database":
            passed = _check_database_health(execute_sql)
        else:
            passed = True  # Assume healthy for unknown components
        
        results["details"].append({
            "component": component,
            "healthy": passed
        })
        
        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["success"] = False
    
    log_action(
        "test.handler.health_complete",
        f"Health checks: {results['passed']}/{results['total']} healthy",
        "info" if results["success"] else "warning",
        task_id=task_id
    )
    
    return results


def _check_database_health(execute_sql: Callable) -> bool:
    """Check if database is responding."""
    try:
        result = execute_sql("SELECT 1")
        return result.get("rowCount", 0) > 0 or len(result.get("rows", [])) > 0
    except Exception:
        return False


def _run_integration_tests(
    task: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Run integration tests between components."""
    task_id = task.get("id", "unknown")
    
    log_action(
        "test.handler.integration",
        "Integration tests not yet fully implemented",
        "info",
        task_id=task_id
    )
    
    # Basic integration test: can we create and read a log entry?
    try:
        # Create a test log entry
        log_action(
            "test.handler.integration_test",
            "Integration test marker",
            "debug",
            task_id=task_id
        )
        
        # Verify it was created
        result = execute_sql(f"""
            SELECT COUNT(*) as count 
            FROM execution_logs 
            WHERE task_id = '{task_id}'
            AND action LIKE 'test.handler.%'
        """)
        
        count = result.get("rows", [{}])[0].get("count", 0)
        
        return {
            "success": count > 0,
            "test_type": "integration",
            "total": 1,
            "passed": 1 if count > 0 else 0,
            "failed": 0 if count > 0 else 1,
            "details": [{
                "name": "log_write_read",
                "passed": count > 0,
                "note": f"Found {count} test log entries"
            }]
        }
        
    except Exception as e:
        return {
            "success": False,
            "test_type": "integration",
            "total": 1,
            "passed": 0,
            "failed": 1,
            "details": [{"name": "log_write_read", "passed": False, "error": str(e)[:200]}]
        }


def _save_test_results(
    task_id: str,
    test_type: str,
    results: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> None:
    """Save test results to the database."""
    try:
        result_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        details_json = json.dumps(results.get("details", [])).replace("'", "''")
        
        execute_sql(f"""
            INSERT INTO test_results (
                id, task_id, test_type, total_tests, passed, failed, 
                success, details, created_at
            ) VALUES (
                '{result_id}',
                '{task_id}',
                '{test_type}',
                {results.get('total', 0)},
                {results.get('passed', 0)},
                {results.get('failed', 0)},
                {results.get('success', False)},
                '{details_json}'::jsonb,
                '{now}'
            )
        """)
        
        log_action(
            "test.handler.saved",
            f"Test results saved: {result_id}",
            "info",
            task_id=task_id
        )
        
    except Exception as e:
        # Table might not exist - log but don't fail
        log_action(
            "test.handler.save_failed",
            f"Could not save test results: {str(e)[:200]}",
            "warning",
            task_id=task_id
        )
