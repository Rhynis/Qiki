"""Repository for admin-in-chat audit log entries."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_audit import AdminAuditLog


class AdminAuditRepository:
    """Persist audit entries for admin-chat mutations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        admin_id: UUID,
        action: str,
        target_type: str,
        target_id: UUID | None,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> AdminAuditLog:
        """Insert one audit row and return it."""
        entry = AdminAuditLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
        )
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry
