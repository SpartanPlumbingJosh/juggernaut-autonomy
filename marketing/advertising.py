"""
Programmatic Advertising API - Automates ad campaigns across platforms.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.database import query_db
from core.platforms import FacebookAds, GoogleAds

async def create_ad_campaign(
    name: str,
    budget: float,
    platforms: List[str],
    target_audience: Dict[str, Any],
    creative: Dict[str, Any],
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """Create new ad campaign across platforms."""
    try:
        # Initialize platform clients
        clients = []
        if "facebook" in platforms:
            clients.append(FacebookAds())
        if "google" in platforms:
            clients.append(GoogleAds())
            
        # Create campaigns
        campaign_ids = []
        for client in clients:
            campaign_id = await client.create_campaign(
                name=name,
                budget=budget,
                target_audience=target_audience,
                creative=creative,
                start_date=start_date,
                end_date=end_date
            )
            campaign_ids.append(campaign_id)
            
        # Save to database
        sql = """
        INSERT INTO ad_campaigns (
            name, budget, platforms, target_audience, creative, 
            start_date, end_date, status, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        result = await query_db(sql, [
            name,
            budget,
            json.dumps(platforms),
            json.dumps(target_audience),
            json.dumps(creative),
            start_date,
            end_date,
            "active",
            datetime.utcnow()
        ])
        
        return {
            "id": result["rows"][0]["id"],
            "platform_campaign_ids": campaign_ids,
            "status": "active"
        }
        
    except Exception as e:
        raise Exception(f"Failed to create ad campaign: {str(e)}")


async def get_campaign_performance(campaign_id: int) -> Dict[str, Any]:
    """Get performance metrics for a campaign."""
    try:
        # Get campaign details
        sql = "SELECT * FROM ad_campaigns WHERE id = %s"
        result = await query_db(sql, [campaign_id])
        campaign = result["rows"][0]
        
        # Initialize platform clients
        clients = []
        platforms = json.loads(campaign["platforms"])
        if "facebook" in platforms:
            clients.append(FacebookAds())
        if "google" in platforms:
            clients.append(GoogleAds())
            
        # Get performance data
        performance = {}
        for client in clients:
            platform_perf = await client.get_campaign_performance(
                campaign["platform_campaign_ids"][platforms.index(client.platform)]
            )
            performance[client.platform] = platform_perf
            
        return {
            "id": campaign_id,
            "performance": performance,
            "status": campaign["status"]
        }
        
    except Exception as e:
        raise Exception(f"Failed to get campaign performance: {str(e)}")


async def update_campaign_budget(campaign_id: int, new_budget: float) -> Dict[str, Any]:
    """Update campaign budget across platforms."""
    try:
        # Get campaign details
        sql = "SELECT * FROM ad_campaigns WHERE id = %s"
        result = await query_db(sql, [campaign_id])
        campaign = result["rows"][0]
        
        # Initialize platform clients
        clients = []
        platforms = json.loads(campaign["platforms"])
        if "facebook" in platforms:
            clients.append(FacebookAds())
        if "google" in platforms:
            clients.append(GoogleAds())
            
        # Update budgets
        for client in clients:
            await client.update_campaign_budget(
                campaign["platform_campaign_ids"][platforms.index(client.platform)],
                new_budget
            )
            
        # Update database
        update_sql = "UPDATE ad_campaigns SET budget = %s WHERE id = %s"
        await query_db(update_sql, [new_budget, campaign_id])
        
        return {
            "id": campaign_id,
            "new_budget": new_budget,
            "status": campaign["status"]
        }
        
    except Exception as e:
        raise Exception(f"Failed to update campaign budget: {str(e)}")


__all__ = ["create_ad_campaign", "get_campaign_performance", "update_campaign_budget"]
