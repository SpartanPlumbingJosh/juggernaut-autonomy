from pydantic import BaseSettings

class Settings(BaseSettings):
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_SUCCESS_URL: str = "https://yourdomain.com/success"
    STRIPE_CANCEL_URL: str = "https://yourdomain.com/cancel"
    
    class Config:
        env_file = ".env"

settings = Settings()
