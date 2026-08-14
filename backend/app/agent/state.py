"""Shared state channel for the Qiki LangGraph agent.

``AsyncPostgresSaver`` checkpoints this dict at every superstep (ADR-0002), so
a checkpoint written today may be resumed by code running a later release
that has added a new key. Two defensive rules follow from that:

* Every key is optional (``total=False``) — nothing in the graph may assume a
  key is present.
* Node code reads via ``state.get("key", default)``, never ``state["key"]``,
  so resuming an old checkpoint can never KeyError on a field that didn't
  exist when it was written.
"""

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

# Hard ceiling on agent turns within one thread, independent of LangGraph's own
# ``recursion_limit`` (a superstep budget for a single ``astream`` call). This
# caps how many router->tool_executor->router loops one user turn may take
# before the graph is forced to respond with whatever it has.
MAX_AGENT_TURNS = 8


class ToolCallRecord(TypedDict, total=False):
    """One tool invocation the router/tool_executor decided to make."""

    name: str
    args: dict[str, Any]


class ToolResultRecord(TypedDict, total=False):
    """The structured outcome of one tool call — never a raised exception."""

    name: str
    ok: bool
    result: Any


class SafetyFlags(TypedDict, total=False):
    """Mirrors ``app.rag.schemas.SafetyResult`` for the fields the graph needs."""

    is_emergency: bool
    matched_pattern: str | None


class RetrievedDocSummary(TypedDict, total=False):
    """A bounded summary of one retrieved KB document (ADR-0002: keep state lean)."""

    id: str
    title: str
    content: str
    similarity: float


class QikiAgentState(TypedDict, total=False):
    """Cross-turn state for one conversation thread (``thread_id = session_id``)."""

    # `add_messages` is the standard LangGraph reducer: new messages appended
    # by a node are merged into the running history instead of overwriting it.
    messages: Annotated[list[AnyMessage], add_messages]

    session_id: str
    user_id: str | None
    locale: Literal["vi", "en"]

    intent: str | None
    confidence: float | None

    retrieved_docs: list[RetrievedDocSummary]
    tool_calls: list[ToolCallRecord]
    tool_results: list[ToolResultRecord]

    safety_flags: SafetyFlags
    turn_count: int
    llm_provider: str | None
