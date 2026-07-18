"""Tests for the admin-in-chat endpoint (auth gating + end-to-end mutation)."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_admin
from app.core.exceptions import ForbiddenException
from app.db.redis import get_redis
from app.db.session import get_db
from app.main import app
from app.models.admin_audit import AdminAuditLog
from app.models.product import Product
from app.models.user import User
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate

pytestmark = pytest.mark.asyncio


def make_admin(user_id: UUID | None = None) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id or uuid4(),
        email=f"admin-{uuid4().hex[:6]}@example.com",
        hashed_password="hashed",
        full_name="Admin User",
        phone=f"09{uuid4().int % 10**8:08d}",
        role="admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def override_forbidden_admin() -> object:
    def forbidden_admin() -> User:
        raise ForbiddenException("Admin role required", error_code="admin_required")

    app.dependency_overrides[get_current_admin] = forbidden_admin
    yield
    app.dependency_overrides.clear()


async def _seed_admin_and_product(session: AsyncSession) -> tuple[User, Product]:
    admin = make_admin()
    session.add(admin)
    product = await ProductRepository(session).create(
        ProductCreate(
            sku="GAS-ELF-12",
            name="Gas Elf 12kg",
            brand="Elf",
            size_kg=Decimal("12"),
            price=Decimal("445000"),
            stock_quantity=15,
        )
    )
    await session.commit()
    return admin, product


def _wire_overrides(admin: User, session: AsyncSession, redis: FakeRedis) -> None:
    async def use_test_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_current_admin] = lambda: admin
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_db] = use_test_session


async def test_admin_chat_requires_admin(
    test_client: AsyncClient,
    override_forbidden_admin: object,
) -> None:
    response = await test_client.post(
        "/api/v1/admin/chat",
        json={"message": "đổi giá Elf 12kg thành 460000"},
    )

    assert response.status_code == 403


async def test_admin_chat_end_to_end_confirm_executes_and_audits(
    test_client: AsyncClient,
    order_session: AsyncSession,
    mock_redis: FakeRedis,
) -> None:
    admin, product = await _seed_admin_and_product(order_session)
    _wire_overrides(admin, order_session, mock_redis)
    try:
        planned = await test_client.post(
            "/api/v1/admin/chat",
            json={"message": "đổi giá Elf 12kg thành 460000"},
        )
        assert planned.status_code == 200
        body = planned.json()
        assert body["status"] == "confirm_required"
        token = body["pending_token"]
        assert token

        executed = await test_client.post(
            "/api/v1/admin/chat",
            json={"message": "", "confirm": True, "pending_token": token},
        )
        assert executed.status_code == 200
        assert executed.json()["status"] == "executed"
    finally:
        app.dependency_overrides.clear()

    refreshed = await order_session.get(Product, product.id)
    assert refreshed is not None
    assert refreshed.price == Decimal("460000")

    audit_rows = (
        (
            await order_session.execute(
                select(AdminAuditLog).where(AdminAuditLog.target_id == product.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "update_price"
    assert audit_rows[0].admin_id == admin.id
    assert audit_rows[0].before == {"price": "445000.00"}
    assert audit_rows[0].after == {"price": "460000"}


async def test_admin_chat_first_message_does_not_mutate(
    test_client: AsyncClient,
    order_session: AsyncSession,
    mock_redis: FakeRedis,
) -> None:
    admin, product = await _seed_admin_and_product(order_session)
    _wire_overrides(admin, order_session, mock_redis)
    try:
        planned = await test_client.post(
            "/api/v1/admin/chat",
            json={"message": "đổi giá Elf 12kg thành 460000"},
        )
        assert planned.status_code == 200
        assert planned.json()["status"] == "confirm_required"
    finally:
        app.dependency_overrides.clear()

    refreshed = await order_session.get(Product, product.id)
    assert refreshed is not None
    # The first (unconfirmed) message must not have changed the live price.
    assert refreshed.price == Decimal("445000")

    audit_rows = (
        (
            await order_session.execute(
                select(AdminAuditLog).where(AdminAuditLog.target_id == product.id)
            )
        )
        .scalars()
        .all()
    )
    assert audit_rows == []
