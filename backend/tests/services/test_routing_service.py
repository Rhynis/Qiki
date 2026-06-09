"""Tests for conversation routing service."""

import uuid

import pytest

from app.intent.categories import IntentCategory
from app.intent.schemas import IntentResult
from app.models.user import User
from app.services.routing_service import RoutingService


class FakeUserRepository:
    def __init__(self, staff: list[User] | None = None, admins: list[User] | None = None) -> None:
        self.staff = staff or []
        self.admins = admins or []

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 20,
        role_filter: str | None = None,
    ) -> tuple[list[User], int]:
        del skip, limit
        users = self.admins if role_filter == "admin" else self.staff
        return users, len(users)


def make_user(role: str = "staff", active: bool = True) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@example.com",
        role=role,
        is_active=active,
    )
    return user


def intent(category: IntentCategory, confidence: float = 0.9) -> IntentResult:
    return IntentResult(
        category=category,
        confidence=confidence,
        reasoning="test",
        classifier="test",
    )


@pytest.mark.asyncio
async def test_product_inquiry_can_auto_respond() -> None:
    service = RoutingService(FakeUserRepository())  # type: ignore[arg-type]

    decision = await service.route_intent(intent(IntentCategory.PRODUCT_INQUIRY))

    assert decision.requires_human is False
    assert decision.priority == 3


@pytest.mark.asyncio
async def test_complaint_requires_human() -> None:
    staff = make_user()
    service = RoutingService(FakeUserRepository(staff=[staff]))  # type: ignore[arg-type]

    decision = await service.route_intent(intent(IntentCategory.COMPLAINT))

    assert decision.requires_human is True
    assert decision.assigned_staff_id == staff.id


@pytest.mark.asyncio
async def test_payment_issue_can_auto_respond() -> None:
    staff = make_user()
    service = RoutingService(FakeUserRepository(staff=[staff]))  # type: ignore[arg-type]

    decision = await service.route_intent(intent(IntentCategory.PAYMENT_ISSUE))

    assert decision.requires_human is False
    assert decision.priority == 1


@pytest.mark.asyncio
async def test_safety_emergency_has_highest_priority() -> None:
    staff = make_user()
    service = RoutingService(FakeUserRepository(staff=[staff]))  # type: ignore[arg-type]

    decision = await service.route_intent(intent(IntentCategory.SAFETY_EMERGENCY))

    assert decision.requires_human is True
    assert decision.priority == 0
    assert decision.assigned_staff_id == staff.id


@pytest.mark.asyncio
async def test_low_confidence_auto_response_does_not_require_human() -> None:
    staff = make_user()
    service = RoutingService(FakeUserRepository(staff=[staff]))  # type: ignore[arg-type]

    decision = await service.route_intent(intent(IntentCategory.GENERAL_INFO, confidence=0.59))

    assert decision.requires_human is False
    assert decision.reason == "Automatic response allowed"


@pytest.mark.asyncio
async def test_inactive_staff_is_not_assigned() -> None:
    inactive_staff = make_user(active=False)
    service = RoutingService(FakeUserRepository(staff=[inactive_staff]))  # type: ignore[arg-type]

    decision = await service.route_intent(intent(IntentCategory.COMPLAINT))

    assert decision.assigned_staff_id is None


@pytest.mark.asyncio
async def test_admin_fallback_when_no_staff_available() -> None:
    admin = make_user(role="admin")
    service = RoutingService(FakeUserRepository(admins=[admin]))  # type: ignore[arg-type]

    decision = await service.route_intent(intent(IntentCategory.COMPLAINT))

    assert decision.assigned_staff_id == admin.id


@pytest.mark.asyncio
async def test_delivery_status_can_auto_respond() -> None:
    service = RoutingService(FakeUserRepository())  # type: ignore[arg-type]

    decision = await service.route_intent(intent(IntentCategory.DELIVERY_STATUS))

    assert decision.requires_human is False


@pytest.mark.asyncio
async def test_technical_issue_can_auto_respond_when_confident() -> None:
    service = RoutingService(FakeUserRepository())  # type: ignore[arg-type]

    decision = await service.route_intent(intent(IntentCategory.TECHNICAL_ISSUE, confidence=0.8))

    assert decision.requires_human is False
