"""Tests for the Phase 4.4 RAG configuration defaults."""

from app.core.config import Settings


def _default(name: str) -> object:
    return Settings.model_fields[name].default


def test_rag_embedding_and_rerank_defaults() -> None:
    # Assert the declared field defaults (independent of any local .env override).
    # Default provider stays Gemini so production behavior is unchanged.
    assert _default("EMBEDDING_PROVIDER") == "gemini"
    assert _default("OLLAMA_BGE_MODEL") == "bge-m3"
    assert _default("BGE_EMBEDDING_DIMENSIONS") == 1024

    assert _default("RAG_THRESHOLD_GEMINI") == 0.5
    assert _default("RAG_THRESHOLD_OLLAMA") == 0.7
    assert _default("RAG_THRESHOLD_BGE") == 0.55

    # Reranker is OFF by default so the production path is byte-for-byte unchanged.
    assert _default("RAG_RERANK_ENABLED") is False
    assert _default("RAG_RERANK_RETRIEVE_K") == 8
    assert _default("RAG_RERANK_TOP_N") == 3
