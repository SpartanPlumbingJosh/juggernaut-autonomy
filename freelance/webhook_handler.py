from typing import Dict, Any
import json
import time
from datetime import datetime

class WebhookHandler:
    """Handle payment webhooks and manage freelance transactions."""
    
    def __init__(self):
        self.payment_events = []
        self.rate_limits = {
            'hourly': 10,
            'daily': 50
        }
        self.last_webhook = datetime.now()
        self.webhook_count = 0
        
    def _check_rate_limit(self):
        """Enforce rate limiting for webhook processing."""
        now = datetime.now()
        if (now - self.last_webhook).seconds < 3600:
            if self.webhook_count >= self.rate_limits['hourly']:
                time.sleep(3600 - (now - self.last_webhook).seconds)
                self.webhook_count = 0
        else:
            self.webhook_count = 0
            
        self.last_webhook = datetime.now()
        self.webhook_count += 1
        
    def handle_payment_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment webhook events."""
        self._check_rate_limit()
        
        try:
            event_type = payload.get('event_type', '')
            amount = payload.get('amount', 0)
            currency = payload.get('currency', 'USD')
            
            if event_type not in ['payment.success', 'payment.failed']:
                return {
                    'success': False,
                    'error': 'Invalid event type',
                    'status': 400
                }
                
            self.payment_events.append({
                'timestamp': datetime.now().isoformat(),
                'event_type': event_type,
                'amount': amount,
                'currency': currency,
                'metadata': payload.get('metadata', {})
            })
            
            return {
                'success': True,
                'status': 200,
                'message': 'Webhook processed successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'status': 500,
                'retry_after': 60
            }
