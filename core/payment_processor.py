import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union
import stripe
import paypalrestsdk

from core.database import query_db, execute_db
from core.idempotency import IdempotencyKey

logger = logging.getLogger(__name__)


class PaymentProcessor:
    def __init__(self):
        self.stripe = stripe
        self.paypal = paypalrestsdk
        
    async def initialize(self, config: Dict[str, Any]):
        """Initialize payment gateways with API keys."""
        self.stripe.api_key = config.get('stripe_secret_key')
        self.paypal.configure({
            'mode': config.get('paypal_mode', 'sandbox'),
            'client_id': config.get('paypal_client_id'),
            'client_secret': config.get('paypal_client_secret')
        })

    async def create_customer(self, user_id: str, email: str, **kwargs) -> Tuple[bool, Dict[str, Any]]:
        """Create customer across all payment providers."""
        try:
            stripe_customer = self.stripe.Customer.create(
                email=email,
                metadata={'user_id': user_id}
            )
            
            paypal_customer = self.paypal.Customer({
                'email': email
            })
            
            if paypal_customer.create():
                await execute_db(
                    """
                    INSERT INTO payment_customers 
                    (user_id, stripe_id, paypal_id, created_at)
                    VALUES (%s, %s, %s, NOW())
                    """,
                    (user_id, stripe_customer.id, paypal_customer.id)
                )
                return True, {
                    'stripe_id': stripe_customer.id,
                    'paypal_id': paypal_customer.id
                }
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
        return False, {}

    async def create_subscription(self, customer_id: str, plan_id: str, idempotency_key: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """Create subscription with idempotency check."""
        async with IdempotencyKey(key=idempotency_key, action="create_subscription") as key:
            if key.exists:
                return True, key.result
            
            try:
                subscription = self.stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"plan": plan_id}],
                    idempotency_key=idempotency_key
                )
                
                key.store_result({
                    'subscription_id': subscription.id,
                    'status': subscription.status
                })
                
                return True, key.result
            except Exception as e:
                logger.error(f"Failed to create subscription: {str(e)}")
                return False, {}

    async def create_invoice(self, customer_id: str, amount: int, currency="usd", 
                           description="", metadata: Dict={}, idempotency_key=None) -> Tuple[bool, Dict[str, Any]]:
        """Create invoice for one-time payment."""
        async with IdempotencyKey(key=idempotency_key, action="create_invoice") as key:
            if key.exists:
                return True, key.result
                
            try:
                invoice = self.stripe.Invoice.create(
                    customer=customer_id,
                    amount=amount,
                    currency=currency,
                    description=description,
                    metadata=metadata
                )
                
                key.store_result({
                    'invoice_id': invoice.id,
                    'status': invoice.status,
                    'amount': invoice.amount_due,
                    'payment_intent_id': getattr(invoice, 'payment_intent', None)
                })
                
                return True, key.result
            except Exception as e:
                logger.error(f"Failed to create invoice: {str(e)}")
                return False, {}

    async def record_payment_event(self, event_data: Dict[str, Any]) -> bool:
        """Record payment event in database."""
        try:
            await execute_db(
                """
                INSERT INTO payment_events 
                (event_id, event_type, provider, data, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (event_data.get('id'), event_data.get('type'), 'stripe', json.dumps(event_data))
            )
            return True
        except Exception as e:
            logger.error(f"Failed to record payment event: {str(e)}")
            return False
