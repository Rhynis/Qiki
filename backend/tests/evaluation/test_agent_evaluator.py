"""Tests for the agent-level evaluation suite (app/evaluation/agent_evaluator.py).

Deterministic only: every evaluator here is built with ``enable_judge=False``,
which forces the LLM-judge subset off — these tests need no LLM, no network,
and no Ollama server, matching the tool-selection/argument-correctness CI hard
gate's contract (see agent_evaluator.py's module docstring). The judge subset
itself (task_completion_rate/trajectory_score) is exercised manually via
``python scripts/run_evaluation.py --suite agent`` when a local Ollama server
is running — not asserted on here, since it is explicitly best-effort/optional.
"""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.agent_evaluator import AgentEvaluator
from app.evaluation.schemas import AgentTestCase, ExpectedToolCall
from app.models.product import Product
from app.repositories.product_repository import ProductRepository
from app.services.product_service import ProductService

# No module-level `pytestmark = pytest.mark.asyncio`: this file mixes sync
# (golden-set shape) and async (evaluator) tests, and `asyncio_mode = "auto"`
# (pyproject.toml) already collects async tests correctly without it.
EXPECTED_CATEGORIES = {
    "product_inquiry",
    "safety_info",
    "ambiguous",
    "out_of_stock",
    "check_inventory",
    "safety_emergency",
    "generic_faq",
}


def load_agent_cases() -> list[AgentTestCase]:
    path = Path("data/eval/agent_test_suite.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [AgentTestCase.model_validate(item) for item in data]


def _cases_by_id(*ids: str) -> list[AgentTestCase]:
    all_cases = {case.id: case for case in load_agent_cases()}
    return [all_cases[case_id] for case_id in ids]


def _evaluator(product_session: AsyncSession) -> AgentEvaluator:
    return AgentEvaluator(
        product_service=ProductService(ProductRepository(product_session)),
        enable_judge=False,
    )


class TestGoldenSetShape:
    def test_suite_has_at_least_25_cases(self) -> None:
        assert len(load_agent_cases()) >= 25

    def test_every_expected_category_present(self) -> None:
        categories = {case.category for case in load_agent_cases()}
        assert categories == EXPECTED_CATEGORIES

    def test_safety_emergency_cases_expect_zero_tool_calls(self) -> None:
        emergency_cases = [c for c in load_agent_cases() if c.category == "safety_emergency"]
        assert len(emergency_cases) >= 3
        for case in emergency_cases:
            assert case.expected_tool_calls == []

    def test_generic_faq_cases_expect_zero_tool_calls(self) -> None:
        faq_cases = [c for c in load_agent_cases() if c.category == "generic_faq"]
        assert len(faq_cases) >= 3
        for case in faq_cases:
            assert case.expected_tool_calls == []

    def test_check_inventory_cases_are_multi_turn(self) -> None:
        checkinv_cases = [c for c in load_agent_cases() if c.category == "check_inventory"]
        assert len(checkinv_cases) >= 2
        for case in checkinv_cases:
            assert len(case.turns) >= 2
            assert case.expected_tool_calls[0].name == "check_inventory"


class TestDeterministicToolSelection:
    """Each test runs the REAL compiled agent graph (stub LLM only) end to end."""

    async def test_product_inquiry_calls_search_products(
        self, product_session: AsyncSession
    ) -> None:
        report = await _evaluator(product_session).evaluate(_cases_by_id("agent_product_001"))

        assert report.metrics.tool_selection_accuracy == 1.0
        assert report.metrics.argument_correctness_rate == 1.0
        assert report.failed_case_ids == []

    async def test_safety_info_calls_lookup_safety_policy_not_emergency(
        self, product_session: AsyncSession
    ) -> None:
        report = await _evaluator(product_session).evaluate(
            _cases_by_id("agent_safety_info_001", "agent_safety_info_004")
        )

        assert report.metrics.tool_selection_accuracy == 1.0
        assert report.metrics.safety_regression_count == 0

    async def test_generic_faq_calls_no_tool(self, product_session: AsyncSession) -> None:
        report = await _evaluator(product_session).evaluate(_cases_by_id("agent_faq_001"))

        assert report.metrics.tool_selection_accuracy == 1.0

    async def test_emergency_case_calls_no_tool_and_returns_the_hotline(
        self, product_session: AsyncSession
    ) -> None:
        report = await _evaluator(product_session).evaluate(
            _cases_by_id("agent_emergency_001", "agent_emergency_004")
        )

        assert report.metrics.tool_selection_accuracy == 1.0
        assert report.metrics.safety_regression_count == 0
        assert report.failed_case_ids == []

    async def test_check_inventory_resolves_the_remembered_product(
        self, product_session: AsyncSession
    ) -> None:
        report = await _evaluator(product_session).evaluate(
            _cases_by_id("agent_checkinv_001", "agent_checkinv_002")
        )

        assert report.metrics.tool_selection_accuracy == 1.0
        assert report.metrics.argument_correctness_rate == 1.0
        assert report.failed_case_ids == []

    async def test_out_of_stock_case_calls_search_products(
        self, product_session: AsyncSession
    ) -> None:
        report = await _evaluator(product_session).evaluate(_cases_by_id("agent_stock_001"))

        assert report.metrics.tool_selection_accuracy == 1.0

    async def test_full_suite_meets_the_ci_threshold(self, product_session: AsyncSession) -> None:
        report = await _evaluator(product_session).evaluate(load_agent_cases())

        assert report.metrics.tool_selection_accuracy is not None
        assert report.metrics.tool_selection_accuracy >= 0.85
        assert report.metrics.safety_regression_count == 0

    async def test_no_llm_judge_scores_when_judge_disabled(
        self, product_session: AsyncSession
    ) -> None:
        # judge_eligible=true in the golden set, but enable_judge=False must win.
        report = await _evaluator(product_session).evaluate(_cases_by_id("agent_product_006"))

        assert report.metrics.task_completion_rate is None
        assert report.metrics.trajectory_score is None


class TestMismatchIsDetected:
    """A deliberately wrong expectation must fail — proves the comparator isn't a no-op."""

    async def test_wrong_expected_tool_name_is_flagged(self, product_session: AsyncSession) -> None:
        case = _cases_by_id("agent_product_001")[0]
        wrong_case = case.model_copy(
            update={
                "expected_tool_calls": [
                    ExpectedToolCall(name="lookup_safety_policy", args={"query": "*"})
                ]
            }
        )

        report = await _evaluator(product_session).evaluate([wrong_case])

        assert report.metrics.tool_selection_accuracy == 0.0
        assert report.failed_case_ids == [case.id]

    async def test_wrong_expected_arg_value_is_flagged(self, product_session: AsyncSession) -> None:
        case = _cases_by_id("agent_checkinv_001")[0]
        wrong_case = case.model_copy(
            update={
                "expected_tool_calls": [
                    ExpectedToolCall(
                        name="check_inventory", args={"product_id": "*", "quantity": 99}
                    )
                ]
            }
        )

        report = await _evaluator(product_session).evaluate([wrong_case])

        assert report.metrics.tool_selection_accuracy == 1.0  # tool name still matched
        assert report.metrics.argument_correctness_rate == 0.0
        assert report.failed_case_ids == [case.id]


class TestSeedProductsCleanedUp:
    async def test_seed_products_do_not_leak_after_evaluate(
        self, product_session: AsyncSession
    ) -> None:
        await _evaluator(product_session).evaluate(_cases_by_id("agent_checkinv_001"))

        result = await product_session.execute(select(Product).where(Product.sku.like("EVAL-%")))
        assert result.scalars().all() == []
