import os
import stripe
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    async def create_customer(self, email: str, name: str) -> Dict:
        """Create a new Stripe customer."""
        return stripe.Customer.create(email=email, name=name)

    async def create_subscription(self, 
                                customer_id: str, 
                                price_id: str,
                                metadata: Optional[Dict] = None) -> Dict:
        """Create a new subscription."""
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{'price': price_id}],
            metadata=metadata or {}
        )

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            event_type = event['type']
            event_data = event['data']['object']
            
            if event_type == 'invoice.paid':
                return await self._handle_payment_success(event_data)
            elif event_type == 'invoice.payment_failed':
                return await self._handle_payment_failed(event_data)
            elif event_type == 'customer.subscription.created':
                return await self._handle_subscription_created(event_data)
            
            return {'status': 'unhandled_event'}
        except Exception as e:
            raise ValueError(f"Webhook error: {str(e)}")

    async def _handle_payment_success(self, invoice: Dict) -> Dict:
        """Handle successful payment."""
        subscription_id = invoice['subscription']
        customer_id = invoice['customer']
        amount = invoice['amount_paid']
        event_id = invoice['id']
        
        # TODO: Implement service delivery
        # await self.deliver_service(customer_id, subscription_id)
        
        return {
            'status': 'success',
            'customer_id': customer_id,
            'subscription_id': subscription_id,
            'amount': amount,
            'event_id': event_id
        }

    async def _record_transaction(self, 
                               customer_id: str,
                               amount: int,
                               event_type: str,
                               metadata: Dict) -> Dict:
        """Record transaction in database."""
        # TODO: Implement database recording
        return {'status': 'recorded'}
