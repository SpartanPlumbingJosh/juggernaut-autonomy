from pydantic import BaseSettings

class Settings(BaseSettings):
    STRIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    PAYPAL_CLIENT_ID: str
    PAYPAL_SECRET: str
    PAYPAL_MODE: str = "sandbox"
    
    class Config:
        env_file = ".env"

settings = Settings()
