"""Postgres-backed tests for conversation mining aggregation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.services.insights_service import InsightsService

pytestmark = pytest.mark.asyncio

# Reference time for tests that rely on InsightsService's default lookback
# window. Anchor to *yesterday* noon UTC, not a fixed calendar date: a hardcoded
# date became a time-bomb once it aged past DEFAULT_PERIOD_DAYS (30) and fell out
# of the default window, zeroing every default-window insight. Yesterday (not
# today) keeps it strictly in the past — today-noon can be in the future when the
# suite runs in the morning UTC, which would push data past the window's end.
NOW = (datetime.now(UTC) - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)


async def _clean(session: AsyncSession) -> None:
    await session.execute(text("TRUNCATE TABLE messages, conversations RESTART IDENTITY CASCADE"))


async def _make_conversation(
    session: AsyncSession,
    *,
    status: str = "active",
    created_at: datetime = NOW,
) -> Conversation:
    conversation = Conversation(
        id=uuid.uuid4(),
        session_id=str(uuid.uuid4()),
        status=status,
    )
    session.add(conversation)
    await session.flush()
    await session.execute(
        text("UPDATE conversations SET created_at = :ts WHERE id = :id"),
        {"ts": created_at, "id": conversation.id},
    )
    await session.flush()
    return conversation


async def _make_message(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    created_at: datetime = NOW,
    intent: str | None = None,
    confidence: Decimal | None = None,
    feedback_score: int | None = None,
    flagged: bool = False,
    retrieved_documents: list[dict[str, Any]] | None = None,
) -> Message:
    message = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        created_at=created_at,
        intent=intent,
        intent_confidence=confidence,
        feedback_score=feedback_score,
        flagged_for_review=flagged,
        retrieved_documents=retrieved_documents,
    )
    session.add(message)
    await session.flush()
    return message


async def test_summary_counts_and_rates(order_session: AsyncSession) -> None:
    await _clean(order_session)
    good = await _make_conversation(order_session, status="active")
    escalated = await _make_conversation(order_session, status="escalated")

    await _make_message(
        order_session, conversation_id=good.id, role="user", content="Giá gas 12kg?"
    )
    await _make_message(
        order_session,
        conversation_id=good.id,
        role="assistant",
        content="Dạ 710.000đ ạ.",
        intent="product_inquiry",
        confidence=Decimal("0.90"),
        retrieved_documents=[{"title": "Bảng giá"}],
    )
    await _make_message(
        order_session, conversation_id=escalated.id, role="user", content="Bình bị xì hơi"
    )
    await _make_message(
        order_session,
        conversation_id=escalated.id,
        role="assistant",
        content="Xin lỗi, tôi chưa có thông tin chi tiết.",
        intent="general",
        confidence=Decimal("0.40"),
        feedback_score=-1,
        flagged=True,
        retrieved_documents=[],
    )

    service = InsightsService(order_session)
    insights = await service.get_insights()
    summary = insights.summary

    assert summary.total_conversations == 2
    assert summary.total_messages == 4
    assert summary.user_messages == 2
    assert summary.assistant_messages == 2
    assert summary.escalated_conversations == 1
    assert summary.flagged_messages == 1
    assert summary.low_confidence_messages == 1
    assert summary.negative_feedback_messages == 1
    # Empty retrieval + refusal phrase => one unanswered assistant turn.
    assert summary.unanswered_messages == 1
    assert summary.escalation_rate == 0.5
    assert summary.flag_rate == 0.25


async def test_low_confidence_detection_uses_threshold(order_session: AsyncSession) -> None:
    await _clean(order_session)
    conversation = await _make_conversation(order_session)
    # Below threshold -> counted.
    await _make_message(
        order_session,
        conversation_id=conversation.id,
        role="assistant",
        content="A",
        confidence=Decimal("0.59"),
        retrieved_documents=[{"title": "x"}],
    )
    # Exactly at threshold -> NOT counted.
    await _make_message(
        order_session,
        conversation_id=conversation.id,
        role="assistant",
        content="B",
        confidence=Decimal("0.60"),
        retrieved_documents=[{"title": "x"}],
    )
    # Null confidence -> NOT counted.
    await _make_message(
        order_session,
        conversation_id=conversation.id,
        role="assistant",
        content="C",
        confidence=None,
        retrieved_documents=[{"title": "x"}],
    )

    service = InsightsService(order_session)
    insights = await service.get_insights()

    assert insights.summary.low_confidence_messages == 1


async def test_top_intents_ordered_by_count(order_session: AsyncSession) -> None:
    await _clean(order_session)
    conversation = await _make_conversation(order_session)
    for _ in range(3):
        await _make_message(
            order_session,
            conversation_id=conversation.id,
            role="assistant",
            content="x",
            intent="product_inquiry",
            retrieved_documents=[{"title": "x"}],
        )
    await _make_message(
        order_session,
        conversation_id=conversation.id,
        role="assistant",
        content="x",
        intent="order_status",
        retrieved_documents=[{"title": "x"}],
    )
    # No-intent message must not appear as an intent bucket.
    await _make_message(
        order_session,
        conversation_id=conversation.id,
        role="user",
        content="hello",
    )

    service = InsightsService(order_session)
    insights = await service.get_insights()

    intents = [(item.intent, item.count) for item in insights.top_intents]
    assert intents == [("product_inquiry", 3), ("order_status", 1)]


async def test_top_questions_groups_normalized_text(order_session: AsyncSession) -> None:
    await _clean(order_session)
    conversation = await _make_conversation(order_session)
    # Same question in different casing/whitespace collapses to one theme.
    await _make_message(
        order_session, conversation_id=conversation.id, role="user", content="Giá gas 12kg?"
    )
    await _make_message(
        order_session, conversation_id=conversation.id, role="user", content="  giá gas 12kg?  "
    )
    await _make_message(
        order_session,
        conversation_id=conversation.id,
        role="user",
        content="Giao hàng mất bao lâu?",
    )
    # Assistant messages are never counted as questions.
    await _make_message(
        order_session,
        conversation_id=conversation.id,
        role="assistant",
        content="Giá gas 12kg?",
        retrieved_documents=[{"title": "x"}],
    )

    service = InsightsService(order_session)
    insights = await service.get_insights()

    questions = {item.question.strip().lower(): item.count for item in insights.top_questions}
    assert questions["giá gas 12kg?"] == 2
    assert questions["giao hàng mất bao lâu?"] == 1


async def test_knowledge_gaps_surface_preceding_question(order_session: AsyncSession) -> None:
    await _clean(order_session)
    conversation = await _make_conversation(order_session)
    base = NOW
    await _make_message(
        order_session,
        conversation_id=conversation.id,
        role="user",
        content="Cửa hàng có bán bếp từ không?",
        created_at=base,
    )
    gap_message = await _make_message(
        order_session,
        conversation_id=conversation.id,
        role="assistant",
        content="Xin lỗi, tôi chưa có thông tin chi tiết về vấn đề này.",
        created_at=base + timedelta(seconds=1),
        intent="general",
        confidence=Decimal("0.30"),
        retrieved_documents=[],
    )

    service = InsightsService(order_session)
    insights = await service.get_insights()

    assert len(insights.knowledge_gaps) == 1
    gap = insights.knowledge_gaps[0]
    assert gap.message_id == gap_message.id
    assert gap.conversation_id == conversation.id
    assert gap.question == "Cửa hàng có bán bếp từ không?"
    assert gap.reason == "no_context"
    assert gap.intent_confidence == pytest.approx(0.30)


async def test_knowledge_gaps_refusal_with_context(order_session: AsyncSession) -> None:
    await _clean(order_session)
    conversation = await _make_conversation(order_session)
    base = NOW
    await _make_message(
        order_session,
        conversation_id=conversation.id,
        role="user",
        content="Bảo hành van như thế nào?",
        created_at=base,
    )
    # Non-empty context but a refusal phrase -> still a gap, reason "refusal".
    await _make_message(
        order_session,
        conversation_id=conversation.id,
        role="assistant",
        content="Rất tiếc, tôi không tìm thấy nội dung phù hợp.",
        created_at=base + timedelta(seconds=1),
        retrieved_documents=[{"title": "Van"}],
    )
    # A well-answered assistant turn must NOT be a gap.
    await _make_message(
        order_session,
        conversation_id=conversation.id,
        role="assistant",
        content="Dạ van bảo hành 12 tháng ạ.",
        created_at=base + timedelta(seconds=2),
        retrieved_documents=[{"title": "Van"}],
    )

    service = InsightsService(order_session)
    insights = await service.get_insights()

    assert len(insights.knowledge_gaps) == 1
    assert insights.knowledge_gaps[0].reason == "refusal"


async def test_period_filter_excludes_out_of_range(order_session: AsyncSession) -> None:
    await _clean(order_session)
    inside = await _make_conversation(order_session, created_at=NOW)
    outside = await _make_conversation(order_session, created_at=NOW - timedelta(days=90))
    await _make_message(
        order_session,
        conversation_id=inside.id,
        role="user",
        content="in range",
        created_at=NOW,
    )
    await _make_message(
        order_session,
        conversation_id=outside.id,
        role="user",
        content="out of range",
        created_at=NOW - timedelta(days=90),
    )

    service = InsightsService(order_session)
    insights = await service.get_insights(
        period_start=NOW - timedelta(days=7),
        period_end=NOW + timedelta(days=1),
    )

    assert insights.summary.total_conversations == 1
    assert insights.summary.user_messages == 1
    questions = [item.question for item in insights.top_questions]
    assert questions == ["in range"]


async def test_trend_buckets_by_day(order_session: AsyncSession) -> None:
    await _clean(order_session)
    day_one = datetime(2026, 6, 10, 9, 0, tzinfo=UTC)
    day_two = datetime(2026, 6, 11, 9, 0, tzinfo=UTC)
    await _make_conversation(order_session, created_at=day_one)
    conv_two = await _make_conversation(order_session, status="escalated", created_at=day_two)
    await _make_message(
        order_session,
        conversation_id=conv_two.id,
        role="assistant",
        content="x",
        created_at=day_two,
        flagged=True,
        retrieved_documents=[{"title": "x"}],
    )

    service = InsightsService(order_session)
    insights = await service.get_insights(
        period_start=day_one - timedelta(days=1),
        period_end=day_two + timedelta(days=1),
    )

    trend = {point.date: point for point in insights.trend}
    assert trend["2026-06-10"].conversations == 1
    assert trend["2026-06-10"].escalated == 0
    assert trend["2026-06-11"].escalated == 1
    assert trend["2026-06-11"].flagged == 1
    # Dates are chronological.
    assert [point.date for point in insights.trend] == ["2026-06-10", "2026-06-11"]


async def test_empty_dataset_returns_zeroed_summary(order_session: AsyncSession) -> None:
    await _clean(order_session)
    service = InsightsService(order_session)

    insights = await service.get_insights()

    assert insights.summary.total_conversations == 0
    assert insights.summary.total_messages == 0
    assert insights.summary.escalation_rate == 0.0
    assert insights.summary.flag_rate == 0.0
    assert insights.top_intents == []
    assert insights.top_questions == []
    assert insights.knowledge_gaps == []
    assert insights.trend == []
