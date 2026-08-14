"""Integration tests for the compiled graph (agent/graph.py).

Covers the issue's explicit acceptance bullets: the FAQ/product path routes
correctly, the safety path never calls the LLM, and the graph resumes from a
checkpoint. Uses a real Postgres-backed ProductService (product_session) so
search_products/check_inventory exercise the real repository, and an
in-memory MemorySaver checkpointer — proving the graph's OWN resume mechanics
work correctly is independent of which checkpointer backend implements the
save/load contract (AsyncPostgresSaver's specific wiring is exercised
separately, live, against real Postgres — see PR description).
"""

from decimal import Decimal

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import RECURSION_LIMIT, build_agent_graph
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.product_service import ProductService
from tests.agent._fakes import FakeLLMProvider

pytestmark = pytest.mark.asyncio


async def _seed_gas_product(session: AsyncSession) -> None:
    await ProductRepository(session).create(
        ProductCreate(
            sku="ELF-12KG-DO",
            name="Bình gas Elf 12kg (đỏ)",
            brand="Elf Gas",
            size_kg=Decimal("12"),
            category="gas",
            unit="kg",
            price=Decimal("710000"),
            stock_quantity=50,
        )
    )


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}


class TestGraphRouting:
    async def test_product_question_routes_through_tool_executor(
        self,
        product_session: AsyncSession,
        safety_checker,
        fake_retriever,
        fake_llm_provider: FakeLLMProvider,
        fake_prompt_library,
        context_builder,
        checkpointer: MemorySaver,
    ) -> None:
        await _seed_gas_product(product_session)
        graph = build_agent_graph(
            safety_checker=safety_checker,
            retriever=fake_retriever,
            product_service=ProductService(ProductRepository(product_session)),
            kb_service=KnowledgeBaseService(repository=None),  # type: ignore[arg-type]
            llm_provider=fake_llm_provider,
            prompt_library=fake_prompt_library,
            context_builder=context_builder,
            checkpointer=checkpointer,
        )

        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content="gas Elf 12kg giá bao nhiêu")],
                "session_id": "t1",
                "locale": "vi",
            },
            config=_config("t1"),
        )

        assert result["tool_calls"][0]["name"] == "search_products"
        assert result["tool_results"][0]["ok"] is True
        assert result["tool_results"][0]["result"]["products"][0]["sku"] == "ELF-12KG-DO"
        fake_retriever.retrieve.assert_not_called()

    async def test_general_faq_routes_through_retriever(
        self,
        safety_checker,
        fake_retriever,
        fake_llm_provider: FakeLLMProvider,
        fake_prompt_library,
        context_builder,
        checkpointer: MemorySaver,
        product_session: AsyncSession,
    ) -> None:
        graph = build_agent_graph(
            safety_checker=safety_checker,
            retriever=fake_retriever,
            product_service=ProductService(ProductRepository(product_session)),
            kb_service=KnowledgeBaseService(repository=None),  # type: ignore[arg-type]
            llm_provider=fake_llm_provider,
            prompt_library=fake_prompt_library,
            context_builder=context_builder,
            checkpointer=checkpointer,
        )

        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content="cửa hàng mở cửa mấy giờ")],
                "session_id": "t2",
                "locale": "vi",
            },
            config=_config("t2"),
        )

        assert result["tool_calls"] == []
        fake_retriever.retrieve.assert_awaited_once()
        assert result["messages"][-1].content == fake_llm_provider.reply


class TestGraphSafety:
    async def test_emergency_query_never_calls_the_llm(
        self,
        safety_checker,
        fake_retriever,
        fake_llm_provider: FakeLLMProvider,
        fake_prompt_library,
        context_builder,
        checkpointer: MemorySaver,
        product_session: AsyncSession,
    ) -> None:
        graph = build_agent_graph(
            safety_checker=safety_checker,
            retriever=fake_retriever,
            product_service=ProductService(ProductRepository(product_session)),
            kb_service=KnowledgeBaseService(repository=None),  # type: ignore[arg-type]
            llm_provider=fake_llm_provider,
            prompt_library=fake_prompt_library,
            context_builder=context_builder,
            checkpointer=checkpointer,
        )

        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content="nhà tôi đang rò gas, cứu tôi với")],
                "session_id": "t3",
                "locale": "vi",
            },
            config=_config("t3"),
        )

        fake_llm_provider.generate.assert_not_called()
        assert fake_llm_provider.stream_calls == []
        assert "090 3026306" in result["messages"][-1].content
        fake_retriever.retrieve.assert_not_called()


class TestGraphCheckpointResume:
    async def test_second_turn_on_the_same_thread_sees_the_first_turns_history(
        self,
        safety_checker,
        fake_retriever,
        fake_llm_provider: FakeLLMProvider,
        fake_prompt_library,
        context_builder,
        checkpointer: MemorySaver,
        product_session: AsyncSession,
    ) -> None:
        graph = build_agent_graph(
            safety_checker=safety_checker,
            retriever=fake_retriever,
            product_service=ProductService(ProductRepository(product_session)),
            kb_service=KnowledgeBaseService(repository=None),  # type: ignore[arg-type]
            llm_provider=fake_llm_provider,
            prompt_library=fake_prompt_library,
            context_builder=context_builder,
            checkpointer=checkpointer,
        )
        config = _config("resume-thread")

        await graph.ainvoke(
            {
                "messages": [HumanMessage(content="xin chào")],
                "session_id": "resume-thread",
                "locale": "vi",
            },
            config=config,
        )
        second = await graph.ainvoke(
            {"messages": [HumanMessage(content="câu hỏi thứ hai")]},
            config=config,
        )

        # The checkpoint carried the first turn's messages forward — a fresh
        # thread would only ever have 2 messages (this turn's human + AI reply).
        assert len(second["messages"]) == 4
        assert second["turn_count"] == 2

    async def test_get_state_reflects_the_checkpointed_thread(
        self,
        safety_checker,
        fake_retriever,
        fake_llm_provider: FakeLLMProvider,
        fake_prompt_library,
        context_builder,
        checkpointer: MemorySaver,
        product_session: AsyncSession,
    ) -> None:
        graph = build_agent_graph(
            safety_checker=safety_checker,
            retriever=fake_retriever,
            product_service=ProductService(ProductRepository(product_session)),
            kb_service=KnowledgeBaseService(repository=None),  # type: ignore[arg-type]
            llm_provider=fake_llm_provider,
            prompt_library=fake_prompt_library,
            context_builder=context_builder,
            checkpointer=checkpointer,
        )
        config = _config("state-thread")

        await graph.ainvoke(
            {
                "messages": [HumanMessage(content="xin chào")],
                "session_id": "state-thread",
                "locale": "vi",
            },
            config=config,
        )

        snapshot = await graph.aget_state(config)

        assert snapshot.values["turn_count"] == 1
        assert snapshot.values["messages"][-1].content == fake_llm_provider.reply
