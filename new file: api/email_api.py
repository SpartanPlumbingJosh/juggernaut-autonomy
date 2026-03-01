"""
Email capture and newsletter API for revenue vertical.
"""
import json
from typing import Dict, Any

from core.database import query_db
from api.revenue_api import _make_response, _error_response

async def handle_email_capture(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """Capture email leads"""
    try:
        email = email_data.get('email')
        if not email:
            return _error_response(400, "Email required")
        
        await query_db(f"""
            INSERT INTO email_leads (
                id, email, source, created_at, 
                metadata, status
            ) VALUES (
                gen_random_uuid(),
                '{email.replace("'", "''")}',
                'mvp_landing',
                NOW(),
                '{{}}'::jsonb,
                'new'
            )
            ON CONFLICT (email) DO UPDATE SET
                updated_at = NOW(),
                metadata = COALESCE(email_leads.metadata, '{{}}'::jsonb) ||
                          jsonb_build_object('new_signup', NOW())
        """)
        
        return _make_response(200, {"status": "registered"})
    
    except Exception as e:
        return _error_response(500, f"Email capture failed: {str(e)}")

def route_request(path: str, method: str, 
                query_params: Dict[str, Any], 
                body: Optional[str] = None) -> Dict[str, Any]:
    """Route email API requests"""
    if method == "POST" and path == "/email":
        if body:
            return handle_email_capture(json.loads(body))
        return _error_response(400, "Email required")
    
    return _error_response(404, "Not found")

__all__ = ["route_request"]
