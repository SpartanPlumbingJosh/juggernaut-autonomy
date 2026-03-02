from typing import Dict, Any
from core.database import query_db
from api.auth_api import verify_token

async def protected_endpoint(token: str) -> Dict[str, Any]:
    """Example protected endpoint"""
    auth = verify_token(token)
    if not auth["success"]:
        return {"success": False, "error": "Unauthorized"}
        
    user_id = auth["user_id"]
    
    # Fetch user-specific data
    res = await query_db(
        f"SELECT data FROM user_data WHERE user_id = '{user_id}'"
    )
    
    if not res.get("rows"):
        return {"success": False, "error": "No data found"}
        
    return {"success": True, "data": res["rows"][0]["data"]}
