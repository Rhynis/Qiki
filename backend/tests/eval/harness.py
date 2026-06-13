"""Multi-turn conversation eval harness.

Drives the real :class:`ConversationService` through scripted dialogues using the
deterministic fakes from the existing unit-test suite, and records each turn as a
DeepEval ``Turn``. Scenarios assert hard invariants (the must-pass core) and can
optionally be scored by an LLM judge when an API key is present.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from app.intent.categories import IntentCategory
from app.models.user import User
from app.schemas.conversation import SendMessageRequest, SendMessageResponse
from app.services.conversation_service import ConversationService

# Reuse the deterministic fakes + builders from the unit-test suite so eval
# scenarios stay reproducible without any live model calls.
from tests.services.test_conversation_service import (
    FakeLLMProvider,
    complete_order_payload,
    make_service,
)

if TYPE_CHECKING:
    from deepeval.test_case import ConversationalTestCase

CHATBOT_ROLE = "Qiki, trợ lý đặt gas và nước của Gas Quốc Cường"
# Fixed business-open VN time so order-confirmation copy is deterministic.
BUSINESS_OPEN_VN = datetime(2026, 6, 8, 9, 0, tzinfo=timezone(timedelta(hours=7)))


@dataclass
class ConversationDriver:
    """Send messages to a ConversationService and record the dialogue turns."""

    service: ConversationService
    conversation_id: uuid.UUID
    turns: list[tuple[str, str]] = field(default_factory=list)

    async def turn(self, content: str, user: User | None = None) -> SendMessageResponse:
        response = await self.service.send_message(
            self.conversation_id, SendMessageRequest(content=content), user=user
        )
        reply = response.assistant_message.content if response.assistant_message else ""
        self.turns.append((content, reply))
        return response

    def to_test_case(
        self, *, scenario: str, expected_outcome: str, name: str
    ) -> ConversationalTestCase:
        """Build a DeepEval ConversationalTestCase from the recorded dialogue.

        DeepEval is imported lazily so the scripted invariant tests never depend
        on it at import time.
        """
        from deepeval.test_case import ConversationalTestCase, Turn

        deepeval_turns: list[Turn] = []
        for user_text, assistant_text in self.turns:
            deepeval_turns.append(Turn(role="user", content=user_text))
            if assistant_text:
                deepeval_turns.append(Turn(role="assistant", content=assistant_text))
        return ConversationalTestCase(
            turns=deepeval_turns,
            scenario=scenario,
            expected_outcome=expected_outcome,
            chatbot_role=CHATBOT_ROLE,
            name=name,
        )


async def start_driver(
    service: ConversationService, session_id: str = "eval"
) -> ConversationDriver:
    conversation = await service.start_conversation(user=None, session_id=session_id)
    return ConversationDriver(service=service, conversation_id=conversation.id)


async def run_full_gas_order(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ConversationDriver, object]:
    """End-to-end: order a specific gas (Petrolimex 12kg) -> summary -> confirm -> created.

    Returns the driver (with recorded turns) and the fake order service so callers
    can assert order creation.
    """
    monkeypatch.setattr(ConversationService, "_now_vn", staticmethod(lambda: BUSINESS_OPEN_VN))
    # A single complete (unconfirmed) extraction is returned for every LLM call;
    # the explicit affirmation on turn 2 is what confirms the order.
    service, _conversations, _messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([complete_order_payload(confirmed=False)]),
    )
    driver = await start_driver(service)

    await driver.turn(
        "Đặt 1 bình Petrolimex 12kg, tên Nguyen Van A, sđt 0903026306, "
        "giao 15 đường số 5, Khu phố 36, Phường Hiệp Bình, thanh toán COD"
    )
    await driver.turn("Đúng rồi, xác nhận đặt đơn này")
    return driver, orders
