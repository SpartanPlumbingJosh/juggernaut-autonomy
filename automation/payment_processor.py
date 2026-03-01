from typing import Dict, Optional
import stripe
from core.database import query_db, execute_sql
from datetime import datetime

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    async def create_payment_intent(self, amount: int, currency: str, metadata: Dict[str, str]) -> Dict:
        """Create a payment intent with Stripe"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata
            )
            return {"success": True, "payment_intent": intent}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                await self._process_successful_payment(payment_intent)
                
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def _process_successful_payment(self, payment_intent: Dict) -> None:
        """Record successful payment and trigger fulfillment"""
        metadata = payment_intent.get('metadata', {})
        await execute_sql(
            f"""
            INSERT INTO payments (
                id, amount, currency, status, 
                customer_email, payment_method, 
                created_at, updated_at, metadata
            ) VALUES (
                '{payment_intent['id']}',
                {payment_intent['amount']},
                '{payment_intent['currency']}',
                'succeeded',
                '{metadata.get('customer_email', '')}',
                '{payment_intent['payment_method']}',
                NOW(),
                NOW(),
                '{json.dumps(metadata)}'
            )
            """
        )
        # Trigger fulfillment
        await self._trigger_fulfillment(payment_intent['id'], metadata)
        
    async def _trigger_fulfillment(self, payment_id: str, metadata: Dict) -> None:
        """Initiate product delivery"""
        # Implementation depends on product type
        pass
