from pydantic_settings import BaseSettings
from typing import List
from pydantic import field_validator


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60  # was 10080 — fixed to match security.py usage

    # Hubtel (payments only — SMS moved to Arkesel)
    HUBTEL_CLIENT_ID: str = ""
    HUBTEL_CLIENT_SECRET: str = ""
    HUBTEL_API_BASE_URL: str = "https://api.hubtel.com"

    # Arkesel (SMS + OTP)
    ARKESEL_API_KEY: str = ""
    ARKESEL_SENDER_ID: str = "RestaurantApp"
    ARKESEL_BASE_URL: str = "https://sms.arkesel.com/api/otp"
    ARKESEL_OTP_LENGTH: int = 6
    ARKESEL_OTP_EXPIRY_MINUTES: int = 10

    # Development mode
    DEV_MODE: bool = False
    DEV_OTP_CODE: str = "123456"

    @field_validator("DEV_MODE", mode="before")
    @classmethod
    def parse_dev_mode(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return v

    # Admin credentials
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()