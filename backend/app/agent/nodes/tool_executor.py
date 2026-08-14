"""``tool_executor`` node: run the tool(s) the router selected.

Every tool returns a structured ``{"ok": bool, ...}`` payload rather than
raising (see ``agent/tools/``), but this node still wraps the call in
``try/except`` so a bug in a tool (or a transient DB error) degrades to a
structured error the ``responder`` can talk around, instead of crashing the
whole graph run.
"""

from typing import Any

from langchain_core.tools import BaseTool

from app.agent.state import QikiAgentState, ToolResultRecord
from app.core.logging import get_logger

logger = get_logger(__name__)


async def tool_executor(state: QikiAgentState, *, tools: dict[str, BaseTool]) -> dict[str, Any]:
    """Invoke each queued tool call and collect its structured result."""
    results: list[ToolResultRecord] = []
    for call in state.get("tool_calls", []):
        name = call.get("name", "")
        tool = tools.get(name)
        if tool is None:
            results.append({"name": name, "ok": False, "result": {"error": "unknown_tool"}})
            continue
        try:
            result = await tool.ainvoke(call.get("args", {}))
        except Exception as exc:  # noqa: BLE001 - a tool failure must not crash the graph
            logger.error("agent_tool_failed", tool=name, error=str(exc))
            result = {"ok": False, "error": "tool_execution_failed", "message": str(exc)}
        results.append({"name": name, "ok": bool(result.get("ok", False)), "result": result})

    return {"tool_results": results}
