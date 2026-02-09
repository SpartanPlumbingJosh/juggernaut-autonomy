"""
Payment Controller - Handles Stripe subscriptions and one-time payments.
"""
import stripe
from datetime import datetime, timezone
from typing import Dict, Any

from api.revenue_api import _make_response, _error_response

# Initialize Stripe
stripe.api_key = "sk_test_YOUR_STRIPE_API_KEY"

async def handle_create_subscription(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Stripe subscription."""
    try:
        # Create Stripe customer
        customer = stripe.Customer.create(
            email=customer_data.get("email"),
            source=customer_data.get("token")
        )

        # Create subscription
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"plan": customer_data.get("plan_id")}]
        )

        return _make_response(200, {
            "customer_id": customer.id,
            "subscription_id": subscription.id,
            "status": subscription.status
        })
        
    except stripe.error.StripeError as e:
        return _error_response(400, f"Payment failed: {str(e)}")


async def handle_create_payment_intent(amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Stripe PaymentIntent for one-time payments."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            payment_method_types=['card'],
            metadata=metadata
        )
        return _make_response(200, {
            "client_secret": intent.client_secret,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status
        })
    except stripe.error.StripeError as e:
        return _error_response(400, f"Payment intent failed: {str(e)}")


def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Route payment API requests."""
    if method == "POST" and path == "/payment/subscribe":
        return handle_create_subscription(body)
        
    if method == "POST" and path == "/payment/intent":
        return handle_create_payment_intent(
            amount=int(body.get("amount")),
            currency=body.get("currency", "usd"),
            metadata=body.get("metadata", {})
        )
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
