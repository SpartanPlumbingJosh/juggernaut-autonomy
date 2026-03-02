from typing import Dict
from datetime import datetime
from core.database import execute_sql

class CustomerProvisioner:
    """Handles autonomous customer provisioning and onboarding."""
    
    async def create_customer(self, email: str, name: str, 
                            metadata: Dict = None) -> Dict:
        """Create a new customer record."""
        try:
            await execute_sql(
                f"""
                INSERT INTO customers (
                    id, email, name, status, 
                    created_at, updated_at, metadata
                ) VALUES (
                    gen_random_uuid(),
                    '{email}',
                    '{name}',
                    'active',
                    NOW(),
                    NOW(),
                    '{json.dumps(metadata or {})}'
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def onboard_customer(self, customer_id: str) -> Dict:
        """Handle self-service customer onboarding."""
        try:
            # Create default subscription
            await execute_sql(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status,
                    current_period_start, current_period_end,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    'default_plan',
                    'active',
                    NOW(),
                    NOW() + INTERVAL '1 month',
                    NOW(),
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
