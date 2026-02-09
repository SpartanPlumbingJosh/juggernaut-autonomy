"""
Marketing Funnel Automation - Handles lead generation, onboarding and conversions.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional
from enum import Enum

class LeadStage(Enum):
    NEW = "new"
    ENGAGED = "engaged"
    ONBOARDING = "onboarding"
    TRIAL = "trial"
    PAYING = "paying"
    CHURNED = "churned"

class MarketingBot:
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def generate_leads(self, source: str, count: int = 10) -> Dict[str, Any]:
        """Generate synthetic leads for testing"""
        try:
            self.execute_sql(
                f"""
                INSERT INTO leads (id, email, source, status, created_at)
                SELECT 
                    gen_random_uuid(),
                    concat('test_', md5(random()::text), '@example.com'),
                    '{source}',
                    '{LeadStage.NEW.value}', 
                    NOW()
                FROM generate_series(1, {count})
                """
            )
            return {"success": True, "count": count}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def start_onboarding(self, lead_id: str) -> Dict[str, Any]:
        """Begin automated onboarding flow"""
        try:
            self.execute_sql(
                f"""
                UPDATE leads 
                SET status = '{LeadStage.ONBOARDING.value}',
                    onboard_started_at = NOW()
                WHERE id = '{lead_id}'
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def complete_onboarding(self, lead_id: str) -> Dict[str, Any]:
        """Mark onboarding as complete"""
        try:
            self.execute_sql(
                f"""
                UPDATE leads 
                SET status = '{LeadStage.TRIAL.value}',
                    onboard_completed_at = NOW()
                WHERE id = '{lead_id}'
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def trigger_payment_flow(self, lead_id: str) -> Dict[str, Any]:
        """Start payment flow for a trial user"""
        try:
            self.execute_sql(
                f"""
                UPDATE leads 
                SET status = '{LeadStage.PAYING.value}',
                    payment_initiated_at = NOW()
                WHERE id = '{lead_id}'
                """
            )
            # TODO: Integrate with payment provider API
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

class FunnelAnalytics:
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
        
    def get_conversion_rates(self) -> Dict[str, float]:
        """Calculate funnel conversion rates"""
        result = self.execute_sql("""
            WITH funnel_counts AS (
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'new') as new_leads,
                    COUNT(*) FILTER (WHERE status = 'onboarding') as onboarding,
                    COUNT(*) FILTER (WHERE status = 'trial') as trial,
                    COUNT(*) FILTER (WHERE status = 'paying') as paying
                FROM leads
                WHERE created_at > NOW() - INTERVAL '30 days'
            )
            SELECT 
                new_leads,
                onboarding,
                trial,
                paying,
                ROUND(100.0 * paying / NULLIF(new_leads, 0), 2) as overall_conversion,
                ROUND(100.0 * paying / NULLIF(trial, 0), 2) as paying_conversion
            FROM funnel_counts
        """)
        return result.get("rows", [{}])[0]
