"""
JUGGERNAUT Dashboard API - FastAPI Server
Runs on Railway as a persistent service instead of Vercel serverless.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os

# Import all dashboard functions
from api.dashboard import (
    handle_request,
    API_VERSION
)

app = FastAPI(
    title="JUGGERNAUT Dashboard API",
    description="Executive Dashboard API for revenue, experiments, agents, and system metrics",
    version=API_VERSION
)

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
            f"/{API_VERSION}/system_alerts"
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
        except:
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
