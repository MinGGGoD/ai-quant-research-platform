from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings."""

    app_name: str = "AI Quant Research Platform"
    environment: str = "development"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    database_url: str = (
        "postgresql+psycopg://ai_quant:local_development_only@localhost:5432/ai_quant"
    )
    database_echo: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    asharehub_api_key: SecretStr | None = None
    asharehub_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    asharehub_sync_max_requests: int = Field(default=20, ge=1, le=100)
    ai_provider: Literal["disabled", "openai_compatible"] = "disabled"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: SecretStr | None = None
    ai_model: str | None = None
    ai_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    ai_max_attempts: int = Field(default=2, ge=1, le=3)
    ai_max_output_characters: int = Field(default=6000, ge=500, le=20000)
    ai_max_output_tokens: int = Field(default=1200, ge=100, le=4000)
    rag_embedding_provider: Literal["local_hash", "openai_compatible"] = "local_hash"
    rag_embedding_base_url: str = "https://api.openai.com/v1"
    rag_embedding_api_key: SecretStr | None = None
    rag_embedding_model: str = "local-hash-v1"
    rag_embedding_dimensions: int = Field(default=256, ge=64, le=2000)
    rag_embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    rag_embedding_max_attempts: int = Field(default=2, ge=1, le=3)
    rag_chunk_size: int = Field(default=1200, ge=200, le=4000)
    rag_chunk_overlap: int = Field(default=200, ge=0, le=1000)
    rag_max_document_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1024,
        le=50 * 1024 * 1024,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AQR_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
