"""``lookup_safety_policy`` tool: informational safety KB lookup (read-only).

This is NOT the emergency safety gate. A query that looks like an active
emergency (gas leak, fire, ...) is caught by ``rag/safety.py`` at the graph's
``safety_emergency`` short-circuit *before* the router ever runs, and answered
with the fixed constant response — never the LLM, never a tool. This tool only
fires for calm, informational safety questions (e.g. "cách bảo quản bình gas
an toàn" — how to store a cylinder safely) that the router sent through the
normal tool-calling path.
"""

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from app.services.knowledge_base_service import KnowledgeBaseService

TOOL_NAME = "lookup_safety_policy"
TOP_K = 3


class LookupSafetyPolicyArgs(BaseModel):
    """A non-emergency safety or usage-guidance question."""

    query: str = Field(
        description=(
            "The customer's safety/usage question, e.g. 'cách bảo quản bình gas' "
            "or 'how often should I check the gas hose'."
        )
    )


def build_lookup_safety_policy_tool(kb_service: KnowledgeBaseService) -> BaseTool:
    """Bind a request-scoped KnowledgeBaseService into a lookup_safety_policy tool."""

    async def _run(query: str) -> dict[str, Any]:
        results = await kb_service.search_documents(
            query, top_k=TOP_K, category="safety", use_hybrid=True
        )
        return {
            "ok": True,
            "documents": [
                {
                    "title": result.title,
                    "content": result.content,
                    "similarity": result.similarity,
                }
                for result in results
            ],
        }

    return StructuredTool.from_function(
        coroutine=_run,
        name=TOOL_NAME,
        description=(
            "Look up non-emergency gas-safety guidance from the knowledge base "
            "(e.g. storage, maintenance, general precautions). Read-only. Do NOT "
            "use this for an active emergency (leak, fire, suffocation) — that is "
            "handled separately and never reaches a tool call."
        ),
        args_schema=LookupSafetyPolicyArgs,
    )
