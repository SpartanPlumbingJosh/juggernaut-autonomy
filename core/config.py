import os

# Stripe configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

# Pricing plans
PRICING_PLANS = {
    "basic": {
        "price_id": os.getenv("STRIPE_BASIC_PRICE_ID"),
        "features": ["Core analytics", "Basic reporting"]
    },
    "pro": {
        "price_id": os.getenv("STRIPE_PRO_PRICE_ID"),
        "features": ["Advanced analytics", "Priority support", "Custom reports"]
    }
}
