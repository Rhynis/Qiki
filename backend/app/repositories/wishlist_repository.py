"""Repository for customer wishlists."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.wishlist import Wishlist


class WishlistRepository:
    """Data access layer for wishlist entries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: UUID, product_id: UUID) -> None:
        """Add a product to a user's wishlist (idempotent via the unique index)."""
        statement = (
            pg_insert(Wishlist)
            .values(user_id=user_id, product_id=product_id)
            .on_conflict_do_nothing(constraint="uq_wishlists_user_product")
        )
        await self.session.execute(statement)
        await self.session.flush()

    async def remove(self, user_id: UUID, product_id: UUID) -> None:
        """Remove a product from a user's wishlist (idempotent)."""
        await self.session.execute(
            delete(Wishlist).where(
                Wishlist.user_id == user_id,
                Wishlist.product_id == product_id,
            )
        )
        await self.session.flush()

    async def list_products(self, user_id: UUID) -> list[Product]:
        """Return the active products a user saved, most recently added first.

        Deactivated products are hidden here just as they are in the catalog, so
        the wishlist never surfaces a discontinued item with an add-to-cart action.
        """
        result = await self.session.execute(
            select(Product)
            .join(Wishlist, Wishlist.product_id == Product.id)
            .where(Wishlist.user_id == user_id, Product.is_active.is_(True))
            .order_by(Wishlist.created_at.desc())
        )
        return list(result.scalars().all())
