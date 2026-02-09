"""
Stripe Configuration

Handles:
- API keys
- Webhook secrets
- Environment settings
"""

import os
from typing import Dict, Any

class StripeConfig:
    def __init__(self):
        self.secret_key = os.getenv("STRIPE_SECRET_KEY")
        self.publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        self.env = os.getenv("STRIPE_ENV", "test")
        
        if self.env == "production":
            stripe.api_version = "2023-08-16"
        else:
            stripe.api_version = "2023-08-16"
            stripe.api_key = self.secret_key

    def get_config(self) -> Dict[str, Any]:
        return {
            "env": self.env,
            "publishable_key": self.publishable_key,
            "api_version": stripe.api_version
        }

stripe_config = StripeConfig()
