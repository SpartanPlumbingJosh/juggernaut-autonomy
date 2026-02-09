"""
Core billing systems - Payment processing, subscriptions, and invoicing.

Integrations:
- Stripe
- PayPal
- Automated invoicing
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import stripe
from paypalrestsdk import Payment

logger = logging.getLogger(__name__)

class BillingSystem:
    def __init__(self, stripe_api_key: str, paypal_client_id: str, paypal_secret: str):
        self.stripe_api_key = stripe_api_key
        self.paypal_client_id = paypal_client_id 
        self.paypal_secret = paypal_secret
        
        stripe.api_key = stripe_api_key
        paypalrestsdk.configure({
            "mode": "live",
            "client_id": paypal_client_id,
            "client_secret": paypal_secret
        })

    async def create_stripe_customer(self, email: str, name: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata
            )
            return {"success": True, "customer_id": customer.id}
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_paypal_payment(self, amount: float, currency: str, description: str) -> Dict[str, Any]:
        """Create a PayPal payment."""
        try:
            payment = Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": currency
                    },
                    "description": description
                }],
                "redirect_urls": {
                    "return_url": "https://example.com/success",
                    "cancel_url": "https://example.com/cancel"
                }
            })
            
            if payment.create():
                return {"success": True, "payment_id": payment.id}
            return {"success": False, "error": "PayPal payment creation failed"}
        except Exception as e:
            logger.error(f"PayPal payment creation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_subscription(self, customer_id: str, plan_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}],
                metadata=metadata
            )
            return {"success": True, "subscription_id": subscription.id}
        except stripe.error.StripeError as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def generate_invoice(self, customer_id: str, amount: float, currency: str, description: str) -> Dict[str, Any]:
        """Generate and send an invoice."""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                auto_advance=True,
                collection_method="send_invoice",
                days_until_due=7,
                description=description,
                metadata={"auto_generated": True}
            )
            
            invoice_item = stripe.InvoiceItem.create(
                customer=customer_id,
                amount=int(amount * 100),
                currency=currency,
                description=description,
                invoice=invoice.id
            )
            
            invoice.send_invoice()
            return {"success": True, "invoice_id": invoice.id}
        except stripe.error.StripeError as e:
            logger.error(f"Invoice generation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def process_payment(self, payment_method: str, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process a payment through the appropriate gateway."""
        if payment_method == "stripe":
            try:
                payment_intent = stripe.PaymentIntent.create(
                    amount=int(amount * 100),
                    currency=currency,
                    metadata=metadata
                )
                return {"success": True, "payment_id": payment_intent.id}
            except stripe.error.StripeError as e:
                logger.error(f"Stripe payment failed: {str(e)}")
                return {"success": False, "error": str(e)}
        elif payment_method == "paypal":
            return await self.create_paypal_payment(amount, currency, metadata.get("description", ""))
        else:
            return {"success": False, "error": "Unsupported payment method"}

    async def handle_webhook(self, payload: Dict[str, Any], signature: str, endpoint_secret: str) -> Dict[str, Any]:
        """Handle webhook events from payment providers."""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, endpoint_secret
            )
            
            if event.type == "payment_intent.succeeded":
                # Handle successful payment
                pass
            elif event.type == "invoice.payment_succeeded":
                # Handle successful invoice payment
                pass
            elif event.type == "customer.subscription.created":
                # Handle new subscription
                pass
            
            return {"success": True}
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {str(e)}")
            return {"success": False, "error": str(e)}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            return {"success": False, "error": str(e)}
