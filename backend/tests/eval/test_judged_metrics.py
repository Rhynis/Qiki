"""Optional LLM-judge conversation metrics.

Skipped by default so CI stays deterministic and free; runs only when a judge key
is present (``DEEPEVAL_JUDGE`` / ``OPENAI_API_KEY``). The scripted invariants in
``test_conversation_evals.py`` are the must-pass core.
"""

from __future__ import annotations

import pytest

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
    assert_test(case, [ConversationCompletenessMetric(threshold=0.7)])
