"""Delivery business logic: split an order into deliveries and roll status up."""

from datetime import UTC, datetime
from uuid import UUID

from app.core.exceptions import NotFoundException, ValidationException
from app.models.order import Order
from app.repositories.delivery_repository import DeliveryRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.delivery import DeliveryCreate, DeliveryResponse

# Per-delivery status transitions (independent of the order-level transitions).
DELIVERY_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["shipping", "delivered", "cancelled"],
    "shipping": ["delivered", "cancelled"],
    "delivered": [],
    "cancelled": [],
}


class DeliveryService:
    """Create/split deliveries for an order and derive the order's status."""

    def __init__(
        self,
        delivery_repo: DeliveryRepository,
        order_repo: OrderRepository,
    ) -> None:
        self.delivery_repo = delivery_repo
        self.order_repo = order_repo

    async def list_deliveries(self, order_id: UUID) -> list[DeliveryResponse]:
        """Return an order's deliveries."""
        order = await self._require_order(order_id)
        return [DeliveryResponse.model_validate(delivery) for delivery in order.deliveries]

    async def create_delivery(self, order_id: UUID, payload: DeliveryCreate) -> DeliveryResponse:
        """Create a delivery carrying some of the order's items.

        Rejects allocating more of any item than was ordered (counting what other
        non-cancelled deliveries already carry).
        """
        order = await self._require_order(order_id)
        if order.status == "cancelled":
            raise ValidationException(
                "Cannot add a delivery to a cancelled order",
                error_code="order_cancelled",
            )

        items_by_id = {item.id: item for item in order.items}
        allocated = self._allocated_quantities(order)

        seen: set[UUID] = set()
        for line in payload.items:
            if line.order_item_id in seen:
                raise ValidationException(
                    "Duplicate order item in delivery",
                    error_code="delivery_duplicate_item",
                )
            seen.add(line.order_item_id)
            order_item = items_by_id.get(line.order_item_id)
            if order_item is None:
                raise ValidationException(
                    "Order item does not belong to this order",
                    error_code="delivery_item_invalid",
                )
            remaining = order_item.quantity - allocated.get(order_item.id, 0)
            if line.quantity > remaining:
                raise ValidationException(
                    f"Cannot allocate {line.quantity} of '{order_item.product_name}'; "
                    f"only {remaining} remaining",
                    error_code="delivery_over_allocation",
                )

        code = f"{order.order_number}-D{len(order.deliveries) + 1}"
        item_rows = [
            {"order_item_id": line.order_item_id, "quantity": line.quantity}
            for line in payload.items
        ]
        delivery = await self.delivery_repo.create(
            order_id,
            code,
            "pending",
            payload.scheduled_at,
            payload.notes,
            item_rows,
        )
        await self._roll_up_order_status(order_id)
        return DeliveryResponse.model_validate(delivery)

    async def update_delivery_status(
        self,
        order_id: UUID,
        delivery_id: UUID,
        new_status: str,
        notes: str | None = None,
    ) -> DeliveryResponse:
        """Update a delivery's status and re-derive the order's status."""
        delivery = await self.delivery_repo.get_by_id(delivery_id)
        if delivery is None or delivery.order_id != order_id:
            raise NotFoundException("Delivery not found", error_code="delivery_not_found")
        if new_status not in DELIVERY_STATUS_TRANSITIONS[delivery.status]:
            raise ValidationException(
                f"Cannot transition delivery from {delivery.status} to {new_status}",
                error_code="invalid_delivery_status_transition",
            )
        delivery.status = new_status
        if notes is not None:
            delivery.notes = notes
        if new_status == "delivered":
            delivery.delivered_at = datetime.now(UTC)
        await self.delivery_repo.flush()
        await self._roll_up_order_status(order_id)
        refreshed = await self.delivery_repo.get_by_id(delivery_id)
        assert refreshed is not None
        return DeliveryResponse.model_validate(refreshed)

    @staticmethod
    def _allocated_quantities(order: Order) -> dict[UUID, int]:
        """Sum quantities already committed to non-cancelled deliveries, per item."""
        allocated: dict[UUID, int] = {}
        for delivery in order.deliveries:
            if delivery.status == "cancelled":
                continue
            for item in delivery.items:
                allocated[item.order_item_id] = allocated.get(item.order_item_id, 0) + item.quantity
        return allocated

    async def _roll_up_order_status(self, order_id: UUID) -> None:
        """Derive the order status from its deliveries (all delivered -> delivered)."""
        order = await self.order_repo.get_by_id(order_id)
        if order is None or not order.deliveries or order.status == "cancelled":
            return

        delivered: dict[UUID, int] = {}
        for delivery in order.deliveries:
            if delivery.status == "delivered":
                for item in delivery.items:
                    delivered[item.order_item_id] = (
                        delivered.get(item.order_item_id, 0) + item.quantity
                    )

        fully_delivered = bool(order.items) and all(
            delivered.get(item.id, 0) >= item.quantity for item in order.items
        )
        if fully_delivered:
            order.status = "delivered"
            if order.delivered_at is None:
                order.delivered_at = datetime.now(UTC)
        elif any(
            delivery.status == "shipping" for delivery in order.deliveries
        ) and order.status in {"pending", "confirmed"}:
            order.status = "shipping"
        await self.delivery_repo.flush()

    async def _require_order(self, order_id: UUID) -> Order:
        order = await self.order_repo.get_by_id(order_id)
        if order is None:
            raise NotFoundException("Order not found", error_code="order_not_found")
        return order
