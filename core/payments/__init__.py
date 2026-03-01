"""
Core payment processing infrastructure with support for multiple providers.
Handles Stripe/PayPal integrations, webhooks, and transaction recording.
"""
from typing import Optional, Dict, Any
import logging
from datetime import datetime, timezone
import json
from uuid import uuid4

# Configure logging
logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Base class for payment processors."""
    
    PROVIDERS = {
        'stripe': 'core.payments.stripe',
        'paypal': 'core.payments.paypal'
    }

    def __init__(self, provider: str = 'stripe'):
        """Initialize payment provider."""
        try:
            self.provider = provider
            self.client = self._init_provider(provider)
        except Exception as e:
            logger.error(f"Payment processor init failed: {str(e)}")
            raise

    def _init_provider(self, provider: str):
        """Initialize specified payment provider."""
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")
        
        module = __import__(self.PROVIDERS[provider], fromlist=['Provider'])
        return module.Provider()
    
    async def create_charge(self, amount: float, currency: str, 
                          metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment charge."""
        try:
            result = await self.client.create_charge(
                amount=amount,
                currency=currency,
                metadata=metadata
            )
            await self._record_transaction(
                amount=amount,
                currency=currency,
                metadata=metadata,
                provider_data=result
            )
            return result
        except Exception as e:
            logger.error(f"Charge creation failed: {str(e)}")
            raise

    async def _record_transaction(self, amount: float, currency: str,
                                metadata: Dict[str, Any], provider_data: Dict[str, Any]):
        """Record transaction in revenue_events."""
        transaction_id = str(uuid4())
        await self._execute_sql(f"""
            INSERT INTO revenue_events (
                id, 
                event_type,
                amount_cents,
                currency,
                source,
                metadata,
                provider_data,
                recorded_at,
                created_at
            ) VALUES (
                '{transaction_id}',
                'revenue',
                {int(amount * 100)},
                '{currency}',
                '{self.provider}',
                '{json.dumps(metadata)}',
                '{json.dumps(provider_data)}',
                '{datetime.now(timezone.utc).isoformat()}',
                NOW()
            )
        """)

    async def _execute_sql(self, query: str):
        """Execute SQL query (implementation depends on db layer)."""
        raise NotImplementedError("Subclasses must implement _execute_sql")

class SubscriptionManager:
    """Manage recurring subscriptions and billing."""
    
    async def create_subscription(self, plan_id: str, customer_data: Dict[str, Any],
                                metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            # Implementation depends on provider
            processor = PaymentProcessor()
            result = await processor.client.create_subscription(
                plan_id=plan_id,
                customer_data=customer_data,
                metadata=metadata
            )
            await self._record_subscription_event(
                event_type='subscription_created',
                plan_id=plan_id,
                customer_data=customer_data,
                metadata=metadata,
                provider_data=result
            )
            return result
        except Exception as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            raise

    async def _record_subscription_event(self, **kwargs):
        """Record subscription event."""
        await self._execute_sql(f"""
            INSERT INTO subscription_events (
                id,
                event_type,
                plan_id,
                customer_data,
                metadata,
                provider_data,
                recorded_at,
                created_at
            ) VALUES (
                '{str(uuid4())}',
                '{kwargs['event_type']}',
                '{kwargs['plan_id']}',
                '{json.dumps(kwargs['customer_data'])}',
                '{json.dumps(kwargs['metadata'])}',
                '{json.dumps(kwargs['provider_data'])}',
                '{datetime.now(timezone.utc).isoformat()}',
                NOW()
            )
        """)

class InvoiceManager:
    """Generate and manage invoices."""
    
    async def generate_invoice(self, transaction_id: str) -> Dict[str, Any]:
        """Generate invoice for a transaction."""
        transaction = await self._get_transaction(transaction_id)
        invoice_data = {
            'transaction_id': transaction_id,
            'amount': transaction['amount'],
            'currency': transaction['currency'],
            'customer': transaction['metadata'].get('customer', {}),
            'items': transaction['metadata'].get('items', []),
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        invoice_id = str(uuid4())
        await self._execute_sql(f"""
            INSERT INTO invoices (
                id,
                transaction_id,
                invoice_data,
                status,
                created_at
            ) VALUES (
                '{invoice_id}',
                '{transaction_id}',
                '{json.dumps(invoice_data)}',
                'generated',
                NOW()
            )
        """)
        
        return {
            'invoice_id': invoice_id,
            **invoice_data
        }

class WebhookHandler:
    """Handle payment provider webhooks."""
    
    async def handle_webhook(self, provider: str, payload: Dict[str, Any],
                           signature: Optional[str] = None) -> Dict[str, Any]:
        """Process incoming webhook."""
        try:
            processor = PaymentProcessor(provider)
            verified = await processor.client.verify_webhook(payload, signature)
            if not verified:
                return {'success': False, 'error': 'Webhook verification failed'}

            event_type = payload.get('type')
            handler = getattr(self, f'_handle_{event_type}', None)
            if handler:
                return await handler(payload)
            return {'success': False, 'error': 'Unhandled event type'}
        except Exception as e:
            logger.error(f"Webhook handling failed: {str(e)}")
            return {'success': False, 'error': str(e)}
