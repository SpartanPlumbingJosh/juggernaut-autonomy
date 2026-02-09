import os
import stripe
from typing import Dict, Any, Optional
from datetime import datetime
from core.database import query_db

class PaymentService:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
    async def create_payment_intent(self, amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency.lower(),
                metadata=metadata,
                automatic_payment_methods={"enabled": True},
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            event_type = event['type']
            data = event['data']['object']
            
            if event_type == 'payment_intent.succeeded':
                return await self._handle_payment_success(data)
            elif event_type == 'charge.refunded':
                return await self._handle_refund(data)
            elif event_type in ['invoice.payment_failed', 'payment_intent.payment_failed']:
                return await self._handle_payment_failed(data)
                
            return {"success": True, "handled": False, "event_type": event_type}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_payment_success(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process successful payment"""
        amount = data['amount'] / 100  # Convert to dollars
        metadata = data.get('metadata', {})
        
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, experiment_id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                {f"'{metadata.get('experiment_id','')}'" if metadata.get('experiment_id') else "NULL"},
                'revenue',
                {int(amount * 100)},
                '{data['currency']}',
                'stripe',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )
        
        await self._provision_access(metadata.get('user_id'), metadata.get('product_id'))
        return {"success": True, "handled": True, "amount": amount}

    async def _provision_access(self, user_id: str, product_id: str) -> None:
        """Grant product access to user"""
        if not user_id or not product_id:
            return
            
        await query_db(
            f"""
            INSERT INTO user_products (
                user_id, product_id, access_granted_at, expires_at
            ) VALUES (
                '{user_id}',
                '{product_id}',
                NOW(),
                NOW() + INTERVAL '1 year'
            )
            ON CONFLICT (user_id, product_id) 
            DO UPDATE SET
                access_granted_at = NOW(),
                expires_at = NOW() + INTERVAL '1 year'
            """
        )
