"""
Payment processing system with Stripe/PayPal integration.
"""
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Initialize payment providers lazily
_stripe_client = None
_paypal_client = None

class PaymentError(Exception):
    """Base class for payment processing errors"""
    pass

class PaymentConfigurationError(PaymentError):
    """Raised when payment provider is not properly configured"""
    pass

def init_payment_system(stripe_api_key: Optional[str] = None, 
                       paypal_client_id: Optional[str] = None,
                       paypal_secret: Optional[str] = None):
    """
    Initialize payment providers with API keys.
    """
    global _stripe_client, _paypal_client
    
    if stripe_api_key:
        try:
            import stripe
            stripe.api_key = stripe_api_key
            _stripe_client = stripe
            logger.info("Stripe payment provider initialized")
        except ImportError:
            logger.warning("Stripe library not installed")
    
    if paypal_client_id and paypal_secret:
        try:
            from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment
            environment = SandboxEnvironment(client_id=paypal_client_id, 
                                           client_secret=paypal_secret)
            _paypal_client = PayPalHttpClient(environment)
            logger.info("PayPal payment provider initialized")
        except ImportError:
            logger.warning("PayPal SDK not installed")

def get_stripe_client():
    if _stripe_client is None:
        raise PaymentConfigurationError("Stripe not initialized")
    return _stripe_client

def get_paypal_client():
    if _paypal_client is None:
        raise PaymentConfigurationError("PayPal not initialized")
    return _paypal_client
