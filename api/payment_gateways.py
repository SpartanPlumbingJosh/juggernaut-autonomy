"""
Payment Gateway Integration - Handle subscriptions, invoices, and payment processing.

Supports:
- Stripe
- PayPal
"""

import os
import stripe
import paypalrestsdk
from datetime import datetime
from typing import Dict, Optional, List
from core.database import query_db

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class PaymentGateway:
    """Base class for payment gateway implementations."""
    
    def create_customer(self, email: str, name: str, metadata: Dict[str, str] = {}) -> Dict[str, Any]:
        raise NotImplementedError
        
    def create_subscription(self, customer_id: str, plan_id: str, trial_days: int = 0) -> Dict[str, Any]:
        raise NotImplementedError
        
    def create_invoice(self, customer_id: str, amount: float, currency: str = "usd") -> Dict[str, Any]:
        raise NotImplementedError
        
    def handle_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

class StripeGateway(PaymentGateway):
    """Stripe payment gateway implementation."""
    
    def create_customer(self, email: str, name: str, metadata: Dict[str, str] = {}) -> Dict[str, Any]:
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata
            )
            return {"success": True, "customer_id": customer.id}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    def create_subscription(self, customer_id: str, plan_id: str, trial_days: int = 0) -> Dict[str, Any]:
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                trial_period_days=trial_days
            )
            return {"success": True, "subscription_id": subscription.id}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    def create_invoice(self, customer_id: str, amount: float, currency: str = "usd") -> Dict[str, Any]:
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                auto_advance=True
            )
            return {"success": True, "invoice_id": invoice.id, "payment_url": invoice.hosted_invoice_url}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    def handle_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
            )
            
            # Handle different event types
            if event["type"] == "invoice.payment_succeeded":
                return self._handle_payment_success(event["data"]["object"])
            elif event["type"] == "invoice.payment_failed":
                return self._handle_payment_failure(event["data"]["object"])
            elif event["type"] == "customer.subscription.deleted":
                return self._handle_subscription_cancelled(event["data"]["object"])
                
            return {"success": True, "handled": False}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _handle_payment_success(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        # Record successful payment in revenue_events
        amount = invoice["amount_paid"] / 100
        currency = invoice["currency"]
        customer_id = invoice["customer"]
        
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(amount * 100)},
                '{currency}',
                'stripe',
                '{{"invoice_id": "{invoice["id"]}", "customer_id": "{customer_id}"}}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
        return {"success": True, "handled": True}
        
    def _handle_payment_failure(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        # Handle failed payment (e.g., send email, retry logic)
        customer_id = invoice["customer"]
        attempt_count = invoice["attempt_count"]
        
        # TODO: Implement retry logic or customer notification
        return {"success": True, "handled": True}
        
    def _handle_subscription_cancelled(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        # Handle subscription cancellation
        customer_id = subscription["customer"]
        
        # TODO: Implement cancellation logic
        return {"success": True, "handled": True}

class PayPalGateway(PaymentGateway):
    """PayPal payment gateway implementation."""
    
    def create_customer(self, email: str, name: str, metadata: Dict[str, str] = {}) -> Dict[str, Any]:
        # PayPal doesn't have a direct customer creation API
        return {"success": True, "customer_id": email}
        
    def create_subscription(self, customer_id: str, plan_id: str, trial_days: int = 0) -> Dict[str, Any]:
        try:
            subscription = paypalrestsdk.BillingPlan.find(plan_id)
            agreement = paypalrestsdk.BillingAgreement({
                "name": "Subscription Agreement",
                "description": "Recurring subscription",
                "start_date": (datetime.utcnow() + timedelta(days=trial_days)).isoformat() + "Z",
                "payer": {
                    "payment_method": "paypal"
                },
                "plan": {
                    "id": plan_id
                }
            })
            
            if agreement.create():
                return {"success": True, "subscription_id": agreement.id}
            return {"success": False, "error": agreement.error}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def create_invoice(self, customer_id: str, amount: float, currency: str = "usd") -> Dict[str, Any]:
        try:
            invoice = paypalrestsdk.Invoice({
                "merchant_info": {
                    "email": os.getenv("PAYPAL_MERCHANT_EMAIL")
                },
                "billing_info": [{
                    "email": customer_id
                }],
                "items": [{
                    "name": "Service",
                    "quantity": 1,
                    "unit_price": {
                        "currency": currency,
                        "value": str(amount)
                    }
                }],
                "note": "Thank you for your business!",
                "payment_term": {
                    "term_type": "NET_30"
                }
            })
            
            if invoice.create() and invoice.send():
                return {"success": True, "invoice_id": invoice.id}
            return {"success": False, "error": invoice.error}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def handle_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        try:
            # Verify webhook signature
            if not paypalrestsdk.WebhookEvent.verify(
                payload,
                signature,
                os.getenv("PAYPAL_WEBHOOK_ID")
            ):
                return {"success": False, "error": "Invalid signature"}
                
            event = paypalrestsdk.WebhookEvent(payload)
            
            # Handle different event types
            if event.event_type == "PAYMENT.SALE.COMPLETED":
                return self._handle_payment_success(event.resource)
            elif event.event_type == "PAYMENT.SALE.DENIED":
                return self._handle_payment_failure(event.resource)
            elif event.event_type == "BILLING.SUBSCRIPTION.CANCELLED":
                return self._handle_subscription_cancelled(event.resource)
                
            return {"success": True, "handled": False}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _handle_payment_success(self, sale: Dict[str, Any]) -> Dict[str, Any]:
        # Record successful payment in revenue_events
        amount = float(sale["amount"]["total"])
        currency = sale["amount"]["currency"]
        customer_id = sale["payer"]["payer_info"]["email"]
        
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(amount * 100)},
                '{currency}',
                'paypal',
                '{{"sale_id": "{sale["id"]}", "customer_id": "{customer_id}"}}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
        return {"success": True, "handled": True}
        
    def _handle_payment_failure(self, sale: Dict[str, Any]) -> Dict[str, Any]:
        # Handle failed payment
        customer_id = sale["payer"]["payer_info"]["email"]
        
        # TODO: Implement retry logic or customer notification
        return {"success": True, "handled": True}
        
    def _handle_subscription_cancelled(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        # Handle subscription cancellation
        customer_id = subscription["subscriber"]["email_address"]
        
        # TODO: Implement cancellation logic
        return {"success": True, "handled": True}

def get_gateway(gateway_name: str) -> PaymentGateway:
    """Get payment gateway instance by name."""
    gateways = {
        "stripe": StripeGateway(),
        "paypal": PayPalGateway()
    }
    return gateways.get(gateway_name.lower())

__all__ = ["get_gateway", "PaymentGateway", "StripeGateway", "PayPalGateway"]
