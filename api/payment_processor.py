import stripe
import paypalrestsdk
from typing import Dict, Optional
from datetime import datetime
from core.database import query_db

class PaymentProcessor:
    def __init__(self):
        self.stripe_api_key = "sk_test_..."  # Should be from config
        self.paypal_client_id = "..."  # Should be from config
        stripe.api_key = self.stripe_api_key
        paypalrestsdk.configure({
            "mode": "sandbox",
            "client_id": self.paypal_client_id,
            "client_secret": "..."
        })

    async def create_payment(self, amount: float, currency: str, method: str, customer_data: Dict) -> Dict:
        """Create a payment with Stripe or PayPal"""
        try:
            if method == "stripe":
                payment = stripe.PaymentIntent.create(
                    amount=int(amount * 100),  # Convert to cents
                    currency=currency,
                    payment_method_types=['card'],
                    metadata={
                        "customer_email": customer_data.get("email"),
                        "customer_name": customer_data.get("name")
                    }
                )
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "client_secret": payment.client_secret
                }
            elif method == "paypal":
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {
                        "payment_method": "paypal"
                    },
                    "transactions": [{
                        "amount": {
                            "total": str(amount),
                            "currency": currency
                        }
                    }],
                    "redirect_urls": {
                        "return_url": "https://example.com/success",
                        "cancel_url": "https://example.com/cancel"
                    }
                })
                if payment.create():
                    return {
                        "success": True,
                        "payment_id": payment.id,
                        "approval_url": payment.links[1].href
                    }
                else:
                    return {"success": False, "error": payment.error}
            else:
                return {"success": False, "error": "Invalid payment method"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_transaction(self, payment_id: str, amount: float, currency: str, 
                               customer_id: Optional[str] = None) -> Dict:
        """Record a successful transaction in the database"""
        try:
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    recorded_at, created_at, metadata
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {int(amount * 100)},
                    '{currency}',
                    'payment',
                    NOW(),
                    NOW(),
                    '{{"payment_id": "{payment_id}", "customer_id": "{customer_id or ''}"}}'::jsonb
                )
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
