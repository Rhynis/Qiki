"""``check_inventory`` tool: wraps ProductService (read-only, structured errors).

Unlike most of the codebase (which lets ``NotFoundException`` propagate to the
FastAPI exception handler), a tool result is read by the LLM, not turned into
an HTTP response — so every failure mode here returns ``{"ok": False, ...}``
instead of raising. An out-of-stock or unknown product is a normal answer for
an agent to reason about, not an error condition.
"""

from typing import Any
from uuid import UUID

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from app.core.exceptions import NotFoundException
from app.services.product_service import ProductService

TOOL_NAME = "check_inventory"


class CheckInventoryArgs(BaseModel):
    """Look up live stock for one product, identified by its catalog ID."""

    product_id: str = Field(
        description="The product's id, as returned by search_products (a UUID string)."
    )
    quantity: int = Field(default=1, ge=1, description="How many units the customer wants.")


def build_check_inventory_tool(product_service: ProductService) -> BaseTool:
    """Bind a request-scoped ProductService into a check_inventory tool."""

    async def _run(product_id: str, quantity: int = 1) -> dict[str, Any]:
        try:
            parsed_id = UUID(product_id)
        except ValueError:
            return {
                "ok": False,
                "error": "invalid_product_id",
                "message": f"'{product_id}' is not a valid product id.",
            }

        try:
            product = await product_service.get_product(parsed_id)
        except NotFoundException:
            return {
                "ok": False,
                "error": "product_not_found",
                "message": "No active product with that id. Use search_products first.",
            }

        return {
            "ok": True,
            "product_id": str(product.id),
            "sku": product.sku,
            "name": product.name,
            "stock_quantity": product.stock_quantity,
            "requested_quantity": quantity,
            "available": product.stock_quantity >= quantity,
        }

    return StructuredTool.from_function(
        coroutine=_run,
        name=TOOL_NAME,
        description=(
            "Check live stock for one product by id. Read-only. Returns the exact "
            "stock_quantity and whether it covers the requested quantity — never "
            "guess availability."
        ),
        args_schema=CheckInventoryArgs,
    )
