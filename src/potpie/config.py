from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = (
        "postgresql://postgres:postgres@localhost:5432/code_review_agent"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # AI Configuration
    # Gemini (Google)
    google_api_key: Optional[str] = None
    gemini_model: str = "gemini-pro"

    # Application
    debug: bool = True
    log_level: str = "INFO"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"


settings = Settings()
