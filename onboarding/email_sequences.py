from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum

class EmailSequenceStepType(Enum):
    WELCOME = "welcome"
    FEATURE_HIGHLIGHT = "feature_highlight"
    CASE_STUDY = "case_study"
    OFFER = "offer"
    FOLLOW_UP = "follow_up"

class EmailSequence:
    def __init__(self, steps: List[Dict[str, Any]]):
        self.steps = steps

    async def send_next_email(self, user_id: str, last_email_sent_at: Optional[datetime] = None) -> Dict[str, Any]:
        """Send the next email in the sequence"""
        # Implementation would integrate with email service provider
        return {"success": True}

class OnboardingEmailSequences:
    def __init__(self):
        self.sequences = {
            "default": EmailSequence([
                {"type": EmailSequenceStepType.WELCOME, "delay_hours": 0},
                {"type": EmailSequenceStepType.FEATURE_HIGHLIGHT, "delay_hours": 24},
                {"type": EmailSequenceStepType.CASE_STUDY, "delay_hours": 48},
                {"type": EmailSequenceStepType.OFFER, "delay_hours": 72},
                {"type": EmailSequenceStepType.FOLLOW_UP, "delay_hours": 96}
            ])
        }

    async def get_sequence(self, sequence_name: str = "default") -> Optional[EmailSequence]:
        return self.sequences.get(sequence_name)
