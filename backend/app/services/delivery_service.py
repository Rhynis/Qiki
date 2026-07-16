"""Delivery business logic: split an order into deliveries and roll status up."""

from datetime import UTC, datetime
from uuid import UUID

from app.core.exceptions import NotFoundException, ValidationException
from app.models.delivery import Delivery
from app.models.order import Order
from app.repositories.delivery_repository import DeliveryRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.user_repository import UserRepository
from app.schemas.delivery import (
    DeliveryCreate,
    DeliveryResponse,
    DriverDeliveryLine,
    DriverDeliveryResponse,
)

# Per-delivery status transitions (independent of the order-level transitions).
DELIVERY_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["shipping", "delivered", "failed", "cancelled"],
    "shipping": ["delivered", "failed", "cancelled"],
    "delivered": [],
    "failed": [],
    "cancelled": [],
}


class DeliveryService:
    """Create/split deliveries for an order and derive the order's status."""

    def __init__(
        self,
        delivery_repo: DeliveryRepository,
        order_repo: OrderRepository,
        user_repo: UserRepository,
    ) -> None:
        self.delivery_repo = delivery_repo
        self.order_repo = order_repo
        self.user_repo = user_repo

    async def assign_driver(self, delivery_id: UUID, driver_id: UUID | None) -> DeliveryResponse:
        """Assign (or clear) the driver carrying a delivery. Staff/admin action."""
        delivery = await self.delivery_repo.get_by_id(delivery_id)
        if delivery is None:
            raise NotFoundException("Delivery not found", error_code="delivery_not_found")
        if driver_id is not None:
            driver = await self.user_repo.get_by_id(driver_id)
            if driver is None or not driver.is_driver():
                raise ValidationException("Assignee must be a driver", error_code="invalid_driver")
        delivery.driver_id = driver_id
        await self.delivery_repo.flush()
        refreshed = await self.delivery_repo.get_by_id(delivery_id)
        assert refreshed is not None
        return DeliveryResponse.model_validate(refreshed)

    async def list_driver_deliveries(self, driver_id: UUID) -> list[DriverDeliveryResponse]:
        """Return the deliveries assigned to a driver (with contact + items)."""
        deliveries = await self.delivery_repo.list_by_driver(driver_id)
        return [self._to_driver_response(delivery) for delivery in deliveries]

    @staticmethod
    def _to_driver_response(delivery: Delivery) -> DriverDeliveryResponse:
        order = delivery.order
        items_by_id = {item.id: item for item in order.items}
        lines = [
            DriverDeliveryLine(
                product_name=items_by_id[line.order_item_id].product_name,
                quantity=line.quantity,
            )
            for line in delivery.items
            if line.order_item_id in items_by_id
        ]
        return DriverDeliveryResponse(
            id=delivery.id,
            code=delivery.code,
            status=delivery.status,  # type: ignore[arg-type]
            customer_name=order.customer_name,
            customer_phone=order.customer_phone,
            delivery_address=order.delivery_address,
            notes=delivery.notes,
            scheduled_at=delivery.scheduled_at,
            delivered_at=delivery.delivered_at,
            last_lat=delivery.last_lat,
            last_lng=delivery.last_lng,
            items=lines,
            created_at=delivery.created_at,
        )

    async def driver_update_status(
        self,
        delivery_id: UUID,
        *,
        actor_id: UUID,
        is_admin: bool,
        new_status: str,
        notes: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> DriverDeliveryResponse:
        """Let the assigned driver (or an admin) mark a delivery delivered/failed."""
        delivery = await self.delivery_repo.get_with_order(delivery_id)
        # A driver may only touch their own delivery; hide others as "not found".
        if delivery is None or (not is_admin and delivery.driver_id != actor_id):
            raise NotFoundException("Delivery not found", error_code="delivery_not_found")
        if new_status not in DELIVERY_STATUS_TRANSITIONS[delivery.status]:
            raise ValidationException(
                f"Cannot transition delivery from {delivery.status} to {new_status}",
                error_code="invalid_delivery_status_transition",
            )
        delivery.status = new_status
        if notes is not None:
            delivery.notes = notes
        if lat is not None and lng is not None:
            delivery.last_lat = lat
            delivery.last_lng = lng
        if new_status == "delivered":
            delivery.delivered_at = datetime.now(UTC)
        await self.delivery_repo.flush()
        await self._roll_up_order_status(delivery.order_id)
        refreshed = await self.delivery_repo.get_with_order(delivery_id)
        assert refreshed is not None
        return self._to_driver_response(refreshed)

    async def list_deliveries(self, order_id: UUID) -> list[DeliveryResponse]:
        """Return an order's deliveries."""
        order = await self._require_order(order_id)
        return [DeliveryResponse.model_validate(delivery) for delivery in order.deliveries]

    async def create_delivery(self, order_id: UUID, payload: DeliveryCreate) -> DeliveryResponse:
        """Create a delivery carrying some of the order's items.

        Rejects allocating more of any item than was ordered (counting what other
        non-cancelled deliveries already carry). The order row is locked for the
        whole read-then-insert so two concurrent creates cannot over-allocate or
        collide on the generated code.
        """
        order = await self._require_order_for_update(order_id)
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
            if delivery.status in ("cancelled", "failed"):
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

    async def _require_order_for_update(self, order_id: UUID) -> Order:
        """Load the order with a row lock so allocation is check-then-act safe."""
        order = await self.order_repo.get_by_id_for_update(order_id)
        if order is None:
            raise NotFoundException("Order not found", error_code="order_not_found")
        return order
