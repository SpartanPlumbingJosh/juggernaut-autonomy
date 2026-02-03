"""
JUGGERNAUT Dashboard API - FastAPI Server
Runs on Railway as a persistent service instead of Vercel serverless.
"""

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn
import os
import logging
import json
from typing import Any, Dict, List, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Import all dashboard functions
from api.dashboard import (
    handle_request,
    API_VERSION,
    check_rate_limit,
    validate_api_key,
)

from core.ai_executor import AIExecutor

# Internal (service-to-service) dashboard endpoints
from api.internal_dashboard import router as internal_dashboard_router

# Public (browser-direct) dashboard endpoints - no auth required
from api.public_dashboard import router as public_dashboard_router

# Public pages API (opportunities, revenue, experiments) - no auth required
from api.public_pages_api import router as public_pages_router

# Approvals API (authenticated via INTERNAL_API_SECRET)
from api.approvals_api import router as approvals_api_router

# Chat sessions API (authenticated)
from api.chat_sessions import handle_chat_request as handle_chat_sessions

# Brain API (Neural Chat consultation)
try:
    from api.brain_api import handle_brain_request as handle_brain_request, handle_consult_stream, BRAIN_AVAILABLE
    BRAIN_API_AVAILABLE = BRAIN_AVAILABLE
except ImportError as e:
    logger.warning("Brain API not available: %s", e)
    BRAIN_API_AVAILABLE = False
    def handle_brain_request(*args, **kwargs):
        return {"status": 503, "body": {"success": False, "error": "brain api not available"}}
    def handle_consult_stream(*args, **kwargs):
        yield 'data: {"type": "error", "message": "brain api not available"}\n\n'

# Self-Heal API (Milestone 2)
try:
    from api.self_heal_api import (
        handle_diagnose,
        handle_repair,
        handle_auto_heal,
        handle_get_executions,
        handle_get_execution_detail
    )
    SELF_HEAL_API_AVAILABLE = True
except ImportError as e:
    logger.warning("Self-Heal API not available: %s", e)
    SELF_HEAL_API_AVAILABLE = False

# Logs API (Milestone 3)
try:
    from api.logs_api import (
        handle_crawl,
        handle_get_errors,
        handle_get_error_detail,
        handle_get_stats
    )
    LOGS_API_AVAILABLE = True
except ImportError as e:
    logger.warning("Logs API not available: %s", e)
    LOGS_API_AVAILABLE = False

# Code API (Milestone 4)
try:
    from api.code_api import (
        handle_analyze,
        handle_get_runs,
        handle_get_run_detail,
        handle_get_findings,
        handle_get_health as handle_code_health
    )
    CODE_API_AVAILABLE = True
except ImportError as e:
    logger.warning("Code API not available: %s", e)
    CODE_API_AVAILABLE = False

# Engine API (Milestone 5)
try:
    from api.engine_api import (
        handle_get_status as handle_engine_status,
        handle_start as handle_engine_start,
        handle_stop as handle_engine_stop,
        handle_get_assignments,
        handle_get_workers
    )
    ENGINE_API_AVAILABLE = True
except ImportError as e:
    logger.warning("Engine API not available: %s", e)
    ENGINE_API_AVAILABLE = False

app = FastAPI(
    title="JUGGERNAUT Dashboard API",
    description="Executive Dashboard API for revenue, experiments, agents, and system metrics",
    version=API_VERSION
)

# Internal routes (authenticated via INTERNAL_API_SECRET)
app.include_router(internal_dashboard_router)

# Public routes (no auth, CORS-enabled for browser access)
app.include_router(public_dashboard_router)

# Public pages API (opportunities, revenue, experiments)
app.include_router(public_pages_router)

# Approval queue routes (authenticated)
app.include_router(approvals_api_router)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "juggernaut-dashboard-api",
        "version": API_VERSION
    }


def _require_dashboard_auth(authorization: Optional[str]) -> str:
    token = (authorization or "").replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing API key")

    user_id = validate_api_key(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not check_rate_limit(user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return user_id


def _require_chat_auth(authorization: Optional[str]) -> str:
    token = (authorization or "").replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing API key")

    internal_secret = (os.getenv("INTERNAL_API_SECRET") or "").strip()
    if internal_secret and token == internal_secret:
        return "internal"

    user_id = validate_api_key(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not check_rate_limit(user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return user_id


@app.post("/api/chat")
@app.post("/api/chat/completions")
async def chat(
    authorization: Optional[str] = Header(default=None),
    body: Dict[str, Any] = Body(default=None),
):
    _require_chat_auth(authorization)
    payload = body or {}

    system_prompt = (
        os.getenv("JUGGERNAUT_CHAT_SYSTEM")
        or "You are JUGGERNAUT, a standalone $0-$100M autonomous indie agent. Respond concisely and directly."
    )

    messages: List[Dict[str, str]] = []
    raw_messages = payload.get("messages")
    if isinstance(raw_messages, list):
        for m in raw_messages:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role") or "").strip() or "user"
            content = str(m.get("content") or "")
            messages.append({"role": role, "content": content})

    if not messages:
        text = (
            payload.get("message")
            or payload.get("prompt")
            or payload.get("text")
            or ""
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": str(text)},
        ]
    else:
        if messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": system_prompt})

    try:
        executor = AIExecutor()
        resp = executor.chat(messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")

    return {
        "success": True,
        "reply": resp.content,
        "model": executor.model,
    }


@app.api_route("/api/chat/sessions/{path:path}", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"])
@app.api_route("/api/chat/sessions", methods=["GET", "POST", "OPTIONS"])
async def chat_sessions_route(request: Request, path: str = ""):
    """
    Route chat session requests to the chat_sessions handler.
    Handles:
    - GET/POST /api/chat/sessions
    - GET/PATCH/DELETE /api/chat/sessions/{id}
    - POST /api/chat/sessions/{id}/messages
    """
    method = request.method
    headers = dict(request.headers)
    query_params = dict(request.query_params)
    
    # Get body for POST/PATCH requests
    body = None
    if method in ["POST", "PATCH"]:
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            body = {}
    
    # Call the chat sessions handler
    result = handle_chat_sessions(
        method=method,
        path=f"sessions/{path}" if path else "sessions",
        params=query_params,
        body=body,
        headers=headers
    )
    
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=result.get("body", {}),
        headers=result.get("headers", {})
    )


@app.post("/api/brain/consult/stream")
@app.post("/api/brain/unified/consult/stream")
async def brain_consult_stream_route(request: Request):
    if not BRAIN_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Brain API not available")

    headers = dict(request.headers)
    query_params = dict(request.query_params)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        body = {}

    stream = handle_consult_stream(body, query_params, headers)
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.api_route("/api/brain/{endpoint:path}", methods=["GET", "POST", "DELETE", "OPTIONS"])
async def brain_route(request: Request, endpoint: str):
    if not BRAIN_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Brain API not available")

    method = request.method
    headers = dict(request.headers)
    query_params = dict(request.query_params)
    body = None
    if method == "POST":
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            body = {}

    result = handle_brain_request(method, endpoint, query_params, body, headers)
    return JSONResponse(status_code=result.get("status", 200), content=result.get("body", {}))


# Self-Heal API Routes
@app.post("/api/self-heal/diagnose")
async def self_heal_diagnose(request: Request):
    if not SELF_HEAL_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Heal API not available")
    
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        body = {}
    
    result = handle_diagnose(body)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.post("/api/self-heal/repair")
async def self_heal_repair(request: Request):
    if not SELF_HEAL_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Heal API not available")
    
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        body = {}
    
    result = handle_repair(body)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.post("/api/self-heal/auto-heal")
async def self_heal_auto_heal(request: Request):
    if not SELF_HEAL_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Heal API not available")
    
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        body = {}
    
    result = handle_auto_heal(body)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.get("/api/self-heal/executions")
async def self_heal_get_executions(request: Request):
    if not SELF_HEAL_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Heal API not available")
    
    query_params = dict(request.query_params)
    result = handle_get_executions(query_params)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.get("/api/self-heal/executions/{execution_id}")
async def self_heal_get_execution_detail(execution_id: str):
    if not SELF_HEAL_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Heal API not available")
    
    result = handle_get_execution_detail(execution_id)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


# Logs API Routes (Milestone 3)
@app.post("/api/logs/crawl")
async def logs_crawl(request: Request):
    if not LOGS_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Logs API not available")
    
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        body = {}
    
    result = handle_crawl(body)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.get("/api/logs/errors")
async def logs_get_errors(request: Request):
    if not LOGS_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Logs API not available")
    
    query_params = dict(request.query_params)
    result = handle_get_errors(query_params)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.get("/api/logs/errors/{fingerprint}")
async def logs_get_error_detail(fingerprint: str):
    if not LOGS_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Logs API not available")
    
    result = handle_get_error_detail(fingerprint)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.get("/api/logs/stats")
async def logs_get_stats():
    if not LOGS_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Logs API not available")
    
    result = handle_get_stats()
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


# Code API Routes (Milestone 4)
@app.post("/api/code/analyze")
async def code_analyze(request: Request):
    if not CODE_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Code API not available")
    
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        body = {}
    
    result = handle_analyze(body)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.get("/api/code/runs")
async def code_get_runs(request: Request):
    if not CODE_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Code API not available")
    
    query_params = dict(request.query_params)
    result = handle_get_runs(query_params)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.get("/api/code/runs/{run_id}")
async def code_get_run_detail(run_id: str):
    if not CODE_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Code API not available")
    
    result = handle_get_run_detail(run_id)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.get("/api/code/findings")
async def code_get_findings(request: Request):
    if not CODE_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Code API not available")
    
    query_params = dict(request.query_params)
    result = handle_get_findings(query_params)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.get("/api/code/health")
async def code_get_health():
    if not CODE_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Code API not available")
    
    result = handle_code_health()
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


# Engine API Routes (Milestone 5)
@app.get("/api/engine/status")
async def engine_get_status():
    if not ENGINE_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Engine API not available")
    
    result = handle_engine_status()
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.post("/api/engine/start")
async def engine_start():
    if not ENGINE_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Engine API not available")
    
    result = handle_engine_start()
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.post("/api/engine/stop")
async def engine_stop():
    if not ENGINE_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Engine API not available")
    
    result = handle_engine_stop()
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.get("/api/engine/assignments")
async def engine_get_assignments(request: Request):
    if not ENGINE_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Engine API not available")
    
    query_params = dict(request.query_params)
    result = handle_get_assignments(query_params)
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.get("/api/engine/workers")
async def engine_get_workers():
    if not ENGINE_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="Engine API not available")
    
    result = handle_get_workers()
    return JSONResponse(
        status_code=result.get("statusCode", 200),
        content=json.loads(result.get("body", "{}"))
    )


@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "service": "juggernaut-dashboard-api",
        "version": API_VERSION,
        "endpoints": [
            f"/{API_VERSION}/overview",
            f"/{API_VERSION}/revenue_summary",
            f"/{API_VERSION}/revenue_by_source",
            f"/{API_VERSION}/experiment_status",
            f"/{API_VERSION}/experiment_details/{{id}}",
            f"/{API_VERSION}/agent_health",
            f"/{API_VERSION}/goal_progress",
            f"/{API_VERSION}/profit_loss",
            f"/{API_VERSION}/pending_approvals",
            f"/{API_VERSION}/system_alerts",
            # Public endpoints (no auth)
            "/public/dashboard/tasks",
            "/public/dashboard/workers",
            "/public/dashboard/logs",
            "/public/dashboard/stats",
            "/public/dashboard/tree",
            "/public/dashboard/dlq",
            "/public/dashboard/cost",
            "/public/dashboard/revenue/summary",
            "/public/dashboard/alerts",
            # Public pages API (Spartan HQ)
            "/public/pages/opportunities",
            "/public/pages/opportunities/stats",
            "/public/pages/opportunities/{id}",
            "/public/pages/revenue",
            "/public/pages/revenue/by-source",
            "/public/pages/experiments",
            "/public/pages/experiments/stats",
            "/public/pages/experiments/{id}",
            # Approvals API (authenticated)
            "/api/approvals",
            # Chat sessions API (authenticated)
            "/api/chat/sessions",
            "/api/chat/sessions/{id}",
            "/api/chat/sessions/{id}/messages",
            # Self-Heal API (Milestone 2)
            "/api/self-heal/diagnose",
            "/api/self-heal/repair",
            "/api/self-heal/auto-heal",
            "/api/self-heal/executions",
            "/api/self-heal/executions/{id}",
            # Logs API (Milestone 3)
            "/api/logs/crawl",
            "/api/logs/errors",
            "/api/logs/errors/{fingerprint}",
            "/api/logs/stats",
            # Code API (Milestone 4)
            "/api/code/analyze",
            "/api/code/runs",
            "/api/code/runs/{id}",
            "/api/code/findings",
            "/api/code/health",
            # Engine API (Milestone 5)
            "/api/engine/status",
            "/api/engine/start",
            "/api/engine/stop",
            "/api/engine/assignments",
            "/api/engine/workers"
        ]
    }

@app.api_route("/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def proxy_to_dashboard(request: Request, path: str):
    """
    Proxy all requests to the dashboard handler.
    This maintains compatibility with the existing dashboard.py code.
    """
    # Extract request data
    method = request.method
    headers = dict(request.headers)
    query_params = dict(request.query_params)
    
    # Get body for POST requests
    body = None
    if method == "POST":
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse JSON body: {e}")
            body = {}
    
    # Call the dashboard handler
    result = handle_request(
        method=method,
        path=f"/{path}",
        headers=headers,
        query_params=query_params,
        body=body
    )
    
    # Return response
    status_code = result.get("status", 200)
    response_body = result.get("body", {})
    
    return JSONResponse(
        status_code=status_code,
        content=response_body
    )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "dashboard_api_main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
