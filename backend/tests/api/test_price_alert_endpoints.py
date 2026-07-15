"""Tests for the price-alert subscription API endpoints."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_admin, get_current_user_optional
from app.core.exceptions import ForbiddenException
from app.main import app
from app.models.user import User
from app.repositories.price_subscription_repository import PriceSubscriptionRepository

pytestmark = pytest.mark.asyncio


def admin_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email="admin@example.com",
        hashed_password="hashed",
        full_name="Admin User",
        phone="0900000000",
        role="admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def override_guest() -> object:
    # The subscribe endpoint reads the optional logged-in user, which normally
    # needs app.state.redis; the test client has no lifespan, so stub the guest.
    app.dependency_overrides[get_current_user_optional] = lambda: None
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_admin() -> object:
    app.dependency_overrides[get_current_admin] = admin_user
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_forbidden_admin() -> object:
    def forbidden_admin() -> User:
        raise ForbiddenException("Admin role required", error_code="admin_required")

    app.dependency_overrides[get_current_admin] = forbidden_admin
    yield
    app.dependency_overrides.clear()


async def test_subscribe_requires_consent(
    test_client: AsyncClient,
    price_alert_session: AsyncSession,
    override_guest: object,
) -> None:
    response = await test_client.post(
        "/api/v1/price-alerts/subscribe",
        json={"email": "buyer@example.com", "consent": False},
    )
    assert response.status_code == 422


async def test_subscribe_then_confirm_flow(
    test_client: AsyncClient,
    price_alert_session: AsyncSession,
    override_guest: object,
) -> None:
    subscribe = await test_client.post(
        "/api/v1/price-alerts/subscribe",
        json={"email": "buyer@example.com", "consent": True},
    )
    assert subscribe.status_code == 200
    assert "message" in subscribe.json()

    row = await PriceSubscriptionRepository(price_alert_session).get_active_by_email(
        "buyer@example.com"
    )
    assert row is not None
    assert row.confirmed is False

    confirm = await test_client.post(
        "/api/v1/price-alerts/confirm",
        json={"token": row.confirm_token},
    )
    assert confirm.status_code == 200


async def test_confirm_invalid_token_returns_404(
    test_client: AsyncClient,
    price_alert_session: AsyncSession,
) -> None:
    response = await test_client.post(
        "/api/v1/price-alerts/confirm",
        json={"token": "not-a-real-token"},
    )
    assert response.status_code == 404


async def test_unsubscribe_invalid_token_returns_404(
    test_client: AsyncClient,
    price_alert_session: AsyncSession,
) -> None:
    response = await test_client.post(
        "/api/v1/price-alerts/unsubscribe",
        json={"token": "not-a-real-token"},
    )
    assert response.status_code == 404


async def test_admin_notify_requires_admin(
    test_client: AsyncClient,
    price_alert_session: AsyncSession,
    override_forbidden_admin: object,
) -> None:
    response = await test_client.post("/api/v1/admin/price-alerts/notify")
    assert response.status_code == 403


async def test_admin_notify_returns_counts(
    test_client: AsyncClient,
    price_alert_session: AsyncSession,
    override_admin: object,
) -> None:
    response = await test_client.post("/api/v1/admin/price-alerts/notify")
    assert response.status_code == 200
    body = response.json()
    assert body["recipient_count"] == 0
    assert body["sent_count"] == 0
