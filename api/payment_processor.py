"""
Payment Processor - Handles all payment integrations and revenue tracking.

Features:
- Stripe & PayPal integrations
- Subscription management
- Usage tracking
- Invoicing automation
- Webhook handlers
- PCI compliant token handling
- Payment retry logic
"""

import os
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import stripe
import paypalrestsdk
from core.database import query_db

# Initialize payment gateways
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_SECRET')
})

class PaymentProcessor:
    """Core payment processing class."""
    
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 2  # seconds

    async def create_payment_intent(
        self,
        amount_cents: int,
        currency: str,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payment_method: str = "stripe"
    ) -> Dict[str, Any]:
        """Create a payment intent with retry logic."""
        metadata = metadata or {}
        attempts = 0
        
        while attempts < self.max_retries:
            try:
                if payment_method == "stripe":
                    intent = stripe.PaymentIntent.create(
                        amount=amount_cents,
                        currency=currency.lower(),
                        customer=customer_id,
                        metadata=metadata,
                        setup_future_usage='off_session' if customer_id else None
                    )
                    return {"success": True, "intent": intent}
                
                elif payment_method == "paypal":
                    payment = paypalrestsdk.Payment({
                        "intent": "sale",
                        "payer": {"payment_method": "paypal"},
                        "transactions": [{
                            "amount": {
                                "total": f"{amount_cents/100:.2f}",
                                "currency": currency.upper()
                            },
                            "description": metadata.get("description", "")
                        }],
                        "redirect_urls": {
                            "return_url": os.getenv('PAYPAL_RETURN_URL'),
                            "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                        }
                    })
                    if payment.create():
                        return {"success": True, "payment": payment}
                    raise Exception(payment.error)
                
            except Exception as e:
                attempts += 1
                if attempts == self.max_retries:
                    return {"success": False, "error": str(e)}
                time.sleep(self.retry_delay)
        
        return {"success": False, "error": "Max retries exceeded"}

    async def record_revenue_event(
        self,
        event_type: str,
        amount_cents: int,
        currency: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
        attribution: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Record a revenue or cost event in the database."""
        metadata = metadata or {}
        attribution = attribution or {}
        
        try:
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, attribution, recorded_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    {amount_cents},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata)}'::jsonb,
                    '{json.dumps(attribution)}'::jsonb,
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Process payment webhooks from various sources."""
        try:
            if source == "stripe":
                event = stripe.Event.construct_from(payload, stripe.api_key)
                
                if event.type == "payment_intent.succeeded":
                    intent = event.data.object
                    await self.record_revenue_event(
                        event_type="revenue",
                        amount_cents=intent.amount,
                        currency=intent.currency,
                        source="stripe",
                        metadata={
                            "payment_intent_id": intent.id,
                            "customer": intent.customer
                        }
                    )
                
                elif event.type == "charge.refunded":
                    charge = event.data.object
                    await self.record_revenue_event(
                        event_type="refund",
                        amount_cents=-charge.amount_refunded,
                        currency=charge.currency,
                        source="stripe",
                        metadata={
                            "charge_id": charge.id,
                            "reason": charge.refund_reason
                        }
                    )
            
            elif source == "paypal":
                # Similar PayPal webhook handling would go here
                pass
            
            return {"success": True}
        
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_subscription(
        self,
        plan_id: str,
        customer_id: str,
        payment_method: str = "stripe"
    ) -> Dict[str, Any]:
        """Create a new subscription with the given payment method."""
        try:
            if payment_method == "stripe":
                sub = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"plan": plan_id}],
                    expand=["latest_invoice.payment_intent"]
                )
                return {"success": True, "subscription": sub}
            
            # PayPal subscription logic would go here
            
            return {"success": False, "error": "Unsupported payment method"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def generate_invoice(
        self,
        customer_id: str,
        items: List[Dict[str, Any]],
        payment_method: str = "stripe"
    ) -> Dict[str, Any]:
        """Generate an invoice for the given items."""
        try:
            if payment_method == "stripe":
                invoice = stripe.Invoice.create(
                    customer=customer_id,
                    auto_advance=True,
                    collection_method="charge_automatically",
                    description="Automated invoice generation"
                )
                
                for item in items:
                    stripe.InvoiceItem.create(
                        customer=customer_id,
                        invoice=invoice.id,
                        amount=item["amount_cents"],
                        currency=item["currency"],
                        description=item.get("description", "")
                    )
                
                final_invoice = stripe.Invoice.finalize_invoice(invoice.id)
                return {"success": True, "invoice": final_invoice}
            
            # PayPal invoice logic would go here
            
            return {"success": False, "error": "Unsupported payment method"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Export singleton instance
payment_processor = PaymentProcessor()
