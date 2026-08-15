"""``tool_executor`` node: run the tool(s) the router selected, gated by the
authorization matrix in ``agent/tools/registry.py`` (issue #348).

Every tool still returns a structured ``{"ok": bool, ...}`` payload rather
than raising (see ``agent/tools/``), and this node still wraps each call in
``try/except`` so a bug in a tool (or a transient DB error) degrades to a
structured error the ``responder`` can talk around, instead of crashing the
whole graph run -- unchanged from #346.

New in #348: before invoking ANY tool, this node checks its declared
authorization policy (read/write, requires_auth, requires_confirm) and
refuses -- with the same "never raise" structured-result convention -- a call
that doesn't satisfy it. A ``requires_confirm`` tool additionally routes
through LangGraph's ``interrupt()``: the first attempt pauses the graph and
surfaces a confirmation prompt instead of executing; a caller who resumes
with ``Command(resume={"approved": True, "pending_token": ...})`` re-validates
against a Redis-backed pending record (mirroring ``AdminChatService``'s
confirm+audit precedent, see ``agent/tools/confirm_gate.py``) and only then
lets the tool actually apply, after which an audit entry is recorded.

``interrupt()`` raises a ``GraphInterrupt`` (a normal ``Exception`` subclass,
verified against the installed langgraph package) on its first call per node
execution, which MUST propagate out of this node uncaught so LangGraph's own
executor can pause the graph on it -- this is why the authorization/confirm
step below runs OUTSIDE the ``try/except Exception`` that wraps the actual
``tool.ainvoke()`` call; catching it there would silently swallow the pause
and misreport it as a plain tool failure.
"""

from typing import Any, NamedTuple

from langchain_core.tools import BaseTool
from langgraph.types import interrupt

from app.agent.state import QikiAgentState, ToolResultRecord
from app.agent.tools.confirm_gate import ToolConfirmGate, derive_pending_token
from app.agent.tools.registry import ToolAuthPolicy, get_tool_policy
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.admin_audit_repository import AdminAuditRepository

logger = get_logger(__name__)

_AUTH_REQUIRED_RESULT: dict[str, Any] = {
    "ok": False,
    "error": "authentication_required",
    "message": "This action requires a signed-in user.",
}


class _AuthDecision(NamedTuple):
    """The outcome of checking one tool call against its authorization policy."""

    # Non-None => short-circuit with this structured result; never call the tool.
    refusal: dict[str, Any] | None
    # Non-None only when a `requires_confirm` call was JUST approved this
    # invocation -- the "before" snapshot to audit once the tool succeeds.
    audit_before: dict[str, Any] | None


async def tool_executor(
    state: QikiAgentState,
    *,
    tools: dict[str, BaseTool],
    current_user: User | None = None,
    confirm_gate: ToolConfirmGate | None = None,
    audit_repository: AdminAuditRepository | None = None,
) -> dict[str, Any]:
    """Invoke each queued tool call, enforcing its authorization policy first."""
    results: list[ToolResultRecord] = []
    for call in state.get("tool_calls", []):
        name = call.get("name", "")
        args = call.get("args", {})
        tool = tools.get(name)
        if tool is None:
            results.append({"name": name, "ok": False, "result": {"error": "unknown_tool"}})
            continue

        decision = await _authorize(
            get_tool_policy(name),
            name=name,
            args=args,
            session_id=state.get("session_id", ""),
            current_user=current_user,
            confirm_gate=confirm_gate,
        )
        if decision.refusal is not None:
            results.append({"name": name, "ok": False, "result": decision.refusal})
            continue

        try:
            result = await tool.ainvoke(args)
        except Exception as exc:  # noqa: BLE001 - a tool failure must not crash the graph
            logger.error("agent_tool_failed", tool=name, error=str(exc))
            result = {"ok": False, "error": "tool_execution_failed", "message": str(exc)}

        ok = bool(result.get("ok", False))
        if ok and decision.audit_before is not None:
            await _record_audit(
                audit_repository,
                current_user=current_user,
                name=name,
                args=args,
                before=decision.audit_before,
                result=result,
            )
        results.append({"name": name, "ok": ok, "result": result})

    return {"tool_results": results}


async def _record_audit(
    audit_repository: AdminAuditRepository | None,
    *,
    current_user: User | None,
    name: str,
    args: dict[str, Any],
    before: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Write one audit entry for a just-approved, just-applied confirm-gated call."""
    if audit_repository is None or current_user is None:
        return
    await audit_repository.record(
        admin_id=current_user.id,
        action=f"agent_tool:{name}",
        target_type="agent_tool_call",
        target_id=None,
        before=before,
        after={"tool": name, "args": args, "result": result},
    )


async def _authorize(
    policy: ToolAuthPolicy,
    *,
    name: str,
    args: dict[str, Any],
    session_id: str,
    current_user: User | None,
    confirm_gate: ToolConfirmGate | None,
) -> _AuthDecision:
    """Check one call against its policy; never raises, always decides."""
    if (policy.requires_auth or policy.requires_confirm) and current_user is None:
        logger.warning("agent_tool_denied_unauthenticated", tool=name)
        return _AuthDecision(refusal=dict(_AUTH_REQUIRED_RESULT), audit_before=None)

    if not policy.requires_confirm:
        return _AuthDecision(refusal=None, audit_before=None)

    if confirm_gate is None:
        # No Redis-backed confirm gate wired in (e.g. a graph built without
        # one) -- fail closed rather than silently skipping confirmation.
        logger.error("agent_tool_denied_no_confirm_gate", tool=name)
        refusal = {"ok": False, "error": "confirmation_unavailable"}
        return _AuthDecision(refusal=refusal, audit_before=None)

    assert current_user is not None  # narrowed by the auth check above
    return await _run_confirm_gate(
        name=name,
        args=args,
        session_id=session_id,
        current_user=current_user,
        confirm_gate=confirm_gate,
    )


async def _run_confirm_gate(
    *,
    name: str,
    args: dict[str, Any],
    session_id: str,
    current_user: User,
    confirm_gate: ToolConfirmGate,
) -> _AuthDecision:
    """Pause on the first attempt via ``interrupt()``; apply only on a valid resume.

    The token is derived deterministically (see ``confirm_gate.py``) because
    everything before the ``interrupt()`` call below re-runs on resume --
    including this function's own ``store_pending`` call -- so the SAME
    (session, user, tool, args) tuple must always yield the SAME token, or
    the resumed decision's ``pending_token`` would no longer match what the
    caller was told to echo back.
    """
    user_id = str(current_user.id)
    token = derive_pending_token(session_id=session_id, user_id=user_id, tool_name=name, args=args)
    await confirm_gate.store_pending(
        token=token,
        user_id=user_id,
        tool_name=name,
        args=args,
        # A real write tool (e.g. future create_order) would snapshot the
        # target row's current state here, exactly like AdminChatService's
        # before_snapshot, so a later optimistic-concurrency check can detect
        # a change between plan and confirm. This demonstration tool has no
        # target row to snapshot.
        before_snapshot={},
    )

    decision = interrupt(
        {
            "type": "confirm_required",
            "tool": name,
            "args": args,
            "pending_token": token,
        }
    )

    if not isinstance(decision, dict) or decision.get("approved") is not True:
        logger.info("agent_tool_confirm_declined", tool=name)
        refusal = {"ok": False, "error": "confirmation_declined"}
        return _AuthDecision(refusal=refusal, audit_before=None)
    if decision.get("pending_token") != token:
        # The resume doesn't reference the call it's supposedly confirming --
        # e.g. a stale/forged token, or a decision meant for a different call.
        logger.warning("agent_tool_confirm_token_mismatch", tool=name)
        refusal = {"ok": False, "error": "confirmation_invalid"}
        return _AuthDecision(refusal=refusal, audit_before=None)

    claimed = await confirm_gate.claim_pending(token)
    if claimed is None:
        refusal = {"ok": False, "error": "confirmation_expired"}
        return _AuthDecision(refusal=refusal, audit_before=None)
    call_matches = claimed.get("tool_name") == name and claimed.get("args") == args
    if claimed.get("user_id") != str(current_user.id) or not call_matches:
        logger.warning("agent_tool_confirm_call_mismatch", tool=name)
        refusal = {"ok": False, "error": "confirmation_invalid"}
        return _AuthDecision(refusal=refusal, audit_before=None)

    before_snapshot = claimed.get("before_snapshot")
    return _AuthDecision(
        refusal=None, audit_before=before_snapshot if before_snapshot is not None else {}
    )
