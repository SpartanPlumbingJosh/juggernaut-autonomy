import stripe
import paypalrestsdk
from typing import Optional, Dict, Any
from datetime import datetime
from core.database import query_db

class PaymentProcessor:
    """Handles payment processing via multiple gateways."""
    
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_API_KEY')
        paypalrestsdk.configure({
            "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
            "client_id": os.getenv('PAYPAL_CLIENT_ID'),
            "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
        })
        
    async def create_payment_intent(
        self, 
        amount: int, 
        currency: str = 'usd',
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a payment intent with Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True}
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def capture_paypal_payment(
        self,
        payment_id: str
    ) -> Dict[str, Any]:
        """Capture a PayPal payment."""
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            if payment.execute({'payer_id': payment.payer.payer_info.payer_id}):
                return {"success": True, "receipt": payment.to_dict()}
            return {"success": False, "error": payment.error}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def record_revenue_event(
        self,
        amount_cents: int,
        source: str,
        metadata: Dict[str, Any],
        event_type: str = 'revenue'
    ) -> Dict[str, Any]:
        """Record revenue event in database."""
        try:
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(), '{event_type}', {amount_cents},
                    '{metadata.get('currency', 'usd')}', '{source}',
                    '{json.dumps(metadata)}', NOW(), NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
