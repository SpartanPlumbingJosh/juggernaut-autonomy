"""
Production configuration for revenue system
"""

# Payment gateway credentials
PAYMENT_GATEWAYS = {
    "stripe": {
        "api_key": "sk_live_...",  # Replace with actual production key
        "webhook_secret": "whsec_...",
        "currency": "usd"
    },
    "paypal": {
        "client_id": "...",
        "client_secret": "...",
        "mode": "live"
    }
}

# Database configuration
DATABASE = {
    "host": "prod-db.example.com",
    "port": 5432,
    "user": "revenue_app",
    "password": "secure_password",
    "database": "revenue_prod",
    "ssl_mode": "require"
}

# Automation schedules
SCHEDULES = {
    "revenue_summary": "0 0 * * *",  # Daily at midnight
    "transaction_sync": "*/15 * * * *",  # Every 15 minutes
    "idea_generation": "0 6 * * *",  # Daily at 6am
    "idea_scoring": "0 7 * * *",  # Daily at 7am
    "experiment_review": "*/30 * * * *"  # Every 30 minutes
}

# Customer acquisition settings
ACQUISITION = {
    "ad_budget": 1000.0,  # Daily ad spend
    "channels": ["google_ads", "facebook_ads", "linkedin_ads"],
    "target_cpa": 50.0  # Target cost per acquisition
}

# Monitoring
MONITORING = {
    "sentry_dsn": "https://...@sentry.io/...",
    "datadog_api_key": "...",
    "log_level": "INFO"
}

# Email notifications
EMAIL = {
    "from_address": "revenue@example.com",
    "admin_alerts": ["admin@example.com"],
    "transaction_alerts": ["finance@example.com"]
}
