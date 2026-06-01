"""Tests for KnowledgeBaseRepository failure isolation."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate

pytestmark = pytest.mark.asyncio


def product_data(sku: str = "AFTER-RAG-FAIL") -> ProductCreate:
    """Return valid product creation data."""
    return ProductCreate(
        sku=sku,
        name="Binh gas 12kg",
        brand="Saigon Petro",
        size_kg=Decimal("12"),
        price=Decimal("350000"),
        stock_quantity=20,
        description="Binh gas gia dinh",
        image_url="https://example.com/gas-12kg.jpg",
        safety_info="Dat binh noi thoang khi.",
    )


async def test_similarity_search_failure_does_not_abort_outer_transaction(
    product_session: AsyncSession,
) -> None:
    repo = KnowledgeBaseRepository(product_session)

    results = await repo.similarity_search([0.0] * 3072, top_k=3)
    product = await ProductRepository(product_session).create(product_data())

    assert results == []
    assert product.sku == "AFTER-RAG-FAIL"
