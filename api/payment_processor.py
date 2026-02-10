"""
Payment Processing System - Handles Stripe/PayPal integrations, subscriptions, invoicing.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

import stripe
from paypalrestsdk import WebhookEvent

from core.database import query_db

# Configure logging
logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, stripe_api_key: str, paypal_client_id: str, paypal_secret: str):
        self.stripe = stripe
        self.stripe.api_key = stripe_api_key
        self.paypal = WebhookEvent
        self.paypal.configure(
            mode="live",
            client_id=paypal_client_id,
            client_secret=paypal_secret
        )

    async def record_transaction(
        self,
        amount_cents: int,
        currency: str,
        source: str,
        event_type: str,
        metadata: Dict[str, Any],
        recorded_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Record a financial transaction in the database."""
        recorded_at = recorded_at or datetime.now(timezone.utc)
        
        try:
            result = await query_db(
                f"""
                INSERT INTO revenue_events (
                    event_type,
                    amount_cents,
                    currency,
                    source,
                    metadata,
                    recorded_at,
                    created_at
                ) VALUES (
                    '{event_type}',
                    {amount_cents},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata)}',
                    '{recorded_at.isoformat()}',
                    NOW()
                )
                RETURNING id
                """
            )
            return {"success": True, "transaction_id": result.get("rows", [{}])[0].get("id")}
        except Exception as e:
            logger.error(f"Failed to record transaction: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_stripe_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, self.stripe_webhook_secret
            )
            
            event_type = event['type']
            data = event['data']['object']
            
            # Handle different event types
            if event_type == 'payment_intent.succeeded':
                amount = data['amount']
                currency = data['currency']
                metadata = {
                    'stripe_id': data['id'],
                    'customer': data.get('customer'),
                    'payment_method': data.get('payment_method')
                }
                return await self.record_transaction(
                    amount_cents=amount,
                    currency=currency,
                    source='stripe',
                    event_type='revenue',
                    metadata=metadata
                )
                
            elif event_type == 'invoice.paid':
                # Handle subscription payments
                amount = data['amount_paid']
                currency = data['currency']
                metadata = {
                    'stripe_id': data['id'],
                    'subscription_id': data['subscription'],
                    'customer': data['customer']
                }
                return await self.record_transaction(
                    amount_cents=amount,
                    currency=currency,
                    source='stripe',
                    event_type='revenue',
                    metadata=metadata
                )
                
            elif event_type == 'charge.refunded':
                # Handle refunds
                amount = data['amount_refunded']
                currency = data['currency']
                metadata = {
                    'stripe_id': data['id'],
                    'charge_id': data['charge'],
                    'reason': data.get('reason')
                }
                return await self.record_transaction(
                    amount_cents=-amount,  # Negative for refunds
                    currency=currency,
                    source='stripe',
                    event_type='refund',
                    metadata=metadata
                )
                
            return {"success": True, "handled": False, "event_type": event_type}
            
        except Exception as e:
            logger.error(f"Stripe webhook error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_paypal_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process PayPal webhook events."""
        try:
            event = self.paypal(payload)
            
            if not event.verify():
                return {"success": False, "error": "Invalid PayPal webhook signature"}
                
            event_type = event.event_type
            
            if event_type == 'PAYMENT.SALE.COMPLETED':
                resource = event.resource
                amount = int(float(resource['amount']['total']) * 100)  # Convert to cents
                currency = resource['amount']['currency']
                metadata = {
                    'paypal_id': resource['id'],
                    'sale_id': resource['sale_id'],
                    'billing_agreement_id': resource.get('billing_agreement_id')
                }
                return await self.record_transaction(
                    amount_cents=amount,
                    currency=currency,
                    source='paypal',
                    event_type='revenue',
                    metadata=metadata
                )
                
            elif event_type == 'PAYMENT.SALE.REFUNDED':
                resource = event.resource
                amount = int(float(resource['amount']['total']) * 100)  # Convert to cents
                currency = resource['amount']['currency']
                metadata = {
                    'paypal_id': resource['id'],
                    'sale_id': resource['sale_id'],
                    'reason': resource.get('reason')
                }
                return await self.record_transaction(
                    amount_cents=-amount,  # Negative for refunds
                    currency=currency,
                    source='paypal',
                    event_type='refund',
                    metadata=metadata
                )
                
            return {"success": True, "handled": False, "event_type": event_type}
            
        except Exception as e:
            logger.error(f"PayPal webhook error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_method_id: Optional[str] = None,
        trial_days: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{'plan': plan_id}],
                default_payment_method=payment_method_id,
                trial_period_days=trial_days,
                metadata=metadata or {}
            )
            
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end
            }
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    async def cancel_subscription(
        self,
        subscription_id: str,
        cancel_at_period_end: bool = False
    ) -> Dict[str, Any]:
        """Cancel a subscription."""
        try:
            subscription = self.stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=cancel_at_period_end
            )
            return {
                "success": True,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end
            }
        except Exception as e:
            logger.error(f"Failed to cancel subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    async def generate_invoice(
        self,
        customer_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate an invoice for a customer."""
        try:
            invoice = self.stripe.Invoice.create(
                customer=customer_id,
                auto_advance=True,
                collection_method='send_invoice',
                days_until_due=30,
                description=description,
                metadata=metadata or {}
            )
            
            invoice_item = self.stripe.InvoiceItem.create(
                customer=customer_id,
                amount=amount_cents,
                currency=currency,
                description=description,
                invoice=invoice.id
            )
            
            final_invoice = self.stripe.Invoice.finalize_invoice(invoice.id)
            
            return {
                "success": True,
                "invoice_id": final_invoice.id,
                "status": final_invoice.status,
                "amount_due": final_invoice.amount_due,
                "hosted_invoice_url": final_invoice.hosted_invoice_url
            }
        except Exception as e:
            logger.error(f"Failed to generate invoice: {str(e)}")
            return {"success": False, "error": str(e)}

    async def process_dunning(
        self,
        max_attempts: int = 3,
        days_between_attempts: int = 3
    ) -> Dict[str, Any]:
        """Handle failed payment recovery (dunning management)."""
        try:
            # Get subscriptions with failed payments
            subscriptions = self.stripe.Subscription.list(
                status='past_due',
                limit=100
            )
            
            processed = 0
            for sub in subscriptions.auto_paging_iter():
                # Check payment attempts
                invoice = self.stripe.Invoice.retrieve(sub.latest_invoice)
                if invoice.attempt_count >= max_attempts:
                    # Cancel subscription if max attempts reached
                    await self.cancel_subscription(sub.id)
                else:
                    # Retry payment
                    self.stripe.Invoice.pay(invoice.id)
                processed += 1
                
            return {"success": True, "processed": processed}
        except Exception as e:
            logger.error(f"Dunning process failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def meter_usage(
        self,
        subscription_item_id: str,
        quantity: int,
        timestamp: Optional[int] = None
    ) -> Dict[str, Any]:
        """Record usage for metered billing."""
        try:
            usage_record = self.stripe.SubscriptionItem.create_usage_record(
                subscription_item_id,
                quantity=quantity,
                timestamp=timestamp or int(datetime.now(timezone.utc).timestamp()),
                action='increment'
            )
            return {
                "success": True,
                "usage_record_id": usage_record.id,
                "quantity": usage_record.quantity
            }
        except Exception as e:
            logger.error(f"Failed to record usage: {str(e)}")
            return {"success": False, "error": str(e)}
