from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

class OutboundOutreach:
    """Automated outbound outreach pipeline to acquire customers."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def find_prospects(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Find high-potential prospects based on ideal customer profile."""
        try:
            res = self.execute_sql(f"""
                SELECT id, name, email, company, title, website, 
                       created_at, last_contacted_at, engagement_score
                FROM prospects
                WHERE engagement_score >= 70
                  AND (last_contacted_at IS NULL OR last_contacted_at < NOW() - INTERVAL '30 days')
                ORDER BY engagement_score DESC, created_at ASC
                LIMIT {limit}
            """)
            return res.get("rows", [])
        except Exception as e:
            self.log_action("outbound.error", f"Failed to find prospects: {str(e)}", level="error")
            return []
            
    def create_outreach_sequence(self, prospect_id: str) -> bool:
        """Create personalized outreach sequence for a prospect."""
        try:
            self.execute_sql(f"""
                INSERT INTO outreach_sequences (prospect_id, steps, status, created_at)
                VALUES (
                    '{prospect_id}',
                    '[{{"type":"email","template":"initial_outreach"}}]'::jsonb,
                    'pending',
                    NOW()
                )
            """)
            return True
        except Exception as e:
            self.log_action("outbound.error", f"Failed to create sequence: {str(e)}", level="error")
            return False
            
    def run_daily_outreach(self) -> Dict[str, Any]:
        """Run daily outreach pipeline."""
        prospects = self.find_prospects()
        created = 0
        
        for prospect in prospects:
            if self.create_outreach_sequence(prospect["id"]):
                created += 1
                
        self.log_action("outbound.run", f"Created {created} outreach sequences", level="info")
        return {"success": True, "created": created}
