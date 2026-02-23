"""
Account Automation API - Handles automated account creation and management
across supported platforms while ensuring ToS compliance.
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from core.platforms import PlatformClient
from core.database import query_db
from core.compliance import check_tos_compliance

async def create_account(platform: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new account on specified platform with compliance checks."""
    try:
        # Validate platform and params
        if not platform or not params:
            return {"error": "Invalid platform or parameters"}
            
        # Check platform ToS compliance
        compliance = await check_tos_compliance(platform, "account_creation")
        if not compliance.get("allowed"):
            return {"error": f"Account creation not allowed: {compliance.get('reason')}"}
        
        # Initialize platform client
        client = PlatformClient(platform)
        
        # Create account
        account = await client.create_account(params)
        
        # Store account details
        await query_db(
            f"""
            INSERT INTO platform_accounts (
                id, platform, account_id, 
                account_details, created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                '{platform}',
                '{account.get('id')}',
                '{json.dumps(account)}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )
        
        return {"success": True, "account": account}
        
    except Exception as e:
        return {"error": f"Account creation failed: {str(e)}"}

async def route_account_request(path: str, method: str, body: Optional[str] = None) -> Dict[str, Any]:
    """Route account automation API requests."""
    if method != "POST":
        return {"error": "Method not allowed"}
    
    try:
        data = json.loads(body or "{}")
        platform = data.get("platform")
        params = data.get("params", {})
        
        if path == "/account/create":
            return await create_account(platform, params)
            
        return {"error": "Invalid endpoint"}
        
    except Exception as e:
        return {"error": f"Request processing failed: {str(e)}"}

__all__ = ["route_account_request"]
