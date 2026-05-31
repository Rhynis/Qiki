"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings are validated on application startup. Sensitive values should
    never be logged or returned in API responses.
    """

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENVIRONMENT: Literal["development", "local-demo", "staging", "production"] = "development"
    DEBUG: bool = False

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> Any:
        """Parse deployment-style DEBUG values defensively."""
        if isinstance(value, str) and value.lower() in {"release", "production", "prod"}:
            return False
        return value

    DATABASE_URL: str = "postgresql+asyncpg://gasbot:gasbot_dev_password@localhost:5432/gasbot_dev"

    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"

    LLM_PROVIDER: Literal["ollama", "gemini"] = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b-instruct-q4_K_M"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT: int = 60
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    EMBEDDING_MODEL: str = "keepitreal/vietnamese-sbert"
    EMBEDDING_DIMENSIONS: int = 768

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    SENTRY_DSN: str = ""

    JWT_SECRET_KEY: str = Field(
        default="development_secret_key_change_me_32_chars_minimum",
        min_length=32,
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12

    CORS_ORIGINS: str = "http://localhost:3000"

    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_PER_MINUTE: int = 5
    RATE_LIMIT_LLM_PER_MINUTE: int = 10

    @property
    def is_production(self) -> bool:
        """Return whether the application runs in production."""
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        """Return whether the application runs in development."""
        return self.ENVIRONMENT == "development"

    @property
    def is_local_demo(self) -> bool:
        """Return whether the application runs in local demo mode."""
        return self.ENVIRONMENT == "local-demo"

    @property
    def cors_origins_list(self) -> list[str]:
        """Return configured CORS origins as a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
