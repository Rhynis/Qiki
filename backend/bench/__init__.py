"""Serving benchmark + quantization-quality harnesses (CPU-only, prod-safe).

These scripts drive Qiki's existing ``BaseLLMProvider`` abstraction so vLLM,
Ollama, Gemini, and Groq are compared apples-to-apples. They never import
``vllm`` itself — the provider they exercise is ``VLLMProvider``, a plain
HTTP client (see ``app/llm/providers/vllm_provider.py``). No GPU or live
model server is required to run these in CI: pass ``--provider mock``.
"""
