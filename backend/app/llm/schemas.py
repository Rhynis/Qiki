"""Pydantic schemas for LLM operations."""

from typing import Literal

from pydantic import BaseModel


class Message(BaseModel):
    """A single message in a conversation."""

    role: Literal["system", "user", "assistant"]
    content: str


class LLMResponse(BaseModel):
    """Response from an LLM generation call."""

    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int
    model: str
    provider: str
    finish_reason: str | None = None
    cost_usd: float | None = None


class LLMStreamChunk(BaseModel):
    """A single chunk from a streaming generation.

    ``provider`` / ``model`` / ``total_tokens`` are surfaced so a streaming caller
    can attribute the answer to the provider that actually served it (e.g. through
    the fallback chain) and record usage when the provider reports it. They are
    optional because not every chunk carries them (usage typically arrives on the
    final chunk).
    """

    delta: str
    finish_reason: str | None = None
    accumulated_text: str
    provider: str | None = None
    model: str | None = None
    total_tokens: int | None = None


class EmbeddingResponse(BaseModel):
    """Response from an embedding call."""

    embedding: list[float]
    dimensions: int
    model: str
