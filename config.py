"""
Application configuration settings.
"""
import os

class Settings:
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "your_stripe_secret_key")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

settings = Settings()
