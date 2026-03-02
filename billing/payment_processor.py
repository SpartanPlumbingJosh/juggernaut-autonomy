import stripe
import json
from datetime import datetime
from typing import Dict, Any, Optional
from core.database import query_db, execute_db

class PaymentProcessor:
    def __init__(self, stripe_secret_key: str):
        stripe.api_key = stripe_secret_key
        
    async def create_customer(self, email: str, name: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer": customer}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return {"success": True, "subscription": subscription}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            # Handle specific event types
            if event['type'] == 'invoice.payment_succeeded':
                await self._handle_payment_success(event)
            elif event['type'] == 'invoice.payment_failed':
                await self._handle_payment_failure(event)
            elif event['type'] == 'customer.subscription.deleted':
                await self._handle_subscription_cancelled(event)
                
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def _handle_payment_success(self, event: Dict[str, Any]) -> None:
        """Log successful payments to revenue tracking."""
        invoice = event['data']['object']
        amount_cents = invoice['amount_paid']
        customer_id = invoice['customer']
        
        await execute_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{invoice['currency']}',
                'stripe',
                '{json.dumps(invoice)}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )
        
    async def _handle_payment_failure(self, event: Dict[str, Any]) -> None:
        """Handle failed payment attempts."""
        invoice = event['data']['object']
        # Implement retry logic or notify customer
        
    async def _handle_subscription_cancelled(self, event: Dict[str, Any]) -> None:
        """Handle subscription cancellations."""
        subscription = event['data']['object']
        # Update subscription status in database
