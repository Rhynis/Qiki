"""Tests for the MCP server (app/mcp_server/) — issue #349.

Three scenarios come straight from the issue's acceptance criteria:

1. The server lists exactly the read-only tools, no write tools — a
   regression guard for when a mutating tool is added elsewhere later and
   someone might carelessly wire it in here too.
2. An unauthenticated call is refused. All 5 tools mirror data already
   public via Qiki's REST API and anonymous chat endpoint (see docs/mcp.md,
   "Why these tools don't need role-gating"), so there's no per-tool
   auth-required/not-required split to test — instead, every MCP tool call
   requires *some* valid Qiki bearer token, a deliberate, conservative
   server-wide default (app/mcp_server/auth.py). That's what's tested below.
3. A search_products MCP call returns the same result as calling the
   underlying tool directly — single source of truth, no duplicated logic.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.search_products import build_search_products_tool
from app.core.config import get_settings
from app.mcp_server.server import READ_ONLY_TOOL_NAMES, create_mcp_server
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate
from app.services.product_service import ProductService


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


class TestToolRegistration:
    pytestmark = pytest.mark.asyncio

    async def test_lists_exactly_the_read_only_tools(self) -> None:
        """No mutating tool exists in the codebase yet, but this must fail
        loudly the moment one is ever wired in here — not silently pass."""
        mcp = create_mcp_server()

        tools = await mcp.list_tools()

        assert {tool.name for tool in tools} == READ_ONLY_TOOL_NAMES
        assert READ_ONLY_TOOL_NAMES == {
            "search_products",
            "check_inventory",
            "lookup_safety_policy",
            "find_nearest_store",
            "calculate_delivery_fee",
        }
        # Nothing here even *looks* like a write — belt and suspenders.
        write_shaped = {"create", "update", "delete", "cancel", "place", "schedule"}
        for name in READ_ONLY_TOOL_NAMES:
            assert not any(verb in name for verb in write_shaped), name


class TestSearchProductsMatchesDirectCall:
    pytestmark = pytest.mark.asyncio

    async def test_mcp_call_matches_the_direct_tool_call(
        self, product_session: AsyncSession
    ) -> None:
        await _seed_gas_product(product_session)
        # The MCP adapter opens its own DB session per call (app/mcp_server/
        # server.py's AsyncSessionLocal() usage) — commit so that separate
        # session/connection can actually see this fixture's row.
        await product_session.commit()

        direct_service = ProductService(ProductRepository(product_session))
        direct_tool = build_search_products_tool(direct_service)
        direct_result = await direct_tool.ainvoke({"query": "Elf 12kg"})

        mcp = create_mcp_server()
        mcp_result = await mcp.call_tool("search_products", {"query": "Elf 12kg"})

        assert mcp_result.structured_content == direct_result
        assert direct_result["total"] == 1


class TestUnauthenticatedCallRefused:
    def test_no_bearer_token_is_refused_with_401(self, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setenv("MCP_ENABLED", "true")
        get_settings.cache_clear()
        try:
            from app.main import create_app

            app = create_app()
            with TestClient(app) as client:
                response = client.post(
                    "/mcp",
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                    },
                    json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                )
        finally:
            get_settings.cache_clear()

        assert response.status_code == 401
        assert response.headers.get("www-authenticate") is not None

    def test_invalid_bearer_token_is_refused_with_401(self, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setenv("MCP_ENABLED", "true")
        get_settings.cache_clear()
        try:
            from app.main import create_app

            app = create_app()
            with TestClient(app) as client:
                response = client.post(
                    "/mcp",
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        "Authorization": "Bearer not-a-real-qiki-token",
                    },
                    json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                )
        finally:
            get_settings.cache_clear()

        assert response.status_code == 401

    def test_mcp_not_mounted_when_disabled(self, monkeypatch: MonkeyPatch) -> None:
        """MCP_ENABLED unset/false: zero regression to existing behavior."""
        monkeypatch.setenv("MCP_ENABLED", "false")
        get_settings.cache_clear()
        try:
            from app.main import create_app

            app = create_app()
            with TestClient(app) as client:
                health_response = client.get("/health")
                mcp_response = client.get("/mcp")
        finally:
            get_settings.cache_clear()

        assert health_response.status_code == 200
        assert mcp_response.status_code == 404
