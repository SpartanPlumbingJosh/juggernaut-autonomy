from datetime import datetime
from typing import Dict, List, Optional
import json

class LeadScorer:
    """Lead scoring engine to prioritize prospects."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def calculate_engagement_score(self, prospect_id: str) -> float:
        """Calculate engagement score based on prospect activity."""
        try:
            res = self.execute_sql(f"""
                SELECT 
                    COUNT(*) FILTER (WHERE event_type = 'email_open') as email_opens,
                    COUNT(*) FILTER (WHERE event_type = 'website_visit') as website_visits,
                    COUNT(*) FILTER (WHERE event_type = 'content_download') as content_downloads,
                    COUNT(*) FILTER (WHERE event_type = 'meeting_booked') as meetings_booked
                FROM prospect_activity
                WHERE prospect_id = '{prospect_id}'
            """)
            row = res.get("rows", [{}])[0]
            
            # Weighted scoring
            score = (
                (row.get("email_opens", 0) * 0.1) +
                (row.get("website_visits", 0) * 0.3) +
                (row.get("content_downloads", 0) * 0.4) +
                (row.get("meetings_booked", 0) * 0.2)
            ) * 100
            
            return min(score, 100)
        except Exception as e:
            self.log_action("scoring.error", f"Failed to calculate score: {str(e)}", level="error")
            return 0.0
            
    def update_prospect_scores(self) -> Dict[str, Any]:
        """Update engagement scores for all prospects."""
        try:
            res = self.execute_sql("""
                SELECT id FROM prospects
                WHERE last_score_updated_at < NOW() - INTERVAL '7 days'
                LIMIT 1000
            """)
            prospects = res.get("rows", [])
            updated = 0
            
            for prospect in prospects:
                score = self.calculate_engagement_score(prospect["id"])
                self.execute_sql(f"""
                    UPDATE prospects
                    SET engagement_score = {score},
                        last_score_updated_at = NOW()
                    WHERE id = '{prospect["id"]}'
                """)
                updated += 1
                
            self.log_action("scoring.run", f"Updated {updated} prospect scores", level="info")
            return {"success": True, "updated": updated}
        except Exception as e:
            self.log_action("scoring.error", f"Failed to update scores: {str(e)}", level="error")
            return {"success": False, "error": str(e)}
