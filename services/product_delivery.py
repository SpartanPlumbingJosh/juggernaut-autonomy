"""
Product Delivery Service - Handles automated product/service fulfillment.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

logger = logging.getLogger(__name__)

class DeliveryService:
    def __init__(self, payment_processor):
        self.payment_processor = payment_processor

    async def process_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle complete order flow from payment to delivery."""
        try:
            # Validate order data
            if not all(k in order_data for k in ['customer_id', 'product_id', 'amount']):
                raise ValueError("Missing required order fields")

            # Process payment
            payment_result = await self.payment_processor.charge(
                amount=order_data['amount'],
                customer_id=order_data['customer_id'],
                description=f"Product {order_data['product_id']}"
            )

            if not payment_result.get('success'):
                raise ValueError(f"Payment failed: {payment_result.get('error')}")

            # Record transaction
            transaction_id = await self._record_transaction(
                order_data=order_data,
                payment_data=payment_result
            )

            # Fulfill order
            delivery_result = await self._fulfill_order(order_data)

            return {
                "success": True,
                "transaction_id": transaction_id,
                "delivery_status": delivery_result['status'],
                "payment_id": payment_result['payment_id']
            }

        except Exception as e:
            logger.error(f"Order processing failed: {str(e)}")
            # Attempt refund if payment was taken but delivery failed
            if 'payment_id' in locals() and 'payment_result' in locals():
                await self._handle_failure(order_data, payment_result)
            return {
                "success": False,
                "error": str(e),
                "order_data": order_data
            }

    async def _record_transaction(self, order_data: Dict, payment_data: Dict) -> str:
        """Record successful transaction in database."""
        sql = """
        INSERT INTO transactions (
            id, customer_id, product_id, amount, 
            payment_id, status, created_at
        ) VALUES (
            gen_random_uuid(), %s, %s, %s, %s, 'completed', NOW()
        )
        RETURNING id
        """
        result = await query_db(
            sql,
            params=(
                order_data['customer_id'],
                order_data['product_id'],
                order_data['amount'],
                payment_data['payment_id']
            )
        )
        return result['rows'][0]['id']

    async def _fulfill_order(self, order_data: Dict) -> Dict:
        """Execute product/service delivery logic."""
        # TODO: Implement actual delivery mechanism based on product type
        # This could be:
        # - Digital download generation
        # - API access provisioning  
        # - Physical shipment tracking
        # - Service scheduling
        
        # For now, just simulate successful delivery
        return {
            "status": "delivered",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def _handle_failure(self, order_data: Dict, payment_data: Dict):
        """Handle failed order scenarios."""
        try:
            # Attempt refund
            if payment_data.get('payment_id'):
                await self.payment_processor.refund(
                    payment_id=payment_data['payment_id'],
                    amount=order_data['amount']
                )
            
            # Record failed transaction
            await query_db(
                """
                INSERT INTO failed_transactions (
                    customer_id, product_id, amount, 
                    payment_id, error, created_at
                ) VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                params=(
                    order_data['customer_id'],
                    order_data['product_id'],
                    order_data['amount'],
                    payment_data.get('payment_id'),
                    "Order processing failed"
                )
            )
        except Exception as e:
            logger.error(f"Failure handling failed: {str(e)}")
