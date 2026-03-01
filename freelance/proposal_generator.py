from typing import Dict
import logging
import random

class ProposalGenerator:
    """Generate personalized proposals for freelance jobs."""
    
    def __init__(self, profile: Dict[str, Any], templates: List[str]):
        self.profile = profile
        self.templates = templates
        self.logger = logging.getLogger(__name__)
        
    def generate_proposal(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a customized proposal for a job."""
        try:
            # Select a random template
            template = random.choice(self.templates)
            
            # Personalize the proposal
            proposal_text = template.format(
                client_name="Hiring Manager",
                job_title=job.get("title", ""),
                skills=", ".join(job.get("skills", [])),
                my_skills=", ".join(self.profile.get("skills", [])),
                my_experience=self.profile.get("experience", ""),
                portfolio_url=self.profile.get("portfolio_url", ""),
                rate=self.profile.get("rate", "")
            )
            
            return {
                "job_id": job.get("id"),
                "platform": job.get("platform"),
                "proposal_text": proposal_text,
                "rate": self.profile.get("rate"),
                "estimated_hours": self._estimate_hours(job),
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate proposal: {str(e)}")
            return {}
            
    def _estimate_hours(self, job: Dict[str, Any]) -> int:
        """Estimate hours based on job description length."""
        desc_length = len(job.get("description", ""))
        return min(max(round(desc_length / 1000), 1), 40)
