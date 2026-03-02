import stripe
import paypalrestsdk
from typing import Dict, Optional
from datetime import datetime
from core.database import query_db, execute_sql

class PaymentProcessor:
    """Handles payment processing through Stripe and PayPal APIs."""
    
    def __init__(self):
        self.stripe = stripe
        self.paypal = paypalrestsdk
        
    async def create_payment_intent(self, amount: int, currency: str, customer_id: str, 
                                  metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent with Stripe."""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata or {},
                capture_method='automatic'
            )
            return {"success": True, "payment_intent": intent}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def create_paypal_order(self, amount: str, currency: str, 
                                return_url: str, cancel_url: str) -> Dict:
        """Create a PayPal order."""
        try:
            payment = self.paypal.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": amount,
                        "currency": currency
                    }
                }],
                "redirect_urls": {
                    "return_url": return_url,
                    "cancel_url": cancel_url
                }
            })
            if payment.create():
                return {"success": True, "payment": payment}
            return {"success": False, "error": "Payment creation failed"}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def log_payment_event(self, event_data: Dict) -> Dict:
        """Log payment event to database."""
        try:
            await execute_sql(
                f"""
                INSERT INTO payment_events (
                    id, event_type, amount_cents, currency, 
                    payment_method, status, metadata, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_data.get("event_type")}',
                    {event_data.get("amount_cents")},
                    '{event_data.get("currency")}',
                    '{event_data.get("payment_method")}',
                    '{event_data.get("status")}',
                    '{json.dumps(event_data.get("metadata", {}))}',
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
