"""Postgres-backed tests for conversation code generation, status, and auto-close."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.conversation_repository import ConversationRepository

pytestmark = pytest.mark.asyncio

CODE_PATTERN = re.compile(r"^CT-\d{8}-\d{3}$")


async def _clean(session: AsyncSession) -> None:
    await session.execute(text("TRUNCATE TABLE messages, conversations RESTART IDENTITY CASCADE"))


async def test_create_assigns_sequential_conversation_code(order_session: AsyncSession) -> None:
    await _clean(order_session)
    repo = ConversationRepository(order_session)

    first = await repo.create({"session_id": "s1", "status": "active"})
    second = await repo.create({"session_id": "s2", "status": "active"})

    assert CODE_PATTERN.match(first.code or "")
    assert CODE_PATTERN.match(second.code or "")
    today = datetime.now(UTC).strftime("%Y%m%d")
    assert first.code == f"CT-{today}-001"
    assert second.code == f"CT-{today}-002"


async def test_set_status_stamps_resolved(order_session: AsyncSession) -> None:
    await _clean(order_session)
    repo = ConversationRepository(order_session)
    conversation = await repo.create({"session_id": "s1", "status": "active"})

    updated = await repo.set_status(conversation.id, "resolved")

    assert updated.status == "resolved"
    assert updated.resolved_at is not None

    reopened = await repo.set_status(conversation.id, "active")

    assert reopened.status == "active"
    assert reopened.resolved_at is None


async def test_close_stale_closes_only_old_active_conversations(
    order_session: AsyncSession,
) -> None:
    await _clean(order_session)
    repo = ConversationRepository(order_session)
    fresh = await repo.create({"session_id": "fresh", "status": "active"})
    stale = await repo.create({"session_id": "stale", "status": "active"})
    # Backdate the stale conversation's creation well past the cutoff.
    await order_session.execute(
        text("UPDATE conversations SET created_at = :old WHERE id = :id"),
        {"old": datetime.now(UTC) - timedelta(days=30), "id": stale.id},
    )

    closed = await repo.close_stale(datetime.now(UTC) - timedelta(days=3))

    assert closed == 1
    # Drop the identity map so the re-read reflects the bulk UPDATE (production
    # reads these rows in a fresh request session).
    order_session.expunge_all()
    assert (await repo.get_by_id(stale.id)).status == "closed"  # type: ignore[union-attr]
    assert (await repo.get_by_id(fresh.id)).status == "active"  # type: ignore[union-attr]
