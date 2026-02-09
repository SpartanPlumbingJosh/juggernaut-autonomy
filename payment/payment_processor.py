import os
import stripe
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = '2023-08-16'

class PaymentStatus(Enum):
    PENDING = 'pending'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    REFUNDED = 'refunded'

class PaymentProcessor:
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql

    async def create_customer(self, email: str, name: str) -> Dict:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={'created_at': datetime.utcnow().isoformat()}
            )
            return {'success': True, 'customer_id': customer.id}
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def create_payment_intent(self, amount: int, currency: str, customer_id: str, 
                                  description: str, metadata: Dict = None) -> Dict:
        """Create a payment intent for one-time payment."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                description=description,
                metadata=metadata or {},
                payment_method_types=['card'],
                confirm=True
            )
            return {'success': True, 'payment_intent_id': intent.id}
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create payment intent: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def create_subscription(self, customer_id: str, price_id: str, 
                                metadata: Dict = None) -> Dict:
        """Create a recurring subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                metadata=metadata or {},
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            return {
                'success': True,
                'subscription_id': subscription.id,
                'payment_intent_id': subscription.latest_invoice.payment_intent.id
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                return await self._handle_payment_success(event)
            elif event['type'] == 'payment_intent.payment_failed':
                return await self._handle_payment_failure(event)
            elif event['type'] == 'invoice.payment_succeeded':
                return await self._handle_invoice_payment(event)
            elif event['type'] == 'invoice.payment_failed':
                return await self._handle_invoice_failure(event)
            
            return {'success': True, 'handled': False}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)}")
            return {'success': False, 'error': 'Invalid signature'}
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def _handle_payment_success(self, event: Dict) -> Dict:
        """Handle successful payment."""
        payment_intent = event['data']['object']
        await self._record_transaction(
            payment_intent['id'],
            payment_intent['amount'],
            payment_intent['currency'],
            'payment',
            PaymentStatus.SUCCEEDED.value,
            payment_intent.get('metadata', {})
        )
        return {'success': True, 'handled': True}

    async def _handle_payment_failure(self, event: Dict) -> Dict:
        """Handle failed payment."""
        payment_intent = event['data']['object']
        await self._record_transaction(
            payment_intent['id'],
            payment_intent['amount'],
            payment_intent['currency'],
            'payment',
            PaymentStatus.FAILED.value,
            payment_intent.get('metadata', {}),
            error=payment_intent.get('last_payment_error')
        )
        return {'success': True, 'handled': True}

    async def _record_transaction(self, transaction_id: str, amount: int, currency: str,
                                event_type: str, status: str, metadata: Dict,
                                error: Optional[str] = None) -> None:
        """Record transaction in database."""
        try:
            await self.execute_sql(
                f"""
                INSERT INTO payment_transactions (
                    id, amount, currency, event_type, status,
                    metadata, error, created_at, updated_at
                ) VALUES (
                    '{transaction_id}',
                    {amount},
                    '{currency}',
                    '{event_type}',
                    '{status}',
                    '{json.dumps(metadata)}',
                    {f"'{error}'" if error else 'NULL'},
                    NOW(),
                    NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    error = EXCLUDED.error,
                    updated_at = NOW()
                """
            )
        except Exception as e:
            logger.error(f"Failed to record transaction: {str(e)}")

    async def generate_invoice(self, customer_id: str, items: List[Dict]) -> Dict:
        """Generate an invoice for a customer."""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                auto_advance=True,
                collection_method='send_invoice',
                days_until_due=30,
                description='Invoice for services rendered'
            )
            
            for item in items:
                stripe.InvoiceItem.create(
                    customer=customer_id,
                    amount=item['amount'],
                    currency=item['currency'],
                    description=item.get('description', ''),
                    invoice=invoice.id
                )
            
            final_invoice = stripe.Invoice.finalize_invoice(invoice.id)
            return {
                'success': True,
                'invoice_id': final_invoice.id,
                'invoice_pdf': final_invoice.invoice_pdf
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to generate invoice: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def retry_failed_payments(self, days: int = 7) -> Dict:
        """Retry failed payments from the last N days."""
        try:
            result = await self.execute_sql(
                f"""
                SELECT id, amount, currency, metadata
                FROM payment_transactions
                WHERE status = '{PaymentStatus.FAILED.value}'
                AND created_at >= NOW() - INTERVAL '{days} days'
                """
            )
            
            retried = 0
            for row in result.get('rows', []):
                payment_intent = stripe.PaymentIntent.retrieve(row['id'])
                if payment_intent.status == 'requires_payment_method':
                    try:
                        stripe.PaymentIntent.confirm(
                            payment_intent.id,
                            payment_method=payment_intent.last_payment_error.payment_method.id
                        )
                        retried += 1
                    except stripe.error.StripeError:
                        continue
            
            return {'success': True, 'retried': retried}
        except Exception as e:
            logger.error(f"Failed to retry payments: {str(e)}")
            return {'success': False, 'error': str(e)}
