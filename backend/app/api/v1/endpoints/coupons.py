"""Coupon endpoints: public validation and admin CRUD."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_admin
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.repositories.coupon_repository import CouponRepository
from app.schemas.coupon import (
    CouponCreate,
    CouponListResponse,
    CouponResponse,
    CouponSearchParams,
    CouponUpdate,
    CouponValidateRequest,
    CouponValidateResponse,
)
from app.services.coupon_service import CouponService

router = APIRouter()


def get_coupon_service(session: Annotated[AsyncSession, Depends(get_db)]) -> CouponService:
    """Build a request-scoped coupon service."""
    return CouponService(CouponRepository(session))


@router.post(
    "/coupons/validate",
    response_model=CouponValidateResponse,
    summary="Validate a coupon",
)
@limiter.limit("30/minute")
async def validate_coupon(
    request: Request,
    payload: CouponValidateRequest,
    service: Annotated[CouponService, Depends(get_coupon_service)],
) -> CouponValidateResponse:
    """Validate a coupon against a cart subtotal (server computes the discount)."""
    return await service.validate_coupon(payload.code, payload.subtotal)


@router.post(
    "/admin/coupons",
    status_code=status.HTTP_201_CREATED,
    response_model=CouponResponse,
    summary="Create coupon",
)
@limiter.limit("30/minute")
async def create_coupon(
    request: Request,
    payload: CouponCreate,
    service: Annotated[CouponService, Depends(get_coupon_service)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> CouponResponse:
    """Create a coupon as an administrator."""
    return await service.create_coupon(payload, admin)


@router.get(
    "/admin/coupons",
    response_model=CouponListResponse,
    summary="List coupons",
)
@limiter.limit("60/minute")
async def list_coupons(
    request: Request,
    service: Annotated[CouponService, Depends(get_coupon_service)],
    admin: Annotated[User, Depends(get_current_admin)],
    params: Annotated[CouponSearchParams, Query()],
) -> CouponListResponse:
    """List coupons with usage counters for administrators."""
    return await service.list_coupons(params, admin)


@router.get(
    "/admin/coupons/{coupon_id}",
    response_model=CouponResponse,
    summary="Get coupon",
)
@limiter.limit("60/minute")
async def get_coupon(
    request: Request,
    coupon_id: UUID,
    service: Annotated[CouponService, Depends(get_coupon_service)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> CouponResponse:
    """Get one coupon by ID as an administrator."""
    return await service.get_coupon(coupon_id, admin)


@router.patch(
    "/admin/coupons/{coupon_id}",
    response_model=CouponResponse,
    summary="Update coupon",
)
@limiter.limit("30/minute")
async def update_coupon(
    request: Request,
    coupon_id: UUID,
    payload: CouponUpdate,
    service: Annotated[CouponService, Depends(get_coupon_service)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> CouponResponse:
    """Update or disable a coupon as an administrator."""
    return await service.update_coupon(coupon_id, payload, admin)
