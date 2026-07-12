"""Wishlist business logic."""

from uuid import UUID

from app.core.exceptions import NotFoundException
from app.repositories.product_repository import ProductRepository
from app.repositories.wishlist_repository import WishlistRepository
from app.schemas.product import ProductResponse


class WishlistService:
    """Application service for a customer's saved products."""

    def __init__(
        self,
        wishlist_repository: WishlistRepository,
        product_repository: ProductRepository,
    ) -> None:
        self.wishlist_repository = wishlist_repository
        self.product_repository = product_repository

    async def add_product(self, user_id: UUID, product_id: UUID) -> None:
        """Save a product to the user's wishlist (idempotent)."""
        product = await self.product_repository.get_by_id(product_id, active_only=True)
        if not product:
            raise NotFoundException("Product not found", error_code="product_not_found")
        await self.wishlist_repository.add(user_id, product_id)

    async def remove_product(self, user_id: UUID, product_id: UUID) -> None:
        """Remove a product from the user's wishlist (idempotent)."""
        await self.wishlist_repository.remove(user_id, product_id)

    async def list_products(self, user_id: UUID) -> list[ProductResponse]:
        """Return the products the user saved."""
        products = await self.wishlist_repository.list_products(user_id)
        return [ProductResponse.model_validate(product) for product in products]
