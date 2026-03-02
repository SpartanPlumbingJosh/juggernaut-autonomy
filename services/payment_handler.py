import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from core.database import query_db

class PaymentHandler:
    """Process payments and log revenue events."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def process_payment(
        self, 
        amount_cents: int,
        currency: str,
        payment_method: str,
        customer_id: str,
        product_id: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Process a payment and log the revenue event."""
        try:
            # 1. Process payment (integration with Stripe/PayPal could go here)
            self.logger.info(f"Processing payment of {amount_cents} {currency} via {payment_method}")
            
            # 2. Record revenue event
            revenue_event = {
                "event_type": "revenue",
                "amount_cents": amount_cents,
                "currency": currency,
                "source": payment_method,
                "customer_id": customer_id,
                "product_id": product_id,
                "metadata": metadata or {},
                "recorded_at": datetime.now(timezone.utc).isoformat()
            }

            # 3. Deliver product/service
            await self._deliver_product(product_id, customer_id)

            # 4. Record in database
            await self._log_revenue_event(revenue_event)

            return {"success": True, "event_id": revenue_event.get("id")}

        except Exception as e:
            self.logger.error(f"Payment processing failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _deliver_product(self, product_id: str, customer_id: str):
        """Handle product/service delivery."""
        # Add your product delivery logic here
        self.logger.info(f"Delivering product {product_id} to customer {customer_id}")
        # Could be: API call, email sending, digital download, etc.
        return {"success": True}

    async def _log_revenue_event(self, event: Dict) -> Dict:
        """Log revenue event to database."""
        try:
            sql = """
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, customer_id, product_id, 
                metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                %(event_type)s,
                %(amount_cents)s,
                %(currency)s,
                %(source)s,
                %(customer_id)s,
                %(product_id)s,
                %(metadata)s::jsonb,
                %(recorded_at)s
            )
            RETURNING id
            """
            result = await query_db(sql, event)
            return {"success": True, "id": result["rows"][0]["id"]}
        except Exception as e:
            self.logger.error(f"Failed to log revenue event: {str(e)}")
            raise

    async def handle_webhook(self, payload: Dict) -> Dict:
        """Process payment webhook notification."""
        try:
            event_type = payload.get("type")
            
            if event_type == "payment.success":
                amount = int(float(payload["amount"]) * 100)  # convert dollar amount to cents
                return await self.process_payment(
                    amount_cents=amount,
                    currency=payload["currency"],
                    payment_method=payload["payment_method"],
                    customer_id=payload["customer"],
                    product_id=payload["product_id"],
                    metadata=payload.get("metadata", {})
                )
            else:
                self.logger.info(f"Ignoring webhook event: {event_type}")
                return {"success": True, "message": "Event not processed"}

        except Exception as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
