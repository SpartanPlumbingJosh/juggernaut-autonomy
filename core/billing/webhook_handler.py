from typing import Dict, Any
from fastapi import Request, HTTPException
import hmac
import hashlib

class WebhookHandler:
    """Handle payment provider webhooks."""
    
    def __init__(self):
        self.webhook_secrets = {
            "stripe": os.getenv("STRIPE_WEBHOOK_SECRET"),
            "paddle": os.getenv("PADDLE_WEBHOOK_SECRET")
        }
        
    def verify_signature(self, provider: str, payload: bytes, signature: str) -> bool:
        """Verify webhook signature."""
        secret = self.webhook_secrets.get(provider)
        if not secret:
            return False
            
        if provider == "stripe":
            return self._verify_stripe_signature(payload, signature, secret)
        elif provider == "paddle":
            return self._verify_paddle_signature(payload, signature, secret)
            
        return False
        
    def _verify_stripe_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify Stripe webhook signature."""
        try:
            return stripe.WebhookSignature.verify_header(
                payload, signature, secret
            )
        except Exception:
            return False
            
    def _verify_paddle_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify Paddle webhook signature."""
        hmac_obj = hmac.new(secret.encode(), payload, hashlib.sha256)
        return hmac.compare_digest(hmac_obj.hexdigest(), signature)
        
    async def process_webhook(self, provider: str, request: Request) -> Dict[str, Any]:
        """Process incoming webhook."""
        payload = await request.body()
        signature = request.headers.get("X-Signature")
        
        if not self.verify_signature(provider, payload, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
            
        event = json.loads(payload)
        return self._handle_event(provider, event)
        
    def _handle_event(self, provider: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle verified webhook event."""
        event_type = event.get("type")
        
        # Handle common events
        if event_type in ["payment_succeeded", "subscription_created"]:
            return self._handle_payment_event(provider, event)
        elif event_type in ["subscription_updated", "subscription_cancelled"]:
            return self._handle_subscription_event(provider, event)
        elif event_type == "invoice_payment_failed":
            return self._handle_failed_payment_event(provider, event)
            
        return {"status": "unhandled_event", "event_type": event_type}
