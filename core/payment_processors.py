from typing import Dict, Any, Optional
from core.logger import get_logger
import requests
import json
from datetime import datetime

logger = get_logger(__name__)

class PaymentProcessor:
    """Handles integration with multiple payment processors"""
    
    def __init__(self):
        self.processors = [
            {"name": "stripe", "url": "https://api.stripe.com/v1"},
            {"name": "paypal", "url": "https://api.paypal.com/v1"}
        ]
        self.current_processor = 0
        
    def process_payment(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through available processors with failover"""
        attempts = 0
        while attempts < len(self.processors):
            processor = self.processors[self.current_processor]
            try:
                response = requests.post(
                    f"{processor['url']}/charges",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._get_api_key(processor['name'])}"
                    },
                    json={
                        "amount": int(amount * 100),
                        "currency": currency.lower(),
                        "metadata": metadata
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    return response.json()
                
                logger.warning(f"Payment failed with {processor['name']}: {response.text}")
                
            except Exception as e:
                logger.error(f"Payment processor error ({processor['name']}): {str(e)}")
            
            # Switch to next processor
            self.current_processor = (self.current_processor + 1) % len(self.processors)
            attempts += 1
            
        raise Exception("All payment processors failed")
        
    def _get_api_key(self, processor_name: str) -> str:
        """Get API key for processor"""
        # In production, this should fetch from secure storage
        return "sk_test_12345"  # Placeholder
        
    def log_transaction(self, transaction: Dict[str, Any]) -> None:
        """Log transaction to database"""
        try:
            # Add timestamp and status
            transaction['timestamp'] = datetime.utcnow().isoformat()
            transaction['status'] = 'completed'
            
            # Save to database
            # Implement database logging here
            pass
        except Exception as e:
            logger.error(f"Failed to log transaction: {str(e)}")
