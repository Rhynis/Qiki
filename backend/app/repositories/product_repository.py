"""Product repository."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.core.exceptions import ConflictException, InsufficientStockException, NotFoundException
from app.models.product import Product, ProductParent
from app.schemas.product import ProductCreate, ProductParentCreate, ProductSearchParams


class ProductRepository:
    """Data access layer for products."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: ProductCreate) -> Product:
        """Create a product."""
        product = Product(**data.model_dump(mode="json"))
        self.session.add(product)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise ConflictException("SKU already exists", error_code="duplicate_sku") from exc
        await self.session.refresh(product)
        return product

    async def get_by_id(self, product_id: UUID, *, active_only: bool = False) -> Product | None:
        """Find a product by ID."""
        query = select(Product).where(Product.id == product_id)
        if active_only:
            query = query.where(Product.is_active.is_(True))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_sku(self, sku: str, *, active_only: bool = False) -> Product | None:
        """Find a product by SKU."""
        query = select(Product).where(Product.sku == sku.upper().strip())
        if active_only:
            query = query.where(Product.is_active.is_(True))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_brands(
        self,
        *,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[str]:
        """Return distinct product brands sorted alphabetically."""
        query = select(Product.brand).distinct().order_by(Product.brand.asc())
        if active_only:
            query = query.where(Product.is_active.is_(True))
        if category:
            query = query.where(Product.category == category)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, product_id: UUID, data: dict[str, object]) -> Product:
        """Update a product."""
        product = await self.get_by_id(product_id)
        if not product:
            raise NotFoundException("Product not found", error_code="product_not_found")
        for key, value in data.items():
            if hasattr(product, key):
                setattr(product, key, value)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise ConflictException("SKU already exists", error_code="duplicate_sku") from exc
        await self.session.refresh(product)
        return product

    async def soft_delete(self, product_id: UUID) -> bool:
        """Mark a product inactive."""
        product = await self.get_by_id(product_id)
        if not product:
            return False
        product.is_active = False
        await self.session.flush()
        return True

    async def list_products(
        self,
        params: ProductSearchParams,
        *,
        active_only: bool = True,
    ) -> tuple[list[Product], int]:
        """List products with search, filters, and pagination."""
        query = select(Product)
        count_query = select(func.count()).select_from(Product)

        conditions: list[ColumnElement[bool]] = []
        if active_only:
            conditions.append(Product.is_active.is_(True))
        if params.search:
            search = params.search.strip()
            conditions.append(
                Product.name.op("%")(search)
                | (func.similarity(Product.name, search) > 0.3)
                | Product.sku.ilike(f"%{search}%")
            )
        if params.brand:
            conditions.append(Product.brand.ilike(f"%{params.brand.strip()}%"))
        if params.category:
            conditions.append(Product.category == params.category)
        if params.min_price is not None:
            conditions.append(Product.price >= params.min_price)
        if params.max_price is not None:
            conditions.append(Product.price <= params.max_price)
        if params.size_kg is not None:
            conditions.append(Product.size_kg == params.size_kg)
        if params.in_stock_only:
            conditions.append(Product.stock_quantity > 0)

        for condition in conditions:
            query = query.where(condition)
            count_query = count_query.where(condition)

        sort_column: Any = {
            "created_at": Product.created_at,
            "price": Product.price,
            "name": Product.name,
        }[params.sort_by]
        query = query.order_by(
            sort_column.asc() if params.sort_order == "asc" else sort_column.desc()
        )
        query = query.offset(params.skip).limit(params.limit)

        total = (await self.session.execute(count_query)).scalar_one()
        products = list((await self.session.execute(query)).scalars().all())
        return products, total

    async def get_many_for_update(self, product_ids: list[UUID]) -> dict[UUID, Product]:
        """Fetch products with row locks for stock updates."""
        result = await self.session.execute(
            select(Product).where(Product.id.in_(product_ids)).with_for_update()
        )
        return {product.id: product for product in result.scalars().all()}

    async def decrement_stock(self, product_id: UUID, quantity: int) -> Product:
        """Atomically decrement stock. Caller must be inside a transaction."""
        result = await self.session.execute(
            select(Product).where(Product.id == product_id).with_for_update()
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundException("Product not found", error_code="product_not_found")
        if product.stock_quantity < quantity:
            raise InsufficientStockException(
                f"Insufficient stock: requested {quantity}, available {product.stock_quantity}"
            )
        product.stock_quantity -= quantity
        await self.session.flush()
        return product

    async def increment_stock(self, product_id: UUID, quantity: int) -> Product:
        """Increment stock, usually after cancellation."""
        result = await self.session.execute(
            select(Product).where(Product.id == product_id).with_for_update()
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundException("Product not found", error_code="product_not_found")
        product.stock_quantity += quantity
        await self.session.flush()
        return product

    async def list_parents(
        self,
        *,
        category: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ProductParent], int]:
        """List active parents (each with its active variants) with pagination."""
        conditions: list[ColumnElement[bool]] = [ProductParent.is_active.is_(True)]
        if category:
            conditions.append(ProductParent.category == category)

        count_query = select(func.count()).select_from(ProductParent)
        query = (
            select(ProductParent)
            .options(selectinload(ProductParent.variants))
            .order_by(ProductParent.name.asc())
        )
        for condition in conditions:
            query = query.where(condition)
            count_query = count_query.where(condition)
        query = query.offset(skip).limit(limit)

        total = (await self.session.execute(count_query)).scalar_one()
        parents = list((await self.session.execute(query)).scalars().unique().all())
        return parents, total

    async def get_parent_by_id(
        self,
        parent_id: UUID,
        *,
        active_only: bool = False,
    ) -> ProductParent | None:
        """Fetch one parent with its variants eagerly loaded."""
        query = (
            select(ProductParent)
            .options(selectinload(ProductParent.variants))
            .where(ProductParent.id == parent_id)
        )
        if active_only:
            query = query.where(ProductParent.is_active.is_(True))
        result = await self.session.execute(query)
        return result.scalars().unique().one_or_none()

    async def create_parent(self, data: ProductParentCreate) -> ProductParent:
        """Create a parent product."""
        parent = ProductParent(**data.model_dump(mode="json"))
        self.session.add(parent)
        await self.session.flush()
        await self.session.refresh(parent)
        return parent

    async def update_parent(self, parent_id: UUID, data: dict[str, object]) -> ProductParent:
        """Update a parent product."""
        parent = await self.get_parent_by_id(parent_id)
        if not parent:
            raise NotFoundException(
                "Parent product not found", error_code="product_parent_not_found"
            )
        for key, value in data.items():
            if hasattr(parent, key):
                setattr(parent, key, value)
        await self.session.flush()
        await self.session.refresh(parent)
        return parent

    async def soft_delete_parent(self, parent_id: UUID) -> bool:
        """Mark a parent and all its variants inactive."""
        parent = await self.get_parent_by_id(parent_id)
        if not parent:
            return False
        parent.is_active = False
        for variant in parent.variants:
            variant.is_active = False
        await self.session.flush()
        return True

    async def get_low_stock_products(self, threshold: int = 10) -> list[Product]:
        """Return active products at or below low-stock threshold."""
        result = await self.session.execute(
            select(Product)
            .where(Product.is_active.is_(True), Product.stock_quantity <= threshold)
            .order_by(Product.stock_quantity.asc(), Product.name.asc())
        )
        return list(result.scalars().all())
