"""Integration tests for chat order intake endpoints."""

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.conversations import get_intent_classifier
from app.intent.base import BaseIntentClassifier
from app.intent.categories import IntentCategory
from app.intent.schemas import IntentResult
from app.llm.base import BaseLLMProvider
from app.llm.dependencies import get_llm_provider
from app.llm.schemas import LLMResponse
from app.main import app
from app.models.order import Order, OrderItem
from app.rag.dependencies import get_rag_pipeline
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate
from app.services.conversation_service import ConversationService

pytestmark = pytest.mark.asyncio


class PlaceOrderClassifier(BaseIntentClassifier):
    """Deterministic place-order classifier for endpoint tests."""

    async def classify(
        self,
        text: str,
        conversation_history: Sequence[Mapping[str, str]] | None = None,
    ) -> IntentResult:
        del text, conversation_history
        return IntentResult(
            category=IntentCategory.PLACE_ORDER,
            confidence=0.95,
            reasoning="test",
            classifier="test",
        )


class JSONLLMProvider(BaseLLMProvider):
    """Fake LLM provider returning JSON payloads."""

    def __init__(self, payload: dict[str, object] | Sequence[dict[str, object]]) -> None:
        super().__init__(model="fake")
        self.payloads = list(payload) if isinstance(payload, Sequence) else [payload]
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
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
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


class UnusedRAGPipeline:
    """Placeholder RAG pipeline; place-order confirmation should not call RAG."""


async def create_catalog_product(session: AsyncSession) -> None:
    """Create a product visible to the real product catalog service."""
    await ProductRepository(session).create(
        ProductCreate(
            sku=f"GAS-{uuid4().hex[:8].upper()}",
            name="Binh gas 12kg",
            brand="Saigon Petro",
            size_kg=Decimal("12"),
            price=Decimal("350000"),
            stock_quantity=10,
            description="Binh gas gia dinh",
            image_url="https://example.com/gas-12kg.jpg",
            safety_info="Dat binh noi thoang khi.",
        )
    )
    await session.commit()


async def create_multi_item_catalog(session: AsyncSession) -> None:
    """Create gas and water products for multi-item chat order tests."""
    repository = ProductRepository(session)
    await repository.create(
        ProductCreate(
            sku=f"WATER-{uuid4().hex[:8].upper()}",
            name="Nước Vihawa 20 lít",
            brand="Vihawa",
            size_kg=Decimal("20"),
            category="nuoc_uong",
            unit="lít",
            price=Decimal("55000"),
            stock_quantity=10,
            description="Nước uống bình 20 lít",
            pricing_note="Giá tại cửa hàng; giao +5.000đ; lên lầu +5.000đ/lầu",
        )
    )
    await repository.create(
        ProductCreate(
            sku=f"GAS-{uuid4().hex[:8].upper()}",
            name="Bình gas Saigon Petro 12kg (xám)",
            brand="Saigon Petro",
            size_kg=Decimal("12"),
            price=Decimal("605000"),
            stock_quantity=10,
            description="Bình gas gia đình",
        )
    )
    await session.commit()


async def test_chat_order_confirm_endpoint_creates_real_order(
    test_client: AsyncClient,
    order_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ConversationService,
        "_now_vn",
        staticmethod(lambda: datetime(2026, 6, 8, 9, 0, tzinfo=timezone(timedelta(hours=7)))),
    )
    await order_session.execute(
        text(
            "TRUNCATE TABLE messages, conversations, order_items, orders, products, users "
            "RESTART IDENTITY CASCADE"
        )
    )
    await order_session.commit()
    await create_catalog_product(order_session)

    payload = {
        "product": "Saigon Petro 12kg",
        "quantity": 1,
        "customer_name": "Nguyen Van A",
        "customer_phone": "0903026306",
        "delivery_address": "15 đường số 5, Phường Hiệp Bình, TP. Hồ Chí Minh",
        "payment_method": "cod",
        "confirmed": True,
    }

    app.dependency_overrides[get_intent_classifier] = lambda: PlaceOrderClassifier()
    app.dependency_overrides[get_llm_provider] = lambda: JSONLLMProvider(payload)
    app.dependency_overrides[get_rag_pipeline] = lambda: UnusedRAGPipeline()
    try:
        started = await test_client.post(
            "/api/v1/conversations/start",
            json={"session_id": "chat-order-confirm"},
        )
        assert started.status_code == 200
        conversation_id = started.json()["id"]

        response = await test_client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "Đúng rồi, xác nhận đặt đơn này"},
        )

        assert response.status_code == 200
        body = response.json()
        answer = body["assistant_message"]["content"]
        # Câu xác nhận đổi theo giờ VN (trong giờ vs ngoài giờ); kiểm phần bất biến.
        assert "Đã ghi nhận đơn" in answer
        assert "xác nhận" in answer
        response_order_number = body["assistant_message"]["retrieved_documents"][0]["order_number"]

        result = await order_session.execute(select(Order))
        orders = result.scalars().all()
        assert len(orders) == 1
        assert orders[0].order_number == response_order_number
        assert orders[0].order_number in answer
        assert orders[0].source == "chatbot"
        assert orders[0].status == "pending"
        assert orders[0].referral_conversation_id is not None
    finally:
        app.dependency_overrides.clear()


async def test_chat_order_multi_item_creates_order_items(
    test_client: AsyncClient,
    order_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ConversationService,
        "_now_vn",
        staticmethod(lambda: datetime(2026, 6, 8, 9, 0, tzinfo=timezone(timedelta(hours=7)))),
    )
    await order_session.execute(
        text(
            "TRUNCATE TABLE messages, conversations, order_items, orders, products, users "
            "RESTART IDENTITY CASCADE"
        )
    )
    await order_session.commit()
    await create_multi_item_catalog(order_session)

    payloads = [
        {
            "product": "Vihawa 20 lít",
            "quantity": 1,
            "customer_name": "Nguyen Van A",
            "customer_phone": "0903026306",
            "delivery_address": "15 đường số 5, Phường Hiệp Bình, TP. Hồ Chí Minh",
            "payment_method": "cod",
            "confirmed": False,
        },
        {},
        {"confirmed": True},
    ]

    llm_provider = JSONLLMProvider(payloads)
    app.dependency_overrides[get_intent_classifier] = lambda: PlaceOrderClassifier()
    app.dependency_overrides[get_llm_provider] = lambda: llm_provider
    app.dependency_overrides[get_rag_pipeline] = lambda: UnusedRAGPipeline()
    try:
        started = await test_client.post(
            "/api/v1/conversations/start",
            json={"session_id": "chat-order-multi-item"},
        )
        assert started.status_code == 200
        conversation_id = started.json()["id"]

        first = await test_client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "đặt 1 Vihawa"},
        )
        assert first.status_code == 200
        assert "Qiki tóm tắt đơn hàng" in first.json()["assistant_message"]["content"]

        second = await test_client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "thêm 1 bình gas Saigon Petro"},
        )
        assert second.status_code == 200
        second_answer = second.json()["assistant_message"]["content"]
        assert "Nước Vihawa 20 lít" in second_answer
        assert "Bình gas Saigon Petro 12kg (xám)" in second_answer

        third = await test_client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "ok xác nhận"},
        )
        assert third.status_code == 200
        answer = third.json()["assistant_message"]["content"]
        assert "Đã ghi nhận đơn" in answer

        result = await order_session.execute(select(Order))
        orders = result.scalars().all()
        assert len(orders) == 1
        assert orders[0].delivery_notes == "[Phí giao nước +5k/bình; lên lầu +5k/lầu]"

        item_result = await order_session.execute(
            select(OrderItem).order_by(OrderItem.product_name)
        )
        items = item_result.scalars().all()
        assert [(item.product_name, item.quantity) for item in items] == [
            ("Bình gas Saigon Petro 12kg (xám)", 1),
            ("Nước Vihawa 20 lít", 1),
        ]
    finally:
        app.dependency_overrides.clear()
