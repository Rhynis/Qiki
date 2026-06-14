"""Optional LLM-judge conversation metrics.

Skipped by default so CI stays deterministic and free; runs only when a judge key
is present (``GEMINI_API_KEY`` for the Gemini judge, or ``DEEPEVAL_JUDGE`` /
``OPENAI_API_KEY``). The scripted invariants in ``test_conversation_evals.py`` are
the must-pass core.
"""

from __future__ import annotations

import pytest

from tests.eval.conftest import build_judge_model, judge_enabled
from tests.eval.harness import run_full_gas_order


@pytest.mark.judge
@pytest.mark.asyncio
async def test_full_gas_order_conversation_completeness(
    monkeypatch: pytest.MonkeyPatch, requires_judge: None
) -> None:
    # Imported lazily: only reached when a judge key enabled the test.
    from deepeval import assert_test
    from deepeval.metrics import ConversationCompletenessMetric

    driver, _orders = await run_full_gas_order(monkeypatch)
    case = driver.to_test_case(
        scenario="Khách đặt 1 bình gas Petrolimex 12kg rồi xác nhận.",
        expected_outcome="Bot tóm tắt đơn, chờ xác nhận, rồi tạo đơn khi khách đồng ý.",
        name="specific_gas_order",
    )
    metric = ConversationCompletenessMetric(threshold=0.7, model=build_judge_model())
    assert_test(case, [metric])


def test_judge_default_skips_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GEMINI_API_KEY", "DEEPEVAL_JUDGE", "OPENAI_API_KEY", "DEEPEVAL_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert judge_enabled() is False
    assert build_judge_model() is None


def test_judge_enabled_with_gemini_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    assert judge_enabled() is True


def test_build_judge_model_returns_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    from deepeval.models import GeminiModel

    model = build_judge_model()
    assert isinstance(model, GeminiModel)
