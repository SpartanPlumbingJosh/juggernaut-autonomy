from typing import Dict, Any
import random
import time
from datetime import datetime

class ProposalGenerator:
    """Automated freelance proposal generator targeting high-probability gigs."""
    
    def __init__(self):
        self.templates = [
            "I specialize in Python automation and data processing. Based on your requirements, I can deliver {task} within {timeframe}. My approach focuses on {key_benefit}.",
            "With {years} years of Python experience, I can help you {task} efficiently. I'll provide {deliverables} with {quality_guarantee}.",
            "I've successfully completed similar {task} projects before. I can start immediately and deliver {deliverables} within {timeframe}."
        ]
        
        self.benefits = [
            "clean, maintainable code",
            "thorough documentation",
            "automated testing",
            "scalable architecture",
            "rapid delivery"
        ]
        
        self.guarantees = [
            "full satisfaction guarantee",
            "unlimited revisions",
            "24/7 support",
            "on-time delivery",
            "bug-free code"
        ]
        
        self.rate_limits = {
            'hourly': 5,
            'daily': 20
        }
        self.last_request = datetime.now()
        self.request_count = 0
        
    def _check_rate_limit(self):
        """Enforce rate limiting to avoid bans."""
        now = datetime.now()
        if (now - self.last_request).seconds < 3600:
            if self.request_count >= self.rate_limits['hourly']:
                time.sleep(3600 - (now - self.last_request).seconds)
                self.request_count = 0
        else:
            self.request_count = 0
            
        self.last_request = datetime.now()
        self.request_count += 1
        
    def generate_proposal(self, gig_details: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a customized proposal for a freelance gig."""
        self._check_rate_limit()
        
        try:
            template = random.choice(self.templates)
            timeframe = f"{random.randint(1, 7)} business days"
            years = random.randint(2, 10)
            
            proposal = template.format(
                task=gig_details.get('task', 'the project'),
                timeframe=timeframe,
                key_benefit=random.choice(self.benefits),
                years=years,
                deliverables=gig_details.get('deliverables', 'the solution'),
                quality_guarantee=random.choice(self.guarantees)
            )
            
            return {
                'success': True,
                'proposal': proposal,
                'rate': f"${random.randint(25, 100)}/hour",
                'timeframe': timeframe
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'retry_after': 60
            }
