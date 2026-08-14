"""``turn_limit`` node: the deterministic reply once a thread exceeds
``MAX_AGENT_TURNS``. Also makes no LLM call — a runaway thread should not cost
another generation on top of whatever made it runaway.
"""

from typing import Any

from langchain_core.messages import AIMessage

from app.agent.state import QikiAgentState

TURN_LIMIT_REPLY_VI = (
    "Cuộc trò chuyện này đã khá dài. Mình xin phép chuyển bạn đến nhân viên hỗ trợ "
    "để được tư vấn kỹ hơn nhé."
)
TURN_LIMIT_REPLY_EN = (
    "This conversation has run long. Let me hand you over to a support agent "
    "for more detailed help."
)


async def turn_limit(state: QikiAgentState) -> dict[str, Any]:
    """Return the fixed hand-off reply for a thread past the turn cap."""
    locale = state.get("locale", "vi")
    reply = TURN_LIMIT_REPLY_EN if locale == "en" else TURN_LIMIT_REPLY_VI
    return {"messages": [AIMessage(content=reply)]}
