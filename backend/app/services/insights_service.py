"""Conversation mining service.

Read-only SQL aggregation over stored conversations and messages that turns chat
history into staff-facing insights: intent distribution, top questions, a
flag/escalation trend, and likely knowledge-base gaps (questions the bot could not
answer well). No schema change, no ML pipeline - just grouped counts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import ColumnElement, case, false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.insights import (
    ConversationInsights,
    InsightsSummary,
    IntentCount,
    KnowledgeGapQuestion,
    QuestionTheme,
    TrendPoint,
)

# Confidence below this is treated as a low-confidence turn (matches the auto-flag
# threshold used when messages are persisted).
LOW_CONFIDENCE_THRESHOLD = Decimal("0.6")

# Substrings that mark a Vietnamese "I cannot answer" fallback response. Combined
# with the empty-retrieval signal to detect likely knowledge-base gaps.
REFUSAL_MARKERS_VI = (
    "chưa có thông tin",
    "không có thông tin",
    "không tìm thấy",
    "chưa có đủ thông tin",
    "xin lỗi, tôi chưa",
)

DEFAULT_PERIOD_DAYS = 30
MAX_PERIOD_DAYS = 365
DEFAULT_TOP_LIMIT = 10
DEFAULT_GAP_LIMIT = 20


class InsightsService:
    """Compute conversation mining insights via read-only SQL aggregation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_insights(
        self,
        *,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        top_limit: int = DEFAULT_TOP_LIMIT,
        gap_limit: int = DEFAULT_GAP_LIMIT,
    ) -> ConversationInsights:
        """Aggregate insights for the messages created within the period."""
        end = period_end or datetime.now(UTC)
        start = period_start or (end - timedelta(days=DEFAULT_PERIOD_DAYS))
        if start > end:
            start, end = end, start

        summary = await self._summary(start, end)
        top_intents = await self._top_intents(start, end, top_limit)
        top_questions = await self._top_questions(start, end, top_limit)
        trend = await self._trend(start, end)
        gaps = await self._knowledge_gaps(start, end, gap_limit)

        return ConversationInsights(
            period_start=start,
            period_end=end,
            summary=summary,
            top_intents=top_intents,
            top_questions=top_questions,
            trend=trend,
            knowledge_gaps=gaps,
        )

    async def _summary(self, start: datetime, end: datetime) -> InsightsSummary:
        message_window = (Message.created_at >= start, Message.created_at <= end)
        empty_context = self._empty_context_clause()

        message_stats = select(
            func.count().label("total_messages"),
            func.count(case((Message.role == "user", 1))).label("user_messages"),
            func.count(case((Message.role == "assistant", 1))).label("assistant_messages"),
            func.count(case((Message.flagged_for_review.is_(True), 1))).label("flagged"),
            func.count(
                case((self._low_confidence_clause(), 1)),
            ).label("low_confidence"),
            func.count(case((Message.feedback_score == -1, 1))).label("negative_feedback"),
            func.count(
                case(
                    ((Message.role == "assistant") & (empty_context | self._refusal_clause()), 1),
                ),
            ).label("unanswered"),
        ).where(*message_window)
        message_row = (await self.session.execute(message_stats)).one()

        conversation_window = (
            Conversation.created_at >= start,
            Conversation.created_at <= end,
        )
        conversation_stats = select(
            func.count().label("total_conversations"),
            func.count(case((Conversation.status == "escalated", 1))).label("escalated"),
        ).where(*conversation_window)
        conversation_row = (await self.session.execute(conversation_stats)).one()

        total_conversations = int(conversation_row.total_conversations or 0)
        total_messages = int(message_row.total_messages or 0)
        escalated = int(conversation_row.escalated or 0)
        flagged = int(message_row.flagged or 0)

        return InsightsSummary(
            total_conversations=total_conversations,
            total_messages=total_messages,
            user_messages=int(message_row.user_messages or 0),
            assistant_messages=int(message_row.assistant_messages or 0),
            escalated_conversations=escalated,
            flagged_messages=flagged,
            low_confidence_messages=int(message_row.low_confidence or 0),
            negative_feedback_messages=int(message_row.negative_feedback or 0),
            unanswered_messages=int(message_row.unanswered or 0),
            escalation_rate=self._rate(escalated, total_conversations),
            flag_rate=self._rate(flagged, total_messages),
        )

    async def _top_intents(self, start: datetime, end: datetime, limit: int) -> list[IntentCount]:
        statement = (
            select(Message.intent, func.count().label("count"))
            .where(
                Message.created_at >= start,
                Message.created_at <= end,
                Message.intent.is_not(None),
            )
            .group_by(Message.intent)
            .order_by(func.count().desc(), Message.intent.asc())
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()
        return [IntentCount(intent=str(intent), count=int(count)) for intent, count in rows]

    async def _top_questions(
        self, start: datetime, end: datetime, limit: int
    ) -> list[QuestionTheme]:
        # Group customer questions by a normalized (lowercased, trimmed) form so
        # near-duplicate phrasings collapse into a single theme.
        normalized = func.lower(func.trim(Message.content))
        statement = (
            select(
                func.min(Message.content).label("sample"),
                func.count().label("count"),
            )
            .where(
                Message.created_at >= start,
                Message.created_at <= end,
                Message.role == "user",
                func.length(func.trim(Message.content)) > 0,
            )
            .group_by(normalized)
            .order_by(func.count().desc(), func.min(Message.content).asc())
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()
        return [QuestionTheme(question=str(sample), count=int(count)) for sample, count in rows]

    async def _trend(self, start: datetime, end: datetime) -> list[TrendPoint]:
        conversations = (
            select(
                func.date(Conversation.created_at).label("day"),
                func.count().label("conversations"),
                func.count(case((Conversation.status == "escalated", 1))).label("escalated"),
            )
            .where(Conversation.created_at >= start, Conversation.created_at <= end)
            .group_by(func.date(Conversation.created_at))
        )
        conv_rows = (await self.session.execute(conversations)).all()

        flags = (
            select(
                func.date(Message.created_at).label("day"),
                func.count(case((Message.flagged_for_review.is_(True), 1))).label("flagged"),
            )
            .where(Message.created_at >= start, Message.created_at <= end)
            .group_by(func.date(Message.created_at))
        )
        flag_rows = (await self.session.execute(flags)).all()
        flags_by_day = {str(day): int(flagged or 0) for day, flagged in flag_rows}

        points: list[TrendPoint] = []
        for day, conversations_count, escalated in sorted(conv_rows, key=lambda row: str(row.day)):
            day_key = str(day)
            points.append(
                TrendPoint(
                    date=day_key,
                    conversations=int(conversations_count or 0),
                    flagged=flags_by_day.get(day_key, 0),
                    escalated=int(escalated or 0),
                )
            )
        return points

    async def _knowledge_gaps(
        self, start: datetime, end: datetime, limit: int
    ) -> list[KnowledgeGapQuestion]:
        # Alias for the user message that immediately precedes an assistant turn in
        # the same conversation, so we can surface the *question* the bot failed on.
        prior_user = Message.__table__.alias("prior_user")
        empty_context = self._empty_context_clause()

        preceding_question = (
            select(prior_user.c.content)
            .where(
                prior_user.c.conversation_id == Message.conversation_id,
                prior_user.c.role == "user",
                prior_user.c.created_at < Message.created_at,
            )
            .order_by(prior_user.c.created_at.desc())
            .limit(1)
            .scalar_subquery()
        )

        gap_reason = case(
            (empty_context, "no_context"),
            else_="refusal",
        )

        statement = (
            select(
                Message.id.label("message_id"),
                Message.conversation_id.label("conversation_id"),
                Message.intent.label("intent"),
                Message.intent_confidence.label("intent_confidence"),
                Message.created_at.label("created_at"),
                preceding_question.label("question"),
                gap_reason.label("reason"),
            )
            .where(
                Message.created_at >= start,
                Message.created_at <= end,
                Message.role == "assistant",
                empty_context | self._refusal_clause(),
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()

        gaps: list[KnowledgeGapQuestion] = []
        for row in rows:
            question = (row.question or "").strip()
            if not question:
                continue
            confidence = float(row.intent_confidence) if row.intent_confidence is not None else None
            gaps.append(
                KnowledgeGapQuestion(
                    conversation_id=row.conversation_id,
                    message_id=row.message_id,
                    question=question,
                    intent=row.intent,
                    intent_confidence=confidence,
                    reason=str(row.reason),
                    created_at=row.created_at,
                )
            )
        return gaps

    @staticmethod
    def _low_confidence_clause() -> ColumnElement[bool]:
        return (Message.intent_confidence.is_not(None)) & (
            Message.intent_confidence < LOW_CONFIDENCE_THRESHOLD
        )

    @staticmethod
    def _empty_context_clause() -> ColumnElement[bool]:
        # A JSONB retrieved_documents that is NULL or an empty array means the bot
        # answered with no supporting context.
        return (Message.retrieved_documents.is_(None)) | (
            func.jsonb_array_length(Message.retrieved_documents) == 0
        )

    @staticmethod
    def _refusal_clause() -> ColumnElement[bool]:
        clause: ColumnElement[bool] | None = None
        lowered = func.lower(Message.content)
        for marker in REFUSAL_MARKERS_VI:
            condition = lowered.like(f"%{marker}%")
            clause = condition if clause is None else (clause | condition)
        return clause if clause is not None else false()

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator, 4)
