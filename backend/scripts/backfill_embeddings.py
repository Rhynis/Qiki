"""Backfill a provider's embedding column on existing knowledge base rows.

Idempotent: only rows whose target column IS NULL are embedded and UPDATEd in
place (never inserted), so it is safe to re-run on an already-seeded KB.

    python -m scripts.backfill_embeddings --provider bge
"""

import argparse
import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.knowledge_base import KnowledgeBase
from app.rag.bge_embeddings import BgeEmbeddingService
from app.rag.embeddings import EmbeddingService
from app.rag.ollama_embeddings import OllamaEmbeddingService

_BATCH_SIZE = 16


class _Embedder:
    async def embed_text(self, text: str) -> list[float]:  # pragma: no cover - protocol
        raise NotImplementedError


def _build_embedder(provider: str) -> tuple[str, _Embedder]:
    """Return (column name, embedding service) for the provider."""
    if provider == "gemini":
        return "embedding", EmbeddingService()  # type: ignore[return-value]
    if provider == "ollama":
        return "embedding_ollama", OllamaEmbeddingService()  # type: ignore[return-value]
    if provider == "bge":
        return "embedding_bge", BgeEmbeddingService()  # type: ignore[return-value]
    raise SystemExit(f"Unknown provider: {provider}")


async def backfill(provider: str) -> None:
    """Embed and store the chosen provider's vector for rows missing it."""
    column_name, embedder = _build_embedder(provider)
    column = getattr(KnowledgeBase, column_name)

    async with AsyncSessionLocal() as session:
        rows = list(
            (await session.execute(select(KnowledgeBase).where(column.is_(None)))).scalars().all()
        )
        total = len(rows)
        print(f"Backfilling '{column_name}' for {total} rows missing it")

        done = 0
        for start in range(0, total, _BATCH_SIZE):
            batch = rows[start : start + _BATCH_SIZE]
            for document in batch:
                text = f"{document.title}\n\n{document.content}"
                setattr(document, column_name, await embedder.embed_text(text))
            await session.commit()
            done += len(batch)
            print(f"  {done}/{total}")
    print("Backfill complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill knowledge base embeddings.")
    parser.add_argument("--provider", required=True, choices=["gemini", "ollama", "bge"])
    args = parser.parse_args()
    asyncio.run(backfill(args.provider))


if __name__ == "__main__":
    main()
