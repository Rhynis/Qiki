"""Factory for creating LLM provider instances."""

from typing import ClassVar

from app.core.config import Settings, get_settings
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import LLMConnectionError, LLMTimeoutError
from app.llm.providers.fallback_provider import FallbackLLMProvider
from app.llm.providers.gemini_provider import GeminiProvider
from app.llm.providers.groq_provider import GroqProvider
from app.llm.providers.ollama_provider import OllamaProvider
from app.llm.providers.vllm_provider import VLLMProvider

# A self-hosted vLLM box's dominant failure mode is "unreachable"/"timed out",
# not quota/rate-limit — extend the fallback trigger set so a downed GPU host
# still fails over, without changing FallbackLLMProvider's default behavior
# for the gemini<->groq chains below.
_VLLM_FALLBACK_ERRORS = (LLMConnectionError, LLMTimeoutError)


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
            if not resolved_settings.GEMINI_USE_VERTEX and not resolved_settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY not configured")
            gemini_provider = GeminiProvider(
                api_key=resolved_settings.GEMINI_API_KEY,
                model=resolved_settings.GEMINI_MODEL,
                embed_model=resolved_settings.GEMINI_EMBED_MODEL,
                settings=resolved_settings,
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
        elif name == "groq":
            if not resolved_settings.GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY not configured")
            groq_provider = GroqProvider(
                api_key=resolved_settings.GROQ_API_KEY,
                model=resolved_settings.GROQ_MODEL,
            )
            # Fall back to Gemini when it's configured so a Groq outage still answers.
            if resolved_settings.GEMINI_USE_VERTEX or resolved_settings.GEMINI_API_KEY:
                provider = FallbackLLMProvider(
                    [
                        groq_provider,
                        GeminiProvider(
                            api_key=resolved_settings.GEMINI_API_KEY,
                            model=resolved_settings.GEMINI_MODEL,
                            embed_model=resolved_settings.GEMINI_EMBED_MODEL,
                            settings=resolved_settings,
                        ),
                    ]
                )
            else:
                provider = groq_provider
        elif name == "vllm":
            vllm_provider = VLLMProvider(
                base_url=resolved_settings.VLLM_BASE_URL,
                model=resolved_settings.VLLM_MODEL,
                api_key=resolved_settings.VLLM_API_KEY,
                timeout=resolved_settings.VLLM_TIMEOUT,
            )
            # Prefer Groq as the API fallback (fast, cheap) when configured;
            # otherwise fall back to Gemini if that's configured; otherwise run
            # vLLM standalone — mirrors the groq/gemini mutual-fallback pattern
            # above.
            api_fallback: BaseLLMProvider | None = None
            if resolved_settings.GROQ_API_KEY:
                api_fallback = GroqProvider(
                    api_key=resolved_settings.GROQ_API_KEY,
                    model=resolved_settings.GROQ_MODEL,
                )
            elif resolved_settings.GEMINI_USE_VERTEX or resolved_settings.GEMINI_API_KEY:
                api_fallback = GeminiProvider(
                    api_key=resolved_settings.GEMINI_API_KEY,
                    model=resolved_settings.GEMINI_MODEL,
                    embed_model=resolved_settings.GEMINI_EMBED_MODEL,
                    settings=resolved_settings,
                )
            if api_fallback is not None:
                provider = FallbackLLMProvider(
                    [vllm_provider, api_fallback],
                    extra_fallback_errors=_VLLM_FALLBACK_ERRORS,
                )
            else:
                provider = vllm_provider
        else:
            raise ValueError(f"Unknown LLM provider: {name}")

        cls._instances[name] = provider
        return provider

    @classmethod
    def reset(cls) -> None:
        """Clear cached provider instances. Used in tests."""
        cls._instances.clear()
