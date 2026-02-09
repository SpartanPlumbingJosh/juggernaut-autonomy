from typing import Dict, Optional
import json
from core.billing_service import BillingService

class OnboardingService:
    """Handle customer onboarding flow and initial service setup."""
    
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
        self.billing = BillingService(execute_sql)
    
    async def start_onboarding(
        self,
        email: str,
        name: str,
        plan_id: str,
        payment_method: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Start new customer onboarding flow."""
        # Create customer record
        customer_res = await self.billing.create_customer(
            email=email,
            name=name,
            payment_method=payment_method,
            metadata=metadata
        )
        if not customer_res['success']:
            return customer_res
            
        customer_id = customer_res['customer_id']
        
        # Create subscription
        sub_res = await self.billing.create_subscription(
            customer_id=customer_id,
            plan_id=plan_id,
            trial_days=7  # Default 7-day trial
        )
        if not sub_res['success']:
            return sub_res
            
        # Initialize service
        service_res = await self._initialize_service(customer_id)
        if not service_res['success']:
            return service_res
            
        return {
            "success": True,
            "customer_id": customer_id,
            "subscription_id": sub_res['subscription_id'],
            "service_id": service_res['service_id']
        }
    
    async def _initialize_service(self, customer_id: str) -> Dict:
        """Initialize service delivery for new customer."""
        try:
            # Create service record
            res = await self.execute_sql(
                f"""
                INSERT INTO customer_services (
                    id, customer_id, status, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    'pending',
                    NOW(),
                    NOW()
                )
                RETURNING id
                """
            )
            service_id = res.get('rows', [{}])[0].get('id')
            
            # TODO: Trigger actual service provisioning
            return {
                "success": True,
                "service_id": service_id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
