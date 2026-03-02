"""
Automated billing service handles payments, subscriptions, and transaction recording.
Integrates with Stripe and PayPal payment processors.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import stripe
from paypalcheckoutsdk.orders import OrdersGetRequest
from paypalhttp import HttpResponse

from core.database import query_db

class BillingService:
    def __init__(self, config: Dict[str, Any], logger=None):
        """Initialize billing service with config and logger."""
        self.stripe_key = config.get('stripe_secret_key')
        self.paypal_client = config.get('paypal_client')
        self.logger = logger
        self.idempotency_keys = set()
        
        if self.stripe_key:
            stripe.api_key = self.stripe_key

    async def process_payment(self, payment_data: Dict[str, Any], idempotency_key: str = None) -> Dict[str, Any]:
        """Process payment through configured processor."""
        if not payment_data.get('amount'):
            raise ValueError("Missing payment amount")
            
        if not payment_data.get('currency'):
            raise ValueError("Missing currency")

        # Handle idempotency
        idempotency_key = idempotency_key or str(uuid.uuid4())
        if idempotency_key in self.idempotency_keys:
            return {"status": "duplicate", "idempotency_key": idempotency_key}
            
        self.idempotency_keys.add(idempotency_key)

        try:
            processor = payment_data.get('processor', 'stripe')
            if processor == 'stripe' and self.stripe_key:
                return await self._process_stripe_payment(payment_data)
            elif processor == 'paypal' and self.paypal_client:
                return await self._process_paypal_payment(payment_data)
            else:
                raise ValueError(f"Processor {processor} not configured")
        except Exception as e:
            await self._log_failed_payment(payment_data, str(e))
            raise

    async def _process_stripe_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment via Stripe."""
        intent = stripe.PaymentIntent.create(
            amount=int(float(payment_data['amount'])*100),
            currency=payment_data['currency'],
            payment_method=payment_data['payment_method_id'],
            confirmation_method='manual',
            confirm=True
        )
        
        receipt = intent.to_dict()
        await self._record_transaction({
            'amount_cents': receipt['amount'],
            'currency': receipt['currency'],
            'processor': 'stripe',
            'processor_id': receipt['id'],
            'status': receipt['status'],
            'metadata': payment_data.get('metadata', {}) 
        })
        
        return receipt

    async def _process_paypal_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment via PayPal."""
        request = OrdersGetRequest(payment_data['order_id'])
        response: HttpResponse = self.paypal_client.execute(request)
        
        order = response.result.to_dict()
        await self._record_transaction({
            'amount_cents': int(float(order['purchase_units'][0]['amount']['value'])*100),
            'currency': order['purchase_units'][0]['amount']['currency_code'],
            'processor': 'paypal', 
            'processor_id': order['id'],
            'status': order['status'],
            'metadata': payment_data.get('metadata', {})
        })
        
        return order

    async def create_subscription(self, customer_id: str, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create and manage subscriptions."""
        idempotency_key = str(uuid.uuid4())
        if idempotency_key in self.idempotency_keys:
            return {"status": "duplicate", "idempotency_key": idempotency_key}
            
        self.idempotency_keys.add(idempotency_key)

        try:
            processor = plan_data.get('processor', 'stripe')
            if processor == 'stripe' and self.stripe_key:
                return await self._create_stripe_subscription(customer_id, plan_data)
            else:
                raise ValueError(f"Processor {processor} not configured for subscriptions")
        except Exception as e:
            await self._log_failed_subscription(customer_id, plan_data, str(e))
            raise

    async def _create_stripe_subscription(self, customer_id: str, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create subscription in Stripe."""
        subscription = await stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": plan_data['price_id']}],
            metadata=plan_data.get('metadata', {})
        )
        
        await self._record_subscription(subscription.to_dict())
        return subscription.to_dict()

    async def _generate_invoice(self, subscription_id: str) -> Dict[str, Any]:
        """Generate invoice for subscription."""
        invoice = await stripe.Invoice.create(
            customer=self.stripe_customer_id,
            subscription=subscription_id
        )
        invoice = await invoice.send_invoice()
        return invoice.to_dict()

    async def _record_transaction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Record transaction in database."""
        transaction_data = {
            "id": str(uuid.uuid4()),
            "event_type": "revenue",
            "amount_cents": data['amount_cents'],
            "currency": data['currency'],
            "processor": data['processor'],
            "processor_id": data['processor_id'],
            "status": data['status'],
            "metadata": data.get('metadata', {}),
            "recorded_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                processor, processor_id, status, metadata, recorded_at
            ) VALUES (
                '{transaction_data['id']}', 
                '{transaction_data['event_type']}',
                {transaction_data['amount_cents']},
                '{transaction_data['currency']}',
                '{transaction_data['processor']}',
                '{transaction_data['processor_id']}',
                '{transaction_data['status']}',
                '{json.dumps(transaction_data['metadata'])}'::jsonb,
                '{transaction_data['recorded_at']}'
            )
            RETURNING id
        """)
        
        return {"success": True, "transaction_id": transaction_data['id']}

    async def _record_subscription(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Record subscription in database."""
        subscription_data = {
            "id": str(uuid.uuid4()),
            "processor": "stripe",
            "processor_id": data['id'],
            "status": data['status'],
            "plan_id": data['items']['data'][0]['price']['id'],
            "customer_id": data['customer'],
            "metadata": {},
            "recorded_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = await query_db(f"""
            INSERT INTO subscriptions (
                id, processor, processor_id, status,
                plan_id, customer_id, metadata, recorded_at
            ) VALUES (
                '{subscription_data['id']}',
                '{subscription_data['processor']}',
                '{subscription_data['processor_id']}',
                '{subscription_data['status']}',
                '{subscription_data['plan_id']}',
                '{subscription_data['customer_id']}',
                '{json.dumps(subscription_data['metadata'])}'::jsonb,
                '{subscription_data['recorded_at']}'
            )
            RETURNING id
        """)
        
        return {"success": True, "subscription_id": subscription_data['id']}

    async def _log_failed_payment(self, payment_data: Dict[str, Any], error: str):
        """Log failed payment attempt."""
        if self.logger:
            await self.logger(
                "billing.payment_failed",
                f"Payment failed: {error}",
                level="error",
                error_data={
                    "error": error,
                    "amount": payment_data.get('amount'),
                    "currency": payment_data.get('currency'),
                    "processor": payment_data.get('processor')
                }
            )

    async def _log_failed_subscription(self, customer_id: str, plan_data: Dict[str, Any], error: str):
        """Log failed subscription attempt."""
        if self.logger:
            await self.logger(
                "billing.subscription_failed", 
                f"Subscription creation failed: {error}",
                level="error",
                error_data={
                    "error": error,
                    "customer_id": customer_id,
                    "plan_id": plan_data.get('price_id')
                }
            )
