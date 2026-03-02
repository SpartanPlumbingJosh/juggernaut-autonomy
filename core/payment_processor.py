import stripe
import paypalrestsdk
from typing import Dict, Optional
from datetime import datetime
from core.database import query_db

class PaymentProcessor:
    def __init__(self):
        self.stripe = stripe
        self.paypal = paypalrestsdk
        
    async def create_customer(self, email: str, payment_method: str, metadata: Optional[Dict] = None) -> Dict:
        """Create customer in payment gateway."""
        try:
            if payment_method == "stripe":
                customer = self.stripe.Customer.create(
                    email=email,
                    metadata=metadata or {}
                )
                return {"success": True, "customer_id": customer.id}
            elif payment_method == "paypal":
                customer = self.paypal.Customer({
                    "email": email,
                    "metadata": metadata or {}
                })
                if customer.create():
                    return {"success": True, "customer_id": customer.id}
            return {"success": False, "error": "Invalid payment method"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Dict:
        """Create subscription for customer."""
        try:
            if payment_method == "stripe":
                subscription = self.stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"plan": plan_id}]
                )
                return {"success": True, "subscription_id": subscription.id}
            elif payment_method == "paypal":
                subscription = self.paypal.Subscription({
                    "plan_id": plan_id,
                    "subscriber": {
                        "customer_id": customer_id
                    }
                })
                if subscription.create():
                    return {"success": True, "subscription_id": subscription.id}
            return {"success": False, "error": "Invalid payment method"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def log_transaction(self, transaction_data: Dict) -> Dict:
        """Log transaction in database."""
        try:
            sql = f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                '{transaction_data.get("event_type")}',
                {transaction_data.get("amount_cents")},
                '{transaction_data.get("currency", "USD")}',
                '{transaction_data.get("source", "payment")}',
                '{json.dumps(transaction_data.get("metadata", {}))}',
                NOW(),
                NOW()
            )
            """
            await query_db(sql)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
