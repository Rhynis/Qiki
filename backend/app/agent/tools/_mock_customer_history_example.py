"""TEST-ONLY FIXTURE -- NOT A PRODUCTION TOOL.

This module exists solely to exercise the read-tool owner-scoping guardrail
(issue #348's cross-user-leak test) end-to-end.

A real ``get_customer_history`` tool would read actual order/conversation
rows for one customer -- exactly the kind of tool a prompt-injection attack
tries to trick into leaking someone ELSE's data. Building that real tool (and
touching real customer PII) is out of scope for #348, so this module is a
disposable stand-in: it returns fabricated, non-PII placeholder data, but
enforces the SAME ownership check a real version would need --
``current_user.id`` must equal the requested ``customer_user_id`` (or the
caller must be staff/admin), or the call is refused.

It is deliberately:

* NOT included in ``build_tools()`` (``agent/graph.py``) -- it is never
  reachable from the real ``/chat/agent/stream`` endpoint or any production
  conversation.
* NOT a real data-model traversal -- no table is queried; the "history" is a
  hardcoded placeholder, keyed only by the id already present in the request.

Registered in ``agent/tools/registry.py`` as ``mode="read", requires_auth=True,
requires_confirm=False``: reading isn't a mutation, but it IS per-user data,
so an anonymous caller must still be refused even though there is nothing
here to confirm. ``tool_executor`` already refuses an unauthenticated caller
before this tool is ever invoked; the ownership check below is
defense-in-depth for the case where a caller IS authenticated but is asking
for someone else's data.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from app.models.user import User

TOOL_NAME = "_mock_customer_history_example"


class MockCustomerHistoryArgs(BaseModel):
    """Args for the disposable mock read-scoped tool (demonstration only)."""

    customer_user_id: str = Field(description="Whose order history to look up.")


def build_mock_customer_history_example_tool(current_user: User | None) -> BaseTool:
    """Bind the resolved caller into the demonstration owner-scoped tool.

    ``current_user`` is closed over at build time -- the same pattern
    ``product_service`` uses -- so ``_run`` never has to trust an ``args``
    field for "who is asking"; only the field a caller could legitimately
    vary (``customer_user_id``, i.e. whose history) comes from the tool call
    itself.
    """

    async def _run(customer_user_id: str) -> dict[str, Any]:
        if current_user is None:
            # Defense-in-depth: tool_executor's authorization matrix already
            # refuses an unauthenticated caller before reaching here.
            return {"ok": False, "error": "authentication_required"}
        is_owner = str(current_user.id) == customer_user_id
        if not is_owner and not current_user.is_staff():
            return {"ok": False, "error": "forbidden_cross_user_access"}
        return {
            "ok": True,
            "customer_user_id": customer_user_id,
            # Fabricated placeholder -- never a real query against orders/users.
            "orders": [],
            "note": "demonstration data only, not a real customer record",
        }

    return StructuredTool.from_function(
        coroutine=_run,
        name=TOOL_NAME,
        description=(
            "DEMONSTRATION ONLY -- not a real tool, never reachable in production. "
            "Exists purely to prove per-record owner-scoping on a read tool."
        ),
        args_schema=MockCustomerHistoryArgs,
    )
