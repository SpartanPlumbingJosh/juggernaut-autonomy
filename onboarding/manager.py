from typing import Dict
from billing.integrations import BillingManager
from core.service_delivery import ServiceDelivery
import logging

class OnboardingManager:
    """Handle customer onboarding process."""
    
    def __init__(self, stripe_api_key: str):
        self.billing = BillingManager(stripe_api_key)
        self.service = ServiceDelivery()
        self.logger = logging.getLogger(__name__)
        
    def onboard_customer(self, email: str, name: str, plan: str) -> Dict:
        """Complete full customer onboarding."""
        try:
            # Step 1: Create customer in Stripe
            customer = self.billing.create_customer(email, name)
            
            # Step 2: Create subscription
            price_id = self._get_price_id_for_plan(plan)
            subscription = self.billing.create_subscription(customer.id, price_id)
            
            # Step 3: Provision services
            provision_result = self.service.provision_service(customer.id, plan)
            
            return {
                "success": True,
                "customer_id": customer.id,
                "subscription_id": subscription.id,
                "provisioning": provision_result
            }
        except Exception as e:
            self.logger.error(f"Onboarding failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    def _get_price_id_for_plan(self, plan: str) -> str:
        """Map plan names to Stripe price IDs."""
        # TODO: Move this to config
        plans = {
            "basic": "price_1XYZ",
            "pro": "price_1ABC",
            "enterprise": "price_1DEF"
        }
        return plans.get(plan, "price_1XYZ")
