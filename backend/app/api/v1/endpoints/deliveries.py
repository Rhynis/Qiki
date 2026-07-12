"""Delivery management endpoints (staff)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_staff
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.repositories.delivery_repository import DeliveryRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.delivery import DeliveryCreate, DeliveryResponse, DeliveryStatusUpdate
from app.services.delivery_service import DeliveryService

router = APIRouter()


def build_delivery_service(session: AsyncSession) -> DeliveryService:
    """Build a delivery service around one DB session."""
    return DeliveryService(DeliveryRepository(session), OrderRepository(session))


@router.get(
    "/admin/orders/{order_id}/deliveries",
    response_model=list[DeliveryResponse],
    summary="List order deliveries",
)
@limiter.limit("60/minute")
async def list_deliveries(
    request: Request,
    order_id: UUID,
    staff: Annotated[User, Depends(get_current_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[DeliveryResponse]:
    """Return all deliveries for an order."""
    del request, staff
    return await build_delivery_service(session).list_deliveries(order_id)


@router.post(
    "/admin/orders/{order_id}/deliveries",
    status_code=status.HTTP_201_CREATED,
    response_model=DeliveryResponse,
    summary="Create an order delivery",
)
@limiter.limit("30/minute")
async def create_delivery(
    request: Request,
    order_id: UUID,
    payload: DeliveryCreate,
    staff: Annotated[User, Depends(get_current_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DeliveryResponse:
    """Create a delivery carrying some of the order's items."""
    del request, staff
    return await build_delivery_service(session).create_delivery(order_id, payload)


@router.patch(
    "/admin/orders/{order_id}/deliveries/{delivery_id}",
    response_model=DeliveryResponse,
    summary="Update a delivery status",
)
@limiter.limit("30/minute")
async def update_delivery_status(
    request: Request,
    order_id: UUID,
    delivery_id: UUID,
    payload: DeliveryStatusUpdate,
    staff: Annotated[User, Depends(get_current_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DeliveryResponse:
    """Update a delivery's status; the order status is re-derived."""
    del request, staff
    return await build_delivery_service(session).update_delivery_status(
        order_id, delivery_id, payload.status, payload.notes
    )
