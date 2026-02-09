import os
import stripe
import paypalrestsdk
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self):
        # Initialize Stripe
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.stripe = stripe
        
        # Initialize PayPal
        paypalrestsdk.configure({
            "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
            "client_id": os.getenv('PAYPAL_CLIENT_ID'),
            "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
        })
        self.paypal = paypalrestsdk

    async def create_payment_intent(self, amount: float, currency: str, metadata: Dict[str, str]) -> Dict:
        """Create a Stripe payment intent"""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                metadata=metadata
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_id": intent.id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_paypal_payment(self, amount: float, currency: str, description: str) -> Dict:
        """Create a PayPal payment"""
        try:
            payment = self.paypal.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": currency.upper()
                    },
                    "description": description
                }],
                "redirect_urls": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
            })
            
            if payment.create():
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "approval_url": next(link.href for link in payment.links if link.rel == "approval_url")
                }
            return {"success": False, "error": payment.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_transaction(self, payment_id: str, amount: float, currency: str, 
                               payment_method: str, metadata: Optional[Dict] = None) -> Dict:
        """Record transaction in revenue_events table"""
        try:
            # Convert to cents for storage
            amount_cents = int(amount * 100)
            
            # Record the transaction
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount_cents},
                    '{currency.upper()}',
                    '{payment_method}',
                    '{json.dumps(metadata or {})}',
                    NOW(),
                    NOW()
                )
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
