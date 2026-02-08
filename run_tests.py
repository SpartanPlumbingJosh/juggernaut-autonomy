#!/usr/bin/env python3
"""
JUGGERNAUT L1-L5 Integration Test Runner

Runs the integration test suite and logs results to test_results table.
Creates governance tasks for any test failures.

Usage:
    python run_tests.py [--level L1|L2|L3|L4|L5] [--create-tasks]
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime
from typing import Any, Optional

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

DATABASE_URL = os.environ.get("DATABASE_URL", "")
NEON_HTTP_ENDPOINT = os.environ.get("NEON_HTTP_ENDPOINT", "")

LEVEL_MARKERS = {
    "L1": "l1",
    "L2": "l2",
    "L3": "l3",
    "L4": "l4",
    "L5": "l5",
}


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
# TASK CREATION
# =============================================================================

def create_fix_task(
    test_name: str,
    level: str,
    error_message: str,
    run_id: str,
) -> Optional[str]:
    """
    Create a governance task to fix a failed test.

    Args:
        test_name: Name of the failed test
        level: Autonomy level (L1-L5)
        error_message: Error message from test
        run_id: Test run ID

    Returns:
        Task ID if created, None if failed
    """
    title = f"FIX: {test_name} ({level}) failing"
    description = f"""ACCEPTANCE CRITERIA:
1. Investigate why {test_name} is failing
2. Fix the underlying issue
3. Verify test passes locally
4. Update test if needed

ERROR MESSAGE:
{error_message[:500]}

CONTEXT:
- Test Level: {level}
- Run ID: {run_id}
- Created: {datetime.utcnow().isoformat()}

EVIDENCE REQUIRED: Test passes in CI"""

    try:
        result = execute_sql("""
            INSERT INTO governance_tasks
            (id, title, description, status, priority, task_type, assigned_worker, created_at)
            VALUES (gen_random_uuid(), $1, $2, 'pending', 'high', 'bugfix', 'claude-chat', NOW())
            RETURNING id
        """, [title, description])

        task_id = result["rows"][0]["id"]
        logger.info("Created fix task: %s", task_id)
        return task_id

    except Exception as exc:
        logger.error("Failed to create fix task: %s", exc)
        return None


# =============================================================================
# TEST EXECUTION
# =============================================================================

def run_tests(
    level: Optional[str] = None,
    create_tasks: bool = False,
    verbose: bool = False,
) -> tuple[int, int, int]:
    """
    Run the integration test suite.

    Args:
        level: Optional level filter (L1-L5)
        create_tasks: Whether to create tasks for failures
        verbose: Verbose output

    Returns:
        Tuple of (passed, failed, skipped) counts
    """
    run_id = str(uuid.uuid4())
    logger.info("Starting test run: %s", run_id)

    # Build pytest command
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_integration_l1_l5.py",
        "-v",
        "--tb=short",
        f"--run-id={run_id}",
    ]

    if level and level.upper() in LEVEL_MARKERS:
        cmd.extend(["-m", LEVEL_MARKERS[level.upper()]])

    if verbose:
        cmd.append("-vv")

    # Run tests
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Parse results
    passed = result.stdout.count(" PASSED")
    failed = result.stdout.count(" FAILED")
    skipped = result.stdout.count(" SKIPPED")

    logger.info("Results: %d passed, %d failed, %d skipped", passed, failed, skipped)

    if verbose:
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

    # Create tasks for failures if requested
    if create_tasks and failed > 0:
        logger.info("Creating tasks for %d failures...", failed)
        # Query test_results for failures from this run
        try:
            failures = execute_sql("""
                SELECT test_name, level, error_message
                FROM test_results
                WHERE run_id = $1 AND status = 'failed'
            """, [run_id])

            for row in failures.get("rows", []):
                create_fix_task(
                    test_name=row["test_name"],
                    level=row["level"],
                    error_message=row.get("error_message", "Unknown error"),
                    run_id=run_id,
                )
        except Exception as exc:
            logger.error("Failed to query failures: %s", exc)

    return passed, failed, skipped


def get_test_summary(run_id: Optional[str] = None) -> dict[str, Any]:
    """
    Get summary of test results.

    Args:
        run_id: Optional run ID filter

    Returns:
        Summary dict with counts by level and status
    """
    query = """
        SELECT 
            level,
            status,
            COUNT(*) as count,
            AVG(duration_ms) as avg_duration_ms
        FROM test_results
        WHERE ($1::uuid IS NULL OR run_id = $1)
        GROUP BY level, status
        ORDER BY level, status
    """
    result = execute_sql(query, [run_id])

    summary: dict[str, Any] = {"by_level": {}, "totals": {"passed": 0, "failed": 0, "skipped": 0}}

    for row in result.get("rows", []):
        level = row["level"]
        status = row["status"]
        count = row["count"]

        if level not in summary["by_level"]:
            summary["by_level"][level] = {}

        summary["by_level"][level][status] = count
        summary["totals"][status] = summary["totals"].get(status, 0) + count

    return summary


# =============================================================================
# CLI
# =============================================================================

def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run JUGGERNAUT L1-L5 integration tests"
    )
    parser.add_argument(
        "--level",
        choices=["L1", "L2", "L3", "L4", "L5"],
        help="Run tests for specific level only"
    )
    parser.add_argument(
        "--create-tasks",
        action="store_true",
        help="Create governance tasks for failed tests"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show test results summary only"
    )
    parser.add_argument(
        "--run-id",
        help="Show summary for specific run ID"
    )

    args = parser.parse_args()

    if args.summary:
        summary = get_test_summary(args.run_id)
        print(json.dumps(summary, indent=2))
        return 0

    passed, failed, skipped = run_tests(
        level=args.level,
        create_tasks=args.create_tasks,
        verbose=args.verbose,
    )

    # Return non-zero exit code if any tests failed
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
