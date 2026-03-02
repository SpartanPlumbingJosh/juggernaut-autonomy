from typing import Dict
from core.revenue.payment_processors import get_payment_processor

class WebhookHandler:
    """Handles incoming payment processor webhooks."""
    
    def __init__(self):
        self.processors = {
            'stripe': get_payment_processor('stripe'),
            'paypal': get_payment_processor('paypal')
        }
    
    def handle_webhook(self, processor: str, payload: bytes, signature: str = None) -> Dict:
        """Route webhook to appropriate processor."""
        if processor not in self.processors:
            return {"error": "unsupported_processor"}
            
        return self.processors[processor].handle_webhook(payload, signature)
