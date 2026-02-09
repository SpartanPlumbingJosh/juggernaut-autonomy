from pydantic import BaseSettings

class Settings(BaseSettings):
    STRIPE_SECRET_KEY: str
    STRIPE_PUBLIC_KEY: str
    STRIPE_PRICE_ID: str
    BASE_URL: str = "http://localhost:8000"
    
    class Config:
        env_file = ".env"

settings = Settings()
