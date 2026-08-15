"""Schemas for RAG evaluation reports."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TestCase(BaseModel):
    """One evaluation test case."""

    id: str
    query: str
    is_safety_critical: bool | None = None
    expected_keywords: list[str] = Field(default_factory=list)
    expected_category: str | None = None


class ExpectedToolCall(BaseModel):
    """One ground-truth tool call for an agent test case (see ``AgentTestCase``).

    An arg value of ``"*"`` means "must be present and non-empty" rather than
    an exact match — needed for values only known at run time, e.g. a seeded
    product's UUID for ``check_inventory``.
    """

    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class AgentTestCase(BaseModel):
    """One agent-level golden-set case (backend/data/eval/agent_test_suite.json).

    A distinct shape from ``TestCase`` (the RAG-suite cases above): agent
    cases carry tool-call ground truth and may be multi-turn, since the
    ``check_inventory`` tool is only reachable via a remembered product from a
    prior turn (see ``app/agent/nodes/router.py``).
    """

    id: str
    category: str
    turns: list[str]
    expected_tool_calls: list[ExpectedToolCall] = Field(default_factory=list)
    expected_outcome: str
    locale: Literal["vi", "en"] = "vi"
    judge_eligible: bool = False


class EvaluationMetrics(BaseModel):
    """Aggregate evaluation metrics."""

    total_cases: int
    safety_detection_rate: float = Field(ge=0, le=1)
    false_positive_rate: float = Field(ge=0, le=1)
    context_precision: float = Field(default=0.0, ge=0, le=1)
    context_recall: float = Field(default=0.0, ge=0, le=1)
    faithfulness: float = Field(default=0.0, ge=0, le=1)
    answer_relevancy: float = Field(default=0.0, ge=0, le=1)
    intent_accuracy: float | None = Field(default=None, ge=0, le=1)
    intent_macro_f1: float | None = Field(default=None, ge=0, le=1)
    per_intent_f1: dict[str, float] = Field(default_factory=dict)
    # Agent-suite metrics (app/evaluation/agent_evaluator.py). All optional so
    # the RAG-suite evaluators above stay byte-for-byte unaffected.
    tool_selection_accuracy: float | None = Field(default=None, ge=0, le=1)
    argument_correctness_rate: float | None = Field(default=None, ge=0, le=1)
    task_completion_rate: float | None = Field(default=None, ge=0, le=1)
    trajectory_score: float | None = Field(default=None, ge=0, le=1)
    safety_regression_count: int = Field(default=0, ge=0)


class EvaluationReport(BaseModel):
    """Serializable report for an evaluation run."""

    suite_name: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metrics: EvaluationMetrics
    failed_case_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
