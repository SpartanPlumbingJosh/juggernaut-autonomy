"""
Marketing Automation Module - Handles all marketing campaigns and lead management.

Includes:
- Landing page generation
- Email sequences
- SEO content
- Paid acquisition
- Lead scoring
- Nurture campaigns
"""

from typing import Dict, List, Optional
import uuid
from datetime import datetime, timedelta
import json

class MarketingAutomation:
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action

    def create_landing_page(self, template_id: str, variants: int = 1) -> Dict[str, str]:
        """Generate personalized landing pages."""
        page_ids = [str(uuid.uuid4()) for _ in range(variants)]
        created_at = datetime.now().isoformat()
        
        try:
            self.execute_sql(
                f"""
                INSERT INTO marketing_pages (id, template_id, created_at, updated_at)
                VALUES {", ".join(f"('{pid}', '{template_id}', '{created_at}', '{created_at}')" for pid in page_ids)}
                """
            )
            return {"success": True, "page_ids": page_ids}
        except Exception as e:
            return {"error": str(e)}

    def create_email_sequence(self, sequence_name: str, emails_conf: List[Dict]) -> Dict:
        """Set up trigger-based email sequence."""
        sequence_id = str(uuid.uuid4())
        emails_json = json.dumps(emails_conf)
        
        try: 
            self.execute_sql(
                f"""
                INSERT INTO email_sequences 
                (id, name, email_config, triggers, created_at, updated_at)
                VALUES (
                    '{sequence_id}',
                    '{sequence_name.replace("'", "''")}',
                    '{emails_json.replace("'", "''")}'::jsonb,
                    '[]'::jsonb,
                    NOW(),
                    NOW()
                )
                """
            )
            return {"success": True, "sequence_id": sequence_id}
        except Exception as e:
            return {"error": str(e)}

    def score_lead(self, lead_data: Dict) -> Dict:
        """Calculate lead score based on engagement and profile."""
        score = 0
        # Engagement weighting
        score += min(lead_data.get('page_views', 0), 10) * 2
        score += min(lead_data.get('email_opens', 0), 5) * 3
        score += lead_data.get('conversions', 0) * 10
        
        # Profile weighting
        if lead_data.get('job_title'):
            if 'executive' in lead_data['job_title'].lower():
                score += 15
            elif 'manager' in lead_data['job_title'].lower():
                score += 10
                
        if lead_data.get('company_size') and lead_data['company_size'] > 100:
            score += lead_data['company_size'] / 100
            
        return {
            "lead_id": lead_data.get('id'),
            "score": min(100, max(0, score)),
            "tier": "hot" if score > 75 else "warm" if score > 50 else "cold"
        }

    def trigger_nurture_campaign(self, lead_id: str, campaign_type: str = "default") -> Dict:
        """Start nurture sequence for a lead."""
        try:
            sequence_id = self._get_campaign_sequence(campaign_type)
            self.execute_sql(
                f"""
                INSERT INTO lead_campaigns
                (id, lead_id, sequence_id, status, started_at)
                VALUES (
                    gen_random_uuid(),
                    '{lead_id}',
                    '{sequence_id}',
                    'started',
                    NOW()
                )
                """
            )
            return {"success": True, "campaign_started": True}
        except Exception as e:
            return {"error": str(e)}

    def _get_campaign_sequence(self, campaign_type: str) -> str:
        """Get sequence ID for campaign type."""
        res = self.execute_sql(
            f"""
            SELECT id FROM email_sequences
            WHERE name ILIKE '%{campaign_type}%'
            LIMIT 1
            """
        )
        if res.get('rows'):
            return res['rows'][0]['id']
        raise ValueError(f"No sequence found for campaign type: {campaign_type}")
