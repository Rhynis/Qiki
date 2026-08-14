"""Unit tests for the deterministic router node (no DB, no LLM).

The router is a plain keyword classifier (see agent/nodes/router.py's
docstring for why it is not an LLM tool-calling planner in this MVP) so these
tests exercise it directly, with no mocking required.
"""

from langchain_core.messages import HumanMessage

from app.agent.nodes.router import route_after_router, router
from app.agent.state import QikiAgentState


def _state(text: str, **overrides: object) -> QikiAgentState:
    base: QikiAgentState = {"messages": [HumanMessage(content=text)]}
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class TestRouter:
    async def test_product_question_routes_to_search_products(self) -> None:
        result = await router(_state("gas Elf 12kg giá bao nhiêu"))

        assert result["tool_calls"] == [
            {"name": "search_products", "args": {"query": "gas elf 12kg gia bao nhieu"}}
        ]

    async def test_safety_info_question_routes_to_lookup_safety_policy(self) -> None:
        result = await router(_state("cách bảo quản bình gas an toàn"))

        assert result["tool_calls"][0]["name"] == "lookup_safety_policy"

    async def test_generic_faq_has_no_tool_call(self) -> None:
        result = await router(_state("cửa hàng mở cửa mấy giờ"))

        assert result["tool_calls"] == []

    async def test_stock_followup_with_remembered_product_routes_to_check_inventory(
        self,
    ) -> None:
        state = _state(
            "còn hàng không",
            tool_results=[
                {
                    "name": "search_products",
                    "ok": True,
                    "result": {"ok": True, "total": 1, "products": [{"id": "prod-123"}]},
                }
            ],
        )

        result = await router(state)

        assert result["tool_calls"] == [
            {"name": "check_inventory", "args": {"product_id": "prod-123", "quantity": 1}}
        ]

    async def test_stock_followup_with_no_remembered_product_falls_through(self) -> None:
        # "còn hàng không" alone matches no PRODUCT_KEYWORDS, so with nothing to
        # remember it must not guess — it goes to the retriever, not a tool.
        result = await router(_state("còn hàng không"))

        assert result["tool_calls"] == []

    async def test_stock_followup_ignores_an_ambiguous_multi_product_result(self) -> None:
        state = _state(
            "còn hàng không",
            tool_results=[
                {
                    "name": "search_products",
                    "ok": True,
                    "result": {
                        "ok": True,
                        "total": 2,
                        "products": [{"id": "prod-1"}, {"id": "prod-2"}],
                    },
                }
            ],
        )

        result = await router(state)

        assert result["tool_calls"] == []


class TestRouteAfterRouter:
    def test_empty_tool_calls_goes_to_retriever(self) -> None:
        assert route_after_router({"tool_calls": []}) == "retriever"

    def test_queued_tool_call_goes_to_tool_executor(self) -> None:
        state: QikiAgentState = {"tool_calls": [{"name": "search_products", "args": {}}]}
        assert route_after_router(state) == "tool_executor"
