"""``retriever`` node: the general-FAQ path, reusing the existing HybridRetriever.

Calls the same retriever ``RAGPipeline`` uses (do NOT reimplement RAG). Only
fetches documents here — generation happens once, in ``responder``, so this
node is reachable from both the retriever path and (indirectly, via its
results) the tool path without duplicating an LLM call.
"""

from typing import Any

from langchain_core.messages import HumanMessage

from app.agent.state import QikiAgentState, RetrievedDocSummary
from app.rag.retriever import BaseRetriever

TOP_K = 5
# Keep state lean (ADR-0002): every checkpoint write serializes this, so cap
# how much of each document's content is kept.
MAX_CONTENT_CHARS = 800


def _last_human_text(state: QikiAgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""


async def retriever_node(state: QikiAgentState, *, retriever: BaseRetriever) -> dict[str, Any]:
    """Fetch supporting KB documents for the general-FAQ path."""
    query = _last_human_text(state)
    documents = await retriever.retrieve(query=query, top_k=TOP_K)
    summaries: list[RetrievedDocSummary] = [
        {
            "id": str(document.id),
            "title": document.title,
            "content": document.content[:MAX_CONTENT_CHARS],
            "similarity": document.similarity,
        }
        for document in documents
    ]
    confidence = documents[0].similarity if documents else 0.0
    return {"retrieved_docs": summaries, "confidence": confidence}
