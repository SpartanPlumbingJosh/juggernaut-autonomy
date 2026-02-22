"""
Analytics Tracking - Track customer acquisition metrics and events.
"""

import json
from datetime import datetime
from typing import Any, Dict

from core.database import query_db

async def track_event(event_name: str, properties: Dict[str, Any] = {}):
    """Track an analytics event."""
    try:
        event_data = {
            "event_name": event_name,
            "properties": json.dumps(properties),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Insert event into database
        await query_db("""
            INSERT INTO analytics_events (event_name, properties, timestamp)
            VALUES (:event_name, :properties, :timestamp)
        """, event_data)
        
    except Exception as e:
        print(f"Error tracking event: {str(e)}")

async def get_acquisition_metrics():
    """Get key customer acquisition metrics."""
    try:
        # Get conversion rates
        conversion_rate_result = await query_db("""
            SELECT 
                COUNT(DISTINCT CASE WHEN event_name = 'conversion' THEN user_id END) * 1.0 /
                COUNT(DISTINCT CASE WHEN event_name = 'visit' THEN user_id END) as conversion_rate
            FROM analytics_events
        """)
        
        # Get acquisition costs
        cost_result = await query_db("""
            SELECT 
                SUM(CAST(properties->>'amount' AS NUMERIC)) as total_cost,
                COUNT(DISTINCT user_id) as acquired_users
            FROM analytics_events
            WHERE event_name = 'ad_click'
        """)
        
        return {
            "conversion_rate": conversion_rate_result.get("rows", [{}])[0].get("conversion_rate", 0),
            "cost_per_acquisition": cost_result.get("rows", [{}])[0].get("total_cost", 0) / 
                                   max(1, cost_result.get("rows", [{}])[0].get("acquired_users", 1))
        }
        
    except Exception as e:
        print(f"Error getting acquisition metrics: {str(e)}")
        return {}

__all__ = ["track_event", "get_acquisition_metrics"]
