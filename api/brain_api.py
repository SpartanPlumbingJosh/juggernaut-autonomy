"""
Brain API Endpoints for JUGGERNAUT Engine.

Provides REST endpoints for interacting with the Brain service:
- POST /api/brain/consult - Consult the brain with a question
- GET /api/brain/history - Get conversation history
- DELETE /api/brain/clear - Clear conversation history

Authentication: Requires token query parameter matching MCP_AUTH_TOKEN env var.
"""

import json
import logging
import os
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

# Configure module logger
logger = logging.getLogger(__name__)

# Authentication token from environment
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")

# Track if brain module is available
BRAIN_AVAILABLE = False
_brain_import_error: Optional[str] = None

try:
    from core.brain import BrainService, BrainError, APIError, DatabaseError
    BRAIN_AVAILABLE = True
except ImportError as e:
    _brain_import_error = str(e)
    logger.warning(f"Brain module not available: {e}")


def authenticate(query_params: Dict[str, list]) -> Tuple[bool, str]:
    """
    Authenticate request using token query parameter.
    
    Args:
        query_params: Parsed query string parameters.
        
    Returns:
        Tuple of (authenticated, error_message).
    """
    if not MCP_AUTH_TOKEN:
        # No auth configured - allow all requests (development mode)
        logger.warning("MCP_AUTH_TOKEN not set - authentication disabled")
        return True, ""
    
    token_list = query_params.get("token", [])
    if not token_list:
        return False, "Missing authentication token"
    
    token = token_list[0]
    if token != MCP_AUTH_TOKEN:
        return False, "Invalid authentication token"
    
    return True, ""


def parse_json_body(handler: BaseHTTPRequestHandler) -> Tuple[Optional[Dict], str]:
    """
    Parse JSON body from request.
    
    Args:
        handler: HTTP request handler.
        
    Returns:
        Tuple of (parsed_body, error_message).
    """
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length == 0:
        return None, "Empty request body"
    
    try:
        body_bytes = handler.rfile.read(content_length)
        body = json.loads(body_bytes.decode("utf-8"))
        return body, ""
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"
    except Exception as e:
        return None, f"Error reading body: {e}"


def handle_brain_consult(
    handler: BaseHTTPRequestHandler,
    query_params: Dict[str, list]
) -> Tuple[int, Dict[str, Any]]:
    """
    Handle POST /api/brain/consult endpoint.
    
    Accepts JSON body:
    {
        "question": "Your question here",
        "session_id": "optional-session-id",
        "context": {"optional": "context data"}
    }
    
    Returns:
    {
        "response": "AI response",
        "session_id": "session-id",
        "memories_used": [...],
        "cost_cents": 0.123,
        "input_tokens": 100,
        "output_tokens": 50,
        "model": "model-name"
    }
    """
    if not BRAIN_AVAILABLE:
        return 503, {
            "success": False,
            "error": f"Brain service unavailable: {_brain_import_error}"
        }
    
    # Parse request body
    body, error = parse_json_body(handler)
    if error:
        return 400, {"success": False, "error": error}
    
    # Validate required fields
    question = body.get("question")
    if not question:
        return 400, {"success": False, "error": "Missing required field: question"}
    
    # Extract optional fields
    session_id = body.get("session_id")
    context = body.get("context")
    include_memories = body.get("include_memories", True)
    system_prompt = body.get("system_prompt")
    
    try:
        # Create service and consult
        service = BrainService()
        result = service.consult(
            question=question,
            session_id=session_id,
            context=context,
            include_memories=include_memories,
            system_prompt=system_prompt
        )
        
        return 200, {
            "success": True,
            "response": result["response"],
            "session_id": result["session_id"],
            "memories_used": result.get("memories_used", []),
            "cost_cents": result.get("cost_cents", 0),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "model": result.get("model", "")
        }
        
    except APIError as e:
        logger.error(f"Brain API error: {e}")
        return 502, {"success": False, "error": f"API error: {e}"}
    except DatabaseError as e:
        logger.error(f"Brain database error: {e}")
        return 500, {"success": False, "error": f"Database error: {e}"}
    except BrainError as e:
        logger.error(f"Brain error: {e}")
        return 500, {"success": False, "error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in brain consult: {e}")
        return 500, {"success": False, "error": f"Internal error: {e}"}


def handle_brain_history(
    handler: BaseHTTPRequestHandler,
    query_params: Dict[str, list]
) -> Tuple[int, Dict[str, Any]]:
    """
    Handle GET /api/brain/history endpoint.
    
    Query parameters:
    - session_id: Required session ID
    - limit: Optional limit (default 20)
    
    Returns conversation history for the session.
    """
    if not BRAIN_AVAILABLE:
        return 503, {
            "success": False,
            "error": f"Brain service unavailable: {_brain_import_error}"
        }
    
    # Get session_id from query params
    session_id_list = query_params.get("session_id", [])
    if not session_id_list:
        return 400, {"success": False, "error": "Missing required parameter: session_id"}
    
    session_id = session_id_list[0]
    
    # Get optional limit
    limit = 20
    limit_list = query_params.get("limit", [])
    if limit_list:
        try:
            limit = min(100, max(1, int(limit_list[0])))
        except ValueError:
            pass
    
    try:
        service = BrainService()
        history = service.get_history(session_id, limit=limit)
        
        return 200, {
            "success": True,
            "session_id": session_id,
            "messages": history,
            "count": len(history)
        }
        
    except DatabaseError as e:
        logger.error(f"Brain database error: {e}")
        return 500, {"success": False, "error": f"Database error: {e}"}
    except Exception as e:
        logger.exception(f"Unexpected error in brain history: {e}")
        return 500, {"success": False, "error": f"Internal error: {e}"}


def handle_brain_clear(
    handler: BaseHTTPRequestHandler,
    query_params: Dict[str, list]
) -> Tuple[int, Dict[str, Any]]:
    """
    Handle DELETE /api/brain/clear endpoint.
    
    Query parameters:
    - session_id: Required session ID to clear
    
    Clears all conversation history for the session.
    """
    if not BRAIN_AVAILABLE:
        return 503, {
            "success": False,
            "error": f"Brain service unavailable: {_brain_import_error}"
        }
    
    # Get session_id from query params
    session_id_list = query_params.get("session_id", [])
    if not session_id_list:
        return 400, {"success": False, "error": "Missing required parameter: session_id"}
    
    session_id = session_id_list[0]
    
    try:
        service = BrainService()
        result = service.clear_history(session_id)
        
        return 200, {
            "success": True,
            "session_id": session_id,
            "deleted": result.get("deleted", 0)
        }
        
    except DatabaseError as e:
        logger.error(f"Brain database error: {e}")
        return 500, {"success": False, "error": f"Database error: {e}"}
    except Exception as e:
        logger.exception(f"Unexpected error in brain clear: {e}")
        return 500, {"success": False, "error": f"Internal error: {e}"}


def handle_brain_request(
    handler: BaseHTTPRequestHandler,
    method: str,
    path: str
) -> Tuple[int, Dict[str, Any]]:
    """
    Main router for brain API requests.
    
    Args:
        handler: HTTP request handler.
        method: HTTP method (GET, POST, DELETE).
        path: Request path.
        
    Returns:
        Tuple of (status_code, response_dict).
    """
    # Parse URL and query params
    parsed = urlparse(path)
    query_params = parse_qs(parsed.query)
    endpoint = parsed.path
    
    # Authenticate
    authenticated, auth_error = authenticate(query_params)
    if not authenticated:
        return 401, {"success": False, "error": auth_error}
    
    # Route to handler
    if endpoint == "/api/brain/consult" and method == "POST":
        return handle_brain_consult(handler, query_params)
    
    elif endpoint == "/api/brain/history" and method == "GET":
        return handle_brain_history(handler, query_params)
    
    elif endpoint == "/api/brain/clear" and method == "DELETE":
        return handle_brain_clear(handler, query_params)
    
    else:
        return 404, {
            "success": False,
            "error": f"Unknown endpoint: {method} {endpoint}",
            "available_endpoints": [
                "POST /api/brain/consult",
                "GET /api/brain/history?session_id=X",
                "DELETE /api/brain/clear?session_id=X"
            ]
        }


def get_brain_status() -> Dict[str, Any]:
    """
    Get brain service status for health checks.
    
    Returns:
        Status dict with availability info.
    """
    return {
        "available": BRAIN_AVAILABLE,
        "import_error": _brain_import_error,
        "auth_configured": bool(MCP_AUTH_TOKEN),
        "endpoints": [
            "POST /api/brain/consult",
            "GET /api/brain/history?session_id=X", 
            "DELETE /api/brain/clear?session_id=X"
        ]
    }


__all__ = [
    "handle_brain_request",
    "get_brain_status",
    "BRAIN_AVAILABLE",
]
