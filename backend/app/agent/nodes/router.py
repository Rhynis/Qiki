"""``router`` node: a small deterministic classifier, not an LLM call.

Reused everything Qiki already has for this instead of reinventing NL parsing:
keyword matching via the same ``strip_accents`` helper
``product_query``/``admin_chat_service`` already use. The router only decides
*which* tool (if any) should run next; the tool itself does the real lookup
against the live catalog/KB, and the final natural-language answer is always
produced by the LLM in the ``responder`` node (never here) — this keeps
routing deterministic and unit-testable without mocking an LLM.

MVP scope: a single tool call per turn (no ReAct-style re-planning loop yet —
see ADR-0001's "near-zero marginal cost to add a planner step later").

Prompt-injection invariant (issue #348): ``tool_calls`` is derived ONLY from
``_last_human_text`` — the most recent ``HumanMessage`` — never from
``AIMessage``/``ToolMessage`` content. Retrieved KB documents and prior tool
output can end up quoted back into the transcript as AI/tool messages; if the
router ever read THOSE for routing decisions, injected text there could steer
a future tool call without a real user ever having typed it. The one
exception, ``_remembered_product_id``, reads a structurally-typed
``product_id`` field off a PRIOR ``search_products`` result (itself sourced
from the real catalog, never free text) — never prose — so it cannot be
steered by injected wording either. See ``tests/agent/test_tool_authz.py``'s
``TestPromptInjectionCannotTriggerAWrite`` for regression coverage of both.
"""

from typing import Any

from langchain_core.messages import HumanMessage

from app.agent.state import QikiAgentState, ToolCallRecord
from app.services.product_query import strip_accents

STOCK_KEYWORDS = ("con hang", "con khong", "ton kho", "in stock", "available")
SAFETY_INFO_KEYWORDS = (
    "bao quan",
    "an toan",
    "kiem tra dinh ky",
    "phong ngua",
    "safety",
    "how to store",
    "maintenance",
)
PRODUCT_KEYWORDS = (
    "gas",
    "binh",
    "nuoc uong",
    "gia",
    "kg",
    "lit",
    "price",
    "bottle",
    "cylinder",
)


def _last_human_text(state: QikiAgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""


def _remembered_product_id(state: QikiAgentState) -> str | None:
    """Find a single unambiguous product from the most recent search_products call.

    Lets a natural follow-up ("còn hàng không?") resolve without repeating the
    product name, mirroring how a human agent would remember what was just
    discussed.
    """
    for record in reversed(state.get("tool_results", [])):
        if record.get("name") != "search_products":
            continue
        result = record.get("result") or {}
        products = result.get("products") if isinstance(result, dict) else None
        if products and len(products) == 1:
            return str(products[0]["id"])
        return None
    return None


def _matches_any(haystack: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in haystack for keyword in keywords)


async def router(state: QikiAgentState) -> dict[str, Any]:
    """Decide the next tool call, if any; an empty list means "go to retriever"."""
    text = strip_accents(_last_human_text(state))

    tool_calls: list[ToolCallRecord] = []
    remembered_id = _remembered_product_id(state)
    if remembered_id and _matches_any(text, STOCK_KEYWORDS):
        tool_calls = [
            {"name": "check_inventory", "args": {"product_id": remembered_id, "quantity": 1}}
        ]
    elif _matches_any(text, SAFETY_INFO_KEYWORDS):
        tool_calls = [{"name": "lookup_safety_policy", "args": {"query": text}}]
    elif _matches_any(text, PRODUCT_KEYWORDS):
        tool_calls = [{"name": "search_products", "args": {"query": text}}]

    return {"tool_calls": tool_calls}


def route_after_router(state: QikiAgentState) -> str:
    """Conditional-edge selector: tool_executor when the router picked a tool."""
    return "tool_executor" if state.get("tool_calls") else "retriever"
