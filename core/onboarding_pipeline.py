from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

class OnboardingPipeline:
    """Customer onboarding pipeline to ensure successful adoption."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def create_onboarding_plan(self, customer_id: str) -> bool:
        """Create personalized onboarding plan for new customer."""
        try:
            self.execute_sql(f"""
                INSERT INTO onboarding_plans (customer_id, steps, status, created_at)
                VALUES (
                    '{customer_id}',
                    '[{{"type":"welcome_email","template":"welcome"}}]'::jsonb,
                    'pending',
                    NOW()
                )
            """)
            return True
        except Exception as e:
            self.log_action("onboarding.error", f"Failed to create plan: {str(e)}", level="error")
            return False
            
    def track_onboarding_progress(self, customer_id: str) -> Dict[str, Any]:
        """Track and report onboarding progress."""
        try:
            res = self.execute_sql(f"""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_steps,
                    COUNT(*) as total_steps,
                    MIN(created_at) as started_at
                FROM onboarding_activity
                WHERE customer_id = '{customer_id}'
            """)
            row = res.get("rows", [{}])[0]
            return {
                "completed": row.get("completed_steps", 0),
                "total": row.get("total_steps", 0),
                "started_at": row.get("started_at")
            }
        except Exception as e:
            self.log_action("onboarding.error", f"Failed to track progress: {str(e)}", level="error")
            return {"error": str(e)}
            
    def run_daily_onboarding(self) -> Dict[str, Any]:
        """Run daily onboarding pipeline."""
        try:
            res = self.execute_sql("""
                SELECT id FROM customers
                WHERE created_at >= NOW() - INTERVAL '30 days'
                  AND onboarding_status = 'pending'
                LIMIT 100
            """)
            customers = res.get("rows", [])
            onboarded = 0
            
            for customer in customers:
                if self.create_onboarding_plan(customer["id"]):
                    onboarded += 1
                    
            self.log_action("onboarding.run", f"Onboarded {onboarded} customers", level="info")
            return {"success": True, "onboarded": onboarded}
        except Exception as e:
            self.log_action("onboarding.error", f"Failed to run onboarding: {str(e)}", level="error")
            return {"success": False, "error": str(e)}
