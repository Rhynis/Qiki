"""Tests for admin user management endpoints."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_admin
from app.core.exceptions import ForbiddenException
from app.main import app
from app.models.user import User

pytestmark = pytest.mark.asyncio


def make_user(
    *,
    user_id: UUID | None = None,
    email: str | None = None,
    role: str = "customer",
    is_active: bool = True,
) -> User:
    now = datetime.now(UTC)
    suffix = uuid4().hex[:8]
    return User(
        id=user_id or uuid4(),
        email=email or f"{role}-{suffix}@example.com",
        hashed_password="hashed",
        full_name=f"{role.title()} User",
        phone=f"09{uuid4().int % 10**8:08d}",
        role=role,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


async def save_user(session: AsyncSession, user: User) -> User:
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
def override_admin() -> object:
    admin = make_user(email="admin@example.com", role="admin")
    app.dependency_overrides[get_current_admin] = lambda: admin
    yield admin
    app.dependency_overrides.clear()


@pytest.fixture
def override_forbidden_admin() -> object:
    def forbidden_admin() -> User:
        raise ForbiddenException("Admin role required", error_code="admin_required")

    app.dependency_overrides[get_current_admin] = forbidden_admin
    yield
    app.dependency_overrides.clear()


async def test_list_users_requires_admin(
    test_client: AsyncClient,
    override_forbidden_admin: object,
) -> None:
    response = await test_client.get("/api/v1/admin/users")

    assert response.status_code == 403


async def test_list_users_omits_hashed_password(
    test_client: AsyncClient,
    order_session: AsyncSession,
    override_admin: object,
) -> None:
    await save_user(order_session, make_user(email="customer@example.com"))

    response = await test_client.get("/api/v1/admin/users")

    assert response.status_code == 200
    user = response.json()["items"][0]
    assert user["email"] == "customer@example.com"
    assert "hashed_password" not in user


async def test_list_users_filters_by_email_role_and_status(
    test_client: AsyncClient,
    order_session: AsyncSession,
    override_admin: object,
) -> None:
    await save_user(order_session, make_user(email="active-staff@example.com", role="staff"))
    await save_user(
        order_session,
        make_user(email="inactive-staff@example.com", role="staff", is_active=False),
    )
    await save_user(order_session, make_user(email="customer@example.com"))

    response = await test_client.get(
        "/api/v1/admin/users",
        params={"email": "staff", "role": "staff", "is_active": "false"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["email"] == "inactive-staff@example.com"


async def test_update_user_role_as_admin(
    test_client: AsyncClient,
    order_session: AsyncSession,
    override_admin: object,
) -> None:
    user = await save_user(order_session, make_user())

    response = await test_client.patch(
        f"/api/v1/admin/users/{user.id}/role",
        json={"role": "staff"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "staff"


async def test_update_user_role_rejects_invalid_role(
    test_client: AsyncClient,
    order_session: AsyncSession,
    override_admin: object,
) -> None:
    user = await save_user(order_session, make_user())

    response = await test_client.patch(
        f"/api/v1/admin/users/{user.id}/role",
        json={"role": "owner"},
    )

    assert response.status_code == 422


async def test_update_user_role_rejects_self_change(
    test_client: AsyncClient,
    order_session: AsyncSession,
) -> None:
    admin = await save_user(order_session, make_user(email="admin@example.com", role="admin"))
    app.dependency_overrides[get_current_admin] = lambda: admin
    try:
        response = await test_client.patch(
            f"/api/v1/admin/users/{admin.id}/role",
            json={"role": "staff"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["error_code"] == "self_role_change_forbidden"


async def test_update_user_status_as_admin(
    test_client: AsyncClient,
    order_session: AsyncSession,
    override_admin: object,
) -> None:
    user = await save_user(order_session, make_user())

    response = await test_client.patch(
        f"/api/v1/admin/users/{user.id}/status",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_update_user_status_rejects_self_change(
    test_client: AsyncClient,
    order_session: AsyncSession,
) -> None:
    admin = await save_user(order_session, make_user(email="admin@example.com", role="admin"))
    app.dependency_overrides[get_current_admin] = lambda: admin
    try:
        response = await test_client.patch(
            f"/api/v1/admin/users/{admin.id}/status",
            json={"is_active": False},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["error_code"] == "self_status_change_forbidden"


async def test_update_user_role_returns_404_for_missing_user(
    test_client: AsyncClient,
    override_admin: object,
) -> None:
    response = await test_client.patch(
        f"/api/v1/admin/users/{uuid4()}/role",
        json={"role": "staff"},
    )

    assert response.status_code == 404


async def test_update_user_role_rejects_final_admin_demotion(
    test_client: AsyncClient,
    order_session: AsyncSession,
) -> None:
    admin = await save_user(order_session, make_user(email="admin@example.com", role="admin"))
    manager = make_user(email="manager@example.com", role="admin")
    app.dependency_overrides[get_current_admin] = lambda: manager
    try:
        response = await test_client.patch(
            f"/api/v1/admin/users/{admin.id}/role",
            json={"role": "staff"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["error_code"] == "final_admin_required"
