"""Tests for conversation orchestration service."""

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.intent.base import BaseIntentClassifier
from app.intent.categories import IntentCategory
from app.intent.schemas import IntentResult
from app.llm.base import BaseLLMProvider
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
            answer="Gọi ngay 114, 115 hoặc 090 3026306" if is_emergency else "Câu trả lời từ RAG",
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
                sku="PLX-12KG-BIEN",
                name="Bình gas Petrolimex 12kg (biển)",
                brand="Petrolimex",
                size_kg=Decimal("12"),
                price=Decimal("675000"),
                stock_quantity=50,
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


class FakeLLMProvider(BaseLLMProvider):
    def __init__(self, payloads: list[dict[str, object]] | None = None) -> None:
        super().__init__(model="fake")
        self.payloads = payloads or []
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "fake"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stop_sequences: list[str] | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        del prompt, system_prompt, temperature, max_tokens, stop_sequences, kwargs
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)] if self.payloads else {}
        self.calls += 1
        return LLMResponse(
            text=json.dumps(payload),
            latency_ms=1,
            model="fake",
            provider="fake",
            total_tokens=1,
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: object,
    ) -> AsyncIterator[object]:
        del prompt, system_prompt, temperature, max_tokens, kwargs
        if False:
            yield object()

    async def health_check(self) -> bool:
        return True


class FakeOrderResponse:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.order_number = "QC-000123"


class FakeOrderService:
    def __init__(self) -> None:
        self.calls = 0
        self.last_checkout: Any = None
        self.last_user: User | None = None
        self.last_idempotency_key: uuid.UUID | None = None

    async def create_order(
        self,
        checkout_data,
        current_user,
        idempotency_key,
        session,
    ):  # type: ignore[no-untyped-def]
        del session
        self.calls += 1
        self.last_checkout = checkout_data
        self.last_user = current_user
        self.last_idempotency_key = idempotency_key
        return FakeOrderResponse()


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def make_service(
    category: IntentCategory = IntentCategory.PRODUCT_INQUIRY,
    confidence: float = 0.9,
    requires_human: bool = False,
    product_service: FakeProductService | None = None,
    llm_provider: FakeLLMProvider | None = None,
    order_service: FakeOrderService | None = None,
) -> tuple[
    ConversationService,
    FakeConversationRepository,
    FakeMessageRepository,
    FakeRAGPipeline,
    FakeOrderService,
]:
    conversations = FakeConversationRepository()
    messages = FakeMessageRepository(conversations)
    rag = FakeRAGPipeline()
    product_service = product_service or FakeProductService()
    order_service = order_service or FakeOrderService()
    session = FakeSession()
    service = ConversationService(
        conversation_repository=conversations,  # type: ignore[arg-type]
        message_repository=messages,  # type: ignore[arg-type]
        intent_classifier=FakeIntentClassifier(category, confidence),
        routing_service=FakeRoutingService(requires_human),  # type: ignore[arg-type]
        rag_pipeline=rag,  # type: ignore[arg-type]
        product_service=product_service,  # type: ignore[arg-type]
        order_service=order_service,  # type: ignore[arg-type]
        llm_provider=llm_provider or FakeLLMProvider(),  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )
    return service, conversations, messages, rag, order_service


@pytest.mark.asyncio
async def test_starts_conversation() -> None:
    service, _conversations, _messages, _rag, _orders = make_service()

    response = await service.start_conversation(user=None, session_id="abc")

    assert response.session_id == "abc"
    assert response.status == "active"


@pytest.mark.asyncio
async def test_send_message_saves_user_and_assistant_messages() -> None:
    service, _conversations, _messages, rag, _orders = make_service()
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Gia gas bao nhieu?"),
        user=None,
    )

    assert response.user_message.role == "user"
    assert response.assistant_message is not None
    assert response.assistant_message.content == "Câu trả lời từ RAG"
    assert len(response.products) == 1
    assert response.products[0].name == "Bình gas Petrolimex 12kg (biển)"
    assert response.products[0].price == Decimal("675000")
    assert rag.calls == 1


@pytest.mark.asyncio
async def test_send_message_adds_product_catalog_context_to_rag() -> None:
    product_service = FakeProductService()
    service, _conversations, _messages, rag, _orders = make_service(product_service=product_service)
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
    assert "675.000đ" in product_context
    assert "còn 50 bình" in product_context


@pytest.mark.asyncio
async def test_send_message_omits_product_cards_for_place_order_slot_fill() -> None:
    payload = complete_order_payload()
    payload["customer_phone"] = None
    service, _conversations, _messages, _rag, _orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([payload]),
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Tôi muốn đặt một bình gas Petrolimex"),
        user=None,
    )

    assert response.products == []


@pytest.mark.asyncio
async def test_send_message_omits_product_cards_for_general_info() -> None:
    service, _conversations, _messages, _rag, _orders = make_service(
        category=IntentCategory.GENERAL_INFO
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Cửa hàng mở cửa mấy giờ?"),
        user=None,
    )

    assert response.products == []


def _multi_catalog() -> list[ProductResponse]:
    now = datetime.now(UTC)
    specs = [
        ("PLX-12KG-BIEN", "Bình gas Petrolimex 12kg (biển)", "Petrolimex", "12", "675000", 50),
        ("VT-12KG-XAM", "Bình gas VT 12kg (xám)", "VT Gas", "12", "605000", 50),
        ("SP-45KG-BO", "Bình gas Saigon Petro 45kg (bò)", "Saigon Petro", "45", "2250000", 20),
    ]
    return [
        ProductResponse(
            id=uuid.uuid4(),
            sku=sku,
            name=name,
            brand=brand,
            size_kg=Decimal(size),
            price=Decimal(price),
            stock_quantity=stock,
            description=None,
            image_url=None,
            safety_info=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        for sku, name, brand, size, price, stock in specs
    ]


def _multi_word_brand_catalog() -> list[ProductResponse]:
    now = datetime.now(UTC)
    specs = [
        ("ELF-12KG-DO", "Bình gas Elf 12kg (đỏ)", "Elf Gas", "12", "710000", 50),
        ("VT-12KG-XAM", "Bình gas VT 12kg (xám)", "VT Gas", "12", "605000", 50),
        ("THUDUC-12KG", "Bình gas Thủ Đức 12kg", "Gas Thủ Đức", "12", "625000", 50),
    ]
    return [
        ProductResponse(
            id=uuid.uuid4(),
            sku=sku,
            name=name,
            brand=brand,
            size_kg=Decimal(size),
            price=Decimal(price),
            stock_quantity=stock,
            description=None,
            image_url=None,
            safety_info=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        for sku, name, brand, size, price, stock in specs
    ]


def _substring_brand_catalog() -> list[ProductResponse]:
    now = datetime.now(UTC)
    specs = [
        ("PLX-12KG-BIEN", "Bình gas Petrolimex 12kg (biển)", "Petrolimex", "12", "675000", 50),
        ("SP-12KG-XAM", "Bình gas Saigon Petro 12kg (xám)", "Saigon Petro", "12", "605000", 50),
        ("ELF-6KG-DO", "Bình gas Elf 6kg (đỏ)", "Elf Gas", "6", "350000", 50),
        ("VT-12KG-XAM", "Bình gas VT 12kg (xám)", "VT Gas", "12", "605000", 50),
    ]
    return [
        ProductResponse(
            id=uuid.uuid4(),
            sku=sku,
            name=name,
            brand=brand,
            size_kg=Decimal(size),
            price=Decimal(price),
            stock_quantity=stock,
            description=None,
            image_url=None,
            safety_info=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        for sku, name, brand, size, price, stock in specs
    ]


def _water_catalog() -> list[ProductResponse]:
    now = datetime.now(UTC)
    return [
        ProductResponse(
            id=uuid.uuid4(),
            sku="HOANHAO-20L",
            name="Nước Hoàn Hảo 20 lít",
            brand="Hoàn Hảo",
            size_kg=Decimal("20"),
            category="nuoc_uong",
            unit="lít",
            price=Decimal("15000"),
            stock_quantity=30,
            description=None,
            image_url=None,
            safety_info=None,
            pricing_note="Giá tại cửa hàng; giao +5.000đ.",
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        ProductResponse(
            id=uuid.uuid4(),
            sku="VIHAWA-20L",
            name="Nước Vihawa 20 lít",
            brand="Vihawa",
            size_kg=Decimal("20"),
            category="nuoc_uong",
            unit="lít",
            price=Decimal("55000"),
            stock_quantity=20,
            description=None,
            image_url=None,
            safety_info=None,
            pricing_note="Giá tại cửa hàng; giao +5.000đ.",
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
    ]


def _category_catalog() -> list[ProductResponse]:
    return _water_catalog() + _multi_catalog()


@pytest.mark.asyncio
async def test_product_cards_filtered_for_specific_product() -> None:
    service, _conversations, _messages, _rag, _orders = make_service(
        product_service=FakeProductService(products=_multi_catalog())
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Giá bình VT Gas 12kg bao nhiêu?"),
        user=None,
    )

    assert [product.sku for product in response.products] == ["VT-12KG-XAM"]


@pytest.mark.asyncio
async def test_product_cards_brand_match_without_generic_gas_word() -> None:
    service, _conversations, _messages, _rag, _orders = make_service(
        product_service=FakeProductService(products=_multi_word_brand_catalog())
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="bình elf 12kg"),
        user=None,
    )

    assert [product.sku for product in response.products] == ["ELF-12KG-DO"]


@pytest.mark.asyncio
async def test_product_cards_brand_match_exact_token_without_substring_bleed() -> None:
    service, _conversations, _messages, _rag, _orders = make_service(
        product_service=FakeProductService(products=_substring_brand_catalog())
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="bình petro 12kg"),
        user=None,
    )

    assert [product.sku for product in response.products] == ["SP-12KG-XAM"]


@pytest.mark.asyncio
async def test_product_cards_saigon_petro_query_excludes_petrolimex() -> None:
    service, _conversations, _messages, _rag, _orders = make_service(
        product_service=FakeProductService(products=_substring_brand_catalog())
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="bình saigon petro"),
        user=None,
    )

    assert [product.sku for product in response.products] == [
        "SP-12KG-XAM",
    ]


@pytest.mark.asyncio
async def test_product_cards_full_brand_name_does_not_match_shorter_substring_brand() -> None:
    service, _conversations, _messages, _rag, _orders = make_service(
        product_service=FakeProductService(products=_substring_brand_catalog())
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="bình petrolimex 12kg"),
        user=None,
    )

    assert [product.sku for product in response.products] == ["PLX-12KG-BIEN"]


@pytest.mark.asyncio
async def test_product_cards_filtered_by_brand() -> None:
    service, _conversations, _messages, _rag, _orders = make_service(
        product_service=FakeProductService(products=_multi_catalog())
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Cho mình xem gas Petrolimex"),
        user=None,
    )

    assert sorted(product.sku for product in response.products) == [
        "PLX-12KG-BIEN",
    ]


@pytest.mark.asyncio
async def test_product_cards_full_catalog_for_general_query() -> None:
    service, _conversations, _messages, _rag, _orders = make_service(
        product_service=FakeProductService(products=_multi_catalog())
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Cửa hàng có những loại gas nào?"),
        user=None,
    )

    assert len(response.products) == 3


@pytest.mark.asyncio
async def test_product_cards_water_category_query_returns_only_water() -> None:
    service, _conversations, _messages, _rag, _orders = make_service(
        product_service=FakeProductService(products=_category_catalog())
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="nước"),
        user=None,
    )

    assert response.user_message.intent == IntentCategory.PRODUCT_INQUIRY.value
    assert [product.sku for product in response.products] == ["HOANHAO-20L", "VIHAWA-20L"]


@pytest.mark.asyncio
async def test_product_cards_gas_category_query_returns_only_gas() -> None:
    service, _conversations, _messages, _rag, _orders = make_service(
        product_service=FakeProductService(products=_category_catalog())
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="gas"),
        user=None,
    )

    assert response.user_message.intent == IntentCategory.PRODUCT_INQUIRY.value
    assert [product.sku for product in response.products] == [
        "PLX-12KG-BIEN",
        "VT-12KG-XAM",
        "SP-45KG-BO",
    ]


def complete_order_payload(
    confirmed: bool = False, address: str | None = None
) -> dict[str, object]:
    return {
        "product": "Petrolimex 12kg",
        "quantity": 1,
        "customer_name": "Nguyen Van A",
        "customer_phone": "0903026306",
        "delivery_address": address or "15 đường số 5, Phường Hiệp Bình, TP. Hồ Chí Minh",
        "payment_method": "cod",
        "confirmed": confirmed,
    }


async def add_order_state_history(
    messages: FakeMessageRepository,
    conversation_id: uuid.UUID,
    status: str = "awaiting_missing_slots",
) -> None:
    await messages.create(
        {
            "conversation_id": conversation_id,
            "role": "user",
            "content": "Mình muốn đặt nước Vihawa 20 lít giao Hiệp Bình",
            "intent": IntentCategory.PLACE_ORDER.value,
            "intent_confidence": 0.9,
        }
    )
    await messages.create(
        {
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": "Bạn cho Qiki xin thêm tên, số điện thoại và thanh toán nhé.",
            "intent": IntentCategory.PLACE_ORDER.value,
            "intent_confidence": 0.9,
            "latency_ms": 0,
            "retrieved_documents": [{"type": "chat_order_state", "status": status}],
        }
    )


@pytest.mark.asyncio
async def test_chat_order_creates_order_on_confirmation() -> None:
    order_service = FakeOrderService()
    service, _conversations, _messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([complete_order_payload(confirmed=True)]),
        order_service=order_service,
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Đúng rồi, xác nhận đặt đơn này"),
        user=None,
    )

    assert orders.calls == 1
    assert response.assistant_message is not None
    assert "QC-000123" in response.assistant_message.content
    assert "Nhân viên sẽ sớm gọi điện lại xác nhận" in response.assistant_message.content
    assert response.products == []
    assert orders.last_checkout.source == "chatbot"
    assert orders.last_checkout.referral_conversation_id == conversation.id
    assert orders.last_checkout.delivery_district == "Thủ Đức"
    assert orders.last_checkout.items[0].quantity == 1
    assert orders.last_user is None
    assert response.assistant_message.retrieved_documents[0]["order_number"] == "QC-000123"


@pytest.mark.asyncio
async def test_chat_order_creates_water_order_without_escalation() -> None:
    products = _water_catalog()
    payload = complete_order_payload(confirmed=True)
    payload["product"] = "Hoàn Hảo 20 lít"
    order_service = FakeOrderService()
    service, _conversations, _messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([payload]),
        product_service=FakeProductService(products=products),
        order_service=order_service,
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Đúng rồi, xác nhận đặt nước Hoàn Hảo"),
        user=None,
    )

    assert orders.calls == 1
    assert response.conversation.status == "active"
    assert response.assistant_message is not None
    assert "QC-000123" in response.assistant_message.content
    assert response.products == []
    assert orders.last_checkout.items[0].product_id == products[0].id
    assert orders.last_checkout.items[0].quantity == 1


@pytest.mark.asyncio
async def test_chat_order_bare_water_category_asks_for_product_choice() -> None:
    payload = complete_order_payload(confirmed=True)
    payload["product"] = "nước"
    service, _conversations, _messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([payload]),
        product_service=FakeProductService(products=_category_catalog()),
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="đặt nước"),
        user=None,
    )

    assert orders.calls == 0
    assert response.assistant_message is not None
    assert "loại nước uống nào" in response.assistant_message.content
    assert [product.sku for product in response.products] == ["HOANHAO-20L", "VIHAWA-20L"]


@pytest.mark.asyncio
async def test_chat_order_missing_slot_asks_again() -> None:
    payload = complete_order_payload()
    payload["customer_phone"] = None
    service, _conversations, _messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([payload]),
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Tôi muốn đặt gas"),
        user=None,
    )

    assert orders.calls == 0
    assert response.assistant_message is not None
    assert "số điện thoại" in response.assistant_message.content
    assert response.products == []


@pytest.mark.asyncio
async def test_chat_order_missing_address_mentions_khu_pho() -> None:
    payload = complete_order_payload()
    payload["delivery_address"] = None
    service, _conversations, _messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([payload]),
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Tôi muốn đặt 1 bình Petrolimex 12kg"),
        user=None,
    )

    assert orders.calls == 0
    assert response.assistant_message is not None
    assert "khu phố" in response.assistant_message.content
    assert "mốc gần nhà" in response.assistant_message.content
    assert response.products == []


@pytest.mark.asyncio
async def test_chat_order_address_slot_fill_does_not_return_full_catalog() -> None:
    payload = complete_order_payload()
    payload["product"] = "Vihawa 20 lít"
    payload["customer_phone"] = None
    payload["delivery_address"] = "15 đường số 5, Khu phố 36, Phường Hiệp Bình, TP.HCM"
    service, _conversations, _messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([payload]),
        product_service=FakeProductService(products=_category_catalog()),
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="15 đường số 5, khu phố 36, phường hiệp bình"),
        user=None,
    )

    assert orders.calls == 0
    assert response.assistant_message is not None
    assert "số điện thoại" in response.assistant_message.content
    assert response.products == []


@pytest.mark.asyncio
async def test_order_in_progress_keeps_order_route_for_ambiguous_phone_message() -> None:
    payload = complete_order_payload()
    payload["product"] = "Vihawa 20 lít"
    payload["customer_name"] = "Vân"
    payload["customer_phone"] = "19002929"
    payload["delivery_address"] = "15 đường số 5, Khu phố 36, Phường Hiệp Bình, TP.HCM"
    payload["payment_method"] = "cod"
    service, _conversations, messages, rag, orders = make_service(
        category=IntentCategory.PRODUCT_INQUIRY,
        llm_provider=FakeLLMProvider([payload]),
        product_service=FakeProductService(products=_category_catalog()),
    )
    conversation = await service.start_conversation(user=None, session_id="abc")
    await add_order_state_history(messages, conversation.id)

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Van 19002929 cod"),
        user=None,
    )

    assert response.user_message.intent == IntentCategory.PLACE_ORDER.value
    assert rag.calls == 0
    assert orders.calls == 0
    assert response.assistant_message is not None
    assert "van điều áp" not in response.assistant_message.content.lower()
    assert "19002929" in response.assistant_message.content
    assert "SĐT Việt Nam" in response.assistant_message.content
    assert response.products == []


@pytest.mark.asyncio
async def test_order_in_progress_unknown_product_stays_catalog_only() -> None:
    payload = complete_order_payload()
    payload["product"] = "van điều áp mã 19002929"
    service, _conversations, messages, rag, orders = make_service(
        category=IntentCategory.PRODUCT_INQUIRY,
        llm_provider=FakeLLMProvider([payload]),
        product_service=FakeProductService(products=_category_catalog()),
    )
    conversation = await service.start_conversation(user=None, session_id="abc")
    await add_order_state_history(messages, conversation.id)

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Van 0903026306 cod"),
        user=None,
    )

    assert response.user_message.intent == IntentCategory.PLACE_ORDER.value
    assert rag.calls == 0
    assert orders.calls == 0
    assert response.assistant_message is not None
    assert "sản phẩm nào trong cửa hàng" in response.assistant_message.content
    assert response.products == []


@pytest.mark.parametrize("phone", ["19002929", "123"])
@pytest.mark.asyncio
async def test_chat_order_rejects_invalid_phone_and_does_not_create_order(phone: str) -> None:
    payload = complete_order_payload(confirmed=True)
    payload["customer_phone"] = phone
    service, _conversations, _messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([payload]),
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content=f"Vân {phone} cod"),
        user=None,
    )

    assert orders.calls == 0
    assert response.assistant_message is not None
    assert phone in response.assistant_message.content
    assert "10 số, đầu 03/05/07/08/09" in response.assistant_message.content
    assert response.products == []


@pytest.mark.asyncio
async def test_chat_order_outside_zone_declined() -> None:
    service, _conversations, _messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider(
            [complete_order_payload(address="12 Lê Lợi, Phường Bến Nghé, Quận 1")]
        ),
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Giao qua Quận 1 giúp tôi"),
        user=None,
    )

    assert orders.calls == 0
    assert response.assistant_message is not None
    assert "chỉ giao trong khu vực Bình Thạnh và Thủ Đức" in response.assistant_message.content
    assert response.products == []


@pytest.mark.asyncio
async def test_chat_order_requires_explicit_confirmation() -> None:
    service, _conversations, _messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([complete_order_payload(confirmed=False)]),
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Tôi muốn đặt 1 bình Petrolimex 12kg"),
        user=None,
    )

    assert orders.calls == 0
    assert response.assistant_message is not None
    assert "Qiki tóm tắt đơn hàng" in response.assistant_message.content
    assert "Bạn xác nhận đặt đơn này không?" in response.assistant_message.content
    assert response.products == []


@pytest.mark.asyncio
async def test_chat_order_rejects_string_false_confirmation() -> None:
    payload = complete_order_payload()
    payload["confirmed"] = "false"
    service, _conversations, _messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([payload]),
    )
    conversation = await service.start_conversation(user=None, session_id="abc")

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Tôi muốn đặt 1 bình Petrolimex 12kg"),
        user=None,
    )

    assert orders.calls == 0
    assert response.assistant_message is not None
    assert "Bạn xác nhận đặt đơn này không?" in response.assistant_message.content
    assert response.products == []


@pytest.mark.asyncio
async def test_safety_emergency_escalates_and_keeps_hotline() -> None:
    product_service = FakeProductService()
    service, _conversations, _messages, rag, _orders = make_service(
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
    assert "090 3026306" in response.assistant_message.content
    assert response.assistant_message.is_emergency is True
    assert response.products == []
    assert product_service.calls == 0
    assert rag.last_kwargs["product_context"] is None


@pytest.mark.asyncio
async def test_order_in_progress_does_not_override_safety_emergency() -> None:
    product_service = FakeProductService()
    service, _conversations, messages, rag, _orders = make_service(
        category=IntentCategory.SAFETY_EMERGENCY,
        requires_human=True,
        product_service=product_service,
    )
    conversation = await service.start_conversation(user=None, session_id="abc")
    await add_order_state_history(messages, conversation.id)

    response = await service.send_message(
        conversation.id,
        SendMessageRequest(content="Tôi ngửi thấy mùi gas"),
        user=None,
    )

    assert response.user_message.intent == IntentCategory.SAFETY_EMERGENCY.value
    assert response.conversation.status == "escalated"
    assert response.assistant_message is not None
    assert response.assistant_message.is_emergency is True
    assert response.products == []
    assert product_service.calls == 0
    assert rag.calls == 1


@pytest.mark.asyncio
async def test_human_handoff_skips_rag_for_complaint() -> None:
    service, _conversations, _messages, rag, _orders = make_service(
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
    service, _conversations, messages, _rag, _orders = make_service(confidence=0.5)
    conversation = await service.start_conversation(user=None, session_id="abc")

    await service.send_message(conversation.id, SendMessageRequest(content="khong ro"), user=None)

    flagged = [message for message in messages.items.values() if message.flagged_for_review]
    assert flagged


@pytest.mark.asyncio
async def test_negative_feedback_flags_message() -> None:
    service, _conversations, messages, _rag, _orders = make_service()
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
    service, _conversations, _messages, _rag, _orders = make_service(requires_human=True)
    staff = User(id=uuid.uuid4(), email="staff@example.com", role="staff", is_active=True)
    conversation = await service.start_conversation(user=None, session_id="abc")

    staff_message = await service.staff_send_message(conversation.id, "Tôi đang hỗ trợ", staff)
    resolved = await service.resolve_conversation(conversation.id, satisfaction_rating=5)

    assert staff_message.role == "staff"
    assert resolved.status == "resolved"
    assert resolved.satisfaction_rating == 5
