"""
BRAIN-03: Brain API Endpoints

REST API endpoints for the JUGGERNAUT brain consultation service.

Endpoints:
    POST /api/brain/consult - Consult the brain with a question
    GET /api/brain/history - Get conversation history for a session
    DELETE /api/brain/clear - Clear conversation history for a session

Authentication:
    All endpoints require a 'token' query parameter matching MCP_AUTH_TOKEN env var.

CORS:
    All endpoints include CORS headers for cross-origin requests.
"""

import json
import logging
import os
from typing import Any, Dict, Generator, Optional, Tuple
from urllib.parse import parse_qs, urlparse

# Configure module logger
logger = logging.getLogger(__name__)

# Auth token from environment
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")

# CORS headers for all responses
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
}

# Check if BrainService is available at module load time
BRAIN_AVAILABLE = False
_brain_import_error = None

try:
    from core.unified_brain import BrainService
    from core.self_healing import get_self_healing_manager

    BRAIN_AVAILABLE = True
except ImportError as e:
    _brain_import_error = str(e)
    logger.warning("BrainService not available: %s", e)


def _make_response(
    status_code: int,
    body: Dict[str, Any],
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Create a standardized API response.

    Args:
        status_code: HTTP status code.
        body: Response body as dictionary.
        extra_headers: Additional headers to include.

    Returns:
        Response dictionary with statusCode, headers, and body.
    """
    headers = {**CORS_HEADERS}
    if extra_headers:
        headers.update(extra_headers)

    return {
        "statusCode": status_code,
        "headers": {**headers, "Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Create an error response.

    Args:
        status_code: HTTP status code.
        message: Error message.

    Returns:
        Error response dictionary.
    """
    return _make_response(status_code, {"error": message, "success": False})


def _validate_auth(
    query_params: Dict[str, Any], headers: Optional[Dict[str, str]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate authentication token from query params or Authorization header.

    Args:
        query_params: Query parameters from request.
        headers: Request headers (optional).

    Returns:
        Tuple of (is_valid, error_message).
    """
    valid_tokens = [
        os.getenv("MCP_AUTH_TOKEN", ""),
        os.getenv("INTERNAL_API_SECRET", ""),
    ]
    valid_tokens = [t for t in valid_tokens if t]

    if not valid_tokens:
        logger.warning("No auth token configured - auth disabled")
        return True, None

    # Check query param first
    token_value = query_params.get("token", "")
    if isinstance(token_value, list):
        token = token_value[0] if token_value else ""
    else:
        token = token_value

    # Check Authorization header if no query param token
    if not token and headers:

        def _get_header_value(target_header: str) -> str:
            for key, val in headers.items():
                key_str = (
                    key.decode("utf-8", "ignore")
                    if isinstance(key, bytes)
                    else str(key)
                )
                if key_str.lower() != target_header:
                    continue
                if isinstance(val, bytes):
                    return val.decode("utf-8", "ignore")
                return str(val)
            return ""

        auth_header = _get_header_value("authorization")
        auth_header_str = (auth_header or "").strip()
        if auth_header_str.lower().startswith("bearer "):
            token = auth_header_str[7:].strip()

        # Also check x-api-key and x-internal-api-secret headers
        if not token:
            token = (
                _get_header_value("x-api-key")
                or _get_header_value("x-internal-api-secret")
            ).strip()

    if not token:
        return False, "Missing authentication token"

    if token not in valid_tokens:
        return False, "Invalid authentication token"

    return True, None


def _get_brain_service():
    """
    Get or create BrainService instance.

    Returns:
        BrainService instance, or None if BrainService is not available.
    """
    if not BRAIN_AVAILABLE:
        logger.error("BrainService not available: %s", _brain_import_error)
        return None
    return BrainService()


def handle_consult(
    body: Dict[str, Any],
    query_params: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Handle POST /api/brain/consult request with optional MCP tool execution.

    Accepts:
        {
            "question": "Your question here",
            "session_id": "optional-session-id",
            "context": {"optional": "context data"},
            "enable_tools": true,  // Enable MCP tool execution (default: true)
            "include_memories": true
        }

    Returns:
        {
            "success": true,
            "response": "AI response text",
            "session_id": "session-id-used",
            "memories_used": [...],
            "tool_executions": [{"tool": "sql_query", "arguments": {...}, "result": {...}}],
            "cost_cents": 0.05,
            "input_tokens": 150,
            "output_tokens": 200,
            "iterations": 2,
            "model": "openrouter/auto"
        }

    Args:
        body: Request body.
        query_params: Query parameters.
        headers: Request headers (optional).

    Returns:
        API response dictionary.
    """
    # Validate auth
    is_valid, error = _validate_auth(query_params, headers)
    if not is_valid:
        return _error_response(401, error)

    # Validate request body
    question = body.get("question")
    if not question:
        return _error_response(400, "Missing required field: question")

    session_id = body.get("session_id")
    context = body.get("context")
    enable_tools = body.get("enable_tools", True)  # Tools enabled by default
    include_memories = body.get("include_memories", True)
    auto_execute = body.get("auto_execute", False)
    system_prompt = body.get("system_prompt")

    try:
        brain = _get_brain_service()
        if brain is None:
            return _error_response(503, "Brain service not available")

        # Use tool-enabled consultation when tools are enabled
        if enable_tools:
            result = brain.consult_with_tools(
                question=question,
                session_id=session_id,
                context=context,
                include_memories=include_memories,
                system_prompt=system_prompt,
                enable_tools=True,
                auto_execute=auto_execute,
            )
        else:
            # Fall back to non-tool consultation
            result = brain.consult(
                question=question,
                session_id=session_id,
                context=context,
                include_memories=include_memories,
                system_prompt=system_prompt,
            )

        return _make_response(
            200,
            {
                "success": True,
                "response": result.get("response", ""),
                "session_id": result.get("session_id", ""),
                "memories_used": result.get("memories_used", []),
                "tool_executions": result.get("tool_executions", []),
                "cost_cents": result.get("cost_cents", 0),
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                "iterations": result.get("iterations", 1),
                "model": result.get("model", ""),
            },
        )

    except ImportError:
        return _error_response(503, "Brain service not available")
    except Exception as e:
        logger.exception("Error in brain consult: %s", str(e))
        return _error_response(500, f"Internal error: {str(e)}")


def handle_health(
    query_params: Dict[str, Any], headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Handle GET /api/brain/health request.

    Returns self-healing system health metrics.

    Returns:
        {
            "success": true,
            "metrics": {
                "total_recovery_attempts": 10,
                "successful_recoveries": 8,
                "recovery_rate_percent": 80.0,
                "recent_failures_1h": 3,
                "failure_breakdown": {"rate_limit": 2, "timeout": 1},
                "component_health": {"model:gpt-5.1:rate_limit": "healthy"}
            },
            "alert": {
                "triggered": false,
                "reason": ""
            }
        }
    """
    if not _validate_auth(query_params, headers):
        return _error_response(401, "Unauthorized")

    if not BRAIN_AVAILABLE:
        return _error_response(503, "Brain service not available")

    try:
        healing_mgr = get_self_healing_manager()
        metrics = healing_mgr.get_health_metrics()
        should_alert, alert_reason = healing_mgr.should_trigger_alert()

        return _make_response(
            200,
            {
                "success": True,
                "metrics": metrics,
                "alert": {
                    "triggered": should_alert,
                    "reason": alert_reason,
                },
            },
        )

    except Exception as e:
        logger.exception("Error getting health metrics: %s", str(e))
        return _error_response(500, f"Internal error: {str(e)}")


def handle_history(
    query_params: Dict[str, Any], headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Handle GET /api/brain/history request.

    Query params:
        session_id: Required session ID to get history for.

    Returns:
        {
            "success": true,
            "session_id": "session-id",
            "history": [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ],
            "message_count": 10
        }

    Args:
        query_params: Query parameters.
        headers: Request headers (optional).

    Returns:
        API response dictionary.
    """
    # Validate auth
    is_valid, error = _validate_auth(query_params, headers)
    if not is_valid:
        return _error_response(401, error)

    # Get session_id from query params
    session_id = (
        query_params.get("session_id", [""])[0]
        if isinstance(query_params.get("session_id"), list)
        else query_params.get("session_id", "")
    )

    if not session_id:
        return _error_response(400, "Missing required parameter: session_id")

    try:
        brain = _get_brain_service()
        if brain is None:
            return _error_response(503, "Brain service not available")

        history = brain.get_history(session_id)

        return _make_response(
            200,
            {
                "success": True,
                "session_id": session_id,
                "history": history,
                "message_count": len(history),
            },
        )

    except ImportError:
        return _error_response(503, "Brain service not available")
    except Exception as e:
        logger.exception("Error getting history: %s", str(e))
        return _error_response(500, f"Internal error: {str(e)}")


def handle_clear(
    query_params: Dict[str, Any], headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Handle DELETE /api/brain/clear request.

    Query params:
        session_id: Required session ID to clear.

    Returns:
        {
            "success": true,
            "session_id": "session-id",
            "messages_deleted": 10
        }

    Args:
        query_params: Query parameters.
        headers: Request headers (optional).

    Returns:
        API response dictionary.
    """
    # Validate auth
    is_valid, error = _validate_auth(query_params, headers)
    if not is_valid:
        return _error_response(401, error)

    # Get session_id from query params
    session_id = (
        query_params.get("session_id", [""])[0]
        if isinstance(query_params.get("session_id"), list)
        else query_params.get("session_id", "")
    )

    if not session_id:
        return _error_response(400, "Missing required parameter: session_id")

    try:
        brain = _get_brain_service()
        if brain is None:
            return _error_response(503, "Brain service not available")

        result = brain.clear_history(session_id)

        return _make_response(
            200,
            {
                "success": True,
                "session_id": result.get("session_id", session_id),
                "messages_deleted": result.get("deleted", 0),
            },
        )

    except ImportError:
        return _error_response(503, "Brain service not available")
    except Exception as e:
        logger.exception("Error clearing history: %s", str(e))
        return _error_response(500, f"Internal error: {str(e)}")


def handle_consult_stream(
    body: Optional[Dict[str, Any]],
    params: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Generator[str, None, None]:
    """
    Handle POST /api/brain/consult/stream request - streaming SSE response.

    This endpoint returns a Server-Sent Events (SSE) stream for real-time
    token streaming from the Brain API. Events are formatted as:
        data: {"type": "...", ...}\n\n

    Event types:
        - session: Session info {session_id, is_new_session}
        - token: Content token {content}
        - tool_start: Tool execution starting {tool, arguments}
        - tool_result: Tool execution complete {tool, result, success}
        - done: Stream complete {input_tokens, output_tokens, cost_cents, ...}
        - error: Error occurred {message}

    Args:
        body: Request body with question, session_id, enable_tools, etc.
        params: Query parameters for auth.
        headers: Request headers for auth.

    Yields:
        SSE formatted strings: "data: {...}\n\n"
    """
    body = body or {}
    params = params or {}
    headers = headers or {}

    # Validate auth
    is_valid, error = _validate_auth(params, headers)
    if not is_valid:
        yield f"data: {json.dumps({'type': 'error', 'message': error})}\n\n"
        return

    # Check if brain service is available
    if not BRAIN_AVAILABLE:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Brain service not available: {_brain_import_error}'})}\n\n"

    # Extract parameters from body
    question = body.get("question", "")
    if not question:
        return _error_response(400, "Missing required parameter: question")

    session_id = body.get("session_id")
    context = body.get("context")
    include_memories = body.get("include_memories", True)
    enable_tools = body.get("enable_tools", True)
    auto_execute = body.get("auto_execute", False)
    system_prompt = body.get("system_prompt")
    mode = body.get("mode")
    budgets = body.get("budgets")

    try:
        brain = _get_brain_service()
        if brain is None:
            return _error_response(503, "Brain service not available")

        if enable_tools and auto_execute:
            result = brain.consult_with_tools(
                question=question,
                session_id=session_id,
                context=context,
                include_memories=include_memories,
                system_prompt=system_prompt,
                enable_tools=enable_tools,
                auto_execute=auto_execute,
            )
        elif enable_tools:
            result = brain.consult_with_tools(
                question=question,
                session_id=session_id,
                context=context,
                include_memories=include_memories,
                system_prompt=system_prompt,
                enable_tools=enable_tools,
            )
            yield f"data: {json.dumps({'type': 'error', 'message': 'Brain service not available'})}\n\n"
            return

        # Stream consultation with tools
        for event in brain.consult_with_tools_stream(
            question=question,
            session_id=session_id,
            context=context,
            include_memories=include_memories,
            system_prompt=system_prompt,
            enable_tools=enable_tools,
            auto_execute=auto_execute,
            mode=mode,
            budgets=budgets,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    except ImportError as e:
        logger.error("Brain service import error: %s", str(e))
        yield f"data: {json.dumps({'type': 'error', 'message': 'Brain service not available'})}\n\n"
    except Exception as e:
        logger.exception("Error in streaming brain consult: %s", str(e))
        yield f"data: {json.dumps({'type': 'error', 'message': f'Internal error: {str(e)}'})}\n\n"


def handle_options() -> Dict[str, Any]:
    """
    Handle OPTIONS request for CORS preflight.

    Returns:
        Response with CORS headers.
    """
    return _make_response(200, {"success": True})


def handle_brain_request(
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Handle brain API requests from main.py.

    This function provides a simplified interface for main.py to route
    brain API requests to the appropriate handlers.

    Args:
        method: HTTP method (GET, POST, DELETE, OPTIONS).
        endpoint: Endpoint name (consult, history, clear).
        params: Query parameters.
        body: Request body for POST requests.
        headers: Request headers for auth.

    Returns:
        Dict with 'status' (int) and 'body' (dict) keys.
    """
    params = params or {}
    body = body or {}
    headers = headers or {}

    # Handle OPTIONS for CORS preflight
    if method == "OPTIONS":
        resp = handle_options()
        return {"status": resp["statusCode"], "body": json.loads(resp["body"])}

    if endpoint.startswith("unified/"):
        endpoint = endpoint[len("unified/") :]

    # Route to appropriate handler based on endpoint
    if endpoint == "consult":
        if method == "POST":
            resp = handle_consult(body, params, headers)
        else:
            resp = _error_response(405, f"Method {method} not allowed")
    elif endpoint == "history":
        if method == "GET":
            resp = handle_history(params, headers)
        else:
            resp = _error_response(405, f"Method {method} not allowed")
    elif endpoint == "clear":
        if method == "DELETE":
            resp = handle_clear(params, headers)
        else:
            resp = _error_response(405, f"Method {method} not allowed")
    elif endpoint == "health":
        if method == "GET":
            resp = handle_health(params, headers)
        else:
            resp = _error_response(405, f"Method {method} not allowed")
    else:
        resp = _error_response(404, f"Unknown endpoint: {endpoint}")

    return {"status": resp["statusCode"], "body": json.loads(resp["body"])}


def route_request(
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
    query_params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Route incoming request to appropriate handler.

    Args:
        method: HTTP method (GET, POST, DELETE, OPTIONS).
        path: Request path (e.g., /api/brain/consult).
        body: Request body for POST requests.
        query_params: Query parameters.
        headers: Request headers.

    Returns:
        API response dictionary.
    """
    body = body or {}
    query_params = query_params or {}
    headers = headers or {}

    # Handle OPTIONS for all paths (CORS preflight)
    if method == "OPTIONS":
        return handle_options()

    # Normalize path
    path = path.rstrip("/")

    # Route to handlers
    if path == "/api/brain/consult":
        if method == "POST":
            return handle_consult(body, query_params, headers)
        return _error_response(405, f"Method {method} not allowed for {path}")

    elif path == "/api/brain/history":
        if method == "GET":
            return handle_history(query_params, headers)
        return _error_response(405, f"Method {method} not allowed for {path}")

    elif path == "/api/brain/clear":
        if method == "DELETE":
            return handle_clear(query_params, headers)
        return _error_response(405, f"Method {method} not allowed for {path}")

    elif path == "/api/brain/unified/consult":
        if method == "POST":
            return handle_consult(body, query_params, headers)
        return _error_response(405, f"Method {method} not allowed for {path}")

    elif path == "/api/brain/unified/history":
        if method == "GET":
            return handle_history(query_params, headers)
        return _error_response(405, f"Method {method} not allowed for {path}")

    elif path == "/api/brain/unified/clear":
        if method == "DELETE":
            return handle_clear(query_params, headers)
        return _error_response(405, f"Method {method} not allowed for {path}")

    return _error_response(404, f"Endpoint not found: {path}")


# =============================================================================
# HTTP Server Integration
# =============================================================================


def create_flask_routes(app):
    """
    Register brain API routes with a Flask app.

    Args:
        app: Flask application instance.
    """
    from flask import request, jsonify

    @app.route("/api/brain/consult", methods=["POST", "OPTIONS"])
    def flask_consult():
        if request.method == "OPTIONS":
            resp = handle_options()
        else:
            body = request.get_json(force=True, silent=True) or {}
            query_params = {k: v for k, v in request.args.items()}
            headers = {k: v for k, v in request.headers.items()}
            resp = handle_consult(body, query_params, headers)

        response = jsonify(json.loads(resp["body"]))
        response.status_code = resp["statusCode"]
        for key, value in resp["headers"].items():
            response.headers[key] = value
        return response

    @app.route("/api/brain/history", methods=["GET", "OPTIONS"])
    def flask_history():
        if request.method == "OPTIONS":
            resp = handle_options()
        else:
            query_params = {k: v for k, v in request.args.items()}
            headers = {k: v for k, v in request.headers.items()}
            resp = handle_history(query_params, headers)

        response = jsonify(json.loads(resp["body"]))
        response.status_code = resp["statusCode"]
        for key, value in resp["headers"].items():
            response.headers[key] = value
        return response

    @app.route("/api/brain/clear", methods=["DELETE", "OPTIONS"])
    def flask_clear():
        if request.method == "OPTIONS":
            resp = handle_options()
        else:
            query_params = {k: v for k, v in request.args.items()}
            headers = {k: v for k, v in request.headers.items()}
            resp = handle_clear(query_params, headers)

        response = jsonify(json.loads(resp["body"]))
        response.status_code = resp["statusCode"]
        for key, value in resp["headers"].items():
            response.headers[key] = value
        return response

    logger.info("Registered brain API routes with Flask")


def create_http_handler():
    """
    Create a simple HTTP request handler for brain API.

    Returns:
        Handler function for HTTP server.
    """

    def handler(environ, start_response):
        """WSGI handler for brain API."""
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")
        query_string = environ.get("QUERY_STRING", "")

        # Parse query params
        query_params = parse_qs(query_string)

        # Parse body for POST
        body = {}
        if method == "POST":
            try:
                content_length = int(environ.get("CONTENT_LENGTH", 0))
                if content_length > 0:
                    body_bytes = environ["wsgi.input"].read(content_length)
                    body = json.loads(body_bytes.decode("utf-8"))
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning("Failed to parse request body: %s", str(e))

        # Route request
        response = route_request(method, path, body, query_params)

        # Build response
        status = f"{response['statusCode']} OK"
        if response["statusCode"] >= 400:
            status = f"{response['statusCode']} Error"

        headers = [(k, v) for k, v in response["headers"].items()]
        start_response(status, headers)

        return [response["body"].encode("utf-8")]

    return handler


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "BRAIN_AVAILABLE",
    "handle_brain_request",
    "handle_consult",
    "handle_history",
    "handle_clear",
    "handle_options",
    "route_request",
    "create_flask_routes",
    "create_http_handler",
]
