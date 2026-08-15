"""LangGraph agent endpoint — feature-flagged (AGENT_ENABLED, default off).

The existing ``/conversations/{id}/messages/stream`` (RAG) endpoint is
untouched by this module; this is an additive, separate path (see
docs/adr/0001-langgraph-agent-orchestration.md).
"""

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import RECURSION_LIMIT, build_agent_graph
from app.agent.state import QikiAgentState
from app.agent.tools.confirm_gate import ToolConfirmGate
from app.api.v1.dependencies.auth import get_current_user_optional
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.redis import get_redis
from app.db.session import get_db
from app.llm.base import BaseLLMProvider
from app.llm.dependencies import get_llm_provider, get_prompt_library
from app.llm.prompts.templates import PromptLibrary
from app.models.user import User
from app.rag.context_builder import ContextBuilder
from app.rag.dependencies import (
    get_context_builder,
    get_default_retriever,
    get_knowledge_base_service,
    get_safety_checker,
)
from app.rag.retriever import BaseRetriever
from app.rag.safety import SafetyChecker
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.conversation import SendMessageRequest
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.product_service import ProductService

router = APIRouter()

AgentGraph = CompiledStateGraph[QikiAgentState, None, QikiAgentState, QikiAgentState]


def get_agent_graph(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    safety_checker: Annotated[SafetyChecker, Depends(get_safety_checker)],
    retriever: Annotated[BaseRetriever, Depends(get_default_retriever)],
    kb_service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
    llm_provider: Annotated[BaseLLMProvider, Depends(get_llm_provider)],
    prompt_library: Annotated[PromptLibrary, Depends(get_prompt_library)],
    context_builder: Annotated[ContextBuilder, Depends(get_context_builder)],
    # Same dependency the route handler resolves for `current_user` below;
    # FastAPI caches it per-request, so this doesn't re-verify the token.
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
) -> AgentGraph:
    """Build the request-scoped compiled agent graph.

    Two gates before this can succeed: ``AGENT_ENABLED`` must be on, and the
    checkpointer must have started (``lifespan`` only opens it when the flag
    is on) — surfacing a clear 503 instead of an AttributeError if a deploy
    somehow reaches this endpoint without going through startup correctly.

    ``confirm_gate``/``audit_repository`` (issue #348) are built the same way
    ``get_admin_chat_service`` builds them for ``AdminChatService`` — a
    Redis-backed pending-confirmation store and the shared audit repository —
    so a future real write tool gets the same guard rails for free. No write
    tool is wired into ``build_tools()`` yet (see agent/tools/registry.py),
    so these are inert for every tool this endpoint can currently reach.
    """
    settings = get_settings()
    if not settings.AGENT_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent is disabled (AGENT_ENABLED=false)",
        )
    checkpointer = getattr(request.app.state, "agent_checkpointer", None)
    if checkpointer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent checkpointer is not ready",
        )

    product_service = ProductService(ProductRepository(session))
    return build_agent_graph(
        safety_checker=safety_checker,
        retriever=retriever,
        product_service=product_service,
        kb_service=kb_service,
        llm_provider=llm_provider,
        prompt_library=prompt_library,
        context_builder=context_builder,
        checkpointer=checkpointer,
        current_user=current_user,
        confirm_gate=ToolConfirmGate(redis),
        audit_repository=AdminAuditRepository(session),
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post(
    "/chat/agent/stream",
    summary="Stream one LangGraph agent turn (feature-flagged)",
)
@limiter.limit("10/minute")
async def stream_agent_turn(
    request: Request,
    payload: SendMessageRequest,
    graph: Annotated[AgentGraph, Depends(get_agent_graph)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
) -> StreamingResponse:
    """Stream one agent turn as Server-Sent Events.

    Event types:

    * ``status`` — the turn started, carries the resolved ``session_id``.
    * ``token`` — an incremental text delta from the responder's LLM call
      (emitted via LangGraph's ``custom`` stream mode — see
      ``agent/nodes/responder.py`` for why not the ``messages`` mode).
    * ``tool_call`` — the router queued a tool call.
    * ``node_complete`` — a node other than the router finished.
    * ``done`` — terminal event with the full assistant reply.

    ``thread_id = session_id`` (ADR-0002): posting again with the same
    ``session_id`` resumes the same checkpointed thread.
    """
    del request
    session_id = payload.session_id or str(uuid4())
    locale = payload.locale or "vi"
    config: RunnableConfig = {
        "configurable": {"thread_id": session_id},
        "recursion_limit": RECURSION_LIMIT,
    }
    input_state: QikiAgentState = {
        "messages": [HumanMessage(content=payload.content)],
        "session_id": session_id,
        "user_id": str(current_user.id) if current_user else None,
        "locale": locale,
    }
    # Must be a genuine `list` — LangGraph's astream() only yields (mode, chunk)
    # 2-tuples when stream_mode is a list; a tuple is treated as a single
    # (unrecognized) mode value and the unpack below raises ValueError.
    stream_modes: list[Literal["updates", "custom"]] = ["updates", "custom"]

    async def event_stream() -> AsyncIterator[str]:
        yield _sse("status", {"session_id": session_id})
        async for stream_mode, chunk in graph.astream(
            input_state,
            config=config,
            stream_mode=stream_modes,
        ):
            if stream_mode == "custom":
                yield _sse("token", cast(dict[str, Any], chunk))
                continue
            updates = cast("dict[str, dict[str, Any] | None]", chunk)
            for node_name, node_update in updates.items():
                if node_update and node_name == "router" and node_update.get("tool_calls"):
                    yield _sse("tool_call", {"tool_calls": node_update["tool_calls"]})
                else:
                    yield _sse("node_complete", {"node": node_name})

        final_state = await graph.aget_state(config)
        last_message = final_state.values["messages"][-1]
        yield _sse(
            "done",
            {
                "session_id": session_id,
                "content": last_message.content,
                "llm_provider": final_state.values.get("llm_provider"),
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
