from typing import Dict, Any
from datetime import datetime
from services.payment_processor import PaymentProcessor

STATE_NEW = "new"
STATE_PAYMENT = "payment"
STATE_COMPLETE = "complete"

class OnboardingFlow:
    """Handle customer onboarding workflow."""
    
    def __init__(self):
        self.step_handlers = {
            STATE_NEW: self._handle_new,
            STATE_PAYMENT: self._handle_payment,
        }

    async def handle(self, state: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process onboarding step."""
        handler = self.step_handlers.get(state)
        if not handler:
            return {"success": False, "error": "Invalid state"}
            
        return await handler(data)

    async def _handle_new(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process new customer signup."""
        try:
            customer = PaymentProcessor.create_customer(
                email=data["email"],
                name=data["name"]
            )
            
            return {
                "success": True,
                "next_state": STATE_PAYMENT,
                "customer_id": customer.id,
                "customer": customer
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment setup."""
        try:
            subscription = PaymentProcessor.create_subscription(
                customer_id=data["customer_id"],
                price_id=data["price_id"]
            )
            
            return {
                "success": True,
                "next_state": STATE_COMPLETE,
                "subscription": subscription,
                "payment_intent": subscription.latest_invoice.payment_intent
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
