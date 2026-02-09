"""
Handles user onboarding flows including free trial and registration.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from core.database import query_db

class UserOnboarder:
    FREE_TRIAL_DAYS = 14

    async def start_free_trial(self, user_id: str) -> Dict:
        """Begin free trial period for new user."""
        try:
            trial_end = datetime.now(timezone.utc) + timedelta(days=self.FREE_TRIAL_DAYS)
            
            await query_db(
                f"""
                INSERT INTO user_trials (
                    user_id,
                    started_at,
                    ends_at
                ) VALUES (
                    '{user_id}',
                    NOW(),
                    '{trial_end.isoformat()}'
                )
                """
            )
            
            return {
                "success": True,
                "trial_end": trial_end,
                "days": self.FREE_TRIAL_DAYS
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def check_trial_status(self, user_id: str) -> Dict:
        """Verify if user still has active trial."""
        try:
            result = await query_db(
                f"""
                SELECT ends_at > NOW() as active
                FROM user_trials
                WHERE user_id = '{user_id}'
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
            
            if not result.get("rows"):
                return {"active": False, "reason": "no_trial_found"}

            return {"active": result["rows"][0]["active"]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def complete_onboarding(self, user_id: str) -> Dict:
        """Mark user as having completed core onboarding."""
        try:
            await query_db(
                f"""
                UPDATE users
                SET onboarding_completed = TRUE,
                    updated_at = NOW()
                WHERE id = '{user_id}'
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
