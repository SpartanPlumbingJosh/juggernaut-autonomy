import logging
import asyncio
from typing import Dict, Optional
from datetime import datetime, timezone
from core.database import query_db

class FulfillmentService:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql

    async def fulfill_order(self, order_data: Dict) -> Dict[str, Union[str, bool]]:
        """Handle order fulfillment with validation and error handling."""
        try:
            # Validate payment first
            payment_valid = await self.verify_payment(order_data['payment_id'], order_data['payment_method'])
            if not payment_valid:
                return {"success": False, "error": "Invalid payment"}

            # Record the revenue event
            revenue_event = await self.record_revenue(
                amount_cents=order_data['amount_cents'],
                currency=order_data['currency'],
                source="online_store",
                payment_id=order_data['payment_id'],
                metadata={
                    "product_id": order_data.get('product_id'),
                    "customer_email": order_data.get('customer_email'),
                    "order_details": order_data.get('order_details')
                }
            )
            
            # Deliver product
            delivery_result = await self.deliver_product(
                order_data.get('product_id'),
                order_data.get('customer_email'),
                order_data.get('customer_details')
            )
            
            if not delivery_result.get('success'):
                await self.record_failure(order_data, delivery_result.get('error'))
                return {"success": False, "error": "Failed to deliver product"}
            
            return {"success": True, "revenue_event_id": revenue_event.get('id')}

        except Exception as e:
            await self.record_failure(order_data, str(e))
            return {"success": False, "error": f"Fulfillment failed: {str(e)}"}

    async def deliver_product(self, product_id: str, email: str, details: Dict) -> Dict:
        """Implement product delivery logic (email, API call, etc.)"""
        # Example: Email delivery for digital products
        try:
            # TODO: Implement actual delivery mechanism based on product type
            logging.info(f"Delivering product {product_id} to {email}")
            await asyncio.sleep(0.5)  # Simulate delivery time
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_revenue(
        self,
        amount_cents: int,
        currency: str,
        source: str,
        payment_id: str,
        metadata: Dict
    ) -> Dict:
        """Record revenue event in database."""
        try:
            metadata_json = json.dumps(metadata)
            sql = f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{currency.upper()}',
                '{source.replace("'", "''")}',
                '{metadata_json.replace("'", "''")}',
                NOW(),
                NOW()
            )
            RETURNING id
            """
            result = await self.execute_sql(sql)
            return {"success": True, "id": result.get('rows', [{}])[0].get('id')}
        except Exception as e:
            logging.error(f"Failed to record revenue: {str(e)}")
            return {"success": False}

    async def verify_payment(self, payment_id: str, provider: str) -> bool:
        """Verify payment was completed."""
        sql = f"""
        SELECT COUNT(*) as count
        FROM payments
        WHERE payment_id = '{payment_id.replace("'", "''")}'
          AND status = 'completed'
          AND provider = '{provider.replace("'", "''")}'
        """
        result = await self.execute_sql(sql)
        return (result.get('rows', [{}])[0].get('count', 0) > 0)

    async def record_failure(self, order_data: Dict, error: str) -> None:
        """Log failed fulfillment attempts."""
        try:
            metadata_json = json.dumps({
                "order_data": order_data,
                "error": error[:500]  # Truncate long errors
            })
            await self.execute_sql(f"""
                INSERT INTO fulfillment_errors (
                    id, order_id, error_details, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{order_data.get('order_id', 'unknown').replace("'", "''")}',
                    '{metadata_json.replace("'", "''")}',
                    NOW()
                )
            """)
        except Exception as e:
            logging.error(f"Failed to record fulfillment error: {str(e)}")
