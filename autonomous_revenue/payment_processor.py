"""
Automated payment processing with fraud detection.
Handles credit cards, PayPal, and crypto payments.
"""
import re
from datetime import datetime
from typing import Dict, Optional, Tuple

class PaymentProcessor:
    def __init__(self, fraud_threshold: float = 0.7):
        self.fraud_threshold = fraud_threshold
        
    def process_payment(self, payment_data: Dict) -> Tuple[bool, Optional[str]]:
        """Process payment with basic fraud checks."""
        # Validate payment method
        if not self._validate_payment_method(payment_data):
            return False, "Invalid payment method"
            
        # Fraud detection
        fraud_score = self._calculate_fraud_score(payment_data)
        if fraud_score > self.fraud_threshold:
            return False, "Potential fraud detected"
            
        # Process payment (simulated)
        transaction_id = f"tx_{datetime.now().timestamp()}"
        return True, transaction_id
        
    def _validate_payment_method(self, payment_data: Dict) -> bool:
        """Validate payment method details."""
        method = payment_data.get("method", "").lower()
        if method == "credit_card":
            return self._validate_credit_card(payment_data.get("card_data", {}))
        elif method == "paypal":
            return bool(payment_data.get("paypal_email"))
        elif method == "crypto":
            return bool(payment_data.get("crypto_wallet"))
        return False
        
    def _validate_credit_card(self, card_data: Dict) -> bool:
        """Basic credit card validation."""
        number = str(card_data.get("number", "")).strip()
        if not re.match(r"^\d{13,19}$", number):
            return False
        if not card_data.get("expiry"):
            return False
        if not card_data.get("cvv"):
            return False
        return True
        
    def _calculate_fraud_score(self, payment_data: Dict) -> float:
        """Calculate fraud probability score (0-1)."""
        score = 0.0
        
        # High amount check
        amount = float(payment_data.get("amount", 0))
        if amount > 1000:
            score += 0.3
            
        # Rapid repeat purchases
        if payment_data.get("is_rapid_repeat"):
            score += 0.4
            
        # VPN/Proxy detection
        if payment_data.get("is_proxy"):
            score += 0.5
            
        # High risk country
        if payment_data.get("country") in ["XX", "YY", "ZZ"]:
            score += 0.3
            
        return min(score, 1.0)
