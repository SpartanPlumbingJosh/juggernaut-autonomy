"""
JUGGERNAUT Dashboard API - FastAPI Server
Runs on Railway as a persistent service instead of Vercel serverless.
"""

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

# Approvals API (authenticated via INTERNAL_API_SECRET)
from api.approvals_api import router as approvals_api_router

app = FastAPI(
    title="JUGGERNAUT Dashboard API",
    description="Executive Dashboard API for revenue, experiments, agents, and system metrics",
    version=API_VERSION
)

# Internal routes (authenticated via INTERNAL_API_SECRET)
app.include_router(internal_dashboard_router)

# Public routes (no auth, CORS-enabled for browser access)
app.include_router(public_dashboard_router)

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
            "/public/dashboard/alerts"
            ,
            # Approvals API (authenticated)
            "/api/approvals"
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
