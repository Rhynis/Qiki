"""Human handoff routing for classified intents."""

from dataclasses import dataclass
from uuid import UUID

from app.intent.categories import INTENT_ROUTING_RULES, IntentCategory
from app.intent.schemas import IntentResult
from app.models.user import User
from app.repositories.user_repository import UserRepository


@dataclass(frozen=True)
class RoutingDecision:
    """Decision for what should happen after intent classification."""

    requires_human: bool
    priority: int
    reason: str
    assigned_staff_id: UUID | None = None


class RoutingService:
    """Route conversations to staff when policy requires it."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def route_intent(self, result: IntentResult) -> RoutingDecision:
        """Return the routing decision for an intent result."""
        rule = INTENT_ROUTING_RULES[result.category]
        requires_human = rule["requires_human"]
        priority = rule["priority"]

        if result.category == IntentCategory.SAFETY_EMERGENCY:
            staff = await self._find_available_staff()
            return RoutingDecision(
                requires_human=True,
                priority=0,
                reason="Safety emergency requires immediate staff attention",
                assigned_staff_id=staff.id if staff else None,
            )

        if requires_human:
            staff = await self._find_available_staff()
            return RoutingDecision(
                requires_human=True,
                priority=priority,
                reason="Intent requires staff",
                assigned_staff_id=staff.id if staff else None,
            )

        return RoutingDecision(
            requires_human=False,
            priority=priority,
            reason="Automatic response allowed",
        )

    async def _find_available_staff(self) -> User | None:
        users, _ = await self.user_repository.list_users(
            skip=0,
            limit=50,
            role_filter="staff",
        )
        staff = [user for user in users if user.is_active]
        if not staff:
            admins, _ = await self.user_repository.list_users(
                skip=0,
                limit=50,
                role_filter="admin",
            )
            staff = [user for user in admins if user.is_active]
        return staff[0] if staff else None
