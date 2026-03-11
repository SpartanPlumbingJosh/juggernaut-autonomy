import os
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Optional, List
from core.database import execute_sql

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class PaymentGateway:
    """Handle payment processing through multiple gateways."""
    
    def __init__(self):
        self.target_revenue = 500000  # cents (5000.00)
        
    async def process_payment(self, amount: float, currency: str, payment_method: str, 
                            customer_email: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through selected gateway."""
        amount_cents = int(amount * 100)
        
        try:
            if payment_method == "stripe":
                payment = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=currency.lower(),
                    receipt_email=customer_email,
                    metadata=metadata
                )
            elif payment_method == "paypal":
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": f"{amount:.2f}",
                            "currency": currency.upper()
                        },
                        "description": metadata.get("description", "")
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv("PAYPAL_RETURN_URL"),
                        "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                    }
                })
                if payment.create():
                    payment = payment.to_dict()
                else:
                    raise Exception(payment.error)
            else:
                raise ValueError("Unsupported payment method")
                
            # Record transaction
            await self.record_transaction(
                amount_cents=amount_cents,
                currency=currency,
                source=payment_method,
                metadata={
                    "payment_id": payment.get("id"),
                    "customer_email": customer_email,
                    **metadata
                }
            )
            
            return {
                "success": True,
                "payment_id": payment.get("id"),
                "amount_cents": amount_cents,
                "status": payment.get("status", "succeeded")
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "payment_id": None
            }
            
    async def record_transaction(self, amount_cents: int, currency: str, source: str, 
                               metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Record revenue transaction in database."""
        try:
            await execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount_cents},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata)}'::jsonb,
                    NOW(),
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def get_revenue_progress(self) -> Dict[str, Any]:
        """Get current revenue progress toward target."""
        try:
            res = await execute_sql(
                """
                SELECT 
                    SUM(amount_cents) FILTER (WHERE event_type = 'revenue') as total_revenue,
                    SUM(amount_cents) FILTER (WHERE event_type = 'cost') as total_cost
                FROM revenue_events
                """
            )
            row = res.get("rows", [{}])[0]
            total_revenue = row.get("total_revenue", 0) or 0
            total_cost = row.get("total_cost", 0) or 0
            
            return {
                "current_revenue": total_revenue,
                "current_cost": total_cost,
                "net_profit": total_revenue - total_cost,
                "target_revenue": self.target_revenue,
                "progress_percent": (total_revenue / self.target_revenue) * 100 if self.target_revenue > 0 else 0
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
