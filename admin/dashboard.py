from typing import Dict, Any
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import APIKeyHeader
from starlette.requests import Request
from starlette.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from ..auth import get_current_user
import os

templates = Jinja2Templates(directory="templates")
api_key_header = APIKeyHeader(name="Authorization")

app = FastAPI()

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    token: str = Depends(api_key_header)
):
    """Admin dashboard UI"""
    user = await get_current_user(token)
    if not is_admin(user.email):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    context = {
        "request": request,
        "period": "30d",
        "chart_data": await get_chart_data("30d"),
    }
    return templates.TemplateResponse("admin/dashboard.html", context)

async def get_chart_data(period: str) -> Dict[str, Any]:
    """Get data for admin charts"""
    # Implement based on your metrics needs
    return {}
