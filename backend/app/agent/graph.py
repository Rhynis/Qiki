"""Compile the Qiki agent graph.

    START -> intake_guardrail -> [turn-limit? / emergency? / normal]
        turn_limit -> END
        safety_emergency -> END           (never calls the LLM)
        router -> [tool_calls queued? ]
            tool_executor -> verifier -> responder -> END
            retriever     -> verifier -> responder -> END

Every node beyond intake_guardrail/safety_emergency/turn_limit/router needs
extra, request-scoped dependencies (a retriever, tools, the LLM provider, ...)
that a bare LangGraph node signature (``state -> dict``) can't receive, so
each is bound via ``functools.partial`` at graph-build time — the node
functions themselves stay plain, synchronously-testable ``async def
node(state, **deps)`` callables (see backend/tests/agent/).
"""

from functools import partial

from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.intake_guardrail import intake_guardrail
from app.agent.nodes.responder import responder
from app.agent.nodes.retriever import retriever_node
from app.agent.nodes.router import route_after_router, router
from app.agent.nodes.safety_emergency import safety_emergency
from app.agent.nodes.tool_executor import tool_executor
from app.agent.nodes.turn_limit import turn_limit
from app.agent.nodes.verifier import verifier
from app.agent.state import MAX_AGENT_TURNS, QikiAgentState
from app.agent.tools.check_inventory import build_check_inventory_tool
from app.agent.tools.confirm_gate import ToolConfirmGate
from app.agent.tools.lookup_safety_policy import build_lookup_safety_policy_tool
from app.agent.tools.recommend_products import build_recommend_products_tool
from app.agent.tools.search_products import build_search_products_tool
from app.llm.base import BaseLLMProvider
from app.llm.prompts.templates import PromptLibrary
from app.models.user import User
from app.rag.context_builder import ContextBuilder
from app.rag.retriever import BaseRetriever
from app.rag.safety import SafetyChecker
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.product_service import ProductService

# LangGraph's own per-invocation superstep budget — an independent safety valve
# from MAX_AGENT_TURNS (which caps total turns *across* a thread's lifetime;
# this caps supersteps *within* one astream call, e.g. a future re-planning
# loop that never converges).
RECURSION_LIMIT = 25


def build_tools(
    product_service: ProductService, kb_service: KnowledgeBaseService
) -> dict[str, BaseTool]:
    """Build the read-only tools, bound to request-scoped services."""
    tools = [
        build_search_products_tool(product_service),
        build_check_inventory_tool(product_service),
        build_lookup_safety_policy_tool(kb_service),
        build_recommend_products_tool(product_service),
    ]
    return {tool.name: tool for tool in tools}


def _route_after_intake(state: QikiAgentState) -> str:
    """Both short-circuits skip router/retriever/tool_executor entirely."""
    if state.get("turn_count", 0) > MAX_AGENT_TURNS:
        return "turn_limit"
    if state.get("safety_flags", {}).get("is_emergency"):
        return "safety_emergency"
    return "router"


def build_agent_graph(
    *,
    safety_checker: SafetyChecker,
    retriever: BaseRetriever,
    product_service: ProductService,
    kb_service: KnowledgeBaseService,
    llm_provider: BaseLLMProvider,
    prompt_library: PromptLibrary,
    context_builder: ContextBuilder,
    checkpointer: BaseCheckpointSaver[str],
    current_user: User | None = None,
    confirm_gate: ToolConfirmGate | None = None,
    audit_repository: AdminAuditRepository | None = None,
) -> CompiledStateGraph[QikiAgentState, None, QikiAgentState, QikiAgentState]:
    """Wire the nodes/edges above into a compiled, checkpointed graph.

    ``current_user``/``confirm_gate``/``audit_repository`` (issue #348) are
    threaded into ``tool_executor`` the same way ``product_service``/
    ``kb_service`` are threaded into the tools themselves: request-scoped
    dependencies bound via ``functools.partial`` at build time, never stored
    in the checkpointed ``QikiAgentState``. All 3 default to ``None`` so
    existing callers (and #346's tests) that only need the public read
    tools keep working unchanged; a write tool call without them is refused,
    never silently allowed (see ``tool_executor._authorize``).
    """
    tools = build_tools(product_service, kb_service)

    graph = StateGraph(QikiAgentState)
    graph.add_node("intake_guardrail", partial(intake_guardrail, safety_checker=safety_checker))
    graph.add_node("safety_emergency", partial(safety_emergency, safety_checker=safety_checker))
    graph.add_node("turn_limit", turn_limit)
    graph.add_node("router", router)
    graph.add_node(
        "tool_executor",
        partial(
            tool_executor,
            tools=tools,
            current_user=current_user,
            confirm_gate=confirm_gate,
            audit_repository=audit_repository,
        ),
    )
    graph.add_node("retriever", partial(retriever_node, retriever=retriever))
    graph.add_node("verifier", verifier)
    graph.add_node(
        "responder",
        partial(
            responder,
            llm_provider=llm_provider,
            prompt_library=prompt_library,
            context_builder=context_builder,
        ),
    )

    graph.add_edge(START, "intake_guardrail")
    graph.add_conditional_edges(
        "intake_guardrail",
        _route_after_intake,
        {"turn_limit": "turn_limit", "safety_emergency": "safety_emergency", "router": "router"},
    )
    graph.add_edge("turn_limit", END)
    graph.add_edge("safety_emergency", END)
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {"tool_executor": "tool_executor", "retriever": "retriever"},
    )
    graph.add_edge("tool_executor", "verifier")
    graph.add_edge("retriever", "verifier")
    graph.add_edge("verifier", "responder")
    graph.add_edge("responder", END)

    return graph.compile(checkpointer=checkpointer)
