"""``intake_guardrail`` node: turn-count cap + the safety check (detection only).

Mirrors ``RAGPipeline.query``'s "safety check first, before retrieval or
generation" ordering. This node only *detects* — it bumps ``turn_count`` and
records ``safety_flags``; the graph's conditional edges decide, from those
flags, whether to route to the ``safety_emergency`` or ``turn_limit`` terminal
node instead of ``router``. Neither short-circuit ever touches the LLM.
"""

from typing import Any

from langchain_core.messages import HumanMessage

from app.agent.state import QikiAgentState
from app.rag.safety import SafetyChecker


def _last_human_text(state: QikiAgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""


async def intake_guardrail(
    state: QikiAgentState, *, safety_checker: SafetyChecker
) -> dict[str, Any]:
    """Bump the turn counter and run the safety detector on the latest message."""
    turn_count = state.get("turn_count", 0) + 1
    safety_result = await safety_checker.check_query(_last_human_text(state))
    return {
        "turn_count": turn_count,
        "safety_flags": {
            "is_emergency": safety_result.is_emergency,
            "matched_pattern": safety_result.matched_pattern,
        },
    }
