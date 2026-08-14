"""Unit tests for the deterministic, non-LLM nodes: intake_guardrail,
safety_emergency, turn_limit, verifier. Each is a plain function, so these
run with no graph, no DB, and (for the safety/turn-limit nodes) no LLM.
"""

from langchain_core.messages import HumanMessage

from app.agent.nodes.intake_guardrail import intake_guardrail
from app.agent.nodes.safety_emergency import safety_emergency
from app.agent.nodes.turn_limit import turn_limit
from app.agent.nodes.verifier import verifier
from app.agent.state import QikiAgentState
from app.rag.safety import SAFETY_EMERGENCY_RESPONSE_EN, SAFETY_EMERGENCY_RESPONSE_VI, SafetyChecker


class TestIntakeGuardrail:
    async def test_increments_turn_count_from_zero(self) -> None:
        state: QikiAgentState = {"messages": [HumanMessage(content="xin chào")]}

        result = await intake_guardrail(state, safety_checker=SafetyChecker())

        assert result["turn_count"] == 1

    async def test_increments_an_existing_turn_count(self) -> None:
        state: QikiAgentState = {"messages": [HumanMessage(content="xin chào")], "turn_count": 4}

        result = await intake_guardrail(state, safety_checker=SafetyChecker())

        assert result["turn_count"] == 5

    async def test_detects_an_emergency_query(self) -> None:
        state: QikiAgentState = {"messages": [HumanMessage(content="nhà tôi đang rò gas")]}

        result = await intake_guardrail(state, safety_checker=SafetyChecker())

        assert result["safety_flags"]["is_emergency"] is True

    async def test_does_not_flag_a_normal_query(self) -> None:
        state: QikiAgentState = {"messages": [HumanMessage(content="giá gas 12kg bao nhiêu")]}

        result = await intake_guardrail(state, safety_checker=SafetyChecker())

        assert result["safety_flags"]["is_emergency"] is False


class TestSafetyEmergency:
    async def test_returns_the_fixed_vi_constant_with_no_llm_call(self) -> None:
        # get_emergency_response is synchronous (a plain constant lookup, no
        # I/O) — this node makes no async call at all, which is the point.
        state: QikiAgentState = {"messages": [], "locale": "vi"}

        result = await safety_emergency(state, safety_checker=SafetyChecker())

        assert result["messages"][0].content == SAFETY_EMERGENCY_RESPONSE_VI
        assert "090 3026306" in result["messages"][0].content
        assert result["confidence"] == 1.0

    async def test_returns_the_fixed_en_constant_for_the_en_locale(self) -> None:
        state: QikiAgentState = {"messages": [], "locale": "en"}

        result = await safety_emergency(state, safety_checker=SafetyChecker())

        assert result["messages"][0].content == SAFETY_EMERGENCY_RESPONSE_EN


class TestTurnLimit:
    async def test_returns_the_vi_handoff_reply_by_default(self) -> None:
        result = await turn_limit({"messages": []})

        assert "nhân viên hỗ trợ" in result["messages"][0].content

    async def test_returns_the_en_handoff_reply(self) -> None:
        result = await turn_limit({"messages": [], "locale": "en"})

        assert "support agent" in result["messages"][0].content


class TestVerifier:
    async def test_leaves_an_already_set_confidence_untouched(self) -> None:
        result = await verifier({"confidence": 0.42})

        assert result == {}

    async def test_derives_high_confidence_from_a_successful_tool_call(self) -> None:
        state: QikiAgentState = {
            "tool_results": [{"name": "search_products", "ok": True, "result": {}}]
        }

        result = await verifier(state)

        assert result["confidence"] == 1.0

    async def test_derives_zero_confidence_when_every_tool_call_failed(self) -> None:
        state: QikiAgentState = {
            "tool_results": [{"name": "check_inventory", "ok": False, "result": {}}]
        }

        result = await verifier(state)

        assert result["confidence"] == 0.0

    async def test_defaults_to_zero_confidence_with_no_results_at_all(self) -> None:
        result = await verifier({})

        assert result["confidence"] == 0.0
