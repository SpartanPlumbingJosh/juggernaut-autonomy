"""
Payment gateway integrations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional

class BasePaymentGateway(ABC):
    """Abstract base class for payment gateways."""
    
    @abstractmethod
    def charge(self, amount: float, currency: str, payment_method: Dict) -> Dict:
        """Process a payment."""
        pass
        
    @abstractmethod
    def create_subscription(self, plan_id: str, customer_id: str) -> Dict:
        """Create a subscription."""
        pass
        
    @abstractmethod
    def handle_webhook(self, payload: Dict, headers: Dict) -> Dict:
        """Process incoming webhooks."""
        pass

class StripeGateway(BasePaymentGateway):
    """Stripe payment gateway implementation."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def charge(self, amount: float, currency: str, payment_method: Dict) -> Dict:
        # Implement Stripe charge logic
        pass
        
    def create_subscription(self, plan_id: str, customer_id: str) -> Dict:
        # Implement Stripe subscription logic
        pass
        
    def handle_webhook(self, payload: Dict, headers: Dict) -> Dict:
        # Implement Stripe webhook validation
        pass

class GatewayFactory:
    """Factory for creating gateway instances."""
    
    @staticmethod
    def create(gateway: str, config: Dict) -> BasePaymentGateway:
        if gateway == "stripe":
            return StripeGateway(config["api_key"])
        raise ValueError(f"Unsupported gateway: {gateway}")
