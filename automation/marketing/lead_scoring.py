"""
Lead scoring based on engagement and predicted conversion.
Integrated with revenue data for value scoring.
"""
from typing import Dict, List, Optional
import math

class LeadScorer:
    def __init__(self):
        self.model_weights = {
            'page_views': 0.5,
            'email_opens': 0.3,
            'form_submissions': 0.8,
            'time_on_site': 0.2,
            'content_downloads': 0.7
        }
    
    def calculate_score(self, engagement: Dict) -> float:
        """Calculate lead score 0-100"""
        score = 0.0
        
        for key, weight in self.model_weights.items():
            value = float(engagement.get(key, 0))
            # Normalize and weight
            score += (1 - math.exp(-value)) * weight * 100
            
        return min(score, 100)  # Cap at 100
    
    async def score_lead(self, contact_id: str, engagement_data: Optional[Dict] = None) -> Dict:
        """Score a lead and update tracking"""
        if not engagement_data:
            # TODO: Fetch from DB
            engagement_data = {}
            
        score = self.calculate_score(engagement_data)
        
        # TODO: Store score in database
        # TODO: Compare against historical conversion rates
        
        return {
            "success": True,
            "contact_id": contact_id,
            "score": round(score, 2),
            "tier": self._determine_tier(score)
        }
    
    def _determine_tier(self, score: float) -> str:
        """Classify lead quality"""
        if score > 75:
            return "hot"
        elif score > 50:
            return "warm" 
        else:
            return "cold"
