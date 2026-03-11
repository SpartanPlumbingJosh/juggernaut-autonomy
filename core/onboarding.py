"""
Automated user onboarding for revenue model MVP.
Handles account creation, welcome sequence, and initial service setup.
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from core.database import execute_sql
from core.payment_processor import PaymentProcessor

class OnboardingManager:
    def __init__(self):
        self.payment_processor = PaymentProcessor()
        
    async def onboard_user(self, email: str, plan: str) -> Dict[str, Any]:
        """Complete automated onboarding for new user."""
        try:
            user_id = str(uuid.uuid4())
            
            # Create user account
            await execute_sql(
                f"""
                INSERT INTO users (
                    id, email, status,
                    created_at, updated_at
                ) VALUES (
                    '{user_id}',
                    '{email}',
                    'active',
                    NOW(),
                    NOW()
                )
                """
            )
            
            # Process initial payment based on plan
            payment_amount = 0
            if plan == "basic":
                payment_amount = 9900  # $99 in cents
            elif plan == "pro":
                payment_amount = 19900  # $199 in cents
                
            payment_result = await self.payment_processor.process_payment(
                user_id=user_id,
                amount_cents=payment_amount,
                payment_method="card",
                description=f"Initial {plan} plan payment"
            )
            
            if not payment_result.get("success"):
                raise Exception(f"Payment failed: {payment_result.get('error')}")
                
            # Activate service
            await execute_sql(
                f"""
                INSERT INTO user_services (
                    id, user_id, plan_type,
                    status, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{user_id}',
                    '{plan}',
                    'active',
                    NOW(),
                    NOW()
                )
                """
            )
            
            return {
                "success": True,
                "user_id": user_id,
                "plan": plan,
                "payment_id": payment_result.get("payment_id")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
