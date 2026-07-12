"""Customer wishlist endpoints (saved products)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.repositories.product_repository import ProductRepository
from app.repositories.wishlist_repository import WishlistRepository
from app.schemas.product import ProductResponse
from app.services.wishlist_service import WishlistService

router = APIRouter()


def get_wishlist_service(session: Annotated[AsyncSession, Depends(get_db)]) -> WishlistService:
    """Build a request-scoped wishlist service."""
    return WishlistService(WishlistRepository(session), ProductRepository(session))


@router.get(
    "/wishlist",
    response_model=list[ProductResponse],
    summary="List saved products",
)
@limiter.limit("60/minute")
async def list_wishlist(
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
    service: Annotated[WishlistService, Depends(get_wishlist_service)],
) -> list[ProductResponse]:
    """Return the current customer's saved products."""
    del request
    return await service.list_products(user.id)


@router.post(
    "/wishlist/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Save a product to the wishlist",
)
@limiter.limit("30/minute")
async def add_to_wishlist(
    request: Request,
    product_id: UUID,
    user: Annotated[User, Depends(get_current_active_user)],
    service: Annotated[WishlistService, Depends(get_wishlist_service)],
) -> Response:
    """Save a product (idempotent — saving twice is a no-op)."""
    del request
    await service.add_product(user.id, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/wishlist/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a product from the wishlist",
)
@limiter.limit("30/minute")
async def remove_from_wishlist(
    request: Request,
    product_id: UUID,
    user: Annotated[User, Depends(get_current_active_user)],
    service: Annotated[WishlistService, Depends(get_wishlist_service)],
) -> Response:
    """Remove a product (idempotent — removing an absent product is a no-op)."""
    del request
    await service.remove_product(user.id, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
