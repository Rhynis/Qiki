"""Seed knowledge base from Vietnamese markdown files."""

import asyncio
from pathlib import Path
from typing import Protocol

from app.db.session import AsyncSessionLocal
from app.llm.exceptions import LLMConnectionError, LLMInvalidRequestError, LLMTimeoutError
from app.rag.bge_embeddings import BgeEmbeddingService
from app.rag.embeddings import EmbeddingService
from app.rag.jina_embeddings import JinaEmbeddingService
from app.rag.ollama_embeddings import OllamaEmbeddingService
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.services.knowledge_base_service import parse_front_matter


class _LocalEmbedder(Protocol):
    async def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]: ...


async def _embed_optional(
    label: str, service: _LocalEmbedder, texts: list[str]
) -> list[list[float] | None]:
    """Embed texts with an optional local Ollama model; skip if unreachable."""
    print(f"Generating {label} embeddings...")
    try:
        return list(await service.embed_batch(texts, batch_size=32))
    except (LLMConnectionError, LLMTimeoutError, LLMInvalidRequestError) as exc:
        print(f"{label} unreachable, leaving its column empty: {exc}")
        return [None] * len(texts)


async def main() -> None:
    """Read seed documents, embed them, and insert into the database."""
    kb_dir = Path("data/knowledge_base")
    files = sorted(kb_dir.rglob("*.md"))
    print(f"Found {len(files)} knowledge base files")

    documents: list[dict[str, object]] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        metadata, body = parse_front_matter(content)
        documents.append(
            {
                "title": metadata.get("title", file_path.stem),
                "content": body,
                "category": metadata.get("category", "faq"),
                "source": metadata.get("source", "seed_data"),
                "metadata_": {"file": str(file_path)},
            }
        )

    embedding_service = EmbeddingService()
    jina_embedding_service = JinaEmbeddingService()
    ollama_embedding_service = OllamaEmbeddingService()
    bge_embedding_service = BgeEmbeddingService()
    texts = [f"{document['title']}\n\n{document['content']}" for document in documents]
    print("Generating Gemini embeddings...")
    embeddings = await embedding_service.embed_batch(texts, batch_size=32)
    print("Generating Jina embeddings...")
    embeddings_jina = await jina_embedding_service.embed_batch(
        texts,
        task="retrieval.passage",
        batch_size=32,
    )

    # The local Ollama columns are optional: skip them when a local server is
    # unreachable so the default Gemini + Jina seed path keeps working.
    embeddings_ollama = await _embed_optional("Ollama (nomic)", ollama_embedding_service, texts)
    embeddings_bge = await _embed_optional("BGE (bge-m3)", bge_embedding_service, texts)

    async with AsyncSessionLocal() as session:
        repo = KnowledgeBaseRepository(session)
        created = await repo.create_batch(
            list(
                zip(
                    documents,
                    embeddings,
                    embeddings_jina,
                    embeddings_ollama,
                    embeddings_bge,
                    strict=True,
                )
            )
        )
        await session.commit()
        print(f"Created {len(created)} knowledge base entries")


if __name__ == "__main__":
    asyncio.run(main())
