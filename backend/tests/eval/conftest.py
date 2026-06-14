"""Eval-suite fixtures: gate LLM-judge metrics behind an API key.

Scripted-invariant tests run unconditionally. Judged (LLM-as-a-judge) metrics only
run when a key is present, so CI stays deterministic and free by default. The judge
reuses the project's GEMINI_API_KEY (Gemini AI Studio), so no OpenAI key is needed.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from app.core.config import get_settings

if TYPE_CHECKING:
    from deepeval.models import GeminiModel


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "judge: conversation eval needing an LLM judge (runs only when a key is present)",
    )


def _gemini_api_key() -> str | None:
    """Gemini AI Studio key from the live env, falling back to loaded settings."""
    return os.getenv("GEMINI_API_KEY") or get_settings().GEMINI_API_KEY


def judge_enabled() -> bool:
    return bool(
        os.getenv("DEEPEVAL_JUDGE")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("DEEPEVAL_API_KEY")
        or _gemini_api_key()
    )


def build_judge_model() -> GeminiModel | None:
    """Return the LLM-judge model, or None to use deepeval's default (OpenAI).

    Prefers Gemini so the judge reuses GEMINI_API_KEY (AI Studio key, no Vertex). When
    no Gemini key is set, returns None so an existing OpenAI/DeepEval key still works
    with deepeval's default judge.
    """
    api_key = _gemini_api_key()
    if not api_key:
        return None
    from deepeval.models import GeminiModel

    return GeminiModel(
        model=get_settings().GEMINI_MODEL,
        api_key=api_key,
        use_vertexai=False,
    )


@pytest.fixture
def requires_judge() -> None:
    if not judge_enabled():
        pytest.skip(
            "LLM-judge disabled: set GEMINI_API_KEY (Gemini) or "
            "DEEPEVAL_JUDGE / OPENAI_API_KEY to enable."
        )
