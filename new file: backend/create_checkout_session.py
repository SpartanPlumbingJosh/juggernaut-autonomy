import json
from datetime import datetime, timezone
from typing import Dict, Any

async def create_checkout_session(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create Stripe checkout session."""
    try:
        # Call Stripe API to create session
        # This is a mock implementation - use Stripe Python SDK in production
        session_data = {
            "id": f"cs_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "amount": product_data.get("price", 4999),
            "currency": "usd",
            "customer_email": product_data.get("customer_email", ""),
            "product_id": product_data.get("product_id", "premium"),
            "metadata": {
                "utm_source": product_data.get("utm_source"),
                "utm_campaign": product_data.get("utm_campaign")
            }
        }
        
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "sessionId": session_data["id"],
                "sessionUrl": f"https://checkout.stripe.com/pay/{session_data['id']}"
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
