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

    REDIS_URL: str = "redis://localhost:6379/0"

    LLM_PROVIDER: Literal["ollama", "gemini", "groq", "vllm"] = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b-instruct-q4_K_M"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT: int = 60
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"
    GEMINI_USE_VERTEX: bool = False
    GOOGLE_CLOUD_PROJECT: str | None = None
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS_JSON: str | None = None
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    JINA_API_KEY: str | None = None
    JINA_EMBED_MODEL: str = "jina-embeddings-v3"
    # Self-hosted vLLM (OpenAI-compatible) serving endpoint. Off by default —
    # LLM_PROVIDER stays "ollama" unless explicitly set to "vllm". No GPU is
    # available in CI or on Railway; this is a benchmark/demo layer the owner
    # runs against a GPU box (RunPod/Kaggle/HF ZeroGPU), not a prod swap.
    VLLM_BASE_URL: str = "http://localhost:8000/v1"
    VLLM_MODEL: str = "Qwen/Qwen3-4B-Instruct-AWQ"
    VLLM_API_KEY: str | None = None
    VLLM_TIMEOUT: int = 120

    EMBEDDING_DIMENSIONS: int = 768
    # Retrieval embedding backend. "gemini" keeps Gemini primary -> Jina fallback;
    # "ollama" uses the local nomic-embed-text model (768-d); "bge" uses the local
    # bge-m3 model (1024-d, stronger Vietnamese retrieval). Default stays "gemini".
    EMBEDDING_PROVIDER: Literal["gemini", "ollama", "bge"] = "gemini"
    OLLAMA_BGE_MODEL: str = "bge-m3"
    BGE_EMBEDDING_DIMENSIONS: int = 1024
    # Read-through Redis cache TTL (seconds) for query embeddings so repeated chat
    # questions skip the embedding-provider round-trip. 0 disables the cache.
    EMBEDDING_QUERY_CACHE_TTL: int = 3600

    # Per-vector-space similarity thresholds. The threshold filter is gated to the
    # local providers; the Gemini retrieval path keeps its existing behavior so
    # production (EMBEDDING_PROVIDER=gemini) output stays identical.
    RAG_THRESHOLD_OLLAMA: float = 0.7
    RAG_THRESHOLD_BGE: float = 0.55

    # Offline LLM reranker (local Ollama model). OFF by default so the production
    # path is byte-for-byte unchanged.
    RAG_RERANK_ENABLED: bool = False
    RAG_RERANK_RETRIEVE_K: int = 8
    RAG_RERANK_TOP_N: int = 3

    # Auto-close active conversations with no activity for this many days.
    CONVERSATION_STALE_DAYS: int = 3

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    SENTRY_DSN: str = ""

    # Legal Vietnamese e-invoice provider. "none" uses the local Noop stub (no
    # external call). "vnpt"/"viettel" are reserved for future real adapters.
    EINVOICE_PROVIDER: Literal["none", "vnpt", "viettel"] = "none"

    # "smtp" (Gmail App Password) | "resend" | "gmail_api" (Gmail API over HTTPS,
    # for hosts that block outbound SMTP such as Railway).
    EMAIL_PROVIDER: Literal["smtp", "resend", "gmail_api"] = "smtp"
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Gas Quốc Cường <onboarding@resend.dev>"
    FRONTEND_URL: str = "http://localhost:3000"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    # Gmail API (OAuth) — sends over HTTPS (port 443); secrets via env only.
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REFRESH_TOKEN: str = ""

    JWT_SECRET_KEY: str = Field(
        default="development_secret_key_change_me_32_chars_minimum",
        min_length=32,
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12

    CORS_ORIGINS: str = "http://localhost:3000"
    CORS_ORIGIN_REGEX: str | None = None

    # LangGraph agent orchestration (docs/adr/0001, docs/adr/0002). Default OFF
    # so the existing /chat RAG endpoint's behavior and startup cost are
    # completely unaffected until this is explicitly turned on.
    AGENT_ENABLED: bool = False
    # Optional override for the checkpointer's Postgres connection string. When
    # unset, LANGGRAPH_DB_URI derives from DATABASE_URL with the +asyncpg
    # SQLAlchemy dialect suffix stripped, because the checkpointer connects via
    # psycopg (v3), not asyncpg (see langgraph_db_uri below).
    LANGGRAPH_DB_URI: str | None = None

    # MCP server (docs/mcp.md) exposing the agent's read-only tools over
    # Streamable HTTP, mounted into this same FastAPI app. Default OFF so the
    # app's existing startup cost and route surface are unaffected until this
    # is explicitly turned on (mirrors AGENT_ENABLED above).
    MCP_ENABLED: bool = False

    @property
    def langgraph_db_uri(self) -> str:
        """Plain ``postgresql://`` URI for the LangGraph checkpointer (psycopg)."""
        if self.LANGGRAPH_DB_URI:
            return self.LANGGRAPH_DB_URI
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

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
