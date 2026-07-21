"""Admin-in-chat service: let an admin manage the catalog through Qiki.

The whole path is admin-only (the endpoint gates on ``get_current_admin``). A
command never mutates on the first message: the service parses it, resolves the
target product against the REAL catalog, validates the new value, and returns a
confirmation prompt with an opaque one-time token. Only a follow-up request that
echoes that token (``confirm=true``) applies the change, re-validating against
the live row and writing an audit entry. This guarantees an LLM/parse mistake
can never silently change a live price or stock level.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.models.product import Product
from app.models.user import User
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.admin_chat import AdminActionPreview, AdminChatRequest, AdminChatResponse
from app.schemas.product import ProductSearchParams, ProductUpdate
from app.services.admin_chat_parser import ParsedInstruction, parse_admin_instruction
from app.services.product_query import filter_products, parse_product_query, strip_accents
from app.services.product_service import ProductService

PENDING_KEY_PREFIX = "admin_chat:pending:"
PENDING_TTL_SECONDS = 300
CATALOG_PAGE_SIZE = 100

UNRECOGNIZED_REPLY = (
    "Mình chưa hiểu yêu cầu quản trị. Bạn có thể nói ví dụ: "
    '"đổi giá Elf 12kg thành 460000", "cập nhật tồn Petrolimex 12kg thành 20", '
    'hoặc "ẩn sản phẩm Gas Đại Hải 12kg".'
)
NOT_FOUND_REPLY = (
    "Mình không tìm thấy sản phẩm phù hợp. Bạn nêu rõ hơn theo tên + dung tích "
    "hoặc mã SKU giúp mình nhé."
)
EXPIRED_REPLY = "Phiên xác nhận đã hết hạn hoặc không hợp lệ. Bạn gửi lại yêu cầu giúp mình nhé."
STALE_REPLY = (
    "Sản phẩm này vừa được thay đổi bởi một thao tác khác, nên Qiki chưa áp dụng để "
    "tránh ghi đè. Bạn gửi lại yêu cầu để mình báo giá/tồn mới nhất nhé."
)


class AdminChatService:
    """Orchestrate parse -> resolve -> validate -> confirm -> execute -> audit."""

    def __init__(
        self,
        product_service: ProductService,
        product_repository: ProductRepository,
        audit_repository: AdminAuditRepository,
        redis: Redis,
    ) -> None:
        self.product_service = product_service
        self.product_repository = product_repository
        self.audit_repository = audit_repository
        self.redis = redis
        self.logger = get_logger(__name__)

    async def handle(self, request: AdminChatRequest, admin: User) -> AdminChatResponse:
        """Route to the confirm-execute path or the parse-preview path."""
        if request.confirm and request.pending_token:
            return await self._execute_pending(request.pending_token, admin)
        return await self._plan(request.message, admin)

    # -- planning (first message: never mutates) --------------------------------

    async def _plan(self, message: str, admin: User) -> AdminChatResponse:
        parsed = parse_admin_instruction(message)
        if parsed is None:
            return AdminChatResponse(status="unrecognized", reply=UNRECOGNIZED_REPLY)

        catalog = await self._load_catalog()
        candidates = self._match(message, catalog)
        if not candidates:
            return AdminChatResponse(status="not_found", reply=NOT_FOUND_REPLY)
        if len(candidates) > 1:
            return AdminChatResponse(status="ambiguous", reply=self._ambiguous_reply(candidates))

        product = candidates[0]
        error = self._validation_error(parsed, product)
        if error is not None:
            return AdminChatResponse(status="invalid", reply=error)

        preview = self._build_preview(parsed, product)
        # Snapshot the value the admin is approving so the confirm step can detect a
        # concurrent change (optimistic concurrency) instead of silently overwriting.
        before_snapshot, _after, _update = self._compute_change(parsed, product)
        token = uuid4().hex
        await self._store_pending(token, admin.id, parsed, product.id, before_snapshot)
        return AdminChatResponse(
            status="confirm_required",
            reply=self._confirm_prompt(parsed, product),
            pending_token=token,
            action=preview,
        )

    # -- execution (confirmation: re-validates, mutates, audits) ----------------

    async def _execute_pending(self, token: str, admin: User) -> AdminChatResponse:
        # Claim the token atomically (GETDEL): read + delete in one round trip so
        # two racing confirms can't both pass and apply the mutation twice. Any
        # later exit path has already consumed it, so no separate delete is needed.
        raw = await self.redis.getdel(self._pending_key(token))
        if raw is None:
            return AdminChatResponse(status="expired", reply=EXPIRED_REPLY)
        data = cast(dict[str, Any], json.loads(raw))
        # A token is scoped to the admin who created it; nobody else may confirm it.
        if data.get("admin_id") != str(admin.id):
            return AdminChatResponse(status="expired", reply=EXPIRED_REPLY)

        parsed = self._instruction_from_payload(data)
        product = await self.product_repository.get_by_id(UUID(data["product_id"]))
        if product is None:
            return AdminChatResponse(status="not_found", reply=NOT_FOUND_REPLY)

        # Re-validate against the live row: the catalog may have changed since the
        # confirmation prompt was issued.
        error = self._validation_error(parsed, product)
        if error is not None:
            return AdminChatResponse(status="invalid", reply=error)

        before, after, update = self._compute_change(parsed, product)
        # Optimistic concurrency: if the live value no longer matches the snapshot the
        # admin approved, another operation changed the row in between. Abort rather
        # than silently overwriting that change; the admin can re-issue for a fresh
        # preview. (The token was already consumed by GETDEL above.)
        before_snapshot = data.get("before_snapshot")
        if before_snapshot is not None and before != before_snapshot:
            self.logger.warning(
                "admin_chat_stale_confirm",
                admin_id=str(admin.id),
                product_id=str(product.id),
                approved=before_snapshot,
                current=before,
            )
            return AdminChatResponse(status="stale", reply=STALE_REPLY)
        product_name = product.name
        await self.product_service.update_product(product.id, update, admin)
        await self.audit_repository.record(
            admin_id=admin.id,
            action=parsed.action,
            target_type="product",
            target_id=product.id,
            before=before,
            after=after,
        )
        self.logger.info(
            "admin_chat_mutation",
            admin_id=str(admin.id),
            action=parsed.action,
            product_id=str(product.id),
            before=before,
            after=after,
        )
        return AdminChatResponse(
            status="executed",
            reply=self._executed_reply(parsed, product_name),
        )

    # -- catalog resolution -----------------------------------------------------

    async def _load_catalog(self) -> list[Product]:
        """Fetch the full catalog (active AND inactive) for resolution.

        ``ProductSearchParams.limit`` is capped at 100, so page through the whole
        catalog rather than silently missing products past the first page.
        """
        products: list[Product] = []
        skip = 0
        while True:
            params = ProductSearchParams(
                limit=CATALOG_PAGE_SIZE, skip=skip, sort_by="name", sort_order="asc"
            )
            page, total = await self.product_repository.list_products(params, active_only=False)
            products.extend(page)
            skip += CATALOG_PAGE_SIZE
            if len(page) < CATALOG_PAGE_SIZE or skip >= total:
                break
        return products

    def _match(self, message: str, catalog: list[Product]) -> list[Product]:
        """Resolve a message to catalog products by SKU, then brand/size."""
        normalized = strip_accents(message)
        sku_matches = [
            product
            for product in catalog
            if len(product.sku) >= 4 and strip_accents(product.sku) in normalized
        ]
        if sku_matches:
            return sku_matches

        brands = sorted({product.brand for product in catalog})
        query = parse_product_query(message, brands)
        # A bare category ("gas") is too broad to safely target a single product;
        # require a brand or a size before matching.
        if not query.is_specific():
            return []
        return [cast(Product, product) for product in filter_products(catalog, query)]

    # -- validation -------------------------------------------------------------

    @staticmethod
    def _validation_error(parsed: ParsedInstruction, product: Product) -> str | None:
        del product
        if parsed.action == "update_price":
            if parsed.price_value is None or parsed.price_value <= 0:
                return "Giá phải lớn hơn 0. Bạn kiểm tra lại số tiền giúp mình nhé."
        elif parsed.action == "update_stock":
            if parsed.stock_value is None or parsed.stock_value < 0:
                return "Tồn kho không thể là số âm. Bạn nhập lại số lượng giúp mình nhé."
        return None

    @staticmethod
    def _compute_change(
        parsed: ParsedInstruction, product: Product
    ) -> tuple[dict[str, Any], dict[str, Any], ProductUpdate]:
        before: dict[str, Any]
        after: dict[str, Any]
        if parsed.action == "update_price":
            new_price = cast(Decimal, parsed.price_value)
            before = {"price": str(product.price)}
            after = {"price": str(new_price)}
            return before, after, ProductUpdate(price=new_price)
        if parsed.action == "update_stock":
            new_stock = cast(int, parsed.stock_value)
            before = {"stock_quantity": product.stock_quantity}
            after = {"stock_quantity": new_stock}
            return before, after, ProductUpdate(stock_quantity=new_stock)
        new_active = cast(bool, parsed.active_value)
        before = {"is_active": product.is_active}
        after = {"is_active": new_active}
        return before, after, ProductUpdate(is_active=new_active)

    # -- pending-action storage (one-time token in Redis) -----------------------

    @staticmethod
    def _pending_key(token: str) -> str:
        return f"{PENDING_KEY_PREFIX}{token}"

    async def _store_pending(
        self,
        token: str,
        admin_id: UUID,
        parsed: ParsedInstruction,
        product_id: UUID,
        before_snapshot: dict[str, Any],
    ) -> None:
        payload: dict[str, Any] = {
            "admin_id": str(admin_id),
            "product_id": str(product_id),
            "action": parsed.action,
            "price_value": str(parsed.price_value) if parsed.price_value is not None else None,
            "stock_value": parsed.stock_value,
            "active_value": parsed.active_value,
            # The live value the preview was built from, to guard against a lost update.
            "before_snapshot": before_snapshot,
        }
        await self.redis.setex(self._pending_key(token), PENDING_TTL_SECONDS, json.dumps(payload))

    @staticmethod
    def _instruction_from_payload(data: dict[str, Any]) -> ParsedInstruction:
        price = data.get("price_value")
        return ParsedInstruction(
            action=data["action"],
            price_value=Decimal(price) if price is not None else None,
            stock_value=data.get("stock_value"),
            active_value=data.get("active_value"),
        )

    # -- reply rendering (Vietnamese, user-facing) ------------------------------

    @staticmethod
    def _format_vnd(value: Decimal) -> str:
        return f"{int(value):,}".replace(",", ".") + "đ"

    def _build_preview(self, parsed: ParsedInstruction, product: Product) -> AdminActionPreview:
        if parsed.action == "update_price":
            current, new = (
                self._format_vnd(product.price),
                self._format_vnd(cast(Decimal, parsed.price_value)),
            )
            field = "price"
        elif parsed.action == "update_stock":
            current, new = str(product.stock_quantity), str(parsed.stock_value)
            field = "stock_quantity"
        else:
            current = "hiển thị" if product.is_active else "ẩn"
            new = "hiển thị" if parsed.active_value else "ẩn"
            field = "is_active"
        return AdminActionPreview(
            action=parsed.action,
            product_id=product.id,
            product_name=product.name,
            sku=product.sku,
            field=field,
            current_value=current,
            new_value=new,
        )

    def _confirm_prompt(self, parsed: ParsedInstruction, product: Product) -> str:
        label = f"{product.name} ({product.sku})"
        if parsed.action == "update_price":
            old = self._format_vnd(product.price)
            new = self._format_vnd(cast(Decimal, parsed.price_value))
            return f"Xác nhận đổi giá {label}: {old} → {new}?"
        if parsed.action == "update_stock":
            return (
                f"Xác nhận cập nhật tồn kho {label}: "
                f"{product.stock_quantity} → {parsed.stock_value}?"
            )
        if parsed.active_value:
            return f"Xác nhận hiển thị lại sản phẩm {label}?"
        return f"Xác nhận ẩn sản phẩm {label}?"

    def _executed_reply(self, parsed: ParsedInstruction, product_name: str) -> str:
        if parsed.action == "update_price":
            new_price = self._format_vnd(cast(Decimal, parsed.price_value))
            return f"Đã đổi giá {product_name} thành {new_price}."
        if parsed.action == "update_stock":
            return f"Đã cập nhật tồn kho {product_name} thành {parsed.stock_value}."
        if parsed.active_value:
            return f"Đã hiển thị lại sản phẩm {product_name}."
        return f"Đã ẩn sản phẩm {product_name}."

    @staticmethod
    def _ambiguous_reply(candidates: list[Product]) -> str:
        listed = "; ".join(f"{product.name} ({product.sku})" for product in candidates[:5])
        return (
            "Có nhiều sản phẩm khớp yêu cầu. Bạn nêu rõ mã SKU giúp mình nhé. "
            f"Các sản phẩm gần đúng: {listed}."
        )
