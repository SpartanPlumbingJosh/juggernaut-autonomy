import stripe
from typing import Dict, Any, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.stripe = stripe

    def create_customer(self, email: str, name: str) -> Dict[str, Any]:
        """Create a new customer in payment system"""
        return self.stripe.Customer.create(
            email=email,
            name=name,
            description=f"Autonomous customer created {datetime.utcnow().isoformat()}"
        )

    def create_subscription(
        self, 
        customer_id: str, 
        price_id: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create recurring subscription"""
        return self.stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            metadata=metadata or {}
        )

    def record_payment_event(
        self, 
        event_type: str, 
        amount: float, 
        currency: str,
        customer_id: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record payment event in revenue system"""
        return {
            "event_type": event_type,
            "amount_cents": int(amount * 100),
            "currency": currency,
            "customer_id": customer_id,
            "metadata": metadata,
            "recorded_at": datetime.utcnow().isoformat()
        }

    def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment webhook events"""
        event = payload.get("type")
        data = payload.get("data", {}).get("object", {})

        if event == "payment_intent.succeeded":
            return self.record_payment_event(
                event_type="revenue",
                amount=data.get("amount") / 100,
                currency=data.get("currency"),
                customer_id=data.get("customer"),
                metadata={"payment_intent": data.get("id")}
            )
        
        return {"status": "unhandled_event"}
