"""User repository for database operations."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate


class UserRepository:
    """Data access layer for User model."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: UserCreate, hashed_password: str) -> User:
        """Create a new user."""
        user = User(
            email=data.email.lower() if data.email else None,
            hashed_password=hashed_password,
            full_name=data.full_name,
            phone=data.phone,
            role="customer",
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Find user by ID."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Find user by email, case-insensitively."""
        result = await self.session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> User | None:
        """Find user by phone number."""
        result = await self.session.execute(select(User).where(User.phone == phone))
        return result.scalar_one_or_none()

    async def update(self, user_id: UUID, data: dict[str, object]) -> User | None:
        """Update user fields."""
        user = await self.get_by_id(user_id)
        if not user:
            return None
        for key, value in data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def soft_delete(self, user_id: UUID) -> bool:
        """Soft delete a user by deactivating it."""
        user = await self.get_by_id(user_id)
        if not user:
            return False
        user.is_active = False
        await self.session.flush()
        return True

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 20,
        role_filter: str | None = None,
    ) -> tuple[list[User], int]:
        """List users with optional role filter."""
        count_query = select(func.count()).select_from(User)
        query = select(User)
        if role_filter:
            count_query = count_query.where(User.role == role_filter)
            query = query.where(User.role == role_filter)

        total = (await self.session.execute(count_query)).scalar_one()
        query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
        users = list((await self.session.execute(query)).scalars().all())
        return users, total
