"""Factory for creating LLM provider instances."""

from typing import ClassVar

from app.core.config import Settings, get_settings
from app.llm.base import BaseLLMProvider
from app.llm.providers.fallback_provider import FallbackLLMProvider
from app.llm.providers.gemini_provider import GeminiProvider
from app.llm.providers.groq_provider import GroqProvider
from app.llm.providers.ollama_provider import OllamaProvider


class LLMProviderFactory:
    """Factory for LLM providers with singleton caching."""

    _instances: ClassVar[dict[str, BaseLLMProvider]] = {}

    @classmethod
    def create(
        cls,
        provider_name: str | None = None,
        settings: Settings | None = None,
    ) -> BaseLLMProvider:
        """Create or return a cached provider instance."""
        resolved_settings = settings or get_settings()
        name = provider_name or resolved_settings.LLM_PROVIDER

        if name in cls._instances:
            return cls._instances[name]

        if name == "ollama":
            provider: BaseLLMProvider = OllamaProvider(
                base_url=resolved_settings.OLLAMA_BASE_URL,
                model=resolved_settings.OLLAMA_MODEL,
                embed_model=resolved_settings.OLLAMA_EMBED_MODEL,
                timeout=resolved_settings.OLLAMA_TIMEOUT,
            )
        elif name == "gemini":
            if not resolved_settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY not configured")
            gemini_provider = GeminiProvider(
                api_key=resolved_settings.GEMINI_API_KEY,
                model=resolved_settings.GEMINI_MODEL,
                embed_model=resolved_settings.GEMINI_EMBED_MODEL,
            )
            if resolved_settings.GROQ_API_KEY:
                provider = FallbackLLMProvider(
                    [
                        gemini_provider,
                        GroqProvider(
                            api_key=resolved_settings.GROQ_API_KEY,
                            model=resolved_settings.GROQ_MODEL,
                        ),
                    ]
                )
            else:
                provider = gemini_provider
        else:
            raise ValueError(f"Unknown LLM provider: {name}")

        cls._instances[name] = provider
        return provider

    @classmethod
    def reset(cls) -> None:
        """Clear cached provider instances. Used in tests."""
        cls._instances.clear()
