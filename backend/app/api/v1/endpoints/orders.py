"""Order endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.api.v1.dependencies.auth import (
    get_current_active_user,
    get_current_staff,
    get_current_user_optional,
    validate_idempotency_key,
)
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.order import (
    CheckoutRequest,
    GuestOrderLookup,
    OrderCancelRequest,
    OrderListResponse,
    OrderResponse,
    OrderSearchParams,
    OrderStatusUpdate,
)
from app.services.order_service import OrderService, is_serialization_failure

router = APIRouter()


def build_order_service(session: AsyncSession) -> OrderService:
    """Build an order service around one DB session."""
    return OrderService(OrderRepository(session), ProductRepository(session))


@retry(
    retry=retry_if_exception(is_serialization_failure),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
    reraise=True,
)
async def _create_order_with_retry(
    service: OrderService,
    payload: CheckoutRequest,
    current_user: User | None,
    idempotency_key: UUID,
    session: AsyncSession,
) -> OrderResponse:
    try:
        return await service.create_order(payload, current_user, idempotency_key, session)
    except Exception as exc:
        if is_serialization_failure(exc):
            await session.rollback()
        raise


@router.post(
    "/orders/checkout",
    status_code=status.HTTP_201_CREATED,
    response_model=OrderResponse,
    summary="Create order",
)
@limiter.limit("20/minute")
async def checkout(
    request: Request,
    payload: CheckoutRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[UUID, Depends(validate_idempotency_key)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
) -> OrderResponse:
    """Create a guest or authenticated order."""
    service = build_order_service(session)
    return await _create_order_with_retry(service, payload, current_user, idempotency_key, session)


@router.post(
    "/orders/lookup",
    response_model=OrderResponse,
    summary="Look up guest order",
)
@limiter.limit("30/minute")
async def lookup_order(
    request: Request,
    payload: GuestOrderLookup,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OrderResponse:
    """Look up a guest order by order number and phone."""
    service = build_order_service(session)
    return await service.lookup_guest_order(payload.order_number, payload.phone)


@router.get("/orders/me", response_model=OrderListResponse, summary="List my orders")
@limiter.limit("60/minute")
async def my_orders(
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    params: Annotated[OrderSearchParams, Query()],
) -> OrderListResponse:
    """Return the authenticated customer's orders."""
    service = build_order_service(session)
    return await service.get_user_orders(user, params)


@router.get("/orders/{order_id}", response_model=OrderResponse, summary="Get order")
@limiter.limit("60/minute")
async def get_order(
    request: Request,
    order_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    phone: Annotated[str | None, Query()] = None,
) -> OrderResponse:
    """Return one order for an owner, staff member, or verified guest phone."""
    service = build_order_service(session)
    return await service.get_order(order_id, current_user, phone)


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse, summary="Cancel order")
@limiter.limit("20/minute")
async def cancel_order(
    request: Request,
    order_id: UUID,
    payload: OrderCancelRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
) -> OrderResponse:
    """Cancel an order and restore stock."""
    service = build_order_service(session)
    return await service.cancel_order(order_id, current_user, payload.reason, payload.phone)


@router.get("/admin/orders", response_model=OrderListResponse, summary="List all orders")
@limiter.limit("60/minute")
async def admin_orders(
    request: Request,
    staff: Annotated[User, Depends(get_current_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
    params: Annotated[OrderSearchParams, Query()],
) -> OrderListResponse:
    """Return all orders for staff/admin users."""
    service = build_order_service(session)
    return await service.list_all_orders(staff, params)


@router.patch(
    "/admin/orders/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status",
)
@limiter.limit("30/minute")
async def update_order_status(
    request: Request,
    order_id: UUID,
    payload: OrderStatusUpdate,
    staff: Annotated[User, Depends(get_current_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OrderResponse:
    """Update an order status using valid transitions only."""
    service = build_order_service(session)
    return await service.update_order_status(order_id, payload.new_status, staff, payload.notes)


@router.get("/admin/orders/statistics", summary="Get order statistics")
@limiter.limit("60/minute")
async def order_statistics(
    request: Request,
    staff: Annotated[User, Depends(get_current_staff)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, int]:
    """Return dashboard-friendly order counts."""
    service = build_order_service(session)
    return await service.get_statistics(staff)
