from pydantic import BaseSettings

class Settings(BaseSettings):
    STRIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"

settings = Settings()
