"""Payment system configuration."""
import os

class PaymentConfig:
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
    PAYPAL_SECRET = os.getenv("PAYPAL_SECRET")
    PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID")
    
    @classmethod
    def validate(cls):
        required = [
            cls.STRIPE_SECRET_KEY,
            cls.STRIPE_PUBLISHABLE_KEY 
        ]
        if not all(required):
            raise ValueError("Missing payment gateway configuration")
