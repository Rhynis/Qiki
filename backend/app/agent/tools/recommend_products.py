"""``recommend_products`` tool: wraps RecommendationService (read-only).

Only ``product_service`` is threaded through ``build_tools()`` (agent/graph.py)
today, so this builds its own request-scoped ``OrderService`` off the same
underlying DB session (``product_service.repository.session``) rather than
widening ``build_tools()``'s signature for one extra dependency -- the popularity
signal needs real order history, which ``OrderService.get_best_sellers`` already
exposes.
"""

from typing import Any
from uuid import UUID

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from app.core.exceptions import NotFoundException
from app.repositories.order_repository import OrderRepository
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.recommendation_service import DEFAULT_LIMIT, RecommendationService

TOOL_NAME = "recommend_products"
MAX_LIMIT = 10


class RecommendProductsArgs(BaseModel):
    """Get ranked product suggestions, optionally relative to one product."""

    product_id: str | None = Field(
        default=None,
        description=(
            "The product the customer is currently looking at, as returned by "
            "search_products (a UUID string). Omit for a general 'popular now' "
            "suggestion when there's no specific product in context."
        ),
    )
    limit: int = Field(
        default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Maximum number of results."
    )


def _to_result(candidate: Any) -> dict[str, Any]:
    """Flatten a RecommendationCandidate into a compact, LLM-friendly result row."""
    product = candidate.product
    return {
        "id": str(product.id),
        "sku": product.sku,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "price": str(product.sale_price or product.price),
        "in_stock": product.stock_quantity > 0,
        "reason": candidate.reason,
    }


def build_recommend_products_tool(product_service: ProductService) -> BaseTool:
    """Bind a request-scoped RecommendationService into a recommend_products tool.

    Builds the sibling ``OrderService`` lazily, inside the returned tool's
    ``_run`` closure rather than here, so ``build_tools()`` still never
    touches ``product_service`` at build time -- matching every other tool
    builder in this module (see ``tests/agent/test_tool_authz.py``'s
    ``TestMockToolsNotWiredIntoProduction``, which builds tools from doubles
    that raise on any attribute access to enforce exactly this).
    """

    def _recommendation_service() -> RecommendationService:
        order_service = OrderService(
            OrderRepository(product_service.repository.session), product_service.repository
        )
        return RecommendationService(product_service, order_service)

    async def _run(product_id: str | None = None, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        parsed_id: UUID | None = None
        if product_id is not None:
            try:
                parsed_id = UUID(product_id)
            except ValueError:
                return {
                    "ok": False,
                    "error": "invalid_product_id",
                    "message": f"'{product_id}' is not a valid product id.",
                }

        try:
            candidates = await _recommendation_service().recommend(
                product_id=parsed_id, limit=min(limit, MAX_LIMIT)
            )
        except NotFoundException:
            return {
                "ok": False,
                "error": "product_not_found",
                "message": "No active product with that id. Use search_products first.",
            }

        return {"ok": True, "recommendations": [_to_result(candidate) for candidate in candidates]}

    return StructuredTool.from_function(
        coroutine=_run,
        name=TOOL_NAME,
        description=(
            "Suggest other active products the customer might want next -- based on "
            "the catalog (same brand, complementary items like water with gas) and "
            "real order popularity, never invented. Read-only. Pass the currently "
            "viewed product's id when there is one; omit it for a general suggestion."
        ),
        args_schema=RecommendProductsArgs,
    )
