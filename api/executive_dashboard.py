"""
Executive Dashboard API Endpoint.

Provides a simple /api/dashboard endpoint for executive reporting.
Uses pre-computed database views (v_*) for efficient queries.

Part of L5 requirement: Executive reporting and dashboard.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Database configuration constants
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
DATABASE_URL = os.getenv("DATABASE_URL")

# Response timeout in seconds
REQUEST_TIMEOUT_SECONDS = 30


class ExecutiveDashboardError(Exception):
    """Custom exception for executive dashboard errors."""

    pass


def _execute_query(sql: str) -> Dict[str, Any]:
    """
    Execute a SQL query against the Neon database.

    Args:
        sql: The SQL query to execute.

    Returns:
        Dictionary containing query results with 'rows' key.

    Raises:
        ExecutiveDashboardError: If the database query fails.
    """
    if not DATABASE_URL:
        raise ExecutiveDashboardError("DATABASE_URL environment variable not set")

    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL
    }

    data = json.dumps({"query": sql}).encode("utf-8")
    request = urllib.request.Request(
        NEON_ENDPOINT,
        data=data,
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8")
        logger.error("Database HTTP error: %s - %s", exc.code, error_body)
        raise ExecutiveDashboardError(f"Database error: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        logger.error("Database connection error: %s", exc.reason)
        raise ExecutiveDashboardError(f"Database connection error: {exc.reason}") from exc


def get_revenue_metrics() -> Dict[str, Any]:
    """
    Get revenue metrics from v_revenue_by_source and v_profit_loss views.

    Returns:
        Dictionary containing revenue summary metrics.
    """
    result: Dict[str, Any] = {
        "total_revenue": 0.0,
        "sources": [],
        "profit_loss": None
    }

    try:
        # Query v_revenue_by_source
        revenue_data = _execute_query("SELECT * FROM v_revenue_by_source;")
        sources: List[Dict[str, Any]] = []
        total_revenue = 0.0

        for row in revenue_data.get("rows", []):
            source_revenue = float(row.get("total_revenue", 0) or 0)
            total_revenue += source_revenue
            sources.append({
                "source_name": row.get("source_name"),
                "source_type": row.get("source_type"),
                "opportunity_count": int(row.get("opportunity_count", 0) or 0),
                "won_count": int(row.get("won_count", 0) or 0),
                "total_revenue": source_revenue
            })

        result["total_revenue"] = total_revenue
        result["sources"] = sources

        # Query v_profit_loss
        pnl_data = _execute_query("SELECT * FROM v_profit_loss LIMIT 1;")
        if pnl_data.get("rows"):
            result["profit_loss"] = pnl_data["rows"][0]

    except ExecutiveDashboardError as exc:
        logger.warning("Failed to fetch revenue metrics: %s", exc)
        result["error"] = str(exc)

    return result


def get_tasks_completed() -> Dict[str, Any]:
    """
    Get task completion metrics from governance_tasks table.

    Returns:
        Dictionary containing task completion statistics.
    """
    result: Dict[str, Any] = {
        "total_completed": 0,
        "completed_today": 0,
        "completed_this_week": 0,
        "by_priority": {}
    }

    try:
        # Total completed tasks
        total_sql = """
            SELECT 
                COUNT(*) FILTER (WHERE status = 'completed') as total_completed,
                COUNT(*) FILTER (WHERE status = 'completed' 
                    AND completed_at >= CURRENT_DATE) as completed_today,
                COUNT(*) FILTER (WHERE status = 'completed' 
                    AND completed_at >= CURRENT_DATE - INTERVAL '7 days') as completed_this_week
            FROM governance_tasks;
        """
        total_data = _execute_query(total_sql)

        if total_data.get("rows"):
            row = total_data["rows"][0]
            result["total_completed"] = int(row.get("total_completed", 0) or 0)
            result["completed_today"] = int(row.get("completed_today", 0) or 0)
            result["completed_this_week"] = int(row.get("completed_this_week", 0) or 0)

        # Completed by priority
        priority_sql = """
            SELECT priority, COUNT(*) as count
            FROM governance_tasks
            WHERE status = 'completed'
            GROUP BY priority;
        """
        priority_data = _execute_query(priority_sql)

        by_priority: Dict[str, int] = {}
        for row in priority_data.get("rows", []):
            priority = row.get("priority", "unknown")
            by_priority[priority] = int(row.get("count", 0) or 0)

        result["by_priority"] = by_priority

    except ExecutiveDashboardError as exc:
        logger.warning("Failed to fetch task metrics: %s", exc)
        result["error"] = str(exc)

    return result


def get_active_experiments() -> Dict[str, Any]:
    """
    Get active experiment metrics from experiments table.

    Returns:
        Dictionary containing experiment status summary.
    """
    result: Dict[str, Any] = {
        "running": 0,
        "total": 0,
        "experiments": []
    }

    try:
        # Experiment counts by status
        status_sql = """
            SELECT 
                status,
                COUNT(*) as count
            FROM experiments
            GROUP BY status;
        """
        status_data = _execute_query(status_sql)

        total = 0
        running = 0
        for row in status_data.get("rows", []):
            status = row.get("status", "")
            count = int(row.get("count", 0) or 0)
            total += count
            if status == "running":
                running = count

        result["running"] = running
        result["total"] = total

        # Get active experiments list
        active_sql = """
            SELECT id, name, hypothesis, status, created_at
            FROM experiments
            WHERE status = 'running'
            ORDER BY created_at DESC
            LIMIT 10;
        """
        active_data = _execute_query(active_sql)
        result["experiments"] = active_data.get("rows", [])

    except ExecutiveDashboardError as exc:
        logger.warning("Failed to fetch experiment metrics: %s", exc)
        result["error"] = str(exc)

    return result


def get_system_health_from_view() -> Dict[str, Any]:
    """
    Get system health metrics from v_system_health view.

    Returns:
        Dictionary containing system health status.
    """
    result: Dict[str, Any] = {
        "status": "unknown",
        "components": [],
        "last_check": None
    }

    try:
        health_data = _execute_query("SELECT * FROM v_system_health;")
        components: List[Dict[str, Any]] = []
        all_healthy = True
        latest_check: Optional[str] = None

        for row in health_data.get("rows", []):
            status = row.get("status", "unknown")
            if status not in ("healthy", "ok", "up"):
                all_healthy = False

            check_time = row.get("last_check_at")
            if check_time and (latest_check is None or check_time > latest_check):
                latest_check = check_time

            components.append({
                "component": row.get("component"),
                "check_type": row.get("check_type"),
                "status": status,
                "response_time_ms": row.get("response_time_ms"),
                "consecutive_failures": row.get("consecutive_failures"),
                "freshness": row.get("freshness")
            })

        result["components"] = components
        result["last_check"] = latest_check

        if not components:
            result["status"] = "no_data"
        elif all_healthy:
            result["status"] = "healthy"
        else:
            result["status"] = "degraded"

    except ExecutiveDashboardError as exc:
        logger.warning("Failed to fetch system health: %s", exc)
        result["status"] = "error"
        result["error"] = str(exc)

    return result


def get_executive_dashboard() -> Dict[str, Any]:
    """
    Get the complete executive dashboard data.

    Aggregates metrics from all sources using pre-computed database views
    for efficient querying.

    Returns:
        Dictionary containing all executive dashboard metrics:
        - timestamp: Current UTC timestamp
        - revenue: Revenue metrics from v_revenue_by_source
        - tasks_completed: Task completion statistics
        - active_experiments: Running experiment count and details
        - system_health: System health status from v_system_health
    """
    logger.info("Generating executive dashboard")

    dashboard: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_version": "1.0",
        "revenue": get_revenue_metrics(),
        "tasks_completed": get_tasks_completed(),
        "active_experiments": get_active_experiments(),
        "system_health": get_system_health_from_view()
    }

    logger.info(
        "Dashboard generated: revenue=$%.2f, tasks=%d, experiments=%d running",
        dashboard["revenue"].get("total_revenue", 0),
        dashboard["tasks_completed"].get("total_completed", 0),
        dashboard["active_experiments"].get("running", 0)
    )

    return dashboard


def handle_dashboard_request(
    method: str,
    headers: Dict[str, str],
    query_params: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Handle an incoming dashboard API request.

    This is a public endpoint that does not require authentication
    for read-only executive summary data.

    Args:
        method: HTTP method (only GET is supported).
        headers: Request headers.
        query_params: Optional query parameters.

    Returns:
        Response dictionary with status code and body.
    """
    if method != "GET":
        return {
            "status": 405,
            "body": {"error": "Method not allowed. Use GET."}
        }

    try:
        dashboard_data = get_executive_dashboard()
        return {
            "status": 200,
            "body": dashboard_data
        }
    except Exception as exc:
        logger.exception("Unexpected error generating dashboard")
        return {
            "status": 500,
            "body": {"error": f"Internal server error: {exc}"}
        }


# For direct testing
if __name__ == "__main__":
    import pprint
    print("Fetching executive dashboard...")
    result = get_executive_dashboard()
    pprint.pprint(result)
