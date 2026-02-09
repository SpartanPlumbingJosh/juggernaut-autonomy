"""
Payment Processor - Handles payments and digital delivery via Stripe/PayPal.

Key Features:
- Processes payments from multiple providers 
- Handles webhooks for instant delivery
- Automated digital provisioning
- Generates revenue events
"""

import json
import logging
import stripe
import paypalrestsdk
from typing import Dict, Any, Optional
from datetime import datetime
from core.database import query_db
from core.delivery import DigitalDeliveryService

# Initialize services
stripe.api_key = "sk_test_xxx"  # Should be from config
paypalrestsdk.configure({
    "mode": "sandbox",  # or "live"
    "client_id": "xxx",
    "client_secret": "xxx"
})
delivery_service = DigitalDeliveryService()

class PaymentProcessor:
    """Handles payment processing and fulfillment."""
    
    async def handle_stripe_payment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process Stripe payment intent webhook."""
        event = stripe.Event.construct_from(payload, stripe.api_key)
        
        if event.type != 'payment_intent.succeeded':
            return {'status': 'skipped', 'reason': 'not_payment_success'}
            
        payment_intent = event.data.object
        await self._record_payment(
            provider='stripe',
            transaction_id=payment_intent.id,
            amount=payment_intent.amount,
            currency=payment_intent.currency,
            customer_id=payment_intent.customer,
            metadata=payment_intent.metadata
        )
        return {'status': 'processed'}

    async def handle_paypal_payment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process PayPal payment webhook."""
        if payload.get('event_type') != 'PAYMENT.SALE.COMPLETED':
            return {'status': 'skipped', 'reason': 'not_payment_success'}
            
        sale = payload.get('resource', {})
        await self._record_payment(
            provider='paypal',
            transaction_id=sale.get('id'),
            amount=int(float(sale.get('amount', {}).get('total', 0)) * 100),
            currency=sale.get('amount', {}).get('currency'),
            customer_id=payload.get('payer', {}).get('payer_info', {}).get('payer_id'),
            metadata=payload.get('custom', {})
        )
        return {'status': 'processed'}

    async def _record_payment(self, 
        provider: str,
        transaction_id: str,
        amount: int,
        currency: str,
        customer_id: Optional[str],
        metadata: Dict[str, Any]
    ) -> None:
        """Record payment and trigger fulfillment."""
        product_id = metadata.get('product_id')
        if not product_id:
            logging.error(f"Missing product_id in payment metadata: {transaction_id}")
            return

        # Create revenue event
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, recorded_at, created_at,
                metadata, attribution
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount},
                '{currency}',
                '{provider}',
                NOW(),
                NOW(),
                '{json.dumps(metadata)}'::jsonb,
                jsonb_build_object(
                    'payment_id', '{transaction_id}',
                    'customer_id', '{customer_id or ''}'
                )
            )
        """)

        # Trigger digital delivery
        await delivery_service.fulfill_order(product_id, customer_id, metadata)

    async def handle_webhook(self, provider: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route webhook to appropriate handler."""
        try:
            if provider == 'stripe':
                return await self.handle_stripe_payment(payload)
            elif provider == 'paypal':
                return await self.handle_paypal_payment(payload)
            return {'status': 'error', 'reason': 'invalid_provider'}
        except Exception as e:
            logging.error(f"Webhook processing failed: {str(e)}")
            return {'status': 'error', 'reason': str(e)}
