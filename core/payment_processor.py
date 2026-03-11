"""
Payment Processor - Handles all payment gateway integrations and transactions.
Supports Stripe and PayPal with failover capabilities.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
import stripe
import paypalrestsdk

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self):
        # Initialize payment gateways
        stripe.api_key = os.getenv('STRIPE_API_KEY')
        paypalrestsdk.configure({
            "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
            "client_id": os.getenv('PAYPAL_CLIENT_ID'),
            "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
        })
        self.primary_gateway = os.getenv('PRIMARY_GATEWAY', 'stripe')
        self.fallback_gateway = 'paypal' if self.primary_gateway == 'stripe' else 'stripe'

    async def process_payment(
        self,
        amount: float,
        currency: str,
        customer_data: Dict[str, Any],
        product_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Process payment with automatic failover between gateways.
        Returns (success, payment_details)
        """
        metadata = metadata or {}
        payment_methods = [self.primary_gateway, self.fallback_gateway]
        
        for gateway in payment_methods:
            try:
                if gateway == 'stripe':
                    return await self._process_stripe_payment(
                        amount, currency, customer_data, product_data, metadata
                    )
                else:
                    return await self._process_paypal_payment(
                        amount, currency, customer_data, product_data, metadata
                    )
            except Exception as e:
                logger.error(f"Payment failed with {gateway}: {str(e)}")
                continue
                
        return False, {"error": "All payment gateways failed"}

    async def _process_stripe_payment(
        self,
        amount: float,
        currency: str,
        customer_data: Dict[str, Any],
        product_data: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Process payment via Stripe"""
        try:
            # Create or retrieve customer
            customer = stripe.Customer.create(
                email=customer_data.get('email'),
                name=customer_data.get('name'),
                metadata=metadata
            )

            # Create payment intent
            payment_intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                customer=customer.id,
                description=product_data.get('description'),
                metadata={
                    **metadata,
                    'product_id': product_data.get('id'),
                    'system': 'spartan'
                }
            )

            # Confirm payment
            confirmed_intent = stripe.PaymentIntent.confirm(
                payment_intent.id,
                payment_method='pm_card_visa'  # In production, use customer's payment method
            )

            if confirmed_intent.status == 'succeeded':
                return True, {
                    "gateway": "stripe",
                    "payment_id": confirmed_intent.id,
                    "customer_id": customer.id,
                    "amount": amount,
                    "currency": currency,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            return False, {"error": f"Stripe payment failed: {confirmed_intent.last_payment_error}"}

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")

    async def _process_paypal_payment(
        self,
        amount: float,
        currency: str,
        customer_data: Dict[str, Any],
        product_data: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Process payment via PayPal"""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "transactions": [{
                    "amount": {
                        "total": str(amount),
                        "currency": currency.upper()
                    },
                    "description": product_data.get('description'),
                    "custom": json.dumps(metadata)
                }],
                "redirect_urls": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
            })

            if payment.create():
                # In production, you'd redirect user to payment.approval_url
                # For automation, we'll simulate approval
                if payment.execute({"payer_id": "fake_payer_id"}):  # Replace with actual payer ID
                    return True, {
                        "gateway": "paypal",
                        "payment_id": payment.id,
                        "amount": amount,
                        "currency": currency,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
            return False, {"error": f"PayPal payment failed: {payment.error}"}

        except Exception as e:
            raise Exception(f"PayPal error: {str(e)}")

    async def record_revenue_event(
        self,
        execute_sql: Callable[[str], Dict[str, Any]],
        payment_data: Dict[str, Any],
        product_data: Dict[str, Any],
        experiment_id: Optional[str] = None
    ) -> bool:
        """Record successful payment in revenue_events table"""
        try:
            attribution = {}
            if experiment_id:
                attribution["experiment_id"] = experiment_id

            sql = f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at, attribution
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(payment_data['amount'] * 100)},
                '{payment_data['currency']}',
                '{payment_data['gateway']}',
                '{json.dumps(product_data)}'::jsonb,
                '{payment_data['timestamp']}',
                NOW(),
                '{json.dumps(attribution)}'::jsonb
            )
            """
            await execute_sql(sql)
            return True
        except Exception as e:
            logger.error(f"Failed to record revenue event: {str(e)}")
            return False
