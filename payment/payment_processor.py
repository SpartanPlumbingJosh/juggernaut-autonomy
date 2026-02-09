import stripe
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import query_db

class PaymentProcessor:
    def __init__(self, stripe_secret_key: str):
        stripe.api_key = stripe_secret_key
        
    async def create_customer(self, email: str, payment_method: Optional[str] = None) -> Dict[str, Any]:
        """Create a new Stripe customer."""
        customer = stripe.Customer.create(
            email=email,
            payment_method=payment_method,
            invoice_settings={
                'default_payment_method': payment_method
            } if payment_method else None
        )
        return customer
    
    async def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create a new subscription."""
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{'price': price_id}],
            expand=['latest_invoice.payment_intent']
        )
        return subscription
    
    async def log_revenue_event(self, event_type: str, amount_cents: int, currency: str, 
                              source: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Log a revenue event to the database."""
        sql = f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency, 
            source, metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            '{event_type}',
            {amount_cents},
            '{currency}',
            '{source}',
            '{json.dumps(metadata)}',
            NOW(),
            NOW()
        )
        """
        return await query_db(sql)
    
    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'invoice.payment_succeeded':
                invoice = event['data']['object']
                await self.log_revenue_event(
                    event_type='revenue',
                    amount_cents=invoice['amount_paid'],
                    currency=invoice['currency'],
                    source='stripe',
                    metadata={
                        'invoice_id': invoice['id'],
                        'subscription_id': invoice['subscription']
                    }
                )
                
            return {'success': True, 'event': event['type']}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
