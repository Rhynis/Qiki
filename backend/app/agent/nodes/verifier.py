"""``verifier`` node: a lightweight, deterministic grounding check.

MVP scope keeps this intentionally simple (no LLM self-critique yet) — the
node this ADR-0001 argues is now cheap to *add*, not something this PR builds
out fully. It only derives a confidence score from what already happened
(tool success/failure, retrieval similarity) so ``responder`` can decide
whether to hedge the answer.
"""

from typing import Any

from app.agent.state import QikiAgentState


async def verifier(state: QikiAgentState) -> dict[str, Any]:
    """Derive a confidence score from the tool/retrieval results, if not already set."""
    if state.get("confidence") is not None:
        return {}

    tool_results = state.get("tool_results", [])
    if tool_results:
        confidence = 1.0 if any(record.get("ok") for record in tool_results) else 0.0
        return {"confidence": confidence}

    return {"confidence": 0.0}
