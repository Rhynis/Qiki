"""Tests for conversation orchestration service."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.intent.base import BaseIntentClassifier
from app.intent.categories import IntentCategory
from app.intent.schemas import IntentResult
from app.llm.schemas import LLMResponse
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.rag.schemas import RAGResponse, SafetyResult
from app.schemas.conversation import SendMessageRequest
from app.schemas.product import ProductResponse
from app.services.conversation_service import ConversationService
from app.services.routing_service import RoutingDecision


class FakeConversationRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Conversation] = {}

    async def create(self, data: dict[str, Any]) -> Conversation:
        conversation = Conversation(
            id=uuid.uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            messages=[],
            **data,
        )
        self.items[conversation.id] = conversation
        return conversation

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        return self.items.get(conversation_id)

    async def get_active_by_user(self, user_id: uuid.UUID) -> Conversation | None:
        return next(
            (
                item
                for item in self.items.values()
                if item.user_id == user_id and item.status == "active"
            ),
            None,
        )

    async def get_active_by_session(self, session_id: str) -> Conversation | None:
        return next(
            (
                item
                for item in self.items.values()
                if item.session_id == session_id and item.status == "active"
            ),
            None,
        )

    async def list_for_staff(self, staff_id, status_filter=None, skip=0, limit=20):  # type: ignore[no-untyped-def]
        del staff_id, status_filter, skip, limit
        return list(self.items.values()), len(self.items)

    async def assign_to_staff(
        self,
        conversation_id: uuid.UUID,
        staff_id: uuid.UUID | None,
        reason: str,
    ) -> Conversation:
        conversation = self.items[conversation_id]
        conversation.status = "escalated"
        conversation.assigned_to = staff_id
        conversation.escalation_reason = reason
        conversation.escalated_at = datetime.now(UTC)
        return conversation

    async def transfer(self, conversation_id: uuid.UUID, staff_id: uuid.UUID) -> Conversation:
        conversation = self.items[conversation_id]
        conversation.assigned_to = staff_id
        return conversation

    async def resolve(
        self,
        conversation_id: uuid.UUID,
        satisfaction_rating: int | None = None,
    ) -> Conversation:
        conversation = self.items[conversation_id]
        conversation.status = "resolved"
        conversation.satisfaction_rating = satisfaction_rating
        conversation.resolved_at = datetime.now(UTC)
        return conversation


class FakeMessageRepository:
    def __init__(self, conversations: FakeConversationRepository) -> None:
        self.conversations = conversations
        self.items: dict[uuid.UUID, Message] = {}

    async def create(self, data: dict[str, Any]) -> Message:
        payload = dict(data)
        message = Message(
            id=uuid.uuid4(),
            created_at=datetime.now(UTC),
            flagged_for_review=bool(payload.pop("flagged_for_review", False)),
            **payload,
        )
        if message.should_be_flagged():
            message.flagged_for_review = True
        self.items[message.id] = message
        self.conversations.items[message.conversation_id].messages.append(message)
        return message

    async def list_by_conversation(
        self,
        conversation_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Message]:
        return self.conversations.items[conversation_id].messages[skip : skip + limit]

    async def get_recent(self, conversation_id: uuid.UUID, limit: int = 10) -> list[Message]:
        return self.conversations.items[conversation_id].messages[-limit:]

    async def update_feedback(self, message_id: uuid.UUID, score: int) -> Message:
        message = self.items[message_id]
        message.feedback_score = score
        if score == -1:
            message.flagged_for_review = True
        return message

    async def flag_for_review(self, message_id: uuid.UUID) -> Message:
        message = self.items[message_id]
        message.flagged_for_review = True
        return message


class FakeIntentClassifier(BaseIntentClassifier):
    def __init__(
        self,
        category: IntentCategory = IntentCategory.PRODUCT_INQUIRY,
        confidence: float = 0.9,
    ) -> None:
        self.category = category
        self.confidence = confidence

    async def classify(self, text: str, conversation_history=None) -> IntentResult:  # type: ignore[no-untyped-def]
        del text, conversation_history
        return IntentResult(
            category=self.category,
            confidence=self.confidence,
            reasoning="test",
            classifier="test",
        )


class FakeRoutingService:
    def __init__(self, requires_human: bool = False) -> None:
        self.requires_human = requires_human
        self.staff_id = uuid.uuid4()

    async def route_intent(self, result: IntentResult) -> RoutingDecision:
        return RoutingDecision(
            requires_human=self.requires_human or result.confidence < 0.6,
            priority=0 if result.category == IntentCategory.SAFETY_EMERGENCY else 2,
            reason="test escalation",
            assigned_staff_id=self.staff_id,
        )


class FakeRAGPipeline:
    def __init__(self) -> None:
        self.calls = 0
        self.last_kwargs: dict[str, object] = {}

    async def query(self, query: str, **kwargs: object) -> RAGResponse:
        self.last_kwargs = kwargs
        self.calls += 1
        is_emergency = "mui gas" in query.lower()
        return RAGResponse(
            answer="Gọi ngay 1900-1234" if is_emergency else "Câu trả lời từ RAG",
            sources=[],
            query=query,
            processed_query=query,
            llm_response=(
                None
                if is_emergency
                else LLMResponse(
                    text="Câu trả lời từ RAG",
                    latency_ms=10,
                    model="fake",
                    provider="fake",
                    total_tokens=12,
                )
            ),
            retrieval_count=0,
            is_safety_critical=is_emergency,
            safety_result=SafetyResult(
                is_emergency=is_emergency,
                severity="critical" if is_emergency else "none",
                suggested_action="emergency_response" if is_emergency else "normal_response",
                detected_via="keyword" if is_emergency else "none",
            ),
            confidence_score=1.0,
            total_latency_ms=10,
        )


class FakeProductService:
    def __init__(self, products: list[ProductResponse] | None = None) -> None:
        now = datetime.now(UTC)
        self.products = products or [
            ProductResponse(
                id=uuid.uuid4(),
                sku="PETROLIMEX-12KG",
                name="Bình gas Petrolimex 12kg",
                brand="Petrolimex",
                size_kg=Decimal("12"),
                price=Decimal("440000"),
                stock_quantity=20,
                description=None,
                image_url=None,
                safety_info=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        ]
        self.calls = 0

    async def list_active_catalog(self, limit: int = 50) -> list[ProductResponse]:
        self.calls += 1
        return self.products[:limit]


def make_service(
    category: IntentCategory = IntentCategory.PRODUCT_INQUIRY,
    confidence: float = 0.9,
    requires_human: bool = False,
    product_service: FakeProductService | None = None,
) -> tuple[ConversationService, FakeConversationRepository, FakeMessageRepository, FakeRAGPipeline]:
    conversations = FakeConversationRepository()
    messages = FakeMessageRepository(conversations)
    rag = FakeRAGPipeline()
    product_service = product_service or FakeProductService()
    service = ConversationService(
        conversation_repository=conversations,  # type: ignore[arg-type]
        message_repository=messages,  # type: ignore[arg-type]
        intent_classifier=FakeIntentClassifier(category, confidence),
        routing_service=FakeRoutingService(requires_human),  # type: ignore[arg-type]
        rag_pipeline=rag,  # type: ignore[arg-type]
        product_service=product_service,  # type: ignore[arg-type]
    )
    return service, conversations, messages, rag


@pytest.mark.asyncio
async def test_starts_conversation() -> None:
    service, _conversations, _messages, _rag = make_service()

    response = await service.start_conversation(user=None, session_id="abc")

    assert response.session_id == "abc"
    assert response.status == "active"


@pytest.mark.asyncio
async def test_send_message_saves_user_and_assistant_messages() -> None:
    service, _conversations, _messages, rag = make_service()
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Gia gas bao nhieu?"),
        user=None,
    )

    assert response.user_message.role == "user"
    assert response.assistant_message is not None
    assert response.assistant_message.content == "Câu trả lời từ RAG"
    assert rag.calls == 1


@pytest.mark.asyncio
async def test_send_message_adds_product_catalog_context_to_rag() -> None:
    product_service = FakeProductService()
    service, _conversations, _messages, rag = make_service(product_service=product_service)
    conversation = await service.start_conversation(user=None, session_id="abc")

    await service.send_message(
        conversation.id,
        SendMessageRequest(content="Giá bình gas 12kg bao nhiêu?"),
        user=None,
    )

    assert product_service.calls == 1
    product_context = rag.last_kwargs["product_context"]
    assert isinstance(product_context, str)
    assert "Bảng giá sản phẩm hiện có" in product_context
    assert "Bình gas Petrolimex 12kg" in product_context
    assert "440.000đ" in product_context
    assert "còn 20 bình" in product_context


@pytest.mark.asyncio
async def test_safety_emergency_escalates_and_keeps_hotline() -> None:
    product_service = FakeProductService()
    service, _conversations, _messages, rag = make_service(
        category=IntentCategory.SAFETY_EMERGENCY,
        requires_human=True,
        product_service=product_service,
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Toi ngui mui gas"),
        user=None,
    )

    assert response.conversation.status == "escalated"
    assert response.assistant_message is not None
    assert "1900-1234" in response.assistant_message.content
    assert response.assistant_message.is_emergency is True
    assert product_service.calls == 0
    assert rag.last_kwargs["product_context"] is None


@pytest.mark.asyncio
async def test_human_handoff_skips_rag_for_complaint() -> None:
    service, _conversations, _messages, rag = make_service(
        category=IntentCategory.COMPLAINT,
        requires_human=True,
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Can khieu nai"),
        user=None,
    )

    assert response.conversation.status == "escalated"
    assert response.assistant_message is not None
    assert "nhân viên" in response.assistant_message.content
    assert rag.calls == 0


@pytest.mark.asyncio
async def test_low_confidence_message_is_flagged() -> None:
    service, _conversations, messages, _rag = make_service(confidence=0.5)
    conversation = await service.start_conversation(user=None, session_id="abc")

    await service.send_message(conversation.id, SendMessageRequest(content="khong ro"), user=None)

    flagged = [message for message in messages.items.values() if message.flagged_for_review]
    assert flagged


@pytest.mark.asyncio
async def test_negative_feedback_flags_message() -> None:
    service, _conversations, messages, _rag = make_service()
    conversation = await service.start_conversation(user=None, session_id="abc")
    sent = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Gia gas bao nhieu?"),
        user=None,
    )

    assert sent.assistant_message is not None
    response = await service.submit_feedback(sent.assistant_message.id, -1)

    assert response.flagged_for_review is True
    assert messages.items[sent.assistant_message.id].flagged_for_review is True


@pytest.mark.asyncio
async def test_staff_can_send_and_resolve() -> None:
    service, _conversations, _messages, _rag = make_service(requires_human=True)
    staff = User(id=uuid.uuid4(), email="staff@example.com", role="staff", is_active=True)
    conversation = await service.start_conversation(user=None, session_id="abc")

    staff_message = await service.staff_send_message(conversation.id, "Tôi đang hỗ trợ", staff)
    resolved = await service.resolve_conversation(conversation.id, satisfaction_rating=5)

    assert staff_message.role == "staff"
    assert resolved.status == "resolved"
    assert resolved.satisfaction_rating == 5
