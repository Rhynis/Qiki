"""FastMCP server exposing Qiki's read-only tools over Streamable HTTP.

Mounted into the existing FastAPI app (app/main.py) behind ``MCP_ENABLED``
— see ``docs/mcp.md`` for how to run and test it, and ``docs/adr/0001`` for
the agent this shares its tools with.

Every tool below is a thin adapter: it opens whatever request-scoped
dependency the real tool needs (a DB session, mostly), builds the SAME
tool the LangGraph agent uses (``app.agent.tools.*``), and calls it via the
same public ``.ainvoke()`` entry point ``agent/nodes/tool_executor.py``
uses. No business logic is duplicated here. The two tools with no
LangGraph equivalent yet (``find_nearest_store``, ``calculate_delivery_fee``
— see app/mcp_server/tools/__init__.py) follow the identical
``build_*_tool() -> BaseTool`` shape so they are a pure file-move if the
agent graph wants them later.

Once the tool-authz issue (#348) merges its ``registry.py``, this module
should switch to reading its declared read-only tool list instead of the
hardcoded ``READ_ONLY_TOOL_NAMES`` set below.
"""

from typing import Any, Literal, cast

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.check_inventory import TOOL_NAME as CHECK_INVENTORY_TOOL_NAME
from app.agent.tools.check_inventory import build_check_inventory_tool
from app.agent.tools.lookup_safety_policy import TOOL_NAME as LOOKUP_SAFETY_POLICY_TOOL_NAME
from app.agent.tools.lookup_safety_policy import build_lookup_safety_policy_tool
from app.agent.tools.search_products import TOOL_NAME as SEARCH_PRODUCTS_TOOL_NAME
from app.agent.tools.search_products import build_search_products_tool
from app.db.session import AsyncSessionLocal
from app.mcp_server.auth import QikiTokenVerifier
from app.mcp_server.tools.calculate_delivery_fee import (
    TOOL_NAME as CALCULATE_DELIVERY_FEE_TOOL_NAME,
)
from app.mcp_server.tools.calculate_delivery_fee import build_calculate_delivery_fee_tool
from app.mcp_server.tools.find_nearest_store import TOOL_NAME as FIND_NEAREST_STORE_TOOL_NAME
from app.mcp_server.tools.find_nearest_store import build_find_nearest_store_tool
from app.rag.dependencies import (
    get_bge_embedding_service,
    get_embedding_service,
    get_jina_embedding_service,
    get_ollama_embedding_service,
)
from app.rag.text_processor import VietnameseTextProcessor
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.repositories.product_repository import ProductRepository
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.product_service import ProductService

# Internal path FastMCP's Streamable HTTP app answers on. app.main mounts the
# resulting ASGI app at the FastAPI root ("/") rather than at "/mcp" itself —
# FastMCP already registers its route at exactly this path, so mounting again
# at "/mcp" would double the prefix to "/mcp/mcp" (verified empirically; see
# the PR description). The external URL is simply http://host/mcp either way.
MCP_PATH = "/mcp"

# Every tool name this server ever registers. Doubles as the regression guard
# in tests/mcp/test_server.py: search_products/check_inventory/
# lookup_safety_policy are the 3 read-only MVP agent tools (#346);
# find_nearest_store/calculate_delivery_fee are the 2 MCP-only additions
# (see app/mcp_server/tools/__init__.py). There is no mutating tool in the
# codebase yet, but if one is ever added elsewhere and someone wires it in
# here too, this set (and its test) must change explicitly — it cannot
# silently grow.
READ_ONLY_TOOL_NAMES = frozenset(
    {
        SEARCH_PRODUCTS_TOOL_NAME,
        CHECK_INVENTORY_TOOL_NAME,
        LOOKUP_SAFETY_POLICY_TOOL_NAME,
        FIND_NEAREST_STORE_TOOL_NAME,
        CALCULATE_DELIVERY_FEE_TOOL_NAME,
    }
)


def _build_kb_service(session: AsyncSession) -> KnowledgeBaseService:
    """Mirror ``app.rag.dependencies.get_knowledge_base_service`` outside FastAPI DI.

    The embedding-service getters are the same ``@lru_cache`` singletons
    FastAPI's ``Depends()`` resolves to, called directly here since there is
    no FastAPI request to inject into an MCP tool call. Redis is omitted:
    ``KnowledgeBaseService`` treats it as an optional query-embedding cache
    (falls back to a live embedding call when absent, see
    ``KnowledgeBaseService.__init__``) — an MCP tool call is not a hot path,
    so skipping the cache avoids needing a second Redis client here.
    """
    return KnowledgeBaseService(
        KnowledgeBaseRepository(session),
        get_embedding_service(),
        get_jina_embedding_service(),
        VietnameseTextProcessor(),
        get_ollama_embedding_service(),
        get_bge_embedding_service(),
    )


async def _search_products(
    query: str | None = None,
    category: Literal["gas", "nuoc_uong"] | None = None,
    brand: str | None = None,
    size_kg: float | None = None,
    max_price: float | None = None,
    in_stock_only: bool = False,
    limit: int = 5,
) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        service = ProductService(ProductRepository(session))
        tool = build_search_products_tool(service)
        result = await tool.ainvoke(
            {
                "query": query,
                "category": category,
                "brand": brand,
                "size_kg": size_kg,
                "max_price": max_price,
                "in_stock_only": in_stock_only,
                "limit": limit,
            }
        )
        return cast(dict[str, Any], result)


async def _check_inventory(product_id: str, quantity: int = 1) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        service = ProductService(ProductRepository(session))
        tool = build_check_inventory_tool(service)
        result = await tool.ainvoke({"product_id": product_id, "quantity": quantity})
        return cast(dict[str, Any], result)


async def _lookup_safety_policy(query: str) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        kb_service = _build_kb_service(session)
        tool = build_lookup_safety_policy_tool(kb_service)
        result = await tool.ainvoke({"query": query})
        return cast(dict[str, Any], result)


async def _find_nearest_store(address: str) -> dict[str, Any]:
    tool = build_find_nearest_store_tool()
    result = await tool.ainvoke({"address": address})
    return cast(dict[str, Any], result)


async def _calculate_delivery_fee(
    category: Literal["gas", "nuoc_uong"], quantity: int = 1
) -> dict[str, Any]:
    tool = build_calculate_delivery_fee_tool()
    result = await tool.ainvoke({"category": category, "quantity": quantity})
    return cast(dict[str, Any], result)


def create_mcp_server() -> FastMCP[Any]:
    """Build the FastMCP server: 5 read-only tools, bearer-token auth.

    Called once from ``app.main.create_app()`` when ``MCP_ENABLED`` is on.
    """
    mcp: FastMCP[Any] = FastMCP(name="qiki-mcp", auth=QikiTokenVerifier())

    mcp.tool(
        _search_products,
        name=SEARCH_PRODUCTS_TOOL_NAME,
        description=(
            "Search the active product catalog (gas cylinders and drinking water). "
            "Read-only. Returns matching products with their real, current price "
            "and stock status — never invent a price."
        ),
    )
    mcp.tool(
        _check_inventory,
        name=CHECK_INVENTORY_TOOL_NAME,
        description=(
            "Check live stock for one product by id. Read-only. Returns the exact "
            "stock_quantity and whether it covers the requested quantity — never "
            "guess availability."
        ),
    )
    mcp.tool(
        _lookup_safety_policy,
        name=LOOKUP_SAFETY_POLICY_TOOL_NAME,
        description=(
            "Look up non-emergency gas-safety guidance from the knowledge base "
            "(e.g. storage, maintenance, general precautions). Read-only. This is "
            "NOT for an active emergency (leak, fire, suffocation) — Qiki's own "
            "chat handles that separately with a fixed emergency response."
        ),
    )
    mcp.tool(
        _find_nearest_store,
        name=FIND_NEAREST_STORE_TOOL_NAME,
        description=(
            "Look up Qiki's store info and whether a given address/ward is inside "
            "the delivery zone (Bình Thạnh, Thủ Đức). Read-only."
        ),
    )
    mcp.tool(
        _calculate_delivery_fee,
        name=CALCULATE_DELIVERY_FEE_TOOL_NAME,
        description=(
            "Calculate the delivery fee for one product line by category and "
            "quantity. Read-only. Gas ships free; drinking water is charged a "
            "flat fee per unit."
        ),
    )

    return mcp
