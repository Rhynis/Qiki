"""Schemas for conversation mining insights."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class IntentCount(BaseModel):
    """A single intent bucket with its message count."""

    intent: str
    count: int


class QuestionTheme(BaseModel):
    """A frequently asked customer question grouped by normalized text."""

    question: str
    count: int


class TrendPoint(BaseModel):
    """Per-day counts for the flag/escalation trend chart."""

    date: str
    conversations: int
    flagged: int
    escalated: int


class KnowledgeGapQuestion(BaseModel):
    """A customer question the bot likely could not answer well."""

    conversation_id: UUID
    message_id: UUID
    question: str
    intent: str | None = None
    intent_confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str
    created_at: datetime


class InsightsSummary(BaseModel):
    """Top-line counts for the mining period."""

    total_conversations: int
    total_messages: int
    user_messages: int
    assistant_messages: int
    escalated_conversations: int
    flagged_messages: int
    low_confidence_messages: int
    negative_feedback_messages: int
    unanswered_messages: int
    escalation_rate: float = Field(ge=0, le=1)
    flag_rate: float = Field(ge=0, le=1)


class ConversationInsights(BaseModel):
    """Aggregated conversation mining insights over a period."""

    period_start: datetime
    period_end: datetime
    summary: InsightsSummary
    top_intents: list[IntentCount] = Field(default_factory=list)
    top_questions: list[QuestionTheme] = Field(default_factory=list)
    trend: list[TrendPoint] = Field(default_factory=list)
    knowledge_gaps: list[KnowledgeGapQuestion] = Field(default_factory=list)
