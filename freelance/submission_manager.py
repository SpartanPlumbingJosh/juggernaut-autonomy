import time
from typing import Dict, List
import logging
from datetime import datetime, timedelta

class SubmissionManager:
    """Manage submission of proposals with rate limiting and tracking."""
    
    def __init__(self, daily_limit: int = 10, hourly_limit: int = 3):
        self.daily_limit = daily_limit
        self.hourly_limit = hourly_limit
        self.submissions = []
        self.logger = logging.getLogger(__name__)
        
    def can_submit(self) -> bool:
        """Check if we can submit another proposal based on rate limits."""
        now = datetime.utcnow()
        
        # Check daily limit
        daily_submissions = [
            s for s in self.submissions 
            if s["submitted_at"] > now - timedelta(days=1)
        ]
        if len(daily_submissions) >= self.daily_limit:
            return False
            
        # Check hourly limit
        hourly_submissions = [
            s for s in self.submissions 
            if s["submitted_at"] > now - timedelta(hours=1)
        ]
        if len(hourly_submissions) >= self.hourly_limit:
            return False
            
        return True
        
    def submit_proposal(self, job: Dict[str, Any], proposal: Dict[str, Any]) -> bool:
        """Submit a proposal to a job."""
        try:
            if not self.can_submit():
                self.logger.warning("Rate limit reached - skipping submission")
                return False
                
            # Simulate submission
            time.sleep(2)  # Simulate network delay
            
            # Record submission
            self.submissions.append({
                "job_id": job.get("id"),
                "platform": job.get("platform"),
                "submitted_at": datetime.utcnow().isoformat(),
                "proposal": proposal
            })
            
            self.logger.info(f"Successfully submitted proposal for job {job.get('id')}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to submit proposal: {str(e)}")
            return False
            
    def get_submission_stats(self) -> Dict[str, Any]:
        """Get statistics about submissions."""
        now = datetime.utcnow()
        return {
            "total_submissions": len(self.submissions),
            "daily_submissions": len([
                s for s in self.submissions 
                if s["submitted_at"] > now - timedelta(days=1)
            ]),
            "hourly_submissions": len([
                s for s in self.submissions 
                if s["submitted_at"] > now - timedelta(hours=1)
            ])
        }
