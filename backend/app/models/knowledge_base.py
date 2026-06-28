"""Knowledge base database model."""

from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class KnowledgeBase(Base, UUIDMixin, TimestampMixin):
    """Knowledge base document for RAG retrieval."""

    __tablename__ = "knowledge_base"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    embedding_jina: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    embedding_ollama: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    embedding_bge: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_message_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    def __repr__(self) -> str:
        return f"<KnowledgeBase {self.category}: {self.title[:50]}>"
