from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import random

from core.database import query_db

class MarketingAutomation:
    """Automated marketing and sales funnel management."""
    
    def __init__(self):
        self.revenue_target = 16_000_000  # $16M annual target
        self.campaigns = []
        
    async def generate_landing_page(self, campaign_id: str) -> Dict[str, Any]:
        """Generate optimized landing page for a campaign."""
        # Get campaign details
        res = await query_db(f"SELECT * FROM marketing_campaigns WHERE id = '{campaign_id}'")
        campaign = res.get("rows", [{}])[0]
        
        # Generate SEO-optimized content
        page = {
            "title": f"{campaign.get('name')} - {campaign.get('tagline')}",
            "meta_description": campaign.get("description")[:160],
            "header": campaign.get("name"),
            "subheader": campaign.get("tagline"),
            "cta_text": campaign.get("cta_text", "Get Started"),
            "features": json.loads(campaign.get("features", "[]")),
            "testimonials": json.loads(campaign.get("testimonials", "[]")),
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Track page generation
        await query_db(f"""
            INSERT INTO landing_pages 
            (id, campaign_id, content, created_at)
            VALUES (gen_random_uuid(), '{campaign_id}', '{json.dumps(page)}', NOW())
        """)
        
        return page
        
    async def create_email_sequence(self, campaign_id: str) -> Dict[str, Any]:
        """Create automated email sequence for a campaign."""
        emails = [
            {
                "subject": "Welcome to {campaign_name}",
                "body": "Thanks for signing up! Here's what you can expect...",
                "delay_days": 0
            },
            {
                "subject": "Getting Started with {campaign_name}",
                "body": "Here's how to make the most of your new account...",
                "delay_days": 2
            },
            {
                "subject": "Special Offer Just for You",
                "body": "As a valued customer, here's an exclusive offer...",
                "delay_days": 5
            }
        ]
        
        await query_db(f"""
            INSERT INTO email_sequences 
            (id, campaign_id, emails, created_at)
            VALUES (gen_random_uuid(), '{campaign_id}', '{json.dumps(emails)}', NOW())
        """)
        
        return {"success": True, "emails": emails}
        
    async def track_conversion(self, event_type: str, campaign_id: str, user_id: str) -> Dict[str, Any]:
        """Track conversion events for CAC and ROI calculations."""
        event = {
            "event_type": event_type,
            "campaign_id": campaign_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await query_db(f"""
            INSERT INTO marketing_events 
            (id, event_type, campaign_id, user_id, timestamp)
            VALUES (gen_random_uuid(), '{event_type}', '{campaign_id}', '{user_id}', NOW())
        """)
        
        return {"success": True, "event": event}
        
    async def calculate_cac(self, campaign_id: str) -> Dict[str, Any]:
        """Calculate Customer Acquisition Cost for a campaign."""
        res = await query_db(f"""
            SELECT 
                SUM(CASE WHEN event_type = 'ad_spend' THEN amount_cents ELSE 0 END) as total_spend,
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'conversion') as conversions
            FROM marketing_events
            WHERE campaign_id = '{campaign_id}'
        """)
        
        row = res.get("rows", [{}])[0]
        total_spend = float(row.get("total_spend", 0)) / 100
        conversions = int(row.get("conversions", 0))
        cac = total_spend / conversions if conversions > 0 else 0
        
        return {
            "success": True,
            "cac": cac,
            "total_spend": total_spend,
            "conversions": conversions
        }
        
    async def generate_referral_code(self, user_id: str) -> Dict[str, Any]:
        """Generate unique referral code for a user."""
        code = f"REF-{user_id[:4]}-{random.randint(1000, 9999)}"
        
        await query_db(f"""
            INSERT INTO referral_codes 
            (id, user_id, code, created_at)
            VALUES (gen_random_uuid(), '{user_id}', '{code}', NOW())
        """)
        
        return {"success": True, "code": code}
        
    async def track_referral(self, referrer_id: str, referred_id: str) -> Dict[str, Any]:
        """Track referral conversions."""
        await query_db(f"""
            INSERT INTO referral_events 
            (id, referrer_id, referred_id, created_at)
            VALUES (gen_random_uuid(), '{referrer_id}', '{referred_id}', NOW())
        """)
        
        return {"success": True}
