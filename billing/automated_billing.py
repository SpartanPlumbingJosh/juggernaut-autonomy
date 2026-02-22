"""
Automated billing system with subscription management, invoicing, and payment processing.
Designed for 24/7 operation with no human intervention.
"""

import datetime
import logging
from typing import Dict, List, Optional

from billing.payment_processors import PaymentProcessor
from billing.models import Subscription, Invoice, PaymentMethod

logger = logging.getLogger(__name__)

class AutomatedBillingSystem:
    def __init__(self, payment_processor: PaymentProcessor):
        self.processor = payment_processor
        self.retry_policy = {
            'initial_delay': 60,  # seconds
            'max_retries': 3,
            'backoff_factor': 2
        }

    async def process_subscription_billing(self, subscription: Subscription) -> Dict:
        """Process recurring subscription billing"""
        try:
            # Check if billing is due
            if not self._is_billing_due(subscription):
                return {'status': 'skipped', 'reason': 'not_due'}

            # Create invoice
            invoice = self._create_invoice(subscription)
            
            # Process payment
            result = await self._charge_customer(
                subscription.customer_id,
                invoice.total_amount,
                invoice.currency,
                subscription.payment_method_id
            )

            if result['success']:
                invoice.mark_paid(result['transaction_id'])
                subscription.update_next_billing_date()
                return {'status': 'success', 'invoice_id': invoice.id}
            
            # Handle payment failure
            self._handle_payment_failure(subscription, invoice, result)
            return {'status': 'failed', 'reason': result['error']}

        except Exception as e:
            logger.error(f"Billing failed for subscription {subscription.id}: {str(e)}")
            return {'status': 'error', 'error': str(e)}

    def _is_billing_due(self, subscription: Subscription) -> bool:
        """Check if billing is due for this subscription"""
        now = datetime.datetime.now(datetime.timezone.utc)
        return subscription.next_billing_date <= now

    def _create_invoice(self, subscription: Subscription) -> Invoice:
        """Generate invoice for subscription"""
        return Invoice.create(
            subscription_id=subscription.id,
            customer_id=subscription.customer_id,
            amount=subscription.plan_amount,
            currency=subscription.plan_currency,
            description=f"Subscription renewal for {subscription.plan_name}"
        )

    async def _charge_customer(self, customer_id: str, amount: float, 
                             currency: str, payment_method_id: str) -> Dict:
        """Charge customer with retry logic"""
        for attempt in range(self.retry_policy['max_retries'] + 1):
            try:
                result = await self.processor.charge(
                    customer_id=customer_id,
                    amount=amount,
                    currency=currency,
                    payment_method_id=payment_method_id
                )
                return result
            except Exception as e:
                if attempt == self.retry_policy['max_retries']:
                    raise
                delay = self.retry_policy['initial_delay'] * (self.retry_policy['backoff_factor'] ** attempt)
                await asyncio.sleep(delay)

    def _handle_payment_failure(self, subscription: Subscription, 
                              invoice: Invoice, result: Dict) -> None:
        """Handle payment failure scenarios"""
        invoice.mark_failed(result.get('error'))
        subscription.increment_failure_count()
        
        if subscription.failure_count >= 3:
            subscription.suspend()
            self._notify_customer(subscription.customer_id, 'account_suspended')

    def _notify_customer(self, customer_id: str, template_name: str) -> None:
        """Send notification to customer"""
        # Implementation would integrate with notification service
        pass
