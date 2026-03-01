from datetime import datetime
from typing import Dict, List, Optional
import uuid

class ClientOnboarding:
    """Handle client onboarding workflow with automated steps and validation."""
    
    def __init__(self):
        self.steps = [
            "initial_contact",
            "needs_assessment", 
            "proposal",
            "contract_signing",
            "kickoff",
            "first_deliverable"
        ]
        self.current_step = 0
        self.client_data: Dict[str, Any] = {}
        self.onboarding_id = str(uuid.uuid4())
        self.created_at = datetime.utcnow()
        
    def start_onboarding(self, client_info: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize onboarding process."""
        self.client_data = client_info
        self.current_step = 0
        return {
            "status": "started",
            "onboarding_id": self.onboarding_id,
            "current_step": self.steps[self.current_step],
            "next_steps": self.steps[self.current_step+1:]
        }
        
    def complete_step(self, step_name: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mark a step as completed with validation."""
        if step_name not in self.steps:
            return {"error": "Invalid step name"}
            
        if self.steps.index(step_name) != self.current_step:
            return {"error": "Steps must be completed in order"}
            
        # Validate step data
        validation = self._validate_step(step_name, step_data)
        if not validation.get("valid"):
            return validation
            
        self.client_data[step_name] = step_data
        self.current_step += 1
        
        return {
            "status": "completed",
            "step": step_name,
            "next_step": self.steps[self.current_step] if self.current_step < len(self.steps) else None
        }
        
    def _validate_step(self, step_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate step-specific requirements."""
        validators = {
            "initial_contact": lambda d: bool(d.get("contact_info")),
            "needs_assessment": lambda d: bool(d.get("business_goals")),
            "proposal": lambda d: bool(d.get("proposal_approved")),
            "contract_signing": lambda d: bool(d.get("contract_signed")),
            "kickoff": lambda d: bool(d.get("team_assigned")),
            "first_deliverable": lambda d: bool(d.get("deliverable_ready"))
        }
        
        if step_name not in validators:
            return {"valid": False, "error": "No validator for step"}
            
        if not validators[step_name](data):
            return {"valid": False, "error": f"Invalid data for {step_name}"}
            
        return {"valid": True}
        
    def get_status(self) -> Dict[str, Any]:
        """Get current onboarding status."""
        return {
            "onboarding_id": self.onboarding_id,
            "current_step": self.steps[self.current_step],
            "completed_steps": self.steps[:self.current_step],
            "client_data": self.client_data,
            "created_at": self.created_at.isoformat()
        }
