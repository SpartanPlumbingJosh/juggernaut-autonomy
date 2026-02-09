from typing import Dict, List, Optional
import json
from core.database import query_db

class LeadGenerationBot:
    """Automated lead generation and qualification."""
    
    def __init__(self):
        self.sources = ["website", "social", "referral", "paid"]
        
    async def capture_lead(self, source: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Capture and qualify a new lead."""
        try:
            # Score lead based on metadata
            score = self._calculate_lead_score(metadata)
            
            # Insert lead record
            insert_sql = f"""
                INSERT INTO leads (
                    id, source, metadata, score,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{source}',
                    '{json.dumps(metadata)}',
                    {score},
                    NOW(),
                    NOW()
                )
            """
            await query_db(insert_sql)
            
            # Trigger email sequence if score is high enough
            if score >= 80:
                await self._trigger_email_sequence(metadata)
                
            return {"success": True, "score": score}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _calculate_lead_score(self, metadata: Dict[str, Any]) -> int:
        """Calculate lead score based on metadata."""
        score = 0
        
        # Score based on lead source
        source = metadata.get("source")
        if source == "website":
            score += 30
        elif source == "referral":
            score += 50
            
        # Score based on company size
        company_size = metadata.get("company_size")
        if company_size == "enterprise":
            score += 40
        elif company_size == "midmarket":
            score += 20
            
        # Score based on budget
        budget = metadata.get("budget")
        if budget == "high":
            score += 50
        elif budget == "medium":
            score += 30
            
        return min(100, score)
        
    async def _trigger_email_sequence(self, metadata: Dict[str, Any]) -> None:
        """Trigger automated email sequence for high-quality leads."""
        # Get email sequence based on lead characteristics
        sequence = self._determine_email_sequence(metadata)
        
        # Schedule emails
        for email in sequence:
            insert_sql = f"""
                INSERT INTO email_sequences (
                    id, lead_id, email_type, scheduled_at,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{metadata.get("lead_id")}',
                    '{email}',
                    NOW() + INTERVAL '{sequence[email]} hours',
                    NOW(),
                    NOW()
                )
            """
            await query_db(insert_sql)
            
    def _determine_email_sequence(self, metadata: Dict[str, Any]) -> Dict[str, int]:
        """Determine appropriate email sequence based on lead metadata."""
        # Basic sequence for most leads
        sequence = {
            "welcome": 0,
            "features": 24,
            "case_study": 48,
            "demo_offer": 72
        }
        
        # Customize based on lead characteristics
        if metadata.get("company_size") == "enterprise":
            sequence["enterprise_features"] = 12
            sequence["enterprise_case_study"] = 36
            
        if metadata.get("budget") == "high":
            sequence["premium_features"] = 12
            sequence["enterprise_pricing"] = 36
            
        return sequence
