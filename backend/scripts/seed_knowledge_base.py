"""Seed knowledge base from Vietnamese markdown files."""

import asyncio
from pathlib import Path

from app.db.session import AsyncSessionLocal
from app.rag.embeddings import EmbeddingService
from app.rag.jina_embeddings import JinaEmbeddingService
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.services.knowledge_base_service import parse_front_matter


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
    texts = [f"{document['title']}\n\n{document['content']}" for document in documents]
    print("Generating Gemini embeddings...")
    embeddings = await embedding_service.embed_batch(texts, batch_size=32)
    print("Generating Jina embeddings...")
    embeddings_jina = await jina_embedding_service.embed_batch(
        texts,
        task="retrieval.passage",
        batch_size=32,
    )

    async with AsyncSessionLocal() as session:
        repo = KnowledgeBaseRepository(session)
        created = await repo.create_batch(
            list(zip(documents, embeddings, embeddings_jina, strict=True))
        )
        await session.commit()
        print(f"Created {len(created)} knowledge base entries")


if __name__ == "__main__":
    asyncio.run(main())
