"""Test handler for verification and test query tasks.

This module handles tasks of type 'test' that execute verification
queries to validate system state, data integrity, or expected conditions.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import BaseHandler, HandlerResult

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
MAX_TEST_QUERIES = 50
MAX_QUERY_LENGTH = 5000


class TestHandler(BaseHandler):
    """Handler for test task type.
    
    Executes verification and test queries to validate system state
    or data integrity. Supports multiple queries per task with
    pass/fail tracking for each.
    """

    task_type = "test"

    def execute(self, task: Dict[str, Any]) -> HandlerResult:
        """Execute a test/verification task.
        
        Args:
            task: Task dictionary with payload containing:
                - queries (list): List of SQL queries to execute
                - sql (str): Single SQL query (alternative to queries)
                - expected_rows (int, optional): Expected row count for validation
                - fail_on_empty (bool, optional): Whether empty results = failure
        
        Returns:
            HandlerResult with test results or error information.
        """
        self._execution_logs = []
        task_id = task.get("id")
        payload = task.get("payload", {})

        # Extract test queries from payload
        test_queries = self._extract_queries(payload)
        
        if not test_queries:
            error_msg = "Test task missing 'queries' or 'sql' in payload"
            self._log(
                "handler.test.missing_queries",
                error_msg,
                level="error",
                task_id=task_id
            )
            return HandlerResult(
                success=False,
                data={"expected_fields": ["queries", "sql"]},
                error=error_msg,
                logs=self._execution_logs
            )

        # Limit number of queries
        if len(test_queries) > MAX_TEST_QUERIES:
            self._log(
                "handler.test.query_limit",
                f"Limiting to {MAX_TEST_QUERIES} queries (provided {len(test_queries)})",
                level="warn",
                task_id=task_id
            )
            test_queries = test_queries[:MAX_TEST_QUERIES]

        # Extract validation options
        expected_rows = payload.get("expected_rows")
        fail_on_empty = payload.get("fail_on_empty", False)

        self._log(
            "handler.test.starting",
            f"Starting test execution with {len(test_queries)} queries",
            task_id=task_id
        )

        try:
            test_results = self._run_tests(
                test_queries,
                expected_rows,
                fail_on_empty,
                task_id
            )

            all_passed = all(r.get("passed", False) for r in test_results)
            passed_count = sum(1 for r in test_results if r.get("passed", False))
            failed_count = len(test_results) - passed_count

            result_data = {
                "executed": True,
                "tests_run": len(test_results),
                "all_passed": all_passed,
                "passed_count": passed_count,
                "failed_count": failed_count,
                "results": test_results,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            log_level = "info" if all_passed else "warn"
            self._log(
                "handler.test.complete",
                f"Tests complete: {passed_count}/{len(test_results)} passed",
                level=log_level,
                task_id=task_id,
                output_data={
                    "tests_run": len(test_results),
                    "passed": passed_count,
                    "failed": failed_count
                }
            )

            return HandlerResult(
                success=all_passed,
                data=result_data,
                logs=self._execution_logs
            )

        except Exception as test_error:
            error_msg = str(test_error)
            self._log(
                "handler.test.failed",
                f"Test execution failed: {error_msg[:200]}",
                level="error",
                task_id=task_id
            )
            return HandlerResult(
                success=False,
                data={"tests_attempted": len(test_queries)},
                error=error_msg,
                logs=self._execution_logs
            )

    def _extract_queries(self, payload: Dict[str, Any]) -> List[str]:
        """Extract test queries from payload.
        
        Handles both 'queries' (list) and 'sql' (string) formats.
        
        Args:
            payload: Task payload dictionary.
        
        Returns:
            List of SQL query strings.
        """
        queries = payload.get("queries", [])
        sql = payload.get("sql")

        # Handle string input for queries
        if isinstance(queries, str):
            queries = [queries]

        # Handle single sql field
        if sql and not queries:
            queries = [sql]

        # Validate and sanitize queries
        valid_queries = []
        for query in queries:
            if isinstance(query, str):
                query = query.strip()
                if query and len(query) <= MAX_QUERY_LENGTH:
                    valid_queries.append(query)

        return valid_queries

    def _run_tests(
        self,
        queries: List[str],
        expected_rows: Optional[int],
        fail_on_empty: bool,
        task_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Execute all test queries and collect results.
        
        Args:
            queries: List of SQL queries to execute.
            expected_rows: Optional expected row count for all queries.
            fail_on_empty: Whether to fail if results are empty.
            task_id: Task ID for logging.
        
        Returns:
            List of result dictionaries for each query.
        """
        results = []

        for index, query in enumerate(queries):
            result = self._execute_single_test(
                index,
                query,
                expected_rows,
                fail_on_empty,
                task_id
            )
            results.append(result)

        return results

    def _execute_single_test(
        self,
        index: int,
        query: str,
        expected_rows: Optional[int],
        fail_on_empty: bool,
        task_id: Optional[str]
    ) -> Dict[str, Any]:
        """Execute a single test query.
        
        Args:
            index: Query index for result tracking.
            query: SQL query to execute.
            expected_rows: Optional expected row count.
            fail_on_empty: Whether to fail on empty results.
            task_id: Task ID for logging.
        
        Returns:
            Dictionary with test result details.
        """
        result = {
            "index": index,
            "passed": False,
            "rowCount": 0,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }

        try:
            query_result = self.execute_sql(query)
            row_count = query_result.get("rowCount", 0)
            result["rowCount"] = row_count
            result["rows_preview"] = query_result.get("rows", [])[:3]

            # Determine pass/fail based on validation criteria
            passed = True
            failure_reason = None

            # Check expected rows if specified
            if expected_rows is not None:
                if row_count != expected_rows:
                    passed = False
                    failure_reason = f"Expected {expected_rows} rows, got {row_count}"

            # Check fail_on_empty
            if fail_on_empty and row_count == 0:
                passed = False
                failure_reason = "Query returned empty results"

            result["passed"] = passed
            if failure_reason:
                result["failure_reason"] = failure_reason

            self._log(
                f"handler.test.query_{index}",
                f"Query {index}: {'PASSED' if passed else 'FAILED'} ({row_count} rows)",
                level="info" if passed else "warn",
                task_id=task_id
            )

        except Exception as query_error:
            error_msg = str(query_error)
            result["passed"] = False
            result["error"] = error_msg[:500]
            result["failure_reason"] = "Query execution failed"
            
            self._log(
                f"handler.test.query_{index}_error",
                f"Query {index}: ERROR - {error_msg[:100]}",
                level="error",
                task_id=task_id
            )

        return result
