"""
Customer onboarding system - handles account creation, service selection,
and initial payment processing.
"""

from typing import Dict, Optional
from datetime import datetime
from billing.payment_processor import PaymentProcessor

class CustomerOnboarding:
    def __init__(self):
        self.payment_processor = PaymentProcessor()

    def create_account(
        self,
        email: str,
        name: str,
        service_plan: str,
        payment_method: str = 'stripe'
    ) -> Dict:
        """Complete customer onboarding flow."""
        try:
            # Step 1: Create payment customer
            customer = self.payment_processor.create_customer(
                email=email,
                name=name,
                payment_method=payment_method
            )
            
            # Step 2: Process initial payment
            payment = self.payment_processor.process_payment(
                amount=self._get_plan_price(service_plan),
                currency='USD',
                customer_id=customer['id'],
                payment_method=payment_method,
                metadata={
                    'service_plan': service_plan,
                    'onboarding': 'true'
                }
            )
            
            # Step 3: Provision services
            service_result = self._provision_services(
                email=email,
                service_plan=service_plan
            )
            
            return {
                'success': True,
                'customer_id': customer['id'],
                'payment_id': payment['id'],
                'service_status': service_result['status'],
                'onboarded_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'onboarded_at': datetime.now().isoformat()
            }

    def _get_plan_price(self, plan: str) -> float:
        """Get pricing for service plans."""
        plans = {
            'starter': 9.99,
            'professional': 29.99,
            'enterprise': 99.99
        }
        return plans.get(plan.lower(), 0.0)

    def _provision_services(self, email: str, service_plan: str) -> Dict:
        """Provision services for new customer."""
        # In a real implementation, this would:
        # 1. Create necessary service accounts
        # 2. Configure access
        # 3. Send welcome email
        
        return {
            'status': 'active',
            'resources_created': True,
            'email_sent': True
        }
