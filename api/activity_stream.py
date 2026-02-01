"""
Activity Stream API (Server-Sent Events)

SSE endpoint for live activity streaming to spartan-hq frontend.

Endpoints:
    GET /api/activity/stream - SSE stream of execution_logs and task status changes

Authentication:
    Requires MCP_AUTH_TOKEN or INTERNAL_API_SECRET in query params.

Usage:
    Client connects via EventSource:
        const es = new EventSource('/api/activity/stream?token=xxx&last_seen=2024-01-01T00:00:00Z');
        es.onmessage = (event) => {
            const data = JSON.parse(event.data);
            // data.type: 'log' | 'task' | 'heartbeat'
            // data.payload: log/task object
        };
"""

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Generator, Optional

# Configure module logger
logger = logging.getLogger(__name__)

# Auth tokens from environment
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")

# Database configuration
NEON_ENDPOINT = os.getenv(
    "NEON_ENDPOINT",
    "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# SSE configuration
POLL_INTERVAL_SECONDS = 2  # How often to check for new events
HEARTBEAT_INTERVAL_SECONDS = 30  # How often to send heartbeat to keep connection alive


def _execute_sql(sql: str) -> Dict[str, Any]:
    """Execute SQL query against Neon database."""
    import urllib.request
    import urllib.error

    if not DATABASE_URL:
        return {"error": "DATABASE_URL not configured", "rows": []}

    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL
    }

    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(
        NEON_ENDPOINT,
        data=data,
        headers=headers,
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        # Extract actual error body from Neon
        error_body = exc.read().decode('utf-8')
        logger.error("Database HTTP error: %s - %s", exc.code, error_body)
        return {"error": f"HTTP {exc.code}: {error_body}", "rows": []}
    except Exception as exc:
        logger.error("Database error: %s", str(exc))
        return {"error": str(exc), "rows": []}


def _escape_sql(value: Any) -> str:
    """Escape a value for safe SQL interpolation."""
    if value is None:
        return "NULL"
    elif isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    elif isinstance(value, (int, float)):
        return str(value)
    else:
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"


def _validate_auth(params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate authentication token."""
    if not MCP_AUTH_TOKEN and not INTERNAL_API_SECRET:
        logger.warning("No auth tokens configured - auth disabled")
        return True, None

    token = params.get("token", "")
    if isinstance(token, list):
        token = token[0] if token else ""

    if not token:
        return False, "Missing authentication token"

    if token == MCP_AUTH_TOKEN or token == INTERNAL_API_SECRET:
        return True, None

    return False, "Invalid authentication token"


def get_recent_logs(since: str, limit: int = 50) -> list:
    """
    Get execution_logs created since the given timestamp.

    Args:
        since: ISO timestamp to fetch logs after
        limit: Max number of logs to return

    Returns:
        List of log entries
    """
    sql = f"""
        SELECT
            id, worker_id, action, message, level,
            goal_id, task_id, source, duration_ms,
            tokens_used, cost_cents, created_at
        FROM execution_logs
        WHERE created_at > {_escape_sql(since)}
        ORDER BY created_at ASC
        LIMIT {limit}
    """
    result = _execute_sql(sql)
    return result.get("rows", [])


def get_task_changes(since: str, limit: int = 50) -> list:
    """
    Get governance_tasks that changed status since the given timestamp.

    Args:
        since: ISO timestamp to fetch changes after
        limit: Max number of tasks to return

    Returns:
        List of task entries with status changes
    """
    sql = f"""
        SELECT
            id, status, stage, title, task_type, priority,
            assigned_worker, created_by, updated_at
        FROM governance_tasks
        WHERE updated_at > {_escape_sql(since)}
        ORDER BY updated_at ASC
        LIMIT {limit}
    """
    result = _execute_sql(sql)
    return result.get("rows", [])


def format_sse_event(event_type: str, data: Any, event_id: Optional[str] = None) -> str:
    """
    Format data as an SSE event.

    Args:
        event_type: Event type (log, task, heartbeat)
        data: Event payload
        event_id: Optional event ID for client reconnection

    Returns:
        SSE formatted string
    """
    payload = {
        "type": event_type,
        "payload": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(payload, default=str)}")
    lines.append("")  # Empty line to end the event
    lines.append("")

    return "\n".join(lines)


def generate_activity_stream(
    last_seen: Optional[str] = None,
    include_logs: bool = True,
    include_tasks: bool = True
) -> Generator[str, None, None]:
    """
    Generate SSE events for activity stream.

    Args:
        last_seen: ISO timestamp to start streaming from (default: 5 minutes ago)
        include_logs: Whether to include execution_logs
        include_tasks: Whether to include task status changes

    Yields:
        SSE formatted event strings
    """
    # Default to 5 minutes ago if no last_seen provided
    if not last_seen:
        last_seen = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

    last_log_time = last_seen
    last_task_time = last_seen
    last_heartbeat = time.time()

    while True:
        try:
            events_sent = 0

            # Fetch new logs
            if include_logs:
                logs = get_recent_logs(last_log_time, limit=20)
                for log in logs:
                    yield format_sse_event("log", log, event_id=str(log.get("id", "")))
                    last_log_time = log.get("created_at", last_log_time)
                    events_sent += 1

            # Fetch task changes
            if include_tasks:
                tasks = get_task_changes(last_task_time, limit=20)
                for task in tasks:
                    yield format_sse_event("task", task, event_id=f"task-{task.get('id', '')}")
                    last_task_time = task.get("updated_at", last_task_time)
                    events_sent += 1

            # Send heartbeat if no events and enough time has passed
            current_time = time.time()
            if events_sent == 0 and (current_time - last_heartbeat) >= HEARTBEAT_INTERVAL_SECONDS:
                yield format_sse_event("heartbeat", {
                    "status": "connected",
                    "last_log_time": last_log_time,
                    "last_task_time": last_task_time
                })
                last_heartbeat = current_time

            # Wait before next poll
            time.sleep(POLL_INTERVAL_SECONDS)

        except GeneratorExit:
            # Client disconnected
            logger.info("Activity stream client disconnected")
            break
        except Exception as e:
            logger.error("Error in activity stream: %s", str(e))
            yield format_sse_event("error", {"message": str(e)})
            time.sleep(5)  # Wait longer on error


class ActivityStreamHandler:
    """
    Handler for activity stream SSE requests.

    Used by main.py to handle /api/activity/stream endpoint.
    """

    @staticmethod
    def validate_request(params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate the incoming request."""
        return _validate_auth(params)

    @staticmethod
    def get_sse_headers() -> Dict[str, str]:
        """Get headers for SSE response."""
        return {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }

    @staticmethod
    def create_stream(params: Dict[str, Any]) -> Generator[str, None, None]:
        """
        Create the activity stream generator.

        Args:
            params: Query parameters including:
                - last_seen: ISO timestamp to start from
                - include_logs: "true"/"false" (default: true)
                - include_tasks: "true"/"false" (default: true)

        Returns:
            Generator yielding SSE events
        """
        last_seen = params.get("last_seen")
        if isinstance(last_seen, list):
            last_seen = last_seen[0] if last_seen else None

        include_logs = params.get("include_logs", "true") != "false"
        include_tasks = params.get("include_tasks", "true") != "false"

        return generate_activity_stream(
            last_seen=last_seen,
            include_logs=include_logs,
            include_tasks=include_tasks
        )


def handle_activity_request(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handle activity API requests (non-streaming).

    For SSE streaming, use ActivityStreamHandler directly in main.py.

    Args:
        method: HTTP method
        path: Request path after /api/activity/
        params: Query parameters

    Returns:
        Response dict for non-streaming endpoints
    """
    params = params or {}

    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": ActivityStreamHandler.get_sse_headers(),
            "body": ""
        }

    # For the /stream endpoint, return info about how to use it
    # (actual streaming handled separately in main.py)
    if path == "stream":
        is_valid, error = _validate_auth(params)
        if not is_valid:
            return {
                "statusCode": 401,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": error, "success": False})
            }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "message": "Use EventSource to connect to this SSE endpoint",
                "example": "new EventSource('/api/activity/stream?token=xxx')",
                "params": {
                    "token": "Required auth token",
                    "last_seen": "Optional ISO timestamp to start from",
                    "include_logs": "Optional, default true",
                    "include_tasks": "Optional, default true"
                }
            })
        }

    return {
        "statusCode": 404,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": f"Unknown endpoint: {path}", "success": False})
    }
