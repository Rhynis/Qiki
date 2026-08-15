"""Declarative tool-authorization matrix (least-privilege, issue #348).

Every tool the agent can call is registered here with its authorization
policy: whether it mutates anything (``mode``), whether it requires an
authenticated caller (``requires_auth``), and whether it requires an explicit
human confirmation before it may run (``requires_confirm``).
``agent/nodes/tool_executor.py`` enforces this matrix before invoking any
tool -- a tool is never called just because the router queued it.

This is the whole point of "declarative": adding a new tool never touches the
enforcement code. A future real mutating tool (e.g. ``create_order``, out of
scope for #348 -- see the issue) just adds one entry here:

    "create_order": ToolAuthPolicy(mode="write", requires_auth=True, requires_confirm=True)

and ``tool_executor`` already knows how to gate it -- no new branches, no
per-tool special-casing.

Fail-closed default: a tool name with NO entry here gets the MOST restrictive
policy (write + auth + confirm), not the most permissive. A missing
registration must never silently grant a new tool unauthenticated,
unconfirmed access -- see ``get_tool_policy``.
"""

from typing import Literal, NamedTuple

ToolMode = Literal["read", "write"]


class ToolAuthPolicy(NamedTuple):
    """One tool's authorization requirements."""

    mode: ToolMode
    requires_auth: bool
    requires_confirm: bool


# The 3 MVP tools (#346): read-only catalog/KB lookups, open to any caller
# (including an anonymous storefront visitor), no confirmation needed.
_READ_PUBLIC = ToolAuthPolicy(mode="read", requires_auth=False, requires_confirm=False)

# The single most-restrictive policy: used both for the worked write-tool
# example below and as the fail-closed default for an unregistered name.
_WRITE_AUTH_CONFIRM = ToolAuthPolicy(mode="write", requires_auth=True, requires_confirm=True)

TOOL_AUTH_REGISTRY: dict[str, ToolAuthPolicy] = {
    "search_products": _READ_PUBLIC,
    "check_inventory": _READ_PUBLIC,
    "lookup_safety_policy": _READ_PUBLIC,
    # --- Worked examples only (issue #348) -------------------------------
    # Neither is wired into `build_tools()` (agent/graph.py) or reachable
    # from the production `/chat/agent/stream` endpoint. They exist so
    # tests/agent/test_tool_authz.py can drive a real write tool and a real
    # per-record-scoped read tool through this matrix end-to-end, before the
    # real `create_order` write tool (a later issue) exists. See their
    # module docstrings under agent/tools/_mock_*_example.py.
    "_mock_create_order_example": _WRITE_AUTH_CONFIRM,
    # A read tool that doesn't mutate anything can still need auth: it
    # returns per-user data, so an anonymous caller must be refused even
    # though there's nothing here for them to confirm.
    "_mock_customer_history_example": ToolAuthPolicy(
        mode="read", requires_auth=True, requires_confirm=False
    ),
}


def get_tool_policy(tool_name: str) -> ToolAuthPolicy:
    """Look up a tool's authorization policy, fail-closed for unregistered names."""
    return TOOL_AUTH_REGISTRY.get(tool_name, _WRITE_AUTH_CONFIRM)
