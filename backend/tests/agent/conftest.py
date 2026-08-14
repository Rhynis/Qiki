"""Shared fixtures for backend/tests/agent/."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.rag.context_builder import ContextBuilder
from app.rag.safety import SafetyChecker
from tests.agent._fakes import FakeLLMProvider


@pytest.fixture
def fake_llm_provider() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture
def fake_prompt_library() -> MagicMock:
    library = MagicMock()
    template = MagicMock()
    template.render = MagicMock(return_value="system prompt")
    library.get = MagicMock(return_value=template)
    return library


@pytest.fixture
def context_builder() -> ContextBuilder:
    return ContextBuilder()


@pytest.fixture
def safety_checker() -> SafetyChecker:
    return SafetyChecker()


@pytest.fixture
def checkpointer() -> MemorySaver:
    return MemorySaver()


@pytest.fixture
def fake_retriever() -> MagicMock:
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(return_value=[])
    return retriever
