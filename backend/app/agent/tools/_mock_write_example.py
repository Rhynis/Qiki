"""TEST-ONLY FIXTURE -- NOT A PRODUCTION TOOL.

This module exists solely to exercise the write-tool authorization + HITL
confirm guardrails (issue #348) end-to-end: a ``mode="write",
requires_auth=True, requires_confirm=True`` tool for
``tests/agent/test_tool_authz.py`` to drive through ``tool_executor``'s
enforcement + ``interrupt()`` confirm gate + audit logging, before the real
mutating tool (``create_order``, a later issue -- #348 explicitly scopes it
out) exists.

It is deliberately:

* NOT included in ``build_tools()`` (``agent/graph.py``) -- it is never
  reachable from the real ``/chat/agent/stream`` endpoint or any production
  conversation. ``test_graph.py``/``test_tool_authz.py`` assert this.
* NOT a real mutation against the ``orders``/``order_items`` tables --
  "applying" upserts a namespaced Redis key, not a database row, and never
  reads or writes real customer/order/product data.

Its "apply" step is an idempotent upsert keyed by ``idempotency_key`` (a
natural id), per the issue's explicit warning that LangGraph re-executes a
node's full body on ``interrupt()`` resume -- a blind INSERT would
double-apply if the node (and therefore this tool call) ran twice.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field
from redis.asyncio import Redis

TOOL_NAME = "_mock_create_order_example"
_REDIS_KEY_PREFIX = "agent_tool:mock_order:"


class MockCreateOrderArgs(BaseModel):
    """Args for the disposable mock write tool (demonstration only)."""

    customer_user_id: str = Field(description="The id of the user this mock order is for.")
    product_sku: str = Field(description="A catalog SKU, for illustration only.")
    idempotency_key: str = Field(
        description="Natural id for the upsert; the SAME key must always produce the SAME row."
    )
    quantity: int = Field(default=1, ge=1)


def build_mock_create_order_example_tool(redis: Redis) -> BaseTool:
    """Bind a Redis client into the demonstration write tool.

    ``redis`` here plays the same role ``product_service`` plays for the 3
    real tools -- a dependency closed over at build time -- except this
    tool's "database" is a disposable Redis namespace, never ``orders``.
    """

    async def _run(
        customer_user_id: str,
        product_sku: str,
        idempotency_key: str,
        quantity: int = 1,
    ) -> dict[str, Any]:
        key = f"{_REDIS_KEY_PREFIX}{idempotency_key}"
        existing = await redis.get(key)
        before = json.loads(existing) if existing else None
        after = {
            "customer_user_id": customer_user_id,
            "product_sku": product_sku,
            "quantity": quantity,
        }
        # Idempotent upsert: the same idempotency_key always converges on the
        # same stored value, so re-running this apply step (a resumed
        # interrupt, a retried request, ...) never accumulates a duplicate
        # "order" -- see the module docstring.
        await redis.set(key, json.dumps(after))
        return {
            "ok": True,
            "idempotency_key": idempotency_key,
            "before": before,
            "after": after,
        }

    return StructuredTool.from_function(
        coroutine=_run,
        name=TOOL_NAME,
        description=(
            "DEMONSTRATION ONLY -- not a real tool, never reachable in production. "
            "Exists purely to prove the write-tool authorization + confirm guardrails."
        ),
        args_schema=MockCreateOrderArgs,
    )
