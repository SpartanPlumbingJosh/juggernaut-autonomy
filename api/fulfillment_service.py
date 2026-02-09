import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import execute_sql
from core.logging import log_action

class FulfillmentService:
    """Handle order fulfillment and delivery."""
    
    @staticmethod
    async def process_order(
        payment_id: str,
        customer: Dict[str, Any],
        items: List[Dict[str, Any]],
        amount: float
    ) -> bool:
        """Process and fulfill an order."""
        try:
            # Create order record
            await execute_sql(
                f"""
                INSERT INTO orders (
                    payment_id, customer_email, customer_id,
                    amount, status, items, created_at
                ) VALUES (
                    '{payment_id}', '{customer.get("email", "")}',
                    '{customer.get("id", "")}', {amount},
                    'processing', '{json.dumps(items)}'::jsonb,
                    NOW()
                )
                """
            )
            
            # Process each item
            for item in items:
                product_id = item.get("id")
                quantity = item.get("quantity", 1)
                
                # Here you would integrate with your actual fulfillment system
                # For MVP, we'll just log and mark as fulfilled
                await execute_sql(
                    f"""
                    INSERT INTO order_items (
                        payment_id, product_id, quantity,
                        status, fulfilled_at
                    ) VALUES (
                        '{payment_id}', '{product_id}', {quantity},
                        'fulfilled', NOW()
                    )
                    """
                )
            
            # Update order status
            await execute_sql(
                f"""
                UPDATE orders
                SET status = 'completed',
                    completed_at = NOW()
                WHERE payment_id = '{payment_id}'
                """
            )
            
            # Record revenue
            await execute_sql(
                f"""
                INSERT INTO revenue_events (
                    event_type, amount_cents, currency,
                    source, metadata, recorded_at
                ) VALUES (
                    'revenue', {amount * 100}, 'usd',
                    'product_sale', 
                    '{json.dumps({
                        "payment_id": payment_id,
                        "items": items
                    })}'::jsonb,
                    NOW()
                )
                """
            )
            
            log_action(
                "order.fulfilled",
                f"Order fulfilled for payment {payment_id}",
                level="info",
                output_data={"payment_id": payment_id, "amount": amount}
            )
            
            return True
            
        except Exception as e:
            log_action(
                "order.failed",
                f"Order processing failed: {str(e)}",
                level="error",
                error_data={
                    "payment_id": payment_id,
                    "error": str(e)
                }
            )
            return False
