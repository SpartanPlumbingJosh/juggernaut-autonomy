from __future__ import annotations
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
import json

class AcquisitionFunnelManager:
    """Manage automated customer acquisition funnel."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def create_landing_page(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new landing page with tracking."""
        try:
            page_id = page_data.get("id") or str(uuid.uuid4())
            page_json = json.dumps(page_data).replace("'", "''")
            
            self.execute_sql(f"""
                INSERT INTO acquisition_pages (
                    id, page_data, status, created_at, updated_at
                ) VALUES (
                    '{page_id}',
                    '{page_json}'::jsonb,
                    'active',
                    NOW(),
                    NOW()
                )
            """)
            
            return {"success": True, "page_id": page_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def track_conversion(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Track a conversion event."""
        try:
            event_json = json.dumps(event_data).replace("'", "''")
            
            self.execute_sql(f"""
                INSERT INTO acquisition_events (
                    id, event_type, event_data, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'conversion',
                    '{event_json}'::jsonb,
                    NOW()
                )
            """)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def get_funnel_metrics(self, period_days: int = 30) -> Dict[str, Any]:
        """Get funnel performance metrics."""
        try:
            res = self.execute_sql(f"""
                WITH funnel_data AS (
                    SELECT
                        COUNT(*) FILTER (WHERE event_type = 'landing_page_view') as views,
                        COUNT(*) FILTER (WHERE event_type = 'signup') as signups,
                        COUNT(*) FILTER (WHERE event_type = 'conversion') as conversions
                    FROM acquisition_events
                    WHERE created_at >= NOW() - INTERVAL '{period_days} days'
                )
                SELECT
                    views,
                    signups,
                    conversions,
                    ROUND(100.0 * signups / NULLIF(views, 0), 2) as signup_rate,
                    ROUND(100.0 * conversions / NULLIF(signups, 0), 2) as conversion_rate
                FROM funnel_data
            """)
            
            return {"success": True, "metrics": res.get("rows", [{}])[0]}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def send_outreach_sequence(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Initiate automated outreach sequence."""
        try:
            sequence_json = json.dumps(contact_data).replace("'", "''")
            
            self.execute_sql(f"""
                INSERT INTO acquisition_outreach (
                    id, contact_data, status, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{sequence_json}'::jsonb,
                    'pending',
                    NOW(),
                    NOW()
                )
            """)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
