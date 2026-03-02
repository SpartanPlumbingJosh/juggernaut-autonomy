"""
Dynamic pricing and payment processing.
Includes fraud detection and rate limiting.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import hashlib
import json

class PricingStrategy:
    """Base pricing strategy class."""
    
    def __init__(self, base_price: float):
        self.base_price = base_price
        
    def calculate_price(self, demand_factor: float = 1.0) -> float:
        """Calculate dynamic price."""
        return self.base_price * demand_factor

class TieredPricing(PricingStrategy):
    """Tiered pricing strategy with volume discounts."""
    
    def calculate_price(self, quantity: int = 1) -> float:
        if quantity >= 100:
            return self.base_price * 0.7
        elif quantity >= 50:
            return self.base_price * 0.8
        elif quantity >= 10:
            return self.base_price * 0.9
        return self.base_price

class FraudDetector:
    """Fraud detection and rate limiting."""
    
    def __init__(self, max_requests: int = 100, window_minutes: int = 5):
        self.max_requests = max_requests
        self.window = timedelta(minutes=window_minutes)
        self.requests = {}

    def check_request(self, client_id: str, amount: float) -> Tuple[bool, Optional[str]]:
        """Check if request appears fraudulent."""
        now = datetime.now()
        
        # Clean up old entries
        self.requests = {
            k: v for k, v in self.requests.items() 
            if now - v["timestamp"] < self.window
        }
        
        # Rate limiting
        if client_id in self.requests:
            if self.requests[client_id]["count"] >= self.max_requests:
                return False, "rate_limit_exceeded"
            self.requests[client_id]["count"] += 1
        else:
            self.requests[client_id] = {"count": 1, "timestamp": now}
        
        # Simple fraud signals
        if amount <= 0:
            return False, "invalid_amount"
        if amount > 10000:  # High value transaction threshold
            return False, "high_value_requires_review"
            
        return True, None

class PaymentProcessor:
    """Handle payment processing with retries."""
    
    def __init__(self, pricing_strategy: PricingStrategy):
        self.pricing = pricing_strategy
        self.fraud_detector = FraudDetector()
        
    async def process_payment(
        self,
        client_id: str,
        quantity: int = 1,
        payment_method: str = "card"
    ) -> Dict[str, Any]:
        """Process a payment with fraud checks."""
        
        total_amount = self.pricing.calculate_price(quantity)
        
        is_valid, reason = self.fraud_detector.check_request(client_id, total_amount)
        if not is_valid:
            return {
                "success": False,
                "error": reason,
                "client_id": hashlib.sha256(client_id.encode()).hexdigest(),
            }
            
        # Here you would integrate with real payment processor
        # This is just a mock implementation
        transaction_id = hashlib.sha256(
            f"{client_id}-{total_amount}-{datetime.now().isoformat()}".encode()
        ).hexdigest()
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "amount": total_amount,
            "quantity": quantity,
            "currency": "USD",
            "timestamp": datetime.now().isoformat()
        }
