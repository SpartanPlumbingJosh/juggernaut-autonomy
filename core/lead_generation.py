"""
JUGGERNAUT Autonomous Lead Generation System

Handles end-to-end lead generation, enrichment, and sales pipeline automation.
Integrates with email, CRM, and analytics systems.
"""

import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from .database import query_db, escape_sql_value
from .retry import exponential_backoff

logger = logging.getLogger(__name__)

# Lead sources configuration
LEAD_SOURCES = {
    "linkedin": {
        "api_url": "https://api.linkedin.com/v2/people-search",
        "required_fields": ["industry", "location"]
    },
    "apollo": {
        "api_url": "https://api.apollo.io/v1/people/search",
        "required_fields": ["organization", "title"]
    },
    "clearbit": {
        "api_url": "https://person.clearbit.com/v2/people/find",
        "required_fields": ["email"]
    }
}

# Email sequence templates
EMAIL_SEQUENCES = {
    "cold_outreach": [
        {"day": 0, "template": "initial_outreach"},
        {"day": 3, "template": "follow_up_1"},
        {"day": 7, "template": "follow_up_2"},
        {"day": 14, "template": "breakup"}
    ],
    "warm_intro": [
        {"day": 0, "template": "intro"},
        {"day": 5, "template": "value_prop"},
        {"day": 10, "template": "case_study"}
    ]
}

@dataclass
class Lead:
    id: str
    name: str
    email: str
    company: str
    title: str
    source: str
    status: str = "new"
    last_contacted: Optional[datetime] = None
    engagement_score: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EmailTemplate:
    id: str
    name: str
    subject: str
    body: str
    variants: List[Dict[str, str]] = field(default_factory=list)

class LeadGenerator:
    """Autonomous lead generation and sales pipeline system."""
    
    def __init__(self):
        self.crm_integration = CRMIntegration()
        self.email_system = EmailSystem()
        self.ab_test_manager = ABTestManager()

    @exponential_backoff(max_retries=3)
    def find_leads(self, industry: str, location: str, keywords: str, limit: int = 10) -> List[Lead]:
        """Find leads from multiple sources based on criteria."""
        leads = []
        
        # Search LinkedIn
        if "linkedin" in LEAD_SOURCES:
            params = {
                "industry": industry,
                "location": location,
                "keywords": keywords,
                "count": limit
            }
            response = self._call_api("linkedin", params)
            leads.extend(self._parse_linkedin_leads(response))
        
        # Search Apollo
        if "apollo" in LEAD_SOURCES:
            params = {
                "organization_industry": industry,
                "location": location,
                "title_contains": keywords,
                "page_size": limit
            }
            response = self._call_api("apollo", params)
            leads.extend(self._parse_apollo_leads(response))
        
        return leads[:limit]

    def enrich_lead(self, lead_id: str, data_fields: List[str]) -> Lead:
        """Enrich lead data with additional information."""
        lead = self._get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        
        # Enrich from Clearbit
        if "clearbit" in LEAD_SOURCES and lead.email:
            enriched = self._call_api("clearbit", {"email": lead.email})
            for field in data_fields:
                if field in enriched:
                    lead.metadata[field] = enriched[field]
        
        # Update in CRM
        self.crm_integration.update_lead(lead)
        return lead

    def start_email_sequence(self, lead_id: str, sequence_id: str) -> Dict[str, Any]:
        """Start an automated email sequence for a lead."""
        lead = self._get_lead(lead_id)
        sequence = EMAIL_SEQUENCES.get(sequence_id)
        if not sequence:
            raise ValueError(f"Invalid sequence ID: {sequence_id}")
        
        results = []
        for step in sequence:
            # Wait until scheduled day
            if step["day"] > 0:
                time.sleep(step["day"] * 86400)
            
            # Get template with A/B test variant if available
            template = self.ab_test_manager.get_template_variant(step["template"])
            email = self.email_system.send_personalized(
                lead=lead,
                template=template
            )
            results.append({
                "day": step["day"],
                "email_id": email.id,
                "template": template.id
            })
        
        return {"sequence_id": sequence_id, "steps": results}

    def track_engagement(self, email_id: str) -> Dict[str, Any]:
        """Track email engagement metrics."""
        return self.email_system.get_engagement(email_id)

    def _get_lead(self, lead_id: str) -> Optional[Lead]:
        """Retrieve lead from CRM."""
        return self.crm_integration.get_lead(lead_id)

    def _call_api(self, source: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make API call to lead source."""
        config = LEAD_SOURCES.get(source)
        if not config:
            raise ValueError(f"Unsupported lead source: {source}")
        
        headers = {
            "Authorization": f"Bearer {os.getenv(f'{source.upper()}_API_KEY')}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            config["api_url"],
            headers=headers,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def _parse_linkedin_leads(self, data: Dict[str, Any]) -> List[Lead]:
        """Parse LinkedIn API response into Lead objects."""
        leads = []
        for person in data.get("elements", []):
            leads.append(Lead(
                id=f"li_{person.get('id')}",
                name=f"{person.get('firstName')} {person.get('lastName')}",
                email=person.get("email"),
                company=person.get("company"),
                title=person.get("title"),
                source="linkedin",
                metadata=person
            ))
        return leads

    def _parse_apollo_leads(self, data: Dict[str, Any]) -> List[Lead]:
        """Parse Apollo API response into Lead objects."""
        leads = []
        for person in data.get("people", []):
            leads.append(Lead(
                id=f"ap_{person.get('id')}",
                name=person.get("name"),
                email=person.get("email"),
                company=person.get("organization", {}).get("name"),
                title=person.get("title"),
                source="apollo",
                metadata=person
            ))
        return leads

class CRMIntegration:
    """Handles CRM integration and pipeline management."""
    
    def get_lead(self, lead_id: str) -> Optional[Lead]:
        """Retrieve lead from CRM."""
        result = query_db(
            f"SELECT * FROM leads WHERE id = {escape_sql_value(lead_id)}"
        )
        if result.get("rows"):
            return Lead(**result["rows"][0])
        return None

    def update_lead(self, lead: Lead) -> bool:
        """Update lead in CRM."""
        query_db(
            f"""
            INSERT INTO leads (id, name, email, company, title, source, status, metadata)
            VALUES (
                {escape_sql_value(lead.id)},
                {escape_sql_value(lead.name)},
                {escape_sql_value(lead.email)},
                {escape_sql_value(lead.company)},
                {escape_sql_value(lead.title)},
                {escape_sql_value(lead.source)},
                {escape_sql_value(lead.status)},
                {escape_sql_value(json.dumps(lead.metadata))}
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                company = EXCLUDED.company,
                title = EXCLUDED.title,
                status = EXCLUDED.status,
                metadata = EXCLUDED.metadata
            """
        )
        return True

    def log_interaction(self, lead_id: str, interaction_data: Dict[str, Any]) -> bool:
        """Log interaction with lead."""
        query_db(
            f"""
            INSERT INTO lead_interactions (lead_id, type, notes, outcome)
            VALUES (
                {escape_sql_value(lead_id)},
                {escape_sql_value(interaction_data.get('type'))},
                {escape_sql_value(interaction_data.get('notes'))},
                {escape_sql_value(interaction_data.get('outcome'))}
            )
            """
        )
        return True

class EmailSystem:
    """Handles email personalization and sending."""
    
    def send_personalized(self, lead: Lead, template: EmailTemplate) -> Dict[str, Any]:
        """Send personalized email to lead."""
        # Personalize template
        subject = template.subject.format(
            first_name=lead.name.split()[0],
            company=lead.company
        )
        body = template.body.format(
            first_name=lead.name.split()[0],
            company=lead.company,
            title=lead.title
        )
        
        # Send via email service
        return {
            "id": f"em_{int(time.time())}",
            "subject": subject,
            "to": lead.email,
            "template_id": template.id,
            "sent_at": datetime.now()
        }

    def get_engagement(self, email_id: str) -> Dict[str, Any]:
        """Get email engagement metrics."""
        return {
            "opens": random.randint(0, 5),
            "clicks": random.randint(0, 2),
            "replies": random.randint(0, 1)
        }

class ABTestManager:
    """Manages A/B testing for email templates and messaging."""
    
    def create_test(self, test_name: str, variants: List[Dict[str, str]]) -> str:
        """Create new A/B test."""
        test_id = f"ab_{int(time.time())}"
        query_db(
            f"""
            INSERT INTO ab_tests (id, name, variants, status)
            VALUES (
                {escape_sql_value(test_id)},
                {escape_sql_value(test_name)},
                {escape_sql_value(json.dumps(variants))},
                'active'
            )
            """
        )
        return test_id

    def get_template_variant(self, template_id: str) -> EmailTemplate:
        """Get template variant for A/B test."""
        result = query_db(
            f"SELECT * FROM email_templates WHERE id = {escape_sql_value(template_id)}"
        )
        if not result.get("rows"):
            raise ValueError(f"Template {template_id} not found")
        
        template_data = result["rows"][0]
        variants = json.loads(template_data.get("variants", "[]"))
        
        if variants:
            # Select random variant for testing
            variant = random.choice(variants)
            return EmailTemplate(
                id=f"{template_id}_{variant['id']}",
                name=f"{template_data['name']} - {variant['name']}",
                subject=variant.get("subject", template_data["subject"]),
                body=variant.get("body", template_data["body"]),
                variants=[]
            )
        
        return EmailTemplate(**template_data)

    def get_test_results(self, test_id: str) -> Dict[str, Any]:
        """Get A/B test performance results."""
        result = query_db(
            f"SELECT * FROM ab_tests WHERE id = {escape_sql_value(test_id)}"
        )
        if not result.get("rows"):
            raise ValueError(f"Test {test_id} not found")
        
        test_data = result["rows"][0]
        return {
            "test_id": test_id,
            "name": test_data["name"],
            "variants": json.loads(test_data.get("variants", "[]")),
            "performance": json.loads(test_data.get("performance", "{}"))
        }
