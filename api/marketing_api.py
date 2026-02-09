"""
Marketing Automation API - Endpoints for autonomous marketing funnel.
"""

from typing import Dict, Any, Optional
import json
from datetime import datetime
from core.marketing_funnel import MarketingFunnel
from core.database import query_db

def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Standard API response format."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }

async def handle_lead_scoring(lead_id: str) -> Dict[str, Any]:
    """Get lead score and recommendations."""
    funnel = MarketingFunnel(query_db, lambda *args, **kwargs: None)
    score = funnel.score_lead(lead_id)
    
    recommendations = []
    if score < 30:
        recommendations.append("nurture_content")
    elif score < 70:
        recommendations.append("product_demo")
    else:
        recommendations.append("sales_contact")
    
    return _make_response(200, {
        "lead_id": lead_id,
        "score": score,
        "recommendations": recommendations,
        "next_best_action": recommendations[0]
    })

async def handle_onboarding_start(lead_id: str) -> Dict[str, Any]:
    """Start automated onboarding process."""
    funnel = MarketingFunnel(query_db, lambda *args, **kwargs: None)
    result = funnel.onboard_customer(lead_id)
    return _make_response(200 if result["success"] else 400, result)

def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route marketing API requests."""
    
    if method == "OPTIONS":
        return _make_response(200, {})
    
    parts = [p for p in path.split("/") if p]
    
    # POST /marketing/leads/{id}/score
    if len(parts) == 4 and parts[0] == "marketing" and parts[1] == "leads" and parts[3] == "score" and method == "GET":
        return handle_lead_scoring(parts[2])
    
    # POST /marketing/leads/{id}/onboard
    if len(parts) == 4 and parts[0] == "marketing" and parts[1] == "leads" and parts[3] == "onboard" and method == "POST":
        return handle_onboarding_start(parts[2])
    
    return _make_response(404, {"error": "Not found"})

__all__ = ["route_request"]
