"""Product catalog endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_admin
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.repositories.product_repository import ProductRepository
from app.schemas.product import (
    ProductCategory,
    ProductCreate,
    ProductListResponse,
    ProductParentCreate,
    ProductParentListResponse,
    ProductParentResponse,
    ProductParentUpdate,
    ProductResponse,
    ProductSearchParams,
    ProductUpdate,
)
from app.services.product_service import ProductService

router = APIRouter()


def get_product_service(session: Annotated[AsyncSession, Depends(get_db)]) -> ProductService:
    """Build a request-scoped product service."""
    return ProductService(ProductRepository(session))


@router.get(
    "/products",
    response_model=ProductListResponse,
    summary="List products",
)
@limiter.limit("60/minute")
async def list_products(
    request: Request,
    service: Annotated[ProductService, Depends(get_product_service)],
    params: Annotated[ProductSearchParams, Query()],
) -> ProductListResponse:
    """Return active products with search, filters, sorting, and pagination."""
    return await service.search_products(params)


@router.get(
    "/products/brands",
    response_model=list[str],
    summary="List product brands",
)
@limiter.limit("60/minute")
async def list_product_brands(
    request: Request,
    service: Annotated[ProductService, Depends(get_product_service)],
    category: Annotated[ProductCategory | None, Query()] = None,
) -> list[str]:
    """Return distinct active product brands, optionally filtered by category."""
    return await service.list_brands(category)


@router.get(
    "/products/parents",
    response_model=ProductParentListResponse,
    summary="List grouped product parents",
)
@limiter.limit("60/minute")
async def list_product_parents(
    request: Request,
    service: Annotated[ProductService, Depends(get_product_service)],
    category: Annotated[ProductCategory | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProductParentListResponse:
    """Return active parent products as catalog cards with a price range."""
    return await service.list_grouped_catalog(category=category, skip=skip, limit=limit)


@router.get(
    "/products/parents/{parent_id}",
    response_model=ProductParentResponse,
    summary="Get product parent with variants",
)
@limiter.limit("60/minute")
async def get_product_parent(
    request: Request,
    parent_id: UUID,
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductParentResponse:
    """Return one active parent product with its selectable variants."""
    return await service.get_parent(parent_id)


@router.post(
    "/products/parents",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductParentResponse,
    summary="Create product parent",
)
@limiter.limit("30/minute")
async def create_product_parent(
    request: Request,
    payload: ProductParentCreate,
    service: Annotated[ProductService, Depends(get_product_service)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> ProductParentResponse:
    """Create a parent product as an administrator."""
    return await service.create_parent(payload, admin)


@router.patch(
    "/products/parents/{parent_id}",
    response_model=ProductParentResponse,
    summary="Update product parent",
)
@limiter.limit("30/minute")
async def update_product_parent(
    request: Request,
    parent_id: UUID,
    payload: ProductParentUpdate,
    service: Annotated[ProductService, Depends(get_product_service)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> ProductParentResponse:
    """Update a parent product as an administrator."""
    return await service.update_parent(parent_id, payload, admin)


@router.delete(
    "/products/parents/{parent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete product parent",
)
@limiter.limit("30/minute")
async def delete_product_parent(
    request: Request,
    parent_id: UUID,
    service: Annotated[ProductService, Depends(get_product_service)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> Response:
    """Soft-delete a parent product and its variants as an administrator."""
    await service.delete_parent(parent_id, admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/products/sku/{sku}",
    response_model=ProductResponse,
    summary="Get product by SKU",
)
@limiter.limit("60/minute")
async def get_product_by_sku(
    request: Request,
    sku: str,
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductResponse:
    """Return one active product by SKU."""
    return await service.get_product_by_sku(sku)


@router.get(
    "/products/{product_id}",
    response_model=ProductResponse,
    summary="Get product by ID",
)
@limiter.limit("60/minute")
async def get_product(
    request: Request,
    product_id: UUID,
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductResponse:
    """Return one active product by ID."""
    return await service.get_product(product_id)


@router.post(
    "/products",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductResponse,
    summary="Create product",
)
@limiter.limit("30/minute")
async def create_product(
    request: Request,
    payload: ProductCreate,
    service: Annotated[ProductService, Depends(get_product_service)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> ProductResponse:
    """Create a product as an administrator."""
    return await service.create_product(payload, admin)


@router.patch(
    "/products/{product_id}",
    response_model=ProductResponse,
    summary="Update product",
)
@limiter.limit("30/minute")
async def update_product(
    request: Request,
    product_id: UUID,
    payload: ProductUpdate,
    service: Annotated[ProductService, Depends(get_product_service)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> ProductResponse:
    """Update a product as an administrator."""
    return await service.update_product(product_id, payload, admin)


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete product",
)
@limiter.limit("30/minute")
async def delete_product(
    request: Request,
    product_id: UUID,
    service: Annotated[ProductService, Depends(get_product_service)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> Response:
    """Soft-delete a product as an administrator."""
    await service.delete_product(product_id, admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/admin/products/low-stock",
    response_model=list[ProductResponse],
    summary="List low-stock products",
)
@limiter.limit("60/minute")
async def get_low_stock_products(
    request: Request,
    service: Annotated[ProductService, Depends(get_product_service)],
    admin: Annotated[User, Depends(get_current_admin)],
    threshold: Annotated[int, Query(ge=0, le=1000)] = 10,
) -> list[ProductResponse]:
    """Return active low-stock products for administrators."""
    return await service.get_low_stock_products(admin, threshold)
