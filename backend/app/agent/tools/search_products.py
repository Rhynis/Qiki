"""``search_products`` tool: wraps ProductService.search_products (read-only)."""

from decimal import Decimal
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from app.schemas.product import ProductSearchParams
from app.services.product_service import ProductService
from app.utils.pricing import effective_price

TOOL_NAME = "search_products"
DEFAULT_LIMIT = 5
MAX_LIMIT = 10


class SearchProductsArgs(BaseModel):
    """Filters for a catalog search. All fields are optional; omit what you don't need."""

    query: str | None = Field(
        default=None,
        description="Free-text search over the product name, e.g. 'Elf 12kg' or 'Vihawa'.",
    )
    category: Literal["gas", "nuoc_uong"] | None = Field(
        default=None,
        description="'gas' for LPG cylinders, 'nuoc_uong' for drinking water.",
    )
    brand: str | None = Field(default=None, description="Brand name, e.g. 'Saigon Petro'.")
    size_kg: float | None = Field(
        default=None, description="Cylinder size in kg for gas (6, 12, or 45)."
    )
    max_price: float | None = Field(
        default=None, description="Upper price bound in VND, if the customer gave one."
    )
    in_stock_only: bool = Field(
        default=False, description="True to only return products with stock available now."
    )
    limit: int = Field(
        default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Maximum number of results."
    )


def _to_result(product: Any) -> dict[str, Any]:
    """Flatten a ProductResponse into a compact, LLM-friendly result row."""
    return {
        "id": str(product.id),
        "sku": product.sku,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "size_kg": str(product.size_kg),
        "unit": product.unit,
        # The effective (charged) price — reuses the same helper the storefront
        # and chatbot pricing use, so this tool can never quote a stale or
        # differently-derived price (#239 regression guard).
        "price": str(effective_price(product.price, product.sale_price)),
        "in_stock": product.stock_quantity > 0,
        "stock_quantity": product.stock_quantity,
    }


def build_search_products_tool(product_service: ProductService) -> BaseTool:
    """Bind a request-scoped ProductService into a search_products tool."""

    async def _run(
        query: str | None = None,
        category: Literal["gas", "nuoc_uong"] | None = None,
        brand: str | None = None,
        size_kg: float | None = None,
        max_price: float | None = None,
        in_stock_only: bool = False,
        limit: int = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        params = ProductSearchParams(
            search=query,
            category=category,
            brand=brand,
            size_kg=Decimal(str(size_kg)) if size_kg is not None else None,
            max_price=Decimal(str(max_price)) if max_price is not None else None,
            in_stock_only=in_stock_only,
            sort_by="price",
            sort_order="asc",
            limit=min(limit, MAX_LIMIT),
        )
        try:
            result = await product_service.search_products(params)
        except ValueError as exc:
            # e.g. an LLM-supplied size_kg outside the allowed gas sizes.
            return {"ok": False, "error": "invalid_filter", "message": str(exc)}
        return {
            "ok": True,
            "total": result.total,
            "products": [_to_result(product) for product in result.items],
        }

    return StructuredTool.from_function(
        coroutine=_run,
        name=TOOL_NAME,
        description=(
            "Search the active product catalog (gas cylinders and drinking water). "
            "Read-only. Returns matching products with their real, current price "
            "and stock status — never invent a price."
        ),
        args_schema=SearchProductsArgs,
    )
