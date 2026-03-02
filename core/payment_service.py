import stripe
from datetime import datetime, timezone
from typing import Dict, Optional, List
import json
from core.database import query_db, execute_sql

class PaymentService:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.webhook_secret = None

    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new Stripe customer."""
        return stripe.Customer.create(
            email=email,
            name=name,
            metadata=metadata or {}
        )

    def create_subscription(self, customer_id: str, price_id: str, trial_days: int = 0) -> Dict:
        """Create a new subscription."""
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            trial_period_days=trial_days,
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )

    def create_invoice(self, customer_id: str, items: List[Dict]) -> Dict:
        """Create an invoice for one-time charges."""
        return stripe.Invoice.create(
            customer=customer_id,
            collection_method="send_invoice",
            days_until_due=30,
            auto_advance=True,
            items=items
        )

    def record_payment_event(self, event: Dict) -> Dict:
        """Record a payment event in the database."""
        event_type = event['type']
        data = event['data']['object']
        
        # Map Stripe event to our revenue event types
        event_mapping = {
            'payment_intent.succeeded': 'revenue',
            'charge.succeeded': 'revenue',
            'invoice.payment_succeeded': 'revenue',
            'invoice.payment_failed': 'cost',
            'charge.refunded': 'cost'
        }
        
        event_type = event_mapping.get(event_type, 'other')
        
        metadata = {
            'stripe_event_id': event['id'],
            'stripe_object': data['object'],
            'stripe_customer_id': data.get('customer'),
            'stripe_invoice_id': data.get('invoice'),
            'stripe_payment_intent_id': data.get('payment_intent'),
            'stripe_charge_id': data.get('charge'),
            'stripe_subscription_id': data.get('subscription')
        }
        
        amount_cents = data.get('amount') or data.get('amount_received') or 0
        
        return execute_sql(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                '{event_type}',
                {amount_cents},
                '{data.get('currency', 'usd')}',
                'stripe',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )

    def handle_webhook(self, payload: str, sig_header: str) -> Dict:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            # Record payment event
            self.record_payment_event(event)
            
            # Handle specific event types
            if event['type'] == 'invoice.payment_succeeded':
                self._handle_payment_success(event)
            elif event['type'] == 'invoice.payment_failed':
                self._handle_payment_failure(event)
            elif event['type'] == 'customer.subscription.deleted':
                self._handle_subscription_cancelled(event)
                
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _handle_payment_success(self, event: Dict) -> None:
        """Handle successful payment."""
        invoice = event['data']['object']
        customer_id = invoice['customer']
        amount = invoice['amount_paid']
        
        # Update customer status
        execute_sql(
            f"""
            UPDATE customers
            SET status = 'active',
                last_payment_at = NOW()
            WHERE stripe_customer_id = '{customer_id}'
            """
        )

    def _handle_payment_failure(self, event: Dict) -> None:
        """Handle failed payment."""
        invoice = event['data']['object']
        customer_id = invoice['customer']
        
        # Update customer status
        execute_sql(
            f"""
            UPDATE customers
            SET status = 'past_due',
                last_payment_failed_at = NOW()
            WHERE stripe_customer_id = '{customer_id}'
            """
        )

    def _handle_subscription_cancelled(self, event: Dict) -> None:
        """Handle subscription cancellation."""
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        # Update customer status
        execute_sql(
            f"""
            UPDATE customers
            SET status = 'cancelled',
                subscription_ended_at = NOW()
            WHERE stripe_customer_id = '{customer_id}'
            """
        )
