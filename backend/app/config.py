import os
import secrets
from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "TerraGuard AI"
    ENVIRONMENT: str = "development"
    SECRET_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440 # 24 hours

    DATABASE_URL: str = "sqlite:///./terraguard.db"

    STORAGE_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage")
    DEMO_DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo_data")

    COPERNICUS_CLIENT_ID: Optional[str] = None
    COPERNICUS_CLIENT_SECRET: Optional[str] = None
    COPERNICUS_ENABLED: bool = False

    DEMO_MODE: bool = True

    @model_validator(mode="after")
    def ensure_signing_key(self):
        environment = self.ENVIRONMENT.lower()
        production = environment in {"production", "prod"}
        key = self.SECRET_KEY

        if key and "replace_with_a_random_secret" in key.lower():
            raise ValueError("Replace the SECRET_KEY placeholder with a generated secret.")
        if production and not key:
            raise ValueError("SECRET_KEY must be set when ENVIRONMENT is production.")
        if production and key and len(key) < 32:
            raise ValueError("Production SECRET_KEY must contain at least 32 characters.")
        if not key:
            self.SECRET_KEY = secrets.token_urlsafe(48)
        return self

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# Ensure storage directories exist
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
os.makedirs(os.path.join(settings.STORAGE_DIR, "imagery"), exist_ok=True)
os.makedirs(os.path.join(settings.STORAGE_DIR, "masks"), exist_ok=True)
os.makedirs(os.path.join(settings.STORAGE_DIR, "evidence"), exist_ok=True)
os.makedirs(os.path.join(settings.STORAGE_DIR, "reports"), exist_ok=True)
os.makedirs(settings.DEMO_DATA_DIR, exist_ok=True)
