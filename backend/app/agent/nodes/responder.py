"""``responder`` node: the ONLY node that calls an LLM (never the emergency path).

Generation goes through the existing ``BaseLLMProvider`` (built via
``LLMProviderFactory`` in dependencies, so multi-provider failover is
preserved unchanged) and the existing prompt templates
(``system_chatbot_vi``/``system_chatbot_en``), the same ones ``RAGPipeline``
uses — same persona, same instructions, just a differently-assembled context
depending on whether the turn went through a tool or the retriever.

Streams token deltas via LangGraph's ``custom`` stream mode
(``get_stream_writer()``), not the ``messages`` stream mode: "messages" mode
only captures LangChain chat-model integrations, and ``BaseLLMProvider`` is
Qiki's own abstraction (the same one ``RAGPipeline.query_stream`` streams
through), not a ``BaseChatModel``. Reuses ``llm_provider.stream()`` — the
exact method the existing RAG streaming endpoint already calls — so the same
provider/model/token attribution and failover-on-first-chunk behavior applies.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.config import get_stream_writer

from app.agent.state import QikiAgentState
from app.llm.base import BaseLLMProvider
from app.llm.prompts.templates import PromptLibrary
from app.rag.context_builder import ContextBuilder

GENERATION_TEMPERATURE = 0.3
GENERATION_MAX_TOKENS = 2048
# Mirrors RAGPipeline._current_date_vn — Vietnam has no DST, so a fixed offset
# is exact (same reasoning as the RAG pipeline this responder parallels).
VN_UTC_OFFSET = timedelta(hours=7)


def _current_date_vn() -> str:
    return (datetime.now(UTC) + VN_UTC_OFFSET).strftime("%d/%m/%Y")


def _last_human_text(state: QikiAgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""


def _history_payload(state: QikiAgentState) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for message in state.get("messages", [])[:-1]:  # exclude the current turn's message
        if isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        else:
            continue
        content = message.content
        payload.append({"role": role, "content": content if isinstance(content, str) else ""})
    return payload


def _tool_results_context(state: QikiAgentState) -> str:
    lines: list[str] = []
    for record in state.get("tool_results", []):
        result = record.get("result", {})
        lines.append(f"[Kết quả công cụ {record.get('name')}]\n{result}")
    return "\n\n".join(lines) if lines else "Không có kết quả công cụ."


def _retrieved_docs_context(state: QikiAgentState) -> str:
    docs = state.get("retrieved_docs", [])
    if not docs:
        return "Không có thông tin liên quan trong cơ sở dữ liệu."
    parts = [
        f"[Tài liệu {i} - {doc.get('title')}]\n{doc.get('content')}"
        for i, doc in enumerate(docs, 1)
    ]
    return "\n\n".join(parts)


async def responder(
    state: QikiAgentState,
    *,
    llm_provider: BaseLLMProvider,
    prompt_library: PromptLibrary,
    context_builder: ContextBuilder,
) -> dict[str, Any]:
    """Generate the final natural-language answer from accumulated context."""
    locale = state.get("locale", "vi")
    used_tools = bool(state.get("tool_results"))
    context = _tool_results_context(state) if used_tools else _retrieved_docs_context(state)
    history = context_builder.format_conversation_history(_history_payload(state))

    prompt_name = "system_chatbot_en" if locale == "en" else "system_chatbot_vi"
    system_prompt = prompt_library.get(prompt_name).render(
        context=context,
        conversation_history=history,
        current_date=_current_date_vn(),
    )

    writer = get_stream_writer()
    chunks: list[str] = []
    served_by: str | None = None
    async for stream_chunk in llm_provider.stream(
        prompt=_last_human_text(state),
        system_prompt=system_prompt,
        temperature=GENERATION_TEMPERATURE,
        max_tokens=GENERATION_MAX_TOKENS,
    ):
        if stream_chunk.provider is not None:
            served_by = stream_chunk.provider
        if stream_chunk.delta:
            chunks.append(stream_chunk.delta)
            writer({"type": "token", "text": stream_chunk.delta})

    return {
        "messages": [AIMessage(content="".join(chunks))],
        "llm_provider": served_by or llm_provider.provider_name,
    }
