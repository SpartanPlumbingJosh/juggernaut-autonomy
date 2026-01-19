"""
JUGGERNAUT Brain API Endpoints

REST API for the Brain consultation service.

Endpoints:
    POST /api/brain/consult - Consult the brain with a question
    GET /api/brain/history - Get conversation history
    DELETE /api/brain/clear - Clear conversation history

Auth:
    All endpoints require ?token=<MCP_AUTH_TOKEN> query parameter.
"""

import json
import logging
import os
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

# Configure module logger
logger = logging.getLogger(__name__)

# Auth configuration
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")

# Import availability flag
BRAIN_MODULE_AVAILABLE = False
_brain_import_error: Optional[str] = None

try:
    from core.brain import BrainService, BrainError, APIError, DatabaseError
    BRAIN_MODULE_AVAILABLE = True
except ImportError as e:
    _brain_import_error = str(e)
    
    # Stub classes for graceful degradation
    class BrainService:
        """Stub BrainService when core.brain is unavailable."""
        
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass
        
        def consult(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            return {"error": "Brain module not available"}
        
        def get_history(self, *args: Any, **kwargs: Any) -> list:
            return []
        
        def clear_history(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            return {"error": "Brain module not available"}
    
    class BrainError(Exception):
        """Stub exception."""
        pass
    
    class APIError(BrainError):
        """Stub exception."""
        pass
    
    class DatabaseError(BrainError):
        """Stub exception."""
        pass


def verify_auth_token(query_params: Dict[str, list]) -> Tuple[bool, str]:
    """
    Verify the auth token from query parameters.
    
    Args:
        query_params: Parsed query parameters dict.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    if not MCP_AUTH_TOKEN:
        # If no token configured, allow access (for development)
        logger.warning("MCP_AUTH_TOKEN not configured - allowing unauthenticated access")
        return True, ""
    
    token = query_params.get("token", [""])[0]
    if not token:
        return False, "Missing required 'token' query parameter"
    
    if token != MCP_AUTH_TOKEN:
        return False, "Invalid authentication token"
    
    return True, ""


def handle_consult(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/brain/consult request.
    
    Args:
        body: Request body with 'question', optional 'session_id', 'context'.
        
    Returns:
        Response dict with consultation result.
    """
    if not BRAIN_MODULE_AVAILABLE:
        return {
            "success": False,
            "error": f"Brain module not available: {_brain_import_error}"
        }
    
    question = body.get("question")
    if not question:
        return {
            "success": False,
            "error": "Missing required field: 'question'"
        }
    
    session_id = body.get("session_id")
    context = body.get("context")
    
    try:
        service = BrainService()
        result = service.consult(
            question=question,
            session_id=session_id,
            context=context
        )
        
        return {
            "success": True,
            "response": result.get("response", ""),
            "session_id": result.get("session_id", ""),
            "memories_used": result.get("memories_used", []),
            "cost_cents": result.get("cost_cents", 0),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "model": result.get("model", "")
        }
        
    except APIError as e:
        logger.error(f"Brain API error: {e}")
        return {
            "success": False,
            "error": f"API error: {str(e)}"
        }
    except DatabaseError as e:
        logger.error(f"Brain database error: {e}")
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    except BrainError as e:
        logger.error(f"Brain error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        logger.exception(f"Unexpected error in brain consult: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def handle_history(query_params: Dict[str, list]) -> Dict[str, Any]:
    """
    Handle GET /api/brain/history request.
    
    Args:
        query_params: Query parameters with 'session_id'.
        
    Returns:
        Response dict with conversation history.
    """
    if not BRAIN_MODULE_AVAILABLE:
        return {
            "success": False,
            "error": f"Brain module not available: {_brain_import_error}"
        }
    
    session_id = query_params.get("session_id", [""])[0]
    if not session_id:
        return {
            "success": False,
            "error": "Missing required query parameter: 'session_id'"
        }
    
    try:
        service = BrainService()
        history = service.get_history(session_id)
        
        return {
            "success": True,
            "session_id": session_id,
            "messages": history,
            "count": len(history)
        }
        
    except DatabaseError as e:
        logger.error(f"Brain database error: {e}")
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    except Exception as e:
        logger.exception(f"Unexpected error in brain history: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def handle_clear(query_params: Dict[str, list]) -> Dict[str, Any]:
    """
    Handle DELETE /api/brain/clear request.
    
    Args:
        query_params: Query parameters with 'session_id'.
        
    Returns:
        Response dict with clear result.
    """
    if not BRAIN_MODULE_AVAILABLE:
        return {
            "success": False,
            "error": f"Brain module not available: {_brain_import_error}"
        }
    
    session_id = query_params.get("session_id", [""])[0]
    if not session_id:
        return {
            "success": False,
            "error": "Missing required query parameter: 'session_id'"
        }
    
    try:
        service = BrainService()
        result = service.clear_history(session_id)
        
        return {
            "success": True,
            "session_id": session_id,
            "deleted": result.get("deleted", 0)
        }
        
    except DatabaseError as e:
        logger.error(f"Brain database error: {e}")
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    except Exception as e:
        logger.exception(f"Unexpected error in brain clear: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def handle_brain_request(
    method: str,
    path: str,
    query_params: Dict[str, list],
    body: Optional[Dict[str, Any]] = None
) -> Tuple[int, Dict[str, Any]]:
    """
    Main request handler for brain API endpoints.
    
    Routes requests to appropriate handlers.
    
    Args:
        method: HTTP method (GET, POST, DELETE).
        path: Request path (e.g., '/api/brain/consult').
        query_params: Parsed query parameters.
        body: Request body (for POST requests).
        
    Returns:
        Tuple of (status_code, response_dict).
    """
    # Verify authentication
    is_valid, auth_error = verify_auth_token(query_params)
    if not is_valid:
        return 401, {"success": False, "error": auth_error}
    
    # Route to appropriate handler
    endpoint = path.replace("/api/brain/", "").split("?")[0]
    
    if endpoint == "consult" and method == "POST":
        if body is None:
            return 400, {"success": False, "error": "Missing request body"}
        result = handle_consult(body)
        status = 200 if result.get("success") else 400
        return status, result
        
    elif endpoint == "history" and method == "GET":
        result = handle_history(query_params)
        status = 200 if result.get("success") else 400
        return status, result
        
    elif endpoint == "clear" and method == "DELETE":
        result = handle_clear(query_params)
        status = 200 if result.get("success") else 400
        return status, result
        
    else:
        return 404, {
            "success": False,
            "error": f"Unknown endpoint or method: {method} {path}"
        }


def get_brain_api_status() -> Dict[str, Any]:
    """
    Get the status of the brain API module.
    
    Returns:
        Status dict with availability info.
    """
    return {
        "available": BRAIN_MODULE_AVAILABLE,
        "auth_configured": bool(MCP_AUTH_TOKEN),
        "import_error": _brain_import_error
    }


__all__ = [
    "handle_brain_request",
    "get_brain_api_status",
    "BRAIN_MODULE_AVAILABLE",
]
