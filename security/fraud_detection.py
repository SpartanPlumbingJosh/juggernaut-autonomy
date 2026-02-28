from typing import Dict, Any
import logging
import re

class FraudDetection:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def analyze_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform basic fraud detection checks"""
        try:
            # Basic fraud detection rules
            email = transaction_data.get('customer_email', '')
            ip_address = transaction_data.get('ip_address', '')
            amount = transaction_data.get('amount', 0)
            
            # Check for suspicious email patterns
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                return {'fraudulent': True, 'reason': 'Invalid email format'}
                
            # Check for high-risk IP addresses
            if ip_address.startswith('192.168.') or ip_address.startswith('10.'):
                return {'fraudulent': True, 'reason': 'Internal IP address'}
                
            # Check for unusually large transactions
            if amount > 10000:  # $10,000 threshold
                return {'fraudulent': True, 'reason': 'Large transaction amount'}
                
            # If all checks pass
            return {'fraudulent': False}
            
        except Exception as e:
            self.logger.error(f"Fraud detection failed: {str(e)}")
            return {'fraudulent': False, 'error': str(e)}
