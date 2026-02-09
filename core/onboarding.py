import logging
from typing import Dict, Optional
from datetime import datetime
from core.billing import BillingManager
from core.fulfillment import FulfillmentManager

class OnboardingManager:
    """Handle self-service customer onboarding."""
    
    def __init__(self, stripe_api_key: str):
        self.billing = BillingManager(stripe_api_key)
        self.fulfillment = FulfillmentManager()
        self.logger = logging.getLogger(__name__)
    
    def create_account(
        self,
        email: str,
        name: str,
        payment_method_id: str,
        plan_id: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Complete full onboarding flow."""
        try:
            # Step 1: Create customer record
            customer_res = self.billing.create_customer(email, name, metadata)
            if not customer_res.get('success'):
                raise Exception(customer_res.get('error', 'Customer creation failed'))
            
            customer_id = customer_res['customer_id']
            
            # Step 2: Create subscription
            sub_res = self.billing.create_subscription(
                customer_id=customer_id,
                price_id=plan_id
            )
            if not sub_res.get('success'):
                raise Exception(sub_res.get('error', 'Subscription creation failed'))
            
            # Step 3: Initial fulfillment
            fulfillment_res = self.fulfillment.process_payment(customer_id, 0)  # Initial $0 charge for setup
            
            if not fulfillment_res.get('success'):
                raise Exception(fulfillment_res.get('error', 'Initial fulfillment failed'))
            
            return {
                "success": True,
                "customer_id": customer_id,
                "subscription_id": sub_res['subscription_id'],
                "fulfillment_status": fulfillment_res['data']['status']
            }
            
        except Exception as e:
            self.logger.error(f"Onboarding failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "stage": "onboarding"
            }
    
    def upgrade_account(self, customer_id: str, new_plan_id: str) -> Dict:
        """Handle account upgrades."""
        try:
            # TODO: Implement plan upgrade logic
            return {
                "success": True,
                "customer_id": customer_id,
                "new_plan_id": new_plan_id
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "customer_id": customer_id
            }
