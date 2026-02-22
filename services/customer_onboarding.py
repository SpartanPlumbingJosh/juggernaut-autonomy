"""
Customer Onboarding - Automates new customer setup and provisioning.
"""

from typing import Dict, Any
from core.database import query_db
from services.payment_processor import PaymentProcessor

class CustomerOnboarding:
    def __init__(self, payment_processor: PaymentProcessor):
        self.payment_processor = payment_processor

    async def onboard_customer(self, email: str, name: str, plan: str, 
                             payment_details: Dict[str, Any]) -> Dict[str, Any]:
        """Complete full customer onboarding process."""
        try:
            # Create customer in payment system
            customer_result = await self.payment_processor.create_customer(
                email=email,
                name=name,
                metadata={"plan": plan}
            )
            
            if not customer_result['success']:
                return {"success": False, "error": "Failed to create customer"}
            
            customer_id = customer_result['customer_id']
            
            # Process initial payment
            payment_result = await self.payment_processor.process_payment(
                amount_cents=payment_details['amount_cents'],
                currency=payment_details['currency'],
                customer_id=customer_id,
                description=f"Initial payment for {plan} plan"
            )
            
            if not payment_result['success']:
                return {"success": False, "error": "Payment failed"}
            
            # Create customer record
            await query_db(f"""
                INSERT INTO customers (
                    id, email, name, plan, 
                    customer_id, status, onboarded_at
                ) VALUES (
                    gen_random_uuid(),
                    '{email}',
                    '{name}',
                    '{plan}',
                    '{customer_id}',
                    'active',
                    NOW()
                )
            """)
            
            return {"success": True, "customer_id": customer_id}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
