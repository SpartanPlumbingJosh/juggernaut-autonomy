"""
Customer Manager - Handle customer lifecycle and subscriptions.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from core.database import query_db

class CustomerManager:
    @staticmethod
    async def create_customer(
        email: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new customer record"""
        try:
            sql = f"""
            INSERT INTO customers (
                id,
                email,
                name,
                status,
                created_at,
                updated_at,
                metadata
            ) VALUES (
                gen_random_uuid(),
                '{email}',
                {'NULL' if name is None else f"'{name}'"},
                'active',
                NOW(),
                NOW(),
                {'NULL' if metadata is None else f"'{json.dumps(metadata)}'"}
            )
            RETURNING id, email, status
            """
            result = await query_db(sql)
            return result.get("rows", [{}])[0]
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def update_subscription(
        customer_id: str,
        subscription_id: str,
        plan_id: str,
        status: str
    ) -> Dict[str, Any]:
        """Update customer subscription"""
        try:
            sql = f"""
            UPDATE customers
            SET 
                subscription_id = '{subscription_id}',
                subscription_plan = '{plan_id}',
                subscription_status = '{status}',
                updated_at = NOW()
            WHERE id = '{customer_id}'
            RETURNING id, email, subscription_status
            """
            result = await query_db(sql)
            return result.get("rows", [{}])[0]
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def record_payment_event(
        customer_id: str,
        amount: float,
        currency: str,
        payment_method: str,
        service_delivered: bool = False
    ) -> Dict[str, Any]:
        """Record payment in revenue_events"""
        try:
            sql = f"""
            INSERT INTO revenue_events (
                customer_id,
                event_type,
                amount_cents,
                currency,
                source,
                recorded_at
            ) VALUES (
                '{customer_id}',
                'revenue',
                {int(amount * 100)},
                '{currency}',
                '{payment_method}',
                NOW()
            )
            RETURNING id
            """
            result = await query_db(sql)
            
            # If this was for service delivery, trigger fulfillment
            if service_delivered:
                await CustomerManager._trigger_fulfillment(customer_id)
            
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def _trigger_fulfillment(customer_id: str) -> None:
        """Trigger automated service delivery"""
        # TODO: Implement fulfillment logic
        pass

customer_manager = CustomerManager()
