"""``find_nearest_store`` tool: resolve an address to Qiki's delivery zone.

New for the MCP surface (see app/mcp_server/tools/__init__.py) — there is no
equivalent LangChain tool in app/agent/tools/ yet. Gas Quốc Cường operates a
SINGLE physical store serving two zones (Bình Thạnh and Thủ Đức), so "find
nearest store" is really "does this address fall inside our delivery zone,
and which one" — this wraps the existing zone-matching logic
(``resolve_ward_delivery_zone``, also used for checkout address validation)
rather than reimplementing it, and adds the store's contact/hours info so an
MCP client gets a complete answer in one call.
"""

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from app.services.address_lookup import resolve_ward_delivery_zone
from app.services.email_service import BRAND_HOTLINE, BRAND_NAME

TOOL_NAME = "find_nearest_store"

# Gas Quốc Cường runs one physical store, not a network of branches. Address
# and hours mirror frontend/lib/constants/index.ts's SHOP_INFO, which has no
# backend-side equivalent yet (BRAND_NAME/BRAND_HOTLINE below already do —
# app/services/email_service.py — and are reused as-is, not re-declared).
STORE_ADDRESS = "15 đường số 5, Khu phố 36, Phường Hiệp Bình, Thành phố Hồ Chí Minh"
STORE_HOURS_SUMMARY = "T2-T6 06:30-20:00 · T7-CN 07:30-20:00"
DELIVERY_AREA_LABEL = "Bình Thạnh, Thủ Đức"


class FindNearestStoreArgs(BaseModel):
    """A customer-supplied address or ward to check against the delivery zone."""

    address: str = Field(
        description=(
            "The customer's free-text address or ward, e.g. 'Hiệp Bình, Thủ Đức' "
            "or '12 Nguyễn Xí, Bình Thạnh'."
        )
    )


def build_find_nearest_store_tool() -> BaseTool:
    """Build the find_nearest_store tool. No request-scoped dependency needed."""

    async def _run(address: str) -> dict[str, Any]:
        match = resolve_ward_delivery_zone(address)
        result: dict[str, Any] = {
            "ok": True,
            # A single store serves both delivery zones, so the store block
            # is always the same — unlike a multi-branch "nearest" lookup.
            "store": {
                "name": BRAND_NAME,
                "address": STORE_ADDRESS,
                "hotline": BRAND_HOTLINE,
                "hours": STORE_HOURS_SUMMARY,
            },
            "serves_address": match is not None,
        }
        if match is not None:
            result["matched_ward"] = match.ward
            result["delivery_zone"] = match.delivery_zone
        else:
            result["message"] = (
                f"Could not confidently match this address to a known ward. "
                f"{BRAND_NAME} currently only delivers within {DELIVERY_AREA_LABEL}."
            )
        return result

    return StructuredTool.from_function(
        coroutine=_run,
        name=TOOL_NAME,
        description=(
            "Look up Qiki's store info and whether a given address/ward is inside "
            "the delivery zone. Read-only. Gas Quốc Cường operates a single store "
            f"serving {DELIVERY_AREA_LABEL} — this returns that store's contact "
            "info plus which zone (if any) the address matched."
        ),
        args_schema=FindNearestStoreArgs,
    )
