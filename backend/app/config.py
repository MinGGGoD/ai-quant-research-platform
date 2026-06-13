from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings."""

    app_name: str = "AI Quant Research Platform"
    environment: str = "development"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AQR_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
