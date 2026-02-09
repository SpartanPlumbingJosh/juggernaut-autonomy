"""
Configuration for payment processing
"""
import os

# Stripe Payment Processing
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY', 'sk_test_...') 
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_...')

# Subscription Plans
PLANS = {
    'basic': {
        'price_id': 'price_...',
        'interval': 'month',
        'amount': 9.99
    },
    'pro': {
        'price_id': 'price_...', 
        'interval': 'month',
        'amount': 29.99
    }
}
