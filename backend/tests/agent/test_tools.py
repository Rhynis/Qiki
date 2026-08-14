"""Unit tests for the 3 read-only MVP tools (agent/tools/).

Every tool must return a structured ``{"ok": ...}`` result instead of raising,
even for "not found" / invalid-input cases — a tool result is read by the
graph, not turned into an HTTP response.
"""

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.check_inventory import build_check_inventory_tool
from app.agent.tools.lookup_safety_policy import build_lookup_safety_policy_tool
from app.agent.tools.search_products import build_search_products_tool
from app.repositories.product_repository import ProductRepository
from app.schemas.knowledge_base import KnowledgeBaseSearchResult
from app.schemas.product import ProductCreate
from app.services.product_service import ProductService

pytestmark = pytest.mark.asyncio


async def _seed_gas_product(session: AsyncSession, **overrides: object) -> object:
    repo = ProductRepository(session)
    defaults: dict[str, object] = {
        "sku": "ELF-12KG-DO",
        "name": "Bình gas Elf 12kg (đỏ)",
        "brand": "Elf Gas",
        "size_kg": Decimal("12"),
        "category": "gas",
        "unit": "kg",
        "price": Decimal("710000"),
        "stock_quantity": 5,
    }
    defaults.update(overrides)
    return await repo.create(ProductCreate(**defaults))  # type: ignore[arg-type]


class TestSearchProductsTool:
    async def test_returns_matching_products_with_effective_price(
        self, product_session: AsyncSession
    ) -> None:
        await _seed_gas_product(product_session)
        service = ProductService(ProductRepository(product_session))
        tool = build_search_products_tool(service)

        result = await tool.ainvoke({"query": "Elf 12kg"})

        assert result["ok"] is True
        assert result["total"] == 1
        product = result["products"][0]
        assert product["sku"] == "ELF-12KG-DO"
        assert product["price"] == "710000.00"
        assert product["in_stock"] is True

    async def test_honors_a_sale_price_via_effective_price(
        self, product_session: AsyncSession
    ) -> None:
        await _seed_gas_product(product_session, sale_price=Decimal("650000"))
        service = ProductService(ProductRepository(product_session))
        tool = build_search_products_tool(service)

        result = await tool.ainvoke({"query": "Elf"})

        # #239 regression guard: the tool must never quote a price other than
        # the same effective_price() the storefront/chatbot already charge.
        assert result["products"][0]["price"] == "650000.00"

    async def test_empty_catalog_returns_ok_with_no_products(
        self, product_session: AsyncSession
    ) -> None:
        service = ProductService(ProductRepository(product_session))
        tool = build_search_products_tool(service)

        result = await tool.ainvoke({"query": "khong ton tai"})

        assert result == {"ok": True, "total": 0, "products": []}


class TestCheckInventoryTool:
    async def test_reports_exact_stock_and_availability(
        self, product_session: AsyncSession
    ) -> None:
        product = await _seed_gas_product(product_session, stock_quantity=3)
        service = ProductService(ProductRepository(product_session))
        tool = build_check_inventory_tool(service)

        result = await tool.ainvoke({"product_id": str(product.id), "quantity": 2})

        assert result == {
            "ok": True,
            "product_id": str(product.id),
            "sku": "ELF-12KG-DO",
            "name": "Bình gas Elf 12kg (đỏ)",
            "stock_quantity": 3,
            "requested_quantity": 2,
            "available": True,
        }

    async def test_out_of_stock_is_a_structured_result_not_an_exception(
        self, product_session: AsyncSession
    ) -> None:
        product = await _seed_gas_product(product_session, stock_quantity=1)
        service = ProductService(ProductRepository(product_session))
        tool = build_check_inventory_tool(service)

        result = await tool.ainvoke({"product_id": str(product.id), "quantity": 5})

        assert result["ok"] is True  # the LOOKUP succeeded; it just isn't available
        assert result["available"] is False
        assert result["stock_quantity"] == 1

    async def test_unknown_product_id_returns_structured_error(
        self, product_session: AsyncSession
    ) -> None:
        service = ProductService(ProductRepository(product_session))
        tool = build_check_inventory_tool(service)

        result = await tool.ainvoke({"product_id": str(uuid4()), "quantity": 1})

        assert result == {
            "ok": False,
            "error": "product_not_found",
            "message": "No active product with that id. Use search_products first.",
        }

    async def test_malformed_product_id_returns_structured_error_not_a_crash(
        self, product_session: AsyncSession
    ) -> None:
        service = ProductService(ProductRepository(product_session))
        tool = build_check_inventory_tool(service)

        result = await tool.ainvoke({"product_id": "not-a-uuid", "quantity": 1})

        assert result["ok"] is False
        assert result["error"] == "invalid_product_id"


class TestLookupSafetyPolicyTool:
    async def test_returns_documents_from_the_knowledge_base(self) -> None:
        kb_service = AsyncMock()
        kb_service.search_documents = AsyncMock(
            return_value=[
                KnowledgeBaseSearchResult(
                    id=uuid4(),
                    title="Bảo quản bình gas",
                    content="Đặt bình nơi thoáng khí...",
                    category="safety",
                    similarity=0.82,
                )
            ]
        )
        tool = build_lookup_safety_policy_tool(kb_service)

        result = await tool.ainvoke({"query": "cách bảo quản bình gas"})

        assert result["ok"] is True
        assert result["documents"][0]["title"] == "Bảo quản bình gas"
        kb_service.search_documents.assert_awaited_once()
        call_kwargs = kb_service.search_documents.await_args.kwargs
        assert call_kwargs["category"] == "safety"
