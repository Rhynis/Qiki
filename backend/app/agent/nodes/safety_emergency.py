"""``safety_emergency`` node: the deterministic, non-LLM emergency response.

Reached only via the conditional edge after ``intake_guardrail`` when
``safety_flags.is_emergency`` is true. Reuses ``rag/safety.py``'s fixed
constant — the exact same text the existing RAG pipeline returns for an
emergency query — so the agent path can never diverge from the audited
RAG-path wording. This node makes NO LLM call.
"""

from typing import Any

from langchain_core.messages import AIMessage

from app.agent.state import QikiAgentState
from app.rag.safety import SafetyChecker


async def safety_emergency(
    state: QikiAgentState, *, safety_checker: SafetyChecker
) -> dict[str, Any]:
    """Return the fixed emergency response for the current locale."""
    locale = state.get("locale", "vi")
    response_text = safety_checker.get_emergency_response(locale)
    return {
        "messages": [AIMessage(content=response_text)],
        "confidence": 1.0,
    }
