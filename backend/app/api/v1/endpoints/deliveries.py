"""Delivery management endpoints (staff)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_driver, get_current_staff
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.repositories.delivery_repository import DeliveryRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.user_repository import UserRepository
from app.schemas.delivery import (
    DeliveryCreate,
    DeliveryResponse,
    DeliveryStatusUpdate,
    DriverAssignRequest,
    DriverDeliveryResponse,
    DriverStatusUpdate,
)
from app.services.delivery_service import DeliveryService

router = APIRouter()


def build_delivery_service(session: AsyncSession) -> DeliveryService:
    """Build a delivery service around one DB session."""
    return DeliveryService(
        DeliveryRepository(session),
        OrderRepository(session),
        UserRepository(session),
    )


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


@router.patch(
    "/admin/deliveries/{delivery_id}/assign",
    response_model=DeliveryResponse,
    summary="Assign a driver to a delivery",
)
@limiter.limit("30/minute")
async def assign_delivery_driver(
    request: Request,
    delivery_id: UUID,
    payload: DriverAssignRequest,
    staff: Annotated[User, Depends(get_current_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DeliveryResponse:
    """Assign (or clear) the driver carrying a delivery."""
    del request, staff
    return await build_delivery_service(session).assign_driver(delivery_id, payload.driver_id)


@router.get(
    "/driver/deliveries",
    response_model=list[DriverDeliveryResponse],
    summary="List the current driver's assigned deliveries",
)
@limiter.limit("60/minute")
async def list_my_driver_deliveries(
    request: Request,
    driver: Annotated[User, Depends(get_current_driver)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[DriverDeliveryResponse]:
    """Return the deliveries assigned to the signed-in driver."""
    del request
    return await build_delivery_service(session).list_driver_deliveries(driver.id)


@router.patch(
    "/driver/deliveries/{delivery_id}/status",
    response_model=DriverDeliveryResponse,
    summary="Driver marks a delivery delivered/failed",
)
@limiter.limit("30/minute")
async def driver_update_delivery_status(
    request: Request,
    delivery_id: UUID,
    payload: DriverStatusUpdate,
    driver: Annotated[User, Depends(get_current_driver)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DriverDeliveryResponse:
    """Mark an assigned delivery delivered or failed, with an optional location."""
    del request
    return await build_delivery_service(session).driver_update_status(
        delivery_id,
        actor_id=driver.id,
        is_admin=driver.is_admin(),
        new_status=payload.status,
        notes=payload.notes,
        lat=payload.lat,
        lng=payload.lng,
    )
