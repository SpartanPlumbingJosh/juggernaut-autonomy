"""
Chat Sessions API

REST API endpoints for chat persistence used by spartan-hq frontend.

Endpoints:
    GET    /api/chat/sessions         - List all sessions ordered by updated_at DESC
    POST   /api/chat/sessions         - Create new session
    GET    /api/chat/sessions/{id}    - Get session + all messages
    POST   /api/chat/sessions/{id}/messages - Append message to session
    PATCH  /api/chat/sessions/{id}    - Update session title
    DELETE /api/chat/sessions/{id}    - Delete session (cascade deletes messages)

Authentication:
    Requires MCP_AUTH_TOKEN or INTERNAL_API_SECRET in query params or Authorization header.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

# Configure module logger
logger = logging.getLogger(__name__)

# Auth tokens from environment
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")

# CORS headers for all responses
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
}

# Database configuration
NEON_ENDPOINT = os.getenv(
    "NEON_ENDPOINT",
    "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
)
DATABASE_URL = os.getenv("DATABASE_URL", "")


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


def _make_response(
    status_code: int,
    body: Dict[str, Any],
    extra_headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Create a standardized API response."""
    headers = {**CORS_HEADERS}
    if extra_headers:
        headers.update(extra_headers)

    return {
        "statusCode": status_code,
        "headers": {**headers, "Content-Type": "application/json"},
        "body": body,
    }


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create an error response."""
    return _make_response(status_code, {"error": message, "success": False})


def _validate_auth(params: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> tuple[bool, Optional[str]]:
    """
    Validate authentication token.

    Checks for token in:
    1. Query params: ?token=xxx
    2. Authorization header: Bearer xxx
    """
    # If no auth configured, allow all
    if not MCP_AUTH_TOKEN and not INTERNAL_API_SECRET:
        logger.warning("No auth tokens configured - auth disabled")
        return True, None

    # Check query param
    token = params.get("token", "")
    if isinstance(token, list):
        token = token[0] if token else ""

    # Check Authorization header
    if not token and headers:
        auth_header = headers.get("Authorization", "") or headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return False, "Missing authentication token"

    # Validate against known tokens
    if token == MCP_AUTH_TOKEN or token == INTERNAL_API_SECRET:
        return True, None

    return False, "Invalid authentication token"


# ============================================================
# API HANDLERS
# ============================================================

def list_sessions(params: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    GET /api/chat/sessions

    List all chat sessions ordered by updated_at DESC.

    Query params:
        user_id: Filter by user (default: 'operator')
        limit: Max results (default: 50)
        offset: Pagination offset (default: 0)

    Returns:
        {
            "success": true,
            "sessions": [
                {"id": "uuid", "title": "...", "user_id": "...", "created_at": "...", "updated_at": "..."}
            ],
            "total": 10
        }
    """
    is_valid, error = _validate_auth(params, headers)
    if not is_valid:
        return _error_response(401, error)

    user_id = params.get("user_id", "operator")
    limit = min(int(params.get("limit", 50)), 100)
    offset = int(params.get("offset", 0))

    # Get total count
    count_sql = f"SELECT COUNT(*) as total FROM chat_sessions WHERE user_id = {_escape_sql(user_id)}"
    count_result = _execute_sql(count_sql)
    total = count_result.get("rows", [{}])[0].get("total", 0) if count_result.get("rows") else 0

    # Get sessions
    sql = f"""
        SELECT id, user_id, title, created_at, updated_at
        FROM chat_sessions
        WHERE user_id = {_escape_sql(user_id)}
        ORDER BY updated_at DESC
        LIMIT {limit} OFFSET {offset}
    """
    result = _execute_sql(sql)

    if "error" in result:
        return _error_response(500, result["error"])

    sessions = result.get("rows", [])

    return _make_response(200, {
        "success": True,
        "sessions": sessions,
        "total": total
    })


def create_session(body: Dict[str, Any], params: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    POST /api/chat/sessions

    Create a new chat session.

    Body:
        {
            "title": "Optional title",
            "user_id": "optional user id (default: operator)"
        }

    Returns:
        {
            "success": true,
            "session": {"id": "uuid", "title": "...", "user_id": "...", "created_at": "..."}
        }
    """
    is_valid, error = _validate_auth(params, headers)
    if not is_valid:
        return _error_response(401, error)

    title = body.get("title", "New Chat")
    user_id = body.get("user_id", "operator")

    sql = f"""
        INSERT INTO chat_sessions (user_id, title)
        VALUES ({_escape_sql(user_id)}, {_escape_sql(title)})
        RETURNING id, user_id, title, created_at, updated_at
    """
    result = _execute_sql(sql)

    if "error" in result:
        return _error_response(500, result["error"])

    if not result.get("rows"):
        return _error_response(500, "Failed to create session")

    session = result["rows"][0]

    return _make_response(201, {
        "success": True,
        "session": session
    })


def get_session(session_id: str, params: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    GET /api/chat/sessions/{id}

    Get a session with all its messages.

    Returns:
        {
            "success": true,
            "session": {"id": "uuid", "title": "...", ...},
            "messages": [
                {"id": "uuid", "role": "user", "content": "...", "created_at": "..."}
            ]
        }
    """
    is_valid, error = _validate_auth(params, headers)
    if not is_valid:
        return _error_response(401, error)

    # Get session
    session_sql = f"""
        SELECT id, user_id, title, created_at, updated_at
        FROM chat_sessions
        WHERE id = {_escape_sql(session_id)}
    """
    session_result = _execute_sql(session_sql)

    if "error" in session_result:
        return _error_response(500, session_result["error"])

    if not session_result.get("rows"):
        return _error_response(404, "Session not found")

    session = session_result["rows"][0]

    # Get messages
    messages_sql = f"""
        SELECT id, session_id, role, content, created_at
        FROM chat_messages
        WHERE session_id = {_escape_sql(session_id)}
        ORDER BY created_at ASC
    """
    messages_result = _execute_sql(messages_sql)

    messages = messages_result.get("rows", []) if "error" not in messages_result else []

    return _make_response(200, {
        "success": True,
        "session": session,
        "messages": messages
    })


def append_message(
    session_id: str,
    body: Dict[str, Any],
    params: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    POST /api/chat/sessions/{id}/messages

    Append a message to a session. Also updates session.updated_at.

    Body:
        {
            "role": "user" | "assistant" | "system",
            "content": "Message content"
        }

    Returns:
        {
            "success": true,
            "message": {"id": "uuid", "role": "...", "content": "...", "created_at": "..."}
        }
    """
    is_valid, error = _validate_auth(params, headers)
    if not is_valid:
        return _error_response(401, error)

    role = body.get("role")
    content = body.get("content")

    if not role:
        return _error_response(400, "Missing required field: role")
    if not content:
        return _error_response(400, "Missing required field: content")
    if role not in ("user", "assistant", "system"):
        return _error_response(400, "Invalid role. Must be 'user', 'assistant', or 'system'")

    # Verify session exists
    check_sql = f"SELECT id FROM chat_sessions WHERE id = {_escape_sql(session_id)}"
    check_result = _execute_sql(check_sql)

    if not check_result.get("rows"):
        return _error_response(404, "Session not found")

    # Insert message
    insert_sql = f"""
        INSERT INTO chat_messages (session_id, role, content)
        VALUES ({_escape_sql(session_id)}, {_escape_sql(role)}, {_escape_sql(content)})
        RETURNING id, session_id, role, content, created_at
    """
    insert_result = _execute_sql(insert_sql)

    if "error" in insert_result:
        return _error_response(500, insert_result["error"])

    if not insert_result.get("rows"):
        return _error_response(500, "Failed to create message")

    message = insert_result["rows"][0]

    # Update session's updated_at
    update_sql = f"""
        UPDATE chat_sessions
        SET updated_at = NOW()
        WHERE id = {_escape_sql(session_id)}
    """
    _execute_sql(update_sql)

    return _make_response(201, {
        "success": True,
        "message": message
    })


def update_session(
    session_id: str,
    body: Dict[str, Any],
    params: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    PATCH /api/chat/sessions/{id}

    Update session title.

    Body:
        {
            "title": "New title"
        }

    Returns:
        {
            "success": true,
            "session": {"id": "uuid", "title": "...", ...}
        }
    """
    is_valid, error = _validate_auth(params, headers)
    if not is_valid:
        return _error_response(401, error)

    title = body.get("title")

    if not title:
        return _error_response(400, "Missing required field: title")

    sql = f"""
        UPDATE chat_sessions
        SET title = {_escape_sql(title)}, updated_at = NOW()
        WHERE id = {_escape_sql(session_id)}
        RETURNING id, user_id, title, created_at, updated_at
    """
    result = _execute_sql(sql)

    if "error" in result:
        return _error_response(500, result["error"])

    if not result.get("rows"):
        return _error_response(404, "Session not found")

    session = result["rows"][0]

    return _make_response(200, {
        "success": True,
        "session": session
    })


def delete_session(session_id: str, params: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    DELETE /api/chat/sessions/{id}

    Delete a session and all its messages (via CASCADE).

    Returns:
        {
            "success": true,
            "deleted": true
        }
    """
    is_valid, error = _validate_auth(params, headers)
    if not is_valid:
        return _error_response(401, error)

    # Check if session exists first
    check_sql = f"SELECT id FROM chat_sessions WHERE id = {_escape_sql(session_id)}"
    check_result = _execute_sql(check_sql)

    if not check_result.get("rows"):
        return _error_response(404, "Session not found")

    # Delete session (messages deleted via CASCADE)
    sql = f"DELETE FROM chat_sessions WHERE id = {_escape_sql(session_id)}"
    result = _execute_sql(sql)

    if "error" in result:
        return _error_response(500, result["error"])

    return _make_response(200, {
        "success": True,
        "deleted": True
    })


# ============================================================
# REQUEST ROUTER
# ============================================================

def handle_chat_request(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Route chat API requests to appropriate handlers.

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE, OPTIONS)
        path: Request path after /api/chat/ (e.g., "sessions", "sessions/uuid", "sessions/uuid/messages")
        params: Query parameters
        body: Request body for POST/PATCH requests
        headers: Request headers

    Returns:
        Dict with 'statusCode', 'headers', and 'body' keys.
    """
    params = params or {}
    body = body or {}
    headers = headers or {}

    # Handle OPTIONS for CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {"success": True})

    # Parse path segments
    # Expected paths:
    #   sessions                    -> list/create
    #   sessions/{id}               -> get/update/delete
    #   sessions/{id}/messages      -> append message

    path = path.strip("/")
    segments = path.split("/") if path else []

    # /api/chat/sessions
    if len(segments) == 1 and segments[0] == "sessions":
        if method == "GET":
            return list_sessions(params, headers)
        elif method == "POST":
            return create_session(body, params, headers)
        return _error_response(405, f"Method {method} not allowed")

    # /api/chat/sessions/{id}
    elif len(segments) == 2 and segments[0] == "sessions":
        session_id = segments[1]
        if method == "GET":
            return get_session(session_id, params, headers)
        elif method == "PATCH":
            return update_session(session_id, body, params, headers)
        elif method == "DELETE":
            return delete_session(session_id, params, headers)
        return _error_response(405, f"Method {method} not allowed")

    # /api/chat/sessions/{id}/messages
    elif len(segments) == 3 and segments[0] == "sessions" and segments[2] == "messages":
        session_id = segments[1]
        if method == "POST":
            return append_message(session_id, body, params, headers)
        return _error_response(405, f"Method {method} not allowed")

    return _error_response(404, f"Unknown endpoint: {path}")
