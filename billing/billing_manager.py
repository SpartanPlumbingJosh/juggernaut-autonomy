import os
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from decimal import Decimal

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class BillingManager:
    """Handle billing operations across Stripe and PayPal."""

    @staticmethod
    def cents_to_decimal(amount_cents: int) -> Decimal:
        """Convert cents to decimal currency value."""
        return Decimal(amount_cents) / 100

    @staticmethod
    def decimal_to_cents(amount: Decimal) -> int:
        """Convert decimal currency value to cents."""
        return int(amount * 100)

    async def create_customer(self, email: str, name: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create customer in both payment systems."""
        try:
            # Create Stripe customer
            stripe_customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )

            # Create PayPal customer
            paypal_customer = paypalrestsdk.Customer({
                "email": email,
                "name": name,
                "metadata": metadata or {}
            })
            if paypal_customer.create():
                return {
                    "stripe_customer_id": stripe_customer.id,
                    "paypal_customer_id": paypal_customer.id,
                    "success": True
                }
            return {"success": False, "error": "Failed to create PayPal customer"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_subscription(self, customer_id: str, plan_id: str, payment_gateway: str = "stripe") -> Dict[str, Any]:
        """Create subscription for customer."""
        try:
            if payment_gateway == "stripe":
                subscription = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"price": plan_id}],
                    expand=["latest_invoice.payment_intent"]
                )
                return {
                    "subscription_id": subscription.id,
                    "status": subscription.status,
                    "payment_gateway": "stripe",
                    "success": True
                }
            else:
                subscription = paypalrestsdk.Subscription({
                    "plan_id": plan_id,
                    "subscriber": {
                        "customer_id": customer_id
                    }
                })
                if subscription.create():
                    return {
                        "subscription_id": subscription.id,
                        "status": subscription.status,
                        "payment_gateway": "paypal",
                        "success": True
                    }
                return {"success": False, "error": "Failed to create PayPal subscription"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_transaction(self, execute_sql: Callable[[str], Dict[str, Any]], 
                               transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record transaction in revenue_tracking database."""
        try:
            amount_cents = self.decimal_to_cents(Decimal(transaction_data["amount"]))
            sql = f"""
            INSERT INTO revenue_events (
                id, experiment_id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                {f"'{transaction_data.get('experiment_id', '')}'" if transaction_data.get('experiment_id') else "NULL"},
                '{transaction_data['event_type']}',
                {amount_cents},
                '{transaction_data['currency']}',
                '{transaction_data['source']}',
                '{json.dumps(transaction_data.get('metadata', {}))}',
                NOW(),
                NOW()
            )
            """
            await execute_sql(sql)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: Dict[str, Any], signature: str, source: str) -> Dict[str, Any]:
        """Process webhook events from payment providers."""
        try:
            if source == "stripe":
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
                )
            else:
                event = paypalrestsdk.WebhookEvent.verify(
                    payload, signature, os.getenv("PAYPAL_WEBHOOK_SECRET")
                )

            # Handle different event types
            event_type = event["type"]
            data = event["data"]

            if event_type in ["invoice.payment_succeeded", "PAYMENT.SALE.COMPLETED"]:
                # Record successful payment
                amount = data["amount"] if source == "stripe" else data["amount"]["total"]
                currency = data["currency"] if source == "stripe" else data["amount"]["currency"]
                await self.record_transaction({
                    "event_type": "revenue",
                    "amount": amount,
                    "currency": currency,
                    "source": source,
                    "metadata": data
                })

            elif event_type in ["invoice.payment_failed", "PAYMENT.SALE.DENIED"]:
                # Handle failed payments
                await self.handle_failed_payment(data, source)

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_failed_payment(self, data: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Handle failed payment attempts and dunning management."""
        try:
            # Get customer details
            customer_id = data["customer"] if source == "stripe" else data["payer"]["payer_info"]["customer_id"]
            
            # Record failed payment attempt
            await self.record_transaction({
                "event_type": "payment_failed",
                "amount": 0,
                "currency": "USD",
                "source": source,
                "metadata": data
            })

            # Implement dunning logic
            if source == "stripe":
                stripe.Invoice.retry(data["id"])
            else:
                paypalrestsdk.Payment.find(data["id"]).retry()

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
