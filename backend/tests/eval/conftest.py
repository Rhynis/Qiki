"""Eval-suite fixtures: gate LLM-judge metrics behind an API key.

Scripted-invariant tests run unconditionally. Judged (LLM-as-a-judge) metrics
only run when a key is present, so CI stays deterministic and free by default.
"""

from __future__ import annotations

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "judge: conversation eval needing an LLM judge (runs only when a key is present)",
    )


def judge_enabled() -> bool:
    return bool(
        os.getenv("DEEPEVAL_JUDGE") or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPEVAL_API_KEY")
    )


@pytest.fixture
def requires_judge() -> None:
    if not judge_enabled():
        pytest.skip("LLM-judge disabled: set DEEPEVAL_JUDGE / OPENAI_API_KEY to enable.")
