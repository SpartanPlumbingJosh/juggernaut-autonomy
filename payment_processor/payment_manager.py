import os
import stripe
import paypalrestsdk
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from core.database import query_db, execute_db

# Initialize payment gateways
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})

class PaymentManager:
    """Handles payment processing, subscriptions, and invoicing."""
    
    def __init__(self):
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    async def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a customer in Stripe and PayPal."""
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
            return {"error": "Failed to create PayPal customer", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str = 'stripe') -> Dict:
        """Create a subscription for a customer."""
        try:
            if payment_method == 'stripe':
                subscription = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"plan": plan_id}],
                    expand=['latest_invoice.payment_intent']
                )
                return {
                    "subscription_id": subscription.id,
                    "status": subscription.status,
                    "success": True
                }
            else:
                agreement = paypalrestsdk.BillingAgreement({
                    "name": "Subscription Agreement",
                    "description": "Recurring Payment Agreement",
                    "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
                    "plan": {"id": plan_id},
                    "payer": {"payment_method": "paypal"}
                })
                if agreement.create():
                    return {
                        "subscription_id": agreement.id,
                        "status": agreement.state,
                        "success": True
                    }
                return {"error": "Failed to create PayPal subscription", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """Process payment webhooks from Stripe and PayPal."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            # Handle Stripe events
            if event['type'] == 'invoice.payment_succeeded':
                await self._handle_payment_success(event['data']['object'])
            elif event['type'] == 'invoice.payment_failed':
                await self._handle_payment_failure(event['data']['object'])
            elif event['type'] == 'customer.subscription.deleted':
                await self._handle_subscription_cancellation(event['data']['object'])
            
            return {"success": True}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    async def _handle_payment_success(self, invoice: Dict) -> None:
        """Handle successful payment."""
        await execute_db(
            f"""
            INSERT INTO payments (id, customer_id, amount, currency, status, payment_method, created_at)
            VALUES ('{invoice['id']}', '{invoice['customer']}', {invoice['amount_paid']}, 
                    '{invoice['currency']}', 'paid', 'stripe', NOW())
            """
        )
    
    async def _handle_payment_failure(self, invoice: Dict) -> None:
        """Handle failed payment and trigger dunning process."""
        await execute_db(
            f"""
            INSERT INTO payment_failures (id, customer_id, amount, currency, reason, created_at)
            VALUES ('{invoice['id']}', '{invoice['customer']}', {invoice['amount_due']}, 
                    '{invoice['currency']}', '{invoice['status']}', NOW())
            """
        )
        # Trigger dunning process
        await self._start_dunning_process(invoice['customer'])
    
    async def _handle_subscription_cancellation(self, subscription: Dict) -> None:
        """Handle subscription cancellation."""
        await execute_db(
            f"""
            UPDATE subscriptions
            SET status = 'canceled', canceled_at = NOW()
            WHERE id = '{subscription['id']}'
            """
        )
    
    async def _start_dunning_process(self, customer_id: str) -> None:
        """Start dunning process for failed payments."""
        # Implement retry logic and notifications
        pass
