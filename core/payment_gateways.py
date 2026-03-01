import os
import stripe
import paypalrestsdk
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum

class PaymentGateway(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

class PaymentStatus(Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PENDING = "pending"
    REFUNDED = "refunded"

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class PaymentProcessor:
    """Handle payment processing across multiple gateways."""
    
    def __init__(self, gateway: PaymentGateway):
        self.gateway = gateway

    def create_customer(self, email: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a customer in the payment gateway."""
        if self.gateway == PaymentGateway.STRIPE:
            return stripe.Customer.create(email=email, metadata=metadata or {})
        elif self.gateway == PaymentGateway.PAYPAL:
            # PayPal doesn't have direct customer objects
            return {"id": email, "email": email}
        raise ValueError(f"Unsupported gateway: {self.gateway}")

    def create_payment_intent(self, amount: int, currency: str, customer_id: str, 
                            metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent."""
        if self.gateway == PaymentGateway.STRIPE:
            return stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata or {}
            )
        elif self.gateway == PaymentGateway.PAYPAL:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount/100:.2f}",
                        "currency": currency
                    }
                }],
                "redirect_urls": {
                    "return_url": os.getenv("PAYPAL_RETURN_URL"),
                    "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                }
            })
            if payment.create():
                return payment
            raise Exception(payment.error)
        raise ValueError(f"Unsupported gateway: {self.gateway}")

    def handle_webhook(self, payload: str, signature: Optional[str] = None) -> Dict:
        """Process webhook events from payment gateway."""
        if self.gateway == PaymentGateway.STRIPE:
            event = stripe.Webhook.construct_event(
                payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
            )
            return self._process_stripe_event(event)
        elif self.gateway == PaymentGateway.PAYPAL:
            event = paypalrestsdk.WebhookEvent.verify(
                payload,
                os.getenv("PAYPAL_WEBHOOK_ID"),
                os.getenv("PAYPAL_WEBHOOK_SECRET")
            )
            return self._process_paypal_event(event)
        raise ValueError(f"Unsupported gateway: {self.gateway}")

    def _process_stripe_event(self, event: stripe.Event) -> Dict:
        """Process Stripe webhook event."""
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'payment_intent.succeeded':
            return self._record_payment(
                gateway=PaymentGateway.STRIPE,
                payment_id=data['id'],
                amount=data['amount'],
                currency=data['currency'],
                status=PaymentStatus.SUCCEEDED,
                customer_id=data['customer'],
                metadata=data.get('metadata', {})
            )
        # Handle other event types...
        return {"status": "unhandled_event"}

    def _process_paypal_event(self, event: paypalrestsdk.WebhookEvent) -> Dict:
        """Process PayPal webhook event."""
        event_type = event.event_type
        resource = event.resource
        
        if event_type == 'PAYMENT.CAPTURE.COMPLETED':
            return self._record_payment(
                gateway=PaymentGateway.PAYPAL,
                payment_id=resource['id'],
                amount=int(float(resource['amount']['value']) * 100),
                currency=resource['amount']['currency_code'],
                status=PaymentStatus.SUCCEEDED,
                customer_id=resource['payer']['email_address'],
                metadata={}
            )
        # Handle other event types...
        return {"status": "unhandled_event"}

    def _record_payment(self, gateway: PaymentGateway, payment_id: str, amount: int,
                      currency: str, status: PaymentStatus, customer_id: str,
                      metadata: Dict) -> Dict:
        """Record payment in the revenue system."""
        # This would be implemented in the RevenueTracker class
        return {
            "gateway": gateway.value,
            "payment_id": payment_id,
            "amount": amount,
            "currency": currency,
            "status": status.value,
            "customer_id": customer_id,
            "metadata": metadata
        }

class SubscriptionManager:
    """Handle subscription lifecycle management."""
    
    def __init__(self, gateway: PaymentGateway):
        self.gateway = gateway
        self.processor = PaymentProcessor(gateway)

    def create_subscription(self, customer_id: str, plan_id: str, 
                          metadata: Optional[Dict] = None) -> Dict:
        """Create a new subscription."""
        if self.gateway == PaymentGateway.STRIPE:
            return stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}],
                metadata=metadata or {}
            )
        elif self.gateway == PaymentGateway.PAYPAL:
            agreement = paypalrestsdk.BillingAgreement({
                "name": "Subscription Agreement",
                "description": "Recurring subscription",
                "start_date": datetime.utcnow().isoformat() + "Z",
                "plan": {"id": plan_id},
                "payer": {"payment_method": "paypal"}
            })
            if agreement.create():
                return agreement
            raise Exception(agreement.error)
        raise ValueError(f"Unsupported gateway: {self.gateway}")

    def handle_dunning(self, subscription_id: str) -> Dict:
        """Handle failed payment recovery."""
        if self.gateway == PaymentGateway.STRIPE:
            # Retry the payment
            subscription = stripe.Subscription.retrieve(subscription_id)
            invoice = stripe.Invoice.retrieve(subscription.latest_invoice)
            return stripe.Invoice.pay(invoice.id)
        elif self.gateway == PaymentGateway.PAYPAL:
            # PayPal handles retries automatically
            return {"status": "pending"}
        raise ValueError(f"Unsupported gateway: {self.gateway}")

class InvoiceManager:
    """Handle invoice generation and management."""
    
    def generate_invoice(self, payment_id: str) -> Dict:
        """Generate an invoice for a payment."""
        # Implementation would depend on the gateway
        return {"invoice_id": f"INV-{payment_id}", "status": "generated"}

class RevenueTracker:
    """Track revenue events and integrate with payment systems."""
    
    def __init__(self):
        self.stripe_processor = PaymentProcessor(PaymentGateway.STRIPE)
        self.paypal_processor = PaymentProcessor(PaymentGateway.PAYPAL)

    def record_revenue_event(self, event_type: str, amount_cents: int, 
                           currency: str, source: str, metadata: Dict) -> Dict:
        """Record a revenue event."""
        # This would integrate with the existing revenue_events table
        return {
            "event_type": event_type,
            "amount_cents": amount_cents,
            "currency": currency,
            "source": source,
            "metadata": metadata,
            "recorded_at": datetime.utcnow().isoformat()
        }
