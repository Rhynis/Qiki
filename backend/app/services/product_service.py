"""Product business logic."""

from typing import cast
from uuid import UUID

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.product import Product
from app.models.user import User
from app.repositories.product_repository import ProductRepository
from app.schemas.product import (
    ALLOWED_SIZES,
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductSearchParams,
    ProductUpdate,
)
from app.services.product_query import ProductQuery, filter_products, price_bounds


class ProductService:
    """Application service for product catalog operations."""

    def __init__(self, repository: ProductRepository) -> None:
        self.repository = repository

    @staticmethod
    def _ensure_admin(user: User) -> None:
        if not user.is_admin():
            raise ForbiddenException("Admin role required", error_code="admin_required")

    async def create_product(self, payload: ProductCreate, admin: User) -> ProductResponse:
        """Create a product as an administrator."""
        self._ensure_admin(admin)
        product = await self.repository.create(payload)
        return ProductResponse.model_validate(product)

    async def get_product(self, product_id: UUID) -> ProductResponse:
        """Get one active product by ID."""
        product = await self.repository.get_by_id(product_id, active_only=True)
        if not product:
            raise NotFoundException("Product not found", error_code="product_not_found")
        return ProductResponse.model_validate(product)

    async def get_product_by_sku(self, sku: str) -> ProductResponse:
        """Get one active product by SKU."""
        product = await self.repository.get_by_sku(sku, active_only=True)
        if not product:
            raise NotFoundException("Product not found", error_code="product_not_found")
        return ProductResponse.model_validate(product)

    async def search_products(self, params: ProductSearchParams) -> ProductListResponse:
        """Search active products with filters and pagination metadata."""
        products, total = await self.repository.list_products(params, active_only=True)
        page = (params.skip // params.limit) + 1
        has_more = params.skip + len(products) < total
        return ProductListResponse(
            items=[ProductResponse.model_validate(product) for product in products],
            total=total,
            page=page,
            limit=params.limit,
            has_more=has_more,
        )

    async def list_active_catalog(self, limit: int = 50) -> list[ProductResponse]:
        """Return active products for compact chatbot catalog context."""
        result = await self.search_products(
            ProductSearchParams(limit=limit, sort_by="name", sort_order="asc")
        )
        return result.items

    async def find_products(self, query: ProductQuery, *, limit: int = 20) -> list[ProductResponse]:
        """Resolve a parsed product/price query to matching active products.

        Brand/size/category and any price range are filtered in SQL; the colour
        variant keyword is matched against the product name. Results are ordered
        by price ascending so callers can read off the cheapest/most expensive.
        """
        min_price, max_price = price_bounds(query)
        # ProductSearchParams rejects gas sizes outside ALLOWED_SIZES (6/12/45).
        # A customer can still ask about an unstocked size ("gas 20kg rẻ nhất");
        # drop it from the SQL filter and let filter_products enforce the exact
        # size in memory (which yields no match -> a "not available" answer).
        sql_size_kg = query.size_kg
        if (
            sql_size_kg is not None
            and query.category != "nuoc_uong"
            and sql_size_kg not in ALLOWED_SIZES
        ):
            sql_size_kg = None
        params = ProductSearchParams(
            brand=query.brand,
            category=query.category,
            size_kg=sql_size_kg,
            min_price=min_price,
            max_price=max_price,
            sort_by="price",
            sort_order="asc",
            limit=limit,
        )
        result = await self.search_products(params)
        return cast(list[ProductResponse], filter_products(result.items, query))

    async def list_brands(self, category: str | None = None) -> list[str]:
        """Return active product brands for filter controls."""
        return await self.repository.list_brands(category=category, active_only=True)

    async def update_product(
        self,
        product_id: UUID,
        payload: ProductUpdate,
        admin: User,
    ) -> ProductResponse:
        """Update a product as an administrator."""
        self._ensure_admin(admin)
        update_data = payload.model_dump(mode="json", exclude_unset=True)
        product = await self.repository.update(product_id, update_data)
        return ProductResponse.model_validate(product)

    async def delete_product(self, product_id: UUID, admin: User) -> None:
        """Soft-delete a product as an administrator."""
        self._ensure_admin(admin)
        deleted = await self.repository.soft_delete(product_id)
        if not deleted:
            raise NotFoundException("Product not found", error_code="product_not_found")

    async def get_low_stock_products(
        self,
        admin: User,
        threshold: int = 10,
    ) -> list[ProductResponse]:
        """Return active products whose stock is at or below the threshold."""
        self._ensure_admin(admin)
        products = await self.repository.get_low_stock_products(threshold)
        return [ProductResponse.model_validate(product) for product in products]

    async def check_availability(self, product_id: UUID, quantity: int) -> bool:
        """Check whether an active product can satisfy the requested quantity."""
        product = await self.repository.get_by_id(product_id, active_only=True)
        if not product:
            raise NotFoundException("Product not found", error_code="product_not_found")
        return product.stock_quantity >= quantity

    async def reserve_stock(self, product_id: UUID, quantity: int) -> Product:
        """Reserve stock using the repository's row-level lock."""
        return await self.repository.decrement_stock(product_id, quantity)
