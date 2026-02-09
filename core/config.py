from pydantic import BaseSettings

class Settings(BaseSettings):
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    TARGET_REVENUE_CENTS: int = 800000000  # $8M in cents

    class Config:
        env_file = ".env"

settings = Settings()
