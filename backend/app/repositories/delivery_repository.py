"""Delivery repository."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.delivery import Delivery, DeliveryItem


class DeliveryRepository:
    """Data access layer for order deliveries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, delivery_id: UUID) -> Delivery | None:
        """Fetch one delivery with its items."""
        result = await self.session.execute(
            select(Delivery).where(Delivery.id == delivery_id).options(selectinload(Delivery.items))
        )
        return result.scalar_one_or_none()

    async def list_by_order(self, order_id: UUID) -> list[Delivery]:
        """List an order's deliveries, oldest first."""
        result = await self.session.execute(
            select(Delivery)
            .where(Delivery.order_id == order_id)
            .order_by(Delivery.created_at)
            .options(selectinload(Delivery.items))
        )
        return list(result.scalars().all())

    async def create(
        self,
        order_id: UUID,
        code: str,
        status: str,
        scheduled_at: datetime | None,
        notes: str | None,
        items: list[dict[str, Any]],
    ) -> Delivery:
        """Create a delivery and its line items in the active transaction."""
        delivery = Delivery(
            order_id=order_id,
            code=code,
            status=status,
            scheduled_at=scheduled_at,
            notes=notes,
        )
        self.session.add(delivery)
        await self.session.flush()
        for item in items:
            self.session.add(DeliveryItem(delivery_id=delivery.id, **item))
        await self.session.flush()
        await self.session.refresh(delivery, attribute_names=["items"])
        return delivery

    async def flush(self) -> None:
        """Flush pending changes on the shared session."""
        await self.session.flush()
