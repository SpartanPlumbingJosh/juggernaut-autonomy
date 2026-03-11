import stripe
import paypalrestsdk
from typing import Dict, Optional
from datetime import datetime
from core.database import query_db, execute_sql

class PaymentProcessor:
    def __init__(self):
        self.stripe = stripe
        self.paypal = paypalrestsdk
        
    async def create_payment_intent(self, amount: float, currency: str = "usd", 
                                  payment_method: str = "stripe", 
                                  metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent with Stripe or PayPal"""
        try:
            if payment_method == "stripe":
                intent = self.stripe.PaymentIntent.create(
                    amount=int(amount * 100),  # Convert to cents
                    currency=currency,
                    metadata=metadata or {},
                    automatic_payment_methods={"enabled": True},
                )
                return {"success": True, "client_secret": intent.client_secret}
            elif payment_method == "paypal":
                payment = self.paypal.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
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
                    return {"success": True, "approval_url": payment.links[1].href}
                else:
                    return {"success": False, "error": payment.error}
            else:
                return {"success": False, "error": "Invalid payment method"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_payment(self, payment_id: str, amount: float, currency: str,
                           user_id: str, product_id: str) -> Dict:
        """Record a successful payment in the database"""
        try:
            await execute_sql(
                f"""
                INSERT INTO payments (
                    id, user_id, product_id, amount, currency,
                    payment_id, status, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{user_id}',
                    '{product_id}',
                    {amount},
                    '{currency}',
                    '{payment_id}',
                    'completed',
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def deliver_product(self, payment_id: str) -> Dict:
        """Deliver product/service after successful payment"""
        try:
            # Get payment details
            res = await query_db(
                f"SELECT product_id, user_id FROM payments WHERE payment_id = '{payment_id}'"
            )
            if not res.get("rows"):
                return {"success": False, "error": "Payment not found"}
            
            payment = res["rows"][0]
            product_id = payment["product_id"]
            user_id = payment["user_id"]
            
            # Here you would implement product-specific delivery logic
            # For digital products, this might mean generating access credentials
            # For physical products, this might trigger shipping
            # For services, this might schedule the service
            
            # Mark product as delivered
            await execute_sql(
                f"""
                UPDATE payments
                SET delivered_at = NOW(),
                    status = 'completed'
                WHERE payment_id = '{payment_id}'
                """
            )
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
