from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 10080  # 7 days

    # Hubtel (payments & SMS)
    HUBTEL_CLIENT_ID: str = ""
    HUBTEL_CLIENT_SECRET: str = ""
    HUBTEL_API_BASE_URL: str = "https://api.hubtel.com"
    HUBTEL_SMS_SENDER_ID: str = ""

    # Admin credentials
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()