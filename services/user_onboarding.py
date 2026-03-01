from typing import Dict, Any
import logging
from services.payment_processor import PaymentProcessor

logger = logging.getLogger(__name__)

class UserOnboarding:
    def __init__(self, payment_processor: PaymentProcessor):
        self.payment_processor = payment_processor

    async def onboard_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle full user onboarding workflow."""
        try:
            # Step 1: Create Stripe customer
            customer_res = await self.payment_processor.create_customer(
                email=user_data['email'],
                name=user_data['name']
            )
            
            if not customer_res['success']:
                return {"success": False, "error": "Failed to create customer"}
            
            # Step 2: Create initial payment intent
            payment_res = await self.payment_processor.create_payment_intent(
                amount=user_data['initial_payment_amount'],
                currency=user_data['currency'],
                customer_id=customer_res['customer_id']
            )
            
            if not payment_res['success']:
                return {"success": False, "error": "Failed to create payment"}
            
            return {
                "success": True,
                "customer_id": customer_res['customer_id'],
                "client_secret": payment_res['client_secret']
            }
            
        except Exception as e:
            logger.error(f"Onboarding failed: {str(e)}")
            return {"success": False, "error": str(e)}
