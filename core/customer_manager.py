from typing import Dict, Optional
from datetime import datetime
from core.payment_processor import PaymentProcessor

class CustomerManager:
    """Manage customer lifecycle and onboarding."""
    
    def __init__(self):
        self.payment_processor = PaymentProcessor()
        
    async def onboard_customer(self, email: str, name: str, plan: str) -> Dict:
        """Onboard a new customer with payment setup."""
        try:
            # Create Stripe customer
            customer_res = await self.payment_processor.create_customer(email, name)
            if not customer_res['success']:
                return customer_res
                
            # Create subscription
            subscription_res = await self._create_subscription(
                customer_res['customer_id'],
                plan
            )
            
            if not subscription_res['success']:
                return subscription_res
                
            return {
                'success': True,
                'customer_id': customer_res['customer_id'],
                'subscription_id': subscription_res['subscription_id'],
                'onboarded_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _create_subscription(self, customer_id: str, plan: str) -> Dict:
        """Create a subscription for the customer."""
        # Get plan details from config
        plan_details = self._get_plan_details(plan)
        if not plan_details:
            return {
                'success': False,
                'error': f'Invalid plan: {plan}'
            }
            
        # Create payment intent
        intent_res = await self.payment_processor.create_payment_intent(
            plan_details['price'],
            customer_id,
            f'Subscription for {plan} plan'
        )
        
        if not intent_res['success']:
            return intent_res
            
        return {
            'success': True,
            'subscription_id': f'sub_{customer_id}_{plan}',
            'payment_intent': intent_res
        }
        
    def _get_plan_details(self, plan: str) -> Optional[Dict]:
        """Get pricing and details for a subscription plan."""
        plans = {
            'basic': {
                'price': 9900,  # $99.00
                'features': ['feature1', 'feature2']
            },
            'pro': {
                'price': 19900,  # $199.00
                'features': ['feature1', 'feature2', 'feature3']
            }
        }
        return plans.get(plan)
