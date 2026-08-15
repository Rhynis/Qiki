"""``calculate_delivery_fee`` tool: flat per-unit water delivery fee.

New for the MCP surface (see app/mcp_server/tools/__init__.py) — there is no
equivalent LangChain tool in app/agent/tools/ yet. Wraps the SAME pure
function the real checkout path uses — ``OrderService._calculate_shipping``
delegates to ``calculate_delivery_fee`` too (app/services/order_service.py)
— rather than re-deriving the fee here.
"""

from decimal import Decimal
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from app.services.order_service import calculate_delivery_fee

TOOL_NAME = "calculate_delivery_fee"


class CalculateDeliveryFeeArgs(BaseModel):
    """A product category + quantity to price delivery for."""

    category: Literal["gas", "nuoc_uong"] = Field(
        description=(
            "Product category: 'gas' (LPG cylinders, free delivery) or "
            "'nuoc_uong' (drinking water, charged per unit)."
        )
    )
    quantity: int = Field(default=1, ge=1, description="Number of units being delivered.")


def build_calculate_delivery_fee_tool() -> BaseTool:
    """Build the calculate_delivery_fee tool. No request-scoped dependency needed."""

    async def _run(category: Literal["gas", "nuoc_uong"], quantity: int = 1) -> dict[str, Any]:
        fee = calculate_delivery_fee(category, quantity)
        return {
            "ok": True,
            "category": category,
            "quantity": quantity,
            "fee": str(fee),
            "currency": "VND",
            "free": fee == Decimal("0"),
        }

    return StructuredTool.from_function(
        coroutine=_run,
        name=TOOL_NAME,
        description=(
            "Calculate the delivery fee for one product line by category and "
            "quantity. Read-only. Gas cylinders ship free; drinking water is "
            "charged a flat fee per unit — never guess this, always call the tool."
        ),
        args_schema=CalculateDeliveryFeeArgs,
    )
