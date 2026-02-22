"""
Payment Processor - Handles payment webhooks and transaction processing.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from core.database import execute_sql
from core.logging import log_action

class PaymentProcessor:
    """Process payments from various payment gateways."""
    
    def __init__(self):
        self.supported_gateways = ["stripe", "paypal", "braintree"]
    
    async def handle_webhook(self, gateway: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment webhook from supported gateways."""
        if gateway not in self.supported_gateways:
            return {"success": False, "error": f"Unsupported gateway: {gateway}"}
        
        try:
            event_type = payload.get("type")
            event_data = payload.get("data", {})
            
            if event_type == "payment.succeeded":
                return await self._process_successful_payment(gateway, event_data)
            elif event_type == "payment.failed":
                return await self._process_failed_payment(gateway, event_data)
            elif event_type == "refund.created":
                return await self._process_refund(gateway, event_data)
            else:
                return {"success": False, "error": f"Unhandled event type: {event_type}"}
        except Exception as e:
            log_action(
                "payment.webhook_error",
                f"Failed to process {gateway} webhook",
                level="error",
                error_data={"error": str(e), "payload": payload}
            )
            return {"success": False, "error": str(e)}
    
    async def _process_successful_payment(self, gateway: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Record a successful payment."""
        try:
            amount_cents = int(float(data.get("amount")) * 100)
            currency = data.get("currency", "usd").lower()
            customer_id = data.get("customer_id", "")
            payment_id = data.get("id", "")
            metadata = data.get("metadata", {})
            
            # Record revenue event
            await execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount_cents},
                    '{currency}',
                    '{gateway}',
                    '{json.dumps(metadata)}'::jsonb,
                    NOW(),
                    NOW()
                )
                """
            )
            
            # Trigger product delivery
            await self._trigger_product_delivery(customer_id, payment_id, metadata)
            
            return {"success": True}
        except Exception as e:
            log_action(
                "payment.processing_error",
                f"Failed to process successful payment",
                level="error",
                error_data={"error": str(e), "data": data}
            )
            return {"success": False, "error": str(e)}
    
    async def _trigger_product_delivery(self, customer_id: str, payment_id: str, metadata: Dict[str, Any]) -> None:
        """Trigger product/service delivery based on payment."""
        product_type = metadata.get("product_type", "digital")
        
        if product_type == "digital":
            await self._deliver_digital_product(customer_id, payment_id, metadata)
        elif product_type == "subscription":
            await self._activate_subscription(customer_id, payment_id, metadata)
        elif product_type == "physical":
            await self._queue_physical_shipment(customer_id, payment_id, metadata)
    
    async def _deliver_digital_product(self, customer_id: str, payment_id: str, metadata: Dict[str, Any]) -> None:
        """Deliver digital product."""
        # Implementation would send email with download links, etc.
        pass
    
    async def _activate_subscription(self, customer_id: str, payment_id: str, metadata: Dict[str, Any]) -> None:
        """Activate subscription."""
        # Implementation would update subscription status
        pass
    
    async def _queue_physical_shipment(self, customer_id: str, payment_id: str, metadata: Dict[str, Any]) -> None:
        """Queue physical product for shipment."""
        # Implementation would integrate with shipping API
        pass
    
    async def _process_failed_payment(self, gateway: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment."""
        # Implementation would notify customer and retry logic
        pass
    
    async def _process_refund(self, gateway: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process refund."""
        # Implementation would handle refunds
        pass
