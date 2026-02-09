"""
Payment Processor - Handles Stripe and PayPal integrations for recurring payments,
one-time charges, and subscription management.
"""

import stripe
import paypalrestsdk
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

class PaymentProcessor:
    def __init__(self, stripe_api_key: str, paypal_client_id: str, paypal_secret: str):
        stripe.api_key = stripe_api_key
        paypalrestsdk.configure({
            "mode": "live",
            "client_id": paypal_client_id,
            "client_secret": paypal_secret
        })
        
    async def create_customer(self, email: str, payment_method: str, 
                            metadata: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """Create customer in both payment systems."""
        try:
            # Create Stripe customer
            stripe_customer = stripe.Customer.create(
                email=email,
                payment_method=payment_method,
                invoice_settings={
                    'default_payment_method': payment_method
                },
                metadata=metadata or {}
            )
            
            # Create PayPal billing agreement
            paypal_agreement = paypalrestsdk.BillingAgreement({
                "name": "Standard Agreement",
                "description": "Recurring Payment Agreement",
                "start_date": datetime.utcnow().isoformat() + "Z",
                "payer": {
                    "payment_method": "paypal",
                    "payer_info": {
                        "email": email
                    }
                },
                "plan": {
                    "type": "MERCHANT_INITIATED_BILLING",
                    "merchant_preferences": {
                        "return_url": "https://example.com/return",
                        "cancel_url": "https://example.com/cancel",
                        "notify_url": "https://example.com/notify"
                    }
                }
            })
            
            if paypal_agreement.create():
                return stripe_customer.id, paypal_agreement.id
            raise Exception("Failed to create PayPal agreement")
            
        except Exception as e:
            raise Exception(f"Payment processor error: {str(e)}")
            
    async def create_subscription(self, customer_id: str, price_id: str, 
                                 trial_days: int = 0) -> Dict[str, Any]:
        """Create subscription with optional trial."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                trial_period_days=trial_days,
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "payment_intent": subscription.latest_invoice.payment_intent
            }
        except Exception as e:
            raise Exception(f"Subscription creation failed: {str(e)}")
            
    async def handle_webhook(self, payload: bytes, sig_header: str, endpoint_secret: str) -> Dict[str, Any]:
        """Process webhook events from payment providers."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
            
            # Handle specific event types
            if event['type'] == 'payment_intent.succeeded':
                return self._handle_payment_success(event)
            elif event['type'] == 'invoice.payment_failed':
                return self._handle_payment_failure(event)
            elif event['type'] == 'customer.subscription.deleted':
                return self._handle_subscription_cancelled(event)
                
            return {"status": "unhandled_event"}
        except Exception as e:
            raise Exception(f"Webhook processing failed: {str(e)}")
            
    def _handle_payment_success(self, event: Any) -> Dict[str, Any]:
        """Handle successful payment."""
        payment_intent = event['data']['object']
        return {
            "status": "success",
            "amount": payment_intent['amount_received'],
            "currency": payment_intent['currency'],
            "customer_id": payment_intent['customer']
        }
        
    def _handle_payment_failure(self, event: Any) -> Dict[str, Any]:
        """Handle failed payment attempt."""
        invoice = event['data']['object']
        return {
            "status": "failure",
            "invoice_id": invoice['id'],
            "customer_id": invoice['customer'],
            "attempt_count": invoice['attempt_count']
        }
        
    def _handle_subscription_cancelled(self, event: Any) -> Dict[str, Any]:
        """Handle subscription cancellation."""
        subscription = event['data']['object']
        return {
            "status": "cancelled",
            "subscription_id": subscription['id'],
            "customer_id": subscription['customer'],
            "cancel_at_period_end": subscription['cancel_at_period_end']
        }
