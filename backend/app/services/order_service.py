"""Order service with ACID-compliant order creation."""

from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ForbiddenException,
    InsufficientStockException,
    NotFoundException,
    ValidationException,
)
from app.core.input_validation import VietnamesePhoneValidator
from app.core.logging import get_logger
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.repositories.order_repository import ALLOWED_STATUS_TRANSITIONS, OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.order import CheckoutRequest, OrderListResponse, OrderResponse, OrderSearchParams

logger = get_logger(__name__)
WATER_DELIVERY_FEE_PER_UNIT = Decimal("5000")


class OrderService:
    """Business logic for order management."""

    def __init__(self, order_repo: OrderRepository, product_repo: ProductRepository) -> None:
        self.order_repo = order_repo
        self.product_repo = product_repo

    async def create_order(
        self,
        checkout_data: CheckoutRequest,
        current_user: User | None,
        idempotency_key: UUID,
        session: AsyncSession,
    ) -> OrderResponse:
        """Create an order with SERIALIZABLE isolation and row-level product locks."""
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

        existing = await self.order_repo.get_by_idempotency_key(idempotency_key)
        if existing:
            logger.info("order_idempotency_hit", order_id=str(existing.id))
            return self._to_response(existing)

        product_ids = list({item.product_id for item in checkout_data.items})
        products = await self.product_repo.get_many_for_update(product_ids)

        for product_id in product_ids:
            product = products.get(product_id)
            if not product:
                raise NotFoundException(
                    f"Product not found: {product_id}", error_code="product_not_found"
                )
            if not product.is_active:
                raise ValidationException(
                    f"Product not available: {product.name}",
                    error_code="product_inactive",
                )

        subtotal = Decimal("0")
        items_data = []
        requested_by_product: dict[UUID, int] = {}
        exchange_by_product: dict[UUID, bool] = {}
        for item in checkout_data.items:
            requested_by_product[item.product_id] = (
                requested_by_product.get(item.product_id, 0) + item.quantity
            )
            exchange_by_product[item.product_id] = (
                exchange_by_product.get(item.product_id, False) or item.is_exchange
            )

        for product_id, quantity in requested_by_product.items():
            product = products[product_id]
            if product.stock_quantity < quantity:
                raise InsufficientStockException(
                    f"Insufficient stock for {product.name}: requested {quantity}, "
                    f"available {product.stock_quantity}"
                )
            item_subtotal = product.price * quantity
            subtotal += item_subtotal
            items_data.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "product_brand": product.brand,
                    "product_size_kg": product.size_kg,
                    "quantity": quantity,
                    "unit_price": product.price,
                    "subtotal": item_subtotal,
                    "is_exchange": exchange_by_product[product_id],
                }
            )

        shipping_fee = self._calculate_shipping(products, requested_by_product)
        total_amount = subtotal + shipping_fee

        for product_id, quantity in requested_by_product.items():
            await self.product_repo.decrement_stock(product_id, quantity)

        order_data = {
            "user_id": current_user.id if current_user else None,
            "customer_name": checkout_data.customer_name,
            "customer_phone": checkout_data.customer_phone,
            "customer_email": str(checkout_data.customer_email)
            if checkout_data.customer_email
            else None,
            "delivery_address": checkout_data.delivery_address,
            "delivery_ward": checkout_data.delivery_ward,
            "delivery_district": checkout_data.delivery_district,
            "delivery_city": checkout_data.delivery_city,
            "delivery_notes": checkout_data.delivery_notes,
            "different_recipient_name": checkout_data.different_recipient_name,
            "different_recipient_phone": checkout_data.different_recipient_phone,
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "total_amount": total_amount,
            "vat_invoice_requested": checkout_data.vat_invoice_requested,
            "vat_info": checkout_data.vat_info.model_dump() if checkout_data.vat_info else None,
            "payment_method": checkout_data.payment_method,
            "payment_status": "pending",
            "status": "pending",
            "source": checkout_data.source,
            "referral_conversation_id": checkout_data.referral_conversation_id,
            "idempotency_key": idempotency_key,
            "customer_notes": checkout_data.customer_notes,
        }

        order = await self.order_repo.create_with_items(order_data, items_data, session)
        logger.info(
            "order_created",
            order_number=order.order_number,
            total=float(total_amount),
            item_count=len(items_data),
            source=checkout_data.source,
            is_guest=current_user is None,
        )
        return self._to_response(order)

    async def lookup_guest_order(self, order_number: str, phone: str) -> OrderResponse:
        """Look up a guest order by number and phone."""
        order = await self.order_repo.get_by_order_number_and_phone(order_number, phone)
        if not order:
            raise NotFoundException("Order not found", error_code="order_not_found")
        return self._to_response(order)

    async def get_user_orders(self, user: User, params: OrderSearchParams) -> OrderListResponse:
        """List orders owned by the current user."""
        orders, total = await self.order_repo.list_user_orders(user.id, params)
        return self._list_response(orders, total, params)

    async def get_order(
        self,
        order_id: UUID,
        current_user: User | None,
        phone: str | None = None,
    ) -> OrderResponse:
        """Get one order with owner, staff, or phone verification."""
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundException("Order not found", error_code="order_not_found")
        normalized_phone = VietnamesePhoneValidator.validate(phone) if phone else None
        self._ensure_can_view(order, current_user, normalized_phone)
        return self._to_response(order)

    async def list_all_orders(self, admin: User, params: OrderSearchParams) -> OrderListResponse:
        """List orders for an administrator."""
        self._ensure_staff(admin)
        orders, total = await self.order_repo.list_all_orders(params)
        return self._list_response(orders, total, params)

    async def update_order_status(
        self,
        order_id: UUID,
        new_status: str,
        admin: User,
        notes: str | None = None,
    ) -> OrderResponse:
        """Update order status as staff/admin."""
        self._ensure_staff(admin)
        existing = await self.order_repo.get_by_id(order_id)
        if not existing:
            raise NotFoundException("Order not found", error_code="order_not_found")
        if new_status not in ALLOWED_STATUS_TRANSITIONS[existing.status]:
            raise ValidationException(
                f"Cannot transition order from {existing.status} to {new_status}",
                error_code="invalid_status_transition",
            )
        if new_status == "cancelled":
            for item in existing.items:
                if item.product_id:
                    await self.product_repo.increment_stock(item.product_id, item.quantity)
        order = await self.order_repo.update_status(order_id, new_status, notes)
        return self._to_response(order)

    async def cancel_order(
        self,
        order_id: UUID,
        current_user: User | None,
        reason: str | None = None,
        phone: str | None = None,
    ) -> OrderResponse:
        """Cancel a pending/confirmed order and restore stock."""
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundException("Order not found", error_code="order_not_found")
        self._ensure_can_view(order, current_user, phone)
        if not order.can_be_cancelled():
            raise ValidationException(
                "Order cannot be cancelled", error_code="order_not_cancellable"
            )
        for item in order.items:
            if item.product_id:
                await self.product_repo.increment_stock(item.product_id, item.quantity)
        cancelled = await self.order_repo.cancel_order(order_id, reason)
        return self._to_response(cancelled)

    async def get_statistics(self, admin: User) -> dict[str, int]:
        """Return simple order statistics for admin dashboards."""
        self._ensure_staff(admin)
        orders, total = await self.order_repo.list_all_orders(OrderSearchParams(limit=100))
        return {
            "total": total,
            "pending": sum(1 for order in orders if order.status == "pending"),
            "confirmed": sum(1 for order in orders if order.status == "confirmed"),
            "shipping": sum(1 for order in orders if order.status == "shipping"),
            "delivered": sum(1 for order in orders if order.status == "delivered"),
            "cancelled": sum(1 for order in orders if order.status == "cancelled"),
        }

    def _calculate_shipping(
        self,
        products: Mapping[UUID, Product],
        requested_by_product: Mapping[UUID, int],
    ) -> Decimal:
        """Charge water delivery per unit; gas and other products ship free."""
        water_units = sum(
            quantity
            for product_id, quantity in requested_by_product.items()
            if products[product_id].category == "nuoc_uong"
        )
        return WATER_DELIVERY_FEE_PER_UNIT * water_units

    @staticmethod
    def _to_response(order: Order) -> OrderResponse:
        return OrderResponse.model_validate(order)

    @staticmethod
    def _list_response(
        orders: list[Order],
        total: int,
        params: OrderSearchParams,
    ) -> OrderListResponse:
        return OrderListResponse(
            items=[OrderResponse.model_validate(order) for order in orders],
            total=total,
            page=(params.skip // params.limit) + 1,
            limit=params.limit,
            has_more=params.skip + len(orders) < total,
        )

    @staticmethod
    def _ensure_staff(user: User) -> None:
        if not user.is_staff():
            raise ForbiddenException("Staff role required", error_code="staff_required")

    @staticmethod
    def _ensure_can_view(order: Order, user: User | None, phone: str | None = None) -> None:
        if user and (user.is_staff() or order.user_id == user.id):
            return
        if phone and order.customer_phone == phone:
            return
        raise ForbiddenException("Order access denied", error_code="order_forbidden")


def is_serialization_failure(exc: BaseException) -> bool:
    """Return whether a database error is a PostgreSQL serialization failure."""
    if not isinstance(exc, DBAPIError):
        return False
    orig = exc.orig
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    return sqlstate == "40001" or orig.__class__.__name__ == "SerializationFailure"
