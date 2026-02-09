from __future__ import annotations
from typing import Dict, List, Optional, Callable
import json
from datetime import datetime, timedelta

class MarketingFunnel:
    """Autonomous marketing and sales funnel system."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
    
    def generate_content(self, topic: str, audience: str) -> Dict[str, Any]:
        """Generate marketing content for a specific topic and audience."""
        # TODO: Integrate with content generation API/LLM
        return {
            "title": f"Guide to {topic} for {audience}",
            "content": f"Comprehensive guide about {topic} tailored for {audience}...",
            "cta": f"Learn more about {topic}",
            "metadata": {
                "topic": topic,
                "audience": audience,
                "generated_at": datetime.now().isoformat()
            }
        }
    
    def score_lead(self, lead_id: str) -> float:
        """Score lead based on engagement and profile data."""
        try:
            res = self.execute_sql(f"""
                SELECT 
                    COUNT(*) as engagement_count,
                    SUM(CASE WHEN event_type = 'page_view' THEN 1 ELSE 0 END) as page_views,
                    SUM(CASE WHEN event_type = 'content_download' THEN 1 ELSE 0 END) as downloads,
                    SUM(CASE WHEN event_type = 'demo_request' THEN 1 ELSE 0 END) as demo_requests
                FROM lead_activity
                WHERE lead_id = '{lead_id}'
            """)
            data = res.get("rows", [{}])[0]
            
            # Simple scoring algorithm
            score = (
                (data.get("page_views", 0) * 1) +
                (data.get("downloads", 0) * 5) + 
                (data.get("demo_requests", 0) * 10)
            )
            return min(100.0, score)  # Cap at 100
            
        except Exception as e:
            self.log_action("lead_scoring.error", f"Failed to score lead: {str(e)}", level="error")
            return 0.0
    
    def trigger_email_sequence(self, lead_id: str, sequence_name: str) -> bool:
        """Trigger an email sequence for a lead."""
        try:
            # Check if sequence already active
            res = self.execute_sql(f"""
                SELECT id 
                FROM email_sequences 
                WHERE lead_id = '{lead_id}' 
                AND sequence_name = '{sequence_name}'
                AND status = 'active'
                LIMIT 1
            """)
            if res.get("rows"):
                return False
                
            # Start new sequence
            self.execute_sql(f"""
                INSERT INTO email_sequences (
                    id, lead_id, sequence_name, status, 
                    current_step, started_at, updated_at
                ) VALUES (
                    gen_random_uuid(), '{lead_id}', '{sequence_name}', 
                    'active', 0, NOW(), NOW()
                )
            """)
            self.log_action("email_sequence.started", f"Started {sequence_name} for lead {lead_id}")
            return True
            
        except Exception as e:
            self.log_action("email_sequence.error", f"Failed to start sequence: {str(e)}", level="error")
            return False
    
    def onboard_customer(self, lead_id: str) -> Dict[str, Any]:
        """Automated self-service onboarding flow."""
        try:
            # Create customer record
            res = self.execute_sql(f"""
                INSERT INTO customers (
                    id, lead_id, onboarding_status, 
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), '{lead_id}', 'started', 
                    NOW(), NOW()
                )
                RETURNING id
            """)
            customer_id = res.get("rows", [{}])[0].get("id")
            
            # Trigger welcome sequence
            self.trigger_email_sequence(lead_id, "welcome_series")
            
            # Log revenue event
            self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, 
                    source, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(), 'revenue', 0, 
                    'onboarding', NOW(), NOW()
                )
            """)
            
            return {
                "success": True,
                "customer_id": customer_id,
                "next_steps": [
                    "welcome_email_sent",
                    "account_activated"
                ]
            }
            
        except Exception as e:
            self.log_action("onboarding.error", f"Failed to onboard customer: {str(e)}", level="error")
            return {"success": False, "error": str(e)}
