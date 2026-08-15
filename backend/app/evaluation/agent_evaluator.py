"""Agent-level evaluation: tool selection, argument correctness, task completion, trajectory.

This is a SEPARATE evaluation layer from the existing RAG suites
(``intent_evaluator.py`` / ``safety_evaluator.py``) — those measure retrieval
and generated text. This one measures whether the LangGraph agent
(``app/agent/``) chose the right TOOLS with the right ARGUMENTS and completed
the task. Do not conflate the two; this module never touches the RAG suites'
files or metrics, and the golden set lives in its own
``data/eval/agent_test_suite.json``.

Two cost tiers, mirroring how the safety suite is CI-gated today
(``scripts/run_evaluation.py``'s ``--suite safety`` hard-fails on
``safety_detection_rate < 1.0``; ``--suite agent`` mirrors that shape):

* **Deterministic** (``tool_selection_accuracy``, ``argument_correctness_rate``)
  — runs the REAL compiled agent graph (``app.agent.graph.build_agent_graph``)
  for every case, but with a stub ``BaseLLMProvider`` bound to the graph's
  ``responder`` node — the ONLY node that calls an LLM (see
  ``app/agent/nodes/router.py``'s docstring: tool selection is a deterministic
  keyword classifier, not an LLM planner). So this tier needs no LLM, no
  network, no API key, and is fast enough to be a hard pytest/CI gate.

  Scope note vs. the issue text: the issue names deepeval's
  ``ToolCorrectnessMetric`` + ``ArgumentCorrectnessMetric`` for this tier.
  Investigating both in the installed deepeval==4.0.6:
  ``ArgumentCorrectnessMetric`` turned out to be LLM-judged (it prompts a
  model for a verdict), not deterministic. And merely *constructing*
  ``ToolCorrectnessMetric()`` without an explicit ``model=`` eagerly builds a
  default ``GPTModel``, which raises ``DeepEvalError`` without
  ``OPENAI_API_KEY`` set — a real footgun for a metric meant to be a free,
  unconditional CI gate (reproduced while building this). So the deterministic
  tier below is a small, transparent Python comparison instead: no deepeval
  import, no risk of a surprise credential requirement breaking CI.

* **LLM-judge** (``task_completion_rate``, ``trajectory_score``) — runs a
  SUBSET of cases (``judge_eligible: true`` in the golden set) a second time
  with a real local Ollama provider generating the responder's reply, then
  judges with deepeval's ``TaskCompletionMetric`` (task completion) and a
  small custom per-turn trajectory judge — both backed by
  ``deepeval.models.OllamaModel``, so cost stays ~0. The trajectory score
  aggregates its per-turn 1-5 ratings with a GEOMETRIC mean (not arithmetic),
  so one badly-handled turn drags the score down instead of being averaged
  away. Automatically skipped if the local Ollama server isn't reachable, so
  CI never needs one running.
"""

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from app.agent.graph import RECURSION_LIMIT, build_agent_graph
from app.agent.state import QikiAgentState
from app.core.config import Settings, get_settings
from app.evaluation.schemas import (
    AgentTestCase,
    EvaluationMetrics,
    EvaluationReport,
    ExpectedToolCall,
)
from app.llm.base import BaseLLMProvider
from app.llm.dependencies import get_prompt_library
from app.llm.prompts.templates import PromptLibrary
from app.llm.providers.ollama_provider import OllamaProvider
from app.llm.schemas import LLMStreamChunk
from app.models.product import Product
from app.rag.context_builder import ContextBuilder
from app.rag.retriever import BaseRetriever
from app.rag.safety import SafetyChecker
from app.rag.schemas import RetrievedDocument
from app.schemas.knowledge_base import KnowledgeBaseSearchResult
from app.schemas.product import ProductCreate
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.product_service import ProductService

# The fixed emergency response's audited hotline (app/rag/safety.py). A
# safety_emergency case whose final reply is missing this, or that called any
# tool at all, is a hard-fail regardless of the overall accuracy threshold.
EMERGENCY_HOTLINE = "090 3026306"

# Sentinel for an expected tool-call arg value only known at run time (e.g. a
# seeded product's UUID for check_inventory) — "must be present and
# non-empty" rather than an exact match.
WILDCARD = "*"

_SEED_PRODUCTS: list[ProductCreate] = [
    ProductCreate(
        sku="EVAL-QIKIFLAME",
        name="Bình gas Qikiflame Xanh 12kg",
        brand="Qikiflame",
        size_kg=Decimal("12"),
        category="gas",
        unit="kg",
        price=Decimal("500000"),
        stock_quantity=20,
    ),
    ProductCreate(
        sku="EVAL-ZORVENTA",
        name="Bình gas Zorventa Cam 6kg",
        brand="Zorventa",
        size_kg=Decimal("6"),
        category="gas",
        unit="kg",
        price=Decimal("300000"),
        stock_quantity=0,
    ),
]
# Deliberately distinctive brand names (not shared with any real catalog
# brand): pg_trgm free-text search (app/repositories/product_repository.py)
# needs a query about ONE of these to return exactly one match, which is what
# lets the router's cross-turn "remembered product" resolution
# (_remembered_product_id in app/agent/nodes/router.py) fire for the
# check_inventory golden cases. Verified empirically against a local Postgres
# before picking these names — generic names like "EvalGas 12kg" / "EvalGas
# 6kg" both matched every query for either one.

_CANNED_SAFETY_DOCS: list[KnowledgeBaseSearchResult] = [
    KnowledgeBaseSearchResult(
        id=uuid4(),
        title="Bảo quản bình gas an toàn",
        content=(
            "Đặt bình gas ở nơi thoáng khí, tránh ánh nắng trực tiếp và nguồn nhiệt. "
            "Kiểm tra dây dẫn và van định kỳ mỗi 6 tháng. Không đặt bình gas nằm ngang."
        ),
        category="safety",
        similarity=0.9,
    ),
]

_CANNED_FAQ_DOCS: list[RetrievedDocument] = [
    RetrievedDocument(
        id=uuid4(),
        title="Giờ mở cửa",
        content="Cửa hàng Gas Quốc Cường mở cửa từ 7:00 đến 20:00 hàng ngày, kể cả cuối tuần.",
        category="general",
        similarity=0.85,
        source_type="hybrid",
    ),
    RetrievedDocument(
        id=uuid4(),
        title="Thông tin liên hệ",
        content="Hotline hỗ trợ: 090 3026306. Khu vực giao hàng: Bình Thạnh và Thủ Đức.",
        category="general",
        similarity=0.8,
        source_type="hybrid",
    ),
]


class _CannedKnowledgeBase(KnowledgeBaseService):
    """A KnowledgeBaseService that returns a fixed safety-doc set.

    The agent suite deliberately does not re-test retrieval QUALITY — that's
    the existing RAG suite's job (``safety_evaluator.py`` / RAGAS) — so
    ``lookup_safety_policy`` gets a small, realistic-enough canned response
    instead of needing a live embedding provider/API key. Subclasses the real
    service (rather than a duck-typed stand-in) so it satisfies
    ``build_agent_graph``'s ``kb_service: KnowledgeBaseService`` parameter
    under mypy strict without widening that signature.
    """

    def __init__(self, documents: list[KnowledgeBaseSearchResult]) -> None:
        super().__init__(repository=None)  # type: ignore[arg-type]
        self._documents = documents

    async def search_documents(
        self,
        query: str,
        *,
        top_k: int = 5,
        category: str | None = None,
        use_hybrid: bool = True,
    ) -> list[KnowledgeBaseSearchResult]:
        """Return the fixed canned document set regardless of the query."""
        del query, top_k, category, use_hybrid
        return self._documents


class _CannedRetriever(BaseRetriever):
    """A fixed general-FAQ document set (see ``_CannedKnowledgeBase`` docstring)."""

    def __init__(self, documents: list[RetrievedDocument]) -> None:
        self._documents = documents

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        category_filter: str | None = None,
    ) -> list[RetrievedDocument]:
        """Return the fixed canned document set regardless of the query."""
        del query, top_k, category_filter
        return self._documents


class _StubLLMProvider(BaseLLMProvider):
    """A no-network ``BaseLLMProvider`` for the deterministic pass.

    ``tool_calls``/``tool_results`` are fully populated by ``router()`` /
    ``tool_executor()`` before the graph ever reaches ``responder`` (the only
    node that calls an LLM), so what this "generates" is never inspected by
    the deterministic tool-selection/argument-correctness scoring — it only
    needs to exist so the graph can complete.
    """

    def __init__(self) -> None:
        super().__init__(model="eval-stub")

    @property
    def provider_name(self) -> str:
        """Provider identifier."""
        return "eval-stub"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stop_sequences: list[str] | None = None,
        **kwargs: object,
    ) -> Any:
        """Unused by the deterministic pass (responder only calls ``stream``)."""
        raise NotImplementedError("the deterministic eval pass only uses stream()")

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: object,
    ) -> Any:
        """Yield one empty chunk — no network, content is never scored."""
        yield LLMStreamChunk(
            delta="",
            accumulated_text="",
            provider=self.provider_name,
            model=self.model,
            total_tokens=0,
        )

    async def health_check(self) -> bool:
        """Always healthy — there is nothing to reach."""
        return True


class _StepScore(BaseModel):
    """Structured judge output for one trajectory step."""

    score: int
    reason: str


@dataclass
class _CaseResult:
    """Per-case scoring, aggregated by ``AgentEvaluator.evaluate``."""

    case_id: str
    category: str
    tool_selection_correct: bool
    argument_correct: bool
    actual_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    final_response: str = ""
    safety_regression: bool = False
    task_completion_score: float | None = None
    trajectory_score: float | None = None
    error: str | None = None


def _last_text(messages: list[Any]) -> str:
    """Return the last message's text content, if any."""
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
    return ""


def _tool_names_match(expected: list[ExpectedToolCall], actual: list[dict[str, Any]]) -> bool:
    """Compare tool-call NAME sequences (MVP calls at most one tool per turn)."""
    return [item.name for item in expected] == [item.get("name") for item in actual]


def _args_match(expected: list[ExpectedToolCall], actual: list[dict[str, Any]]) -> bool:
    """Compare tool-call ARGS, honoring the ``"*"`` (present + non-empty) wildcard.

    The golden set never asserts an exact id (e.g. check_inventory's
    product_id, only known once ``_seed_products`` runs) — it uses the ``"*"``
    wildcard for those instead, so this comparison needs no seeded-id lookup.
    """
    if len(expected) != len(actual):
        return False
    for expected_call, actual_call in zip(expected, actual, strict=True):
        actual_args = actual_call.get("args", {}) or {}
        for key, value in expected_call.args.items():
            if value == WILDCARD:
                if not actual_args.get(key):
                    return False
            elif actual_args.get(key) != value:
                return False
    return True


def _describe_action(state: dict[str, Any]) -> str:
    """A short, judge-readable summary of what the graph did for one turn."""
    tool_calls = state.get("tool_calls") or []
    if tool_calls:
        call = tool_calls[0]
        return f"called tool `{call.get('name')}` with args {call.get('args')}"
    if state.get("safety_flags", {}).get("is_emergency"):
        return "short-circuited to the fixed emergency response (no tool, no LLM call)"
    return "found no matching tool and routed to the general-FAQ retriever path"


def _geometric_mean(values: list[float]) -> float:
    """Geometric mean of positive values (0.0 for an empty/non-positive input).

    A manual 3-line implementation rather than ``scipy.stats.gmean`` — scipy
    isn't already a dependency of this project, and this is the only place
    that would need it.
    """
    if not values or any(value <= 0 for value in values):
        return 0.0
    return math.exp(sum(math.log(value) for value in values) / len(values))


class AgentEvaluator:
    """Evaluate the LangGraph agent's tool selection, argument correctness, and task success."""

    def __init__(
        self,
        *,
        product_service: ProductService,
        kb_service: KnowledgeBaseService | None = None,
        retriever: BaseRetriever | None = None,
        prompt_library: PromptLibrary | None = None,
        safety_checker: SafetyChecker | None = None,
        context_builder: ContextBuilder | None = None,
        settings: Settings | None = None,
        enable_judge: bool | None = None,
    ) -> None:
        self.product_service = product_service
        self.kb_service = kb_service or _CannedKnowledgeBase(_CANNED_SAFETY_DOCS)
        self.retriever = retriever or _CannedRetriever(_CANNED_FAQ_DOCS)
        self.prompt_library = prompt_library or get_prompt_library()
        self.safety_checker = safety_checker or SafetyChecker()
        self.context_builder = context_builder or ContextBuilder()
        self.settings = settings or get_settings()
        # None (default) => auto-detect via an Ollama health check; True/False
        # forces the LLM-judge subset on/off regardless of reachability
        # (tests use this to avoid a real network call).
        self._enable_judge_override = enable_judge

    async def evaluate(self, cases: list[AgentTestCase]) -> EvaluationReport:
        """Run every case and return an aggregate report."""
        judge_enabled = await self._judge_available()
        seeded_ids = await self._seed_products()
        try:
            results = [await self._run_case(case, judge_enabled) for case in cases]
        finally:
            await self._cleanup_products()

        return self._build_report(cases, results, judge_enabled, seeded_ids)

    # -- setup / teardown -----------------------------------------------

    async def _seed_products(self) -> dict[str, str]:
        """Create this suite's fixture products; return sku -> id."""
        seeded: dict[str, str] = {}
        for payload in _SEED_PRODUCTS:
            product = await self.product_service.repository.create(payload)
            seeded[payload.sku] = str(product.id)
        return seeded

    async def _cleanup_products(self) -> None:
        """Best-effort hard delete of this evaluator's own seed products.

        Not exposed on ``ProductRepository`` (production code only ever
        soft-deletes) because the real risk is a seeded product leaking into a
        live, purchasable catalog if this suite is ever pointed at a real
        database — not just row-count tidiness.
        """
        session = self.product_service.repository.session
        skus = [payload.sku for payload in _SEED_PRODUCTS]
        try:
            await session.execute(delete(Product).where(Product.sku.in_(skus)))
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()

    async def _judge_available(self) -> bool:
        """Whether the LLM-judge subset should run (auto-detected or forced)."""
        if self._enable_judge_override is not None:
            return self._enable_judge_override
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.settings.OLLAMA_BASE_URL}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    # -- per-case execution -----------------------------------------------

    async def _run_graph_once(
        self,
        case: AgentTestCase,
        *,
        llm_provider: BaseLLMProvider,
    ) -> list[dict[str, Any]]:
        """Run every turn of ``case`` on one fresh thread; return the state after each turn."""
        checkpointer: MemorySaver = MemorySaver()
        graph = build_agent_graph(
            safety_checker=self.safety_checker,
            retriever=self.retriever,
            product_service=self.product_service,
            kb_service=self.kb_service,
            llm_provider=llm_provider,
            prompt_library=self.prompt_library,
            context_builder=self.context_builder,
            checkpointer=checkpointer,
        )
        thread_id = f"eval-{case.id}-{uuid4().hex[:8]}"
        config: RunnableConfig = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": RECURSION_LIMIT,
        }
        turn_states: list[dict[str, Any]] = []
        for turn_text in case.turns:
            input_state: QikiAgentState = {
                "messages": [HumanMessage(content=turn_text)],
                "session_id": thread_id,
                "user_id": None,
                "locale": case.locale,
            }
            state = await graph.ainvoke(input_state, config=config)
            turn_states.append(state)
        return turn_states

    async def _run_case(self, case: AgentTestCase, judge_enabled: bool) -> _CaseResult:
        """Score one case: always deterministic, plus the judge subset when eligible."""
        try:
            turn_states = await self._run_graph_once(case, llm_provider=_StubLLMProvider())
        except Exception as exc:  # noqa: BLE001 - one bad case must not sink the whole suite
            return _CaseResult(
                case_id=case.id,
                category=case.category,
                tool_selection_correct=False,
                argument_correct=False,
                safety_regression=case.category == "safety_emergency",
                error=f"graph run failed: {exc}",
            )

        final_state = turn_states[-1]
        actual_tool_calls: list[dict[str, Any]] = final_state.get("tool_calls", []) or []
        tool_selection_correct = _tool_names_match(case.expected_tool_calls, actual_tool_calls)
        argument_correct = tool_selection_correct and _args_match(
            case.expected_tool_calls, actual_tool_calls
        )
        final_text = _last_text(final_state.get("messages", []))
        safety_regression = case.category == "safety_emergency" and (
            bool(actual_tool_calls) or EMERGENCY_HOTLINE not in final_text
        )

        result = _CaseResult(
            case_id=case.id,
            category=case.category,
            tool_selection_correct=tool_selection_correct,
            argument_correct=argument_correct,
            actual_tool_calls=actual_tool_calls,
            final_response=final_text,
            safety_regression=safety_regression,
        )

        if judge_enabled and case.judge_eligible:
            try:
                await self._score_with_judge(case, result)
            except Exception as exc:  # noqa: BLE001 - the judge subset is best-effort
                result.error = f"judge scoring failed: {exc}"

        return result

    async def _score_with_judge(self, case: AgentTestCase, result: _CaseResult) -> None:
        """Populate ``task_completion_score``/``trajectory_score`` via the local Ollama judge."""
        from deepeval.metrics import TaskCompletionMetric
        from deepeval.models import OllamaModel
        from deepeval.test_case import LLMTestCase, ToolCall

        judge_llm = OllamaProvider(
            base_url=self.settings.OLLAMA_BASE_URL,
            model=self.settings.OLLAMA_MODEL,
            timeout=self.settings.OLLAMA_TIMEOUT,
        )
        judge_model = OllamaModel(
            base_url=self.settings.OLLAMA_BASE_URL, model=self.settings.OLLAMA_MODEL
        )

        turn_states = await self._run_graph_once(case, llm_provider=judge_llm)
        final_state = turn_states[-1]
        final_text = _last_text(final_state.get("messages", []))
        actual_tool_calls: list[dict[str, Any]] = final_state.get("tool_calls", []) or []
        result.final_response = final_text  # the stub pass's text is empty; this one is real

        test_case = LLMTestCase(
            input=" | ".join(case.turns),
            actual_output=final_text,
            tools_called=[
                ToolCall(name=call.get("name", ""), input_parameters=call.get("args", {}))
                for call in actual_tool_calls
            ],
        )
        metric = TaskCompletionMetric(model=judge_model, task=case.expected_outcome, threshold=0.5)
        await metric.a_measure(test_case, _show_indicator=False)
        result.task_completion_score = metric.score

        step_scores: list[int] = []
        history = ""
        for turn_text, state in zip(case.turns, turn_states, strict=True):
            action = _describe_action(state)
            step_scores.append(
                await self._score_trajectory_step(judge_model, history, turn_text, action)
            )
            history += f"\nUser: {turn_text}\nAssistant action: {action}\n"
        result.trajectory_score = _geometric_mean([score / 5.0 for score in step_scores])

    async def _score_trajectory_step(
        self,
        judge_model: Any,
        history: str,
        turn_text: str,
        action: str,
    ) -> int:
        """Ask the local judge to rate ONE (state, action) step from 1 to 5."""
        prompt = (
            "You are grading ONE step of a Vietnamese gas/water delivery chatbot's "
            "decision trajectory.\n\n"
            f"Conversation so far:{history or ' (start of conversation)'}\n\n"
            f"Customer's message at this step: {turn_text}\n"
            f"The assistant's action at this step: {action}\n\n"
            "Rate ONLY this step's appropriateness from 1 (completely wrong) to "
            "5 (ideal). Respond using the requested JSON schema."
        )
        output, _cost = await judge_model.a_generate(prompt, schema=_StepScore)
        if isinstance(output, _StepScore):
            return max(1, min(5, output.score))
        return 3  # neutral fallback if the model didn't return structured output

    # -- report assembly ----------------------------------------------------

    def _build_report(
        self,
        cases: list[AgentTestCase],
        results: list[_CaseResult],
        judge_enabled: bool,
        seeded_ids: dict[str, str],
    ) -> EvaluationReport:
        total = len(results)
        tool_selection_accuracy = (
            sum(1 for r in results if r.tool_selection_correct) / total if total else 0.0
        )
        argument_correctness_rate = (
            sum(1 for r in results if r.argument_correct) / total if total else 0.0
        )
        safety_regressions = [r.case_id for r in results if r.safety_regression]

        judged_completion = [r for r in results if r.task_completion_score is not None]
        task_completion_rate = (
            sum(r.task_completion_score for r in judged_completion) / len(judged_completion)  # type: ignore[misc]
            if judged_completion
            else None
        )
        judged_trajectory = [r for r in results if r.trajectory_score is not None]
        trajectory_score = (
            sum(r.trajectory_score for r in judged_trajectory) / len(judged_trajectory)  # type: ignore[misc]
            if judged_trajectory
            else None
        )

        failed_case_ids = sorted(
            {r.case_id for r in results if not r.tool_selection_correct or not r.argument_correct}
            | set(safety_regressions)
        )
        errors = [f"{r.case_id}: {r.error}" for r in results if r.error]

        return EvaluationReport(
            suite_name="agent",
            metrics=EvaluationMetrics(
                total_cases=total,
                # Not this suite's concern (see module docstring) — filled in
                # only because EvaluationMetrics requires them, same as the
                # "rag" suite branch in scripts/run_evaluation.py.
                safety_detection_rate=1.0,
                false_positive_rate=0.0,
                tool_selection_accuracy=tool_selection_accuracy,
                argument_correctness_rate=argument_correctness_rate,
                task_completion_rate=task_completion_rate,
                trajectory_score=trajectory_score,
                safety_regression_count=len(safety_regressions),
            ),
            failed_case_ids=failed_case_ids,
            notes=[
                f"judge_enabled={judge_enabled}",
                f"judge_eligible_cases={sum(1 for c in cases if c.judge_eligible)}",
                f"judged_for_task_completion={len(judged_completion)}",
                f"judged_for_trajectory={len(judged_trajectory)}",
                f"safety_regressions={safety_regressions}",
                f"seeded_product_ids={seeded_ids}",
                *([f"errors={errors}"] if errors else []),
            ],
        )
