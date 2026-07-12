"""Data access for price-alert subscriptions."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_subscription import PriceSubscription


class PriceSubscriptionRepository:
    """Data access layer for the PriceSubscription model."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, email: str, token: str, user_id: UUID | None = None
    ) -> PriceSubscription:
        """Insert a new (unconfirmed, active) subscription."""
        subscription = PriceSubscription(email=email, token=token, user_id=user_id)
        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def get_active_by_email(self, email: str) -> PriceSubscription | None:
        """Return the active (not-unsubscribed) subscription for an email, if any."""
        result = await self.session.execute(
            select(PriceSubscription).where(
                PriceSubscription.email == email,
                PriceSubscription.unsubscribed_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_token(self, token: str) -> PriceSubscription | None:
        """Return the subscription matching an opaque token, if any."""
        result = await self.session.execute(
            select(PriceSubscription).where(PriceSubscription.token == token)
        )
        return result.scalar_one_or_none()

    async def list_confirmed_active(self) -> list[PriceSubscription]:
        """Return all confirmed subscriptions that have not unsubscribed."""
        result = await self.session.execute(
            select(PriceSubscription)
            .where(
                PriceSubscription.confirmed.is_(True),
                PriceSubscription.unsubscribed_at.is_(None),
            )
            .order_by(PriceSubscription.created_at.asc())
        )
        return list(result.scalars().all())

    async def mark_confirmed(self, subscription: PriceSubscription) -> PriceSubscription:
        """Mark a subscription as confirmed (idempotent)."""
        if not subscription.confirmed:
            subscription.confirmed = True
            subscription.confirmed_at = datetime.now(UTC)
            await self.session.flush()
        return subscription

    async def mark_unsubscribed(self, subscription: PriceSubscription) -> PriceSubscription:
        """Mark a subscription as unsubscribed (idempotent)."""
        if subscription.unsubscribed_at is None:
            subscription.unsubscribed_at = datetime.now(UTC)
            await self.session.flush()
        return subscription
