"""
API Server - Main entry point for all API endpoints.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.revenue_api import route_request as revenue_route
from api.acquisition_api import route_request as acquisition_route

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def catch_all(request: Request, path: str):
    """Route all API requests."""
    query_params = dict(request.query_params)
    body = await request.body()
    
    # Route to appropriate API handler
    if path.startswith("revenue"):
        return JSONResponse(revenue_route(path, request.method, query_params, body))
    elif path.startswith("acquisition"):
        return JSONResponse(acquisition_route(path, request.method, query_params, body))
    
    return JSONResponse({"error": "Not found"}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
