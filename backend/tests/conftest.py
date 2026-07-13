"""Shared pytest fixtures."""

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://gasbot:gasbot_dev_password@localhost:5432/gasbot_dev"
)
os.environ["JWT_SECRET_KEY"] = "test_secret_key_at_least_32_characters_long"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["ENVIRONMENT"] = "development"
os.environ["DEBUG"] = "false"
# Pin the default RAG providers so tests are hermetic regardless of a local .env
# (CI has no .env). Provider-specific tests override these explicitly.
os.environ["EMBEDDING_PROVIDER"] = "gemini"
os.environ["RAG_RERANK_ENABLED"] = "false"
# DeepEval (tests/eval) ships a pytest plugin; keep it offline + deterministic in CI.
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("ERROR_REPORTING", "0")


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Use asyncio for async tests."""
    return "asyncio"


@pytest_asyncio.fixture
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class FakeUserRepository:
    """In-memory user repository for auth tests."""

    def __init__(self) -> None:
        self.users_by_id: dict[UUID, object] = {}
        self.users_by_email: dict[str, object] = {}
        self.users_by_phone: dict[str, object] = {}

    async def create(self, data: Any, hashed_password: str) -> object:
        """Create a user from a schema-like object."""
        from app.models.user import User

        now = datetime.now(UTC)
        email = data.email.lower() if data.email else None
        user = User(
            id=uuid4(),
            email=email,
            email_verified=False,
            hashed_password=hashed_password,
            full_name=data.full_name,
            phone=data.phone,
            role="customer",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.users_by_id[user.id] = user
        if email:
            self.users_by_email[email] = user
        if data.phone:
            self.users_by_phone[data.phone] = user
        return user

    async def get_by_id(self, user_id: UUID) -> object | None:
        """Find a user by ID."""
        return self.users_by_id.get(user_id)

    async def get_by_email(self, email: str) -> object | None:
        """Find a user by email."""
        return self.users_by_email.get(email.lower())

    async def get_by_phone(self, phone: str) -> object | None:
        """Find a user by phone number."""
        return self.users_by_phone.get(phone)

    async def update(self, user_id: UUID, data: dict[str, object]) -> object | None:
        """Update user fields."""
        user = self.users_by_id.get(user_id)
        if not user:
            return None
        for key, value in data.items():
            setattr(user, key, value)
        return user


@pytest.fixture
def fake_user_repository() -> FakeUserRepository:
    """Return an isolated fake user repository."""
    return FakeUserRepository()


@pytest_asyncio.fixture
async def mock_redis() -> AsyncGenerator[FakeRedis, None]:
    """Return an isolated fake Redis client."""
    redis = FakeRedis(decode_responses=True)
    await redis.flushall()
    try:
        yield redis
    finally:
        await redis.flushall()
        await redis.aclose()


@pytest_asyncio.fixture
async def product_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated Postgres-backed product session."""
    from app.db.base import Base
    from app.db.session import AsyncSessionLocal, engine

    await engine.dispose()
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        tables = [table for table in Base.metadata.sorted_tables if table.name != "knowledge_base"]
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
        await conn.execute(
            text("TRUNCATE TABLE products, product_parents RESTART IDENTITY CASCADE")
        )

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE products RESTART IDENTITY CASCADE"))

    await engine.dispose()


@pytest_asyncio.fixture
async def order_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated Postgres-backed order session."""
    from app.db.base import Base
    from app.db.session import AsyncSessionLocal, engine

    await engine.dispose()
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        tables = [table for table in Base.metadata.sorted_tables if table.name != "knowledge_base"]
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
        await conn.execute(
            text(
                "TRUNCATE TABLE order_items, orders, products, product_parents, users "
                "RESTART IDENTITY CASCADE"
            )
        )

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE order_items, orders, products, product_parents, users "
                "RESTART IDENTITY CASCADE"
            )
        )

    await engine.dispose()


@pytest_asyncio.fixture
async def price_alert_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated Postgres-backed session for price-alert tests."""
    from app.db.base import Base
    from app.db.session import AsyncSessionLocal, engine

    await engine.dispose()
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        tables = [table for table in Base.metadata.sorted_tables if table.name != "knowledge_base"]
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
        await conn.execute(
            text(
                "TRUNCATE TABLE price_subscriptions, order_items, orders, products, "
                "product_parents, users RESTART IDENTITY CASCADE"
            )
        )

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE price_subscriptions, order_items, orders, products, "
                "product_parents, users RESTART IDENTITY CASCADE"
            )
        )

    await engine.dispose()


def product_data(
    sku: str = "GAS-12-SAIGON",
    name: str = "Binh gas 12kg",
    brand: str = "Saigon Petro",
    price: Decimal = Decimal("350000"),
    stock_quantity: int = 20,
) -> object:
    """Return valid product creation data."""
    from app.schemas.product import ProductCreate

    return ProductCreate(
        sku=sku,
        name=name,
        brand=brand,
        size_kg=Decimal("12"),
        price=price,
        stock_quantity=stock_quantity,
        description="Binh gas gia dinh",
        image_url="https://example.com/gas-12kg.jpg",
        safety_info="Dat binh noi thoang khi.",
    )


async def create_product(
    session: AsyncSession,
    **overrides: object,
) -> object:
    """Create and commit a product for product tests."""
    from app.models.product import Product
    from app.repositories.product_repository import ProductRepository
    from app.schemas.product import ProductCreate

    data = product_data(**overrides)
    if not isinstance(data, ProductCreate):
        raise TypeError("product_data returned unexpected type")
    product = await ProductRepository(session).create(data)
    await session.commit()
    assert isinstance(product, Product)
    return product
