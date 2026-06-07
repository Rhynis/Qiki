"""Conversation orchestration service for chatbot and staff messages."""

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.input_validation import VietnamesePhoneValidator
from app.intent.base import BaseIntentClassifier
from app.intent.categories import IntentCategory
from app.intent.schemas import IntentResult
from app.llm.base import BaseLLMProvider
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.rag.pipeline import RAGPipeline
from app.rag.schemas import RAGResponse, RetrievedDocument
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.conversation import (
    ConversationResponse,
    ProductCardResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from app.schemas.message import MessageResponse
from app.schemas.order import CheckoutRequest, OrderItemCreate, OrderResponse
from app.schemas.product import ProductResponse
from app.services.address_lookup import resolve_ward_delivery_zone
from app.services.order_service import OrderService, is_serialization_failure
from app.services.product_service import ProductService
from app.services.routing_service import RoutingDecision, RoutingService

CHAT_ORDER_METADATA_TYPE = "chat_order"
CHAT_ORDER_STATE_METADATA_TYPE = "chat_order_state"
ORDER_CONFIRMATION_PROMPT = "Bạn xác nhận đặt đơn này không?"
ORDER_CONTEXT_CONFIDENCE = 0.9
VN_TIMEZONE = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class ChatOrderSlots:
    """Order details extracted from chat history."""

    product: str | None = None
    quantity: int | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    delivery_address: str | None = None
    payment_method: str | None = None
    confirmed: bool = False


@dataclass(frozen=True)
class ChatOrderResult:
    """Assistant reply plus contextual product cards for an order turn."""

    message: Message
    card_products: list[ProductResponse]


class ConversationService:
    """Coordinate intent classification, RAG answers, and staff handoff."""

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        intent_classifier: BaseIntentClassifier,
        routing_service: RoutingService,
        rag_pipeline: RAGPipeline,
        product_service: ProductService,
        order_service: OrderService,
        llm_provider: BaseLLMProvider,
        session: AsyncSession,
    ) -> None:
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository
        self.intent_classifier = intent_classifier
        self.routing_service = routing_service
        self.rag_pipeline = rag_pipeline
        self.product_service = product_service
        self.order_service = order_service
        self.llm_provider = llm_provider
        self.session = session

    async def start_conversation(
        self,
        user: User | None,
        session_id: str | None = None,
        initial_message: str | None = None,
    ) -> ConversationResponse:
        """Start a new conversation."""
        conversation = await self.conversation_repository.create(
            {
                "user_id": user.id if user else None,
                "session_id": session_id or str(uuid4()),
                "status": "active",
            }
        )
        if initial_message:
            await self.send_message(
                conversation.id,
                SendMessageRequest(content=initial_message, session_id=conversation.session_id),
                user,
            )
            conversation = await self._require_conversation(conversation.id)
        return self._conversation_to_response(conversation)

    async def get_active_conversation(
        self,
        user: User | None,
        session_id: str | None = None,
    ) -> ConversationResponse | None:
        """Return the current active conversation for user or anonymous session."""
        conversation: Conversation | None = None
        if user:
            conversation = await self.conversation_repository.get_active_by_user(user.id)
        if conversation is None and session_id:
            conversation = await self.conversation_repository.get_active_by_session(session_id)
        return self._conversation_to_response(conversation) if conversation else None

    async def get_conversation(self, conversation_id: UUID) -> ConversationResponse:
        """Return a conversation by ID."""
        return self._conversation_to_response(await self._require_conversation(conversation_id))

    async def list_messages(
        self,
        conversation_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[MessageResponse]:
        """List conversation messages."""
        messages = await self.message_repository.list_by_conversation(conversation_id, skip, limit)
        return [self._message_to_response(message) for message in messages]

    async def send_message(
        self,
        conversation_id: UUID,
        request: SendMessageRequest,
        user: User | None,
    ) -> SendMessageResponse:
        """Handle a customer message and optional assistant reply."""
        conversation = await self._require_conversation(conversation_id)
        history = await self.message_repository.get_recent(conversation_id, limit=10)
        history_payload = self._history_to_payload(history)
        intent = await self.intent_classifier.classify(request.content, history_payload)
        intent = self._apply_order_context_intent(intent, history)

        catalog_products: list[ProductResponse] | None = None
        if intent.category in {IntentCategory.PRODUCT_INQUIRY, IntentCategory.PLACE_ORDER}:
            catalog_products = await self.product_service.list_active_catalog(limit=50)
        if (
            intent.category == IntentCategory.PRODUCT_INQUIRY
            and catalog_products
            and self._looks_like_order_request(request.content, catalog_products)
        ):
            intent = self._order_context_intent(intent, "product_quantity_order")

        user_message = await self.message_repository.create(
            {
                "conversation_id": conversation.id,
                "role": "user",
                "content": request.content,
                "intent": intent.category.value,
                "intent_confidence": intent.confidence,
            }
        )

        routing = await self.routing_service.route_intent(intent)
        if routing.requires_human:
            conversation = await self.conversation_repository.assign_to_staff(
                conversation.id,
                routing.assigned_staff_id,
                routing.reason,
            )

        product_cards: list[ProductCardResponse] = []
        if intent.category == IntentCategory.PRODUCT_INQUIRY:
            assert catalog_products is not None
            card_products = self._select_card_products(request.content, catalog_products)
            product_cards = [self._product_to_card(product) for product in card_products]

        assistant_message: Message | None
        if intent.category == IntentCategory.SAFETY_EMERGENCY:
            assistant_message = await self._create_rag_answer(
                conversation,
                request.content,
                history_payload,
                user,
                intent.category,
                intent.confidence,
            )
        elif routing.requires_human:
            assistant_message = await self._create_handoff_message(conversation, routing)
        elif intent.category == IntentCategory.PLACE_ORDER:
            order_result = await self._handle_chat_order(
                conversation,
                request.content,
                history,
                history_payload,
                user,
                intent.confidence,
                catalog_products or [],
            )
            assistant_message = order_result.message
            product_cards = [
                self._product_to_card(product) for product in order_result.card_products
            ]
        else:
            assistant_message = await self._create_rag_answer(
                conversation,
                request.content,
                history_payload,
                user,
                intent.category,
                intent.confidence,
                catalog_products=catalog_products,
            )

        conversation = await self._require_conversation(conversation.id)
        return SendMessageResponse(
            user_message=self._message_to_response(user_message),
            assistant_message=(
                self._message_to_response(assistant_message) if assistant_message else None
            ),
            conversation=self._conversation_to_response(conversation),
            products=product_cards,
        )

    async def submit_feedback(self, message_id: UUID, score: int) -> MessageResponse:
        """Apply message feedback and flag negative feedback."""
        message = await self.message_repository.update_feedback(message_id, score)
        if score == -1:
            message = await self.message_repository.flag_for_review(message_id)
        return self._message_to_response(message)

    async def staff_send_message(
        self,
        conversation_id: UUID,
        content: str,
        staff: User,
    ) -> MessageResponse:
        """Store a staff reply."""
        del staff
        conversation = await self._require_conversation(conversation_id)
        message = await self.message_repository.create(
            {
                "conversation_id": conversation.id,
                "role": "staff",
                "content": content,
            }
        )
        return self._message_to_response(message)

    async def list_staff_conversations(
        self,
        staff: User,
        status_filter: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ConversationResponse], int]:
        """List staff conversations."""
        conversations, total = await self.conversation_repository.list_for_staff(
            staff.id,
            status_filter,
            skip,
            limit,
        )
        return [self._conversation_to_response(item) for item in conversations], total

    async def transfer_conversation(
        self, conversation_id: UUID, staff_id: UUID
    ) -> ConversationResponse:
        """Transfer an escalated conversation to another staff member."""
        return self._conversation_to_response(
            await self.conversation_repository.transfer(conversation_id, staff_id)
        )

    async def resolve_conversation(
        self,
        conversation_id: UUID,
        satisfaction_rating: int | None = None,
    ) -> ConversationResponse:
        """Resolve a conversation."""
        return self._conversation_to_response(
            await self.conversation_repository.resolve(conversation_id, satisfaction_rating)
        )

    async def _handle_chat_order(
        self,
        conversation: Conversation,
        content: str,
        history: Sequence[Message],
        history_payload: Sequence[Mapping[str, str]],
        user: User | None,
        confidence: float,
        products: Sequence[ProductResponse],
    ) -> ChatOrderResult:
        existing_order = self._find_existing_chat_order(history)
        if existing_order:
            order_number = str(existing_order.get("order_number", ""))
            return ChatOrderResult(
                message=await self._create_assistant_message(
                    conversation,
                    (
                        f"Đơn **{order_number}** đã được ghi nhận trước đó. "
                        "Nhân viên sẽ sớm gọi điện lại xác nhận với bạn trong giờ làm việc."
                    ),
                    IntentCategory.PLACE_ORDER,
                    confidence,
                    metadata=[existing_order],
                ),
                card_products=[],
            )

        def category_cards(query: str | None) -> list[ProductResponse]:
            category = self._category_filter_from_query(self._normalize_match_text(query or ""))
            if category is None:
                return []
            return [product for product in products if product.category == category]

        def result(
            message: Message,
            card_products: Sequence[ProductResponse] | None = None,
        ) -> ChatOrderResult:
            return ChatOrderResult(message=message, card_products=list(card_products or []))

        async def order_state_message(
            content: str,
            status: str,
            state_slots: ChatOrderSlots | None = None,
        ) -> Message:
            return await self._create_assistant_message(
                conversation,
                content,
                IntentCategory.PLACE_ORDER,
                confidence,
                metadata=[self._order_state_metadata(status, state_slots)],
            )

        order_state = self._find_order_state(history)
        previous_slots = self._slots_from_order_state(order_state)
        slots = await self._extract_order_slots(content, history_payload, products)
        slots = self._merge_order_slots(
            previous_slots,
            self._infer_order_slots(content, products),
            slots,
        )
        slots = self._with_phone_candidate(slots, content)
        slots = self._with_order_cues(slots, content)
        if order_state and order_state.get("status") == "awaiting_confirmation":
            slots = replace(
                slots,
                confirmed=slots.confirmed or self._is_affirmation(content),
            )
        if self._is_bare_category_query(slots.product):
            return result(
                await order_state_message(
                    self._format_category_product_question(slots.product or ""),
                    "awaiting_product_choice",
                    slots,
                ),
                category_cards(slots.product),
            )

        matched_product = self._match_product(slots.product, products)
        normalized_phone = (
            self._validate_phone(slots.customer_phone) if slots.customer_phone else None
        )
        if slots.customer_phone and normalized_phone is None:
            return result(
                await order_state_message(
                    self._format_invalid_phone_question(slots.customer_phone),
                    "awaiting_missing_slots",
                    slots,
                )
            )
        if matched_product is None and slots.product:
            return result(
                await order_state_message(
                    (
                        "Qiki chưa tìm thấy sản phẩm này trong catalog. "
                        "Bạn muốn đặt sản phẩm nào trong cửa hàng (gas hoặc nước uống hiện có)?"
                    ),
                    "awaiting_product_choice",
                    slots,
                )
            )
        missing = self._missing_order_slots(slots, matched_product)
        if missing:
            return result(
                await order_state_message(
                    self._format_missing_slot_question(missing),
                    "awaiting_missing_slots",
                    slots,
                )
            )

        assert slots.quantity is not None
        assert slots.customer_name is not None
        assert slots.customer_phone is not None
        assert slots.delivery_address is not None
        assert slots.payment_method is not None
        assert matched_product is not None
        assert normalized_phone is not None

        delivery_zone_match = resolve_ward_delivery_zone(slots.delivery_address)
        if delivery_zone_match is None:
            return result(
                await order_state_message(
                    (
                        "Hiện Gas Quốc Cường chỉ giao trong khu vực Bình Thạnh và Thủ Đức. "
                        "Địa chỉ này chưa thuộc khu vực Qiki có thể nhận đơn qua chat. "
                        "Bạn có thể gọi 090 3026306 để được nhân viên hỗ trợ thêm."
                    ),
                    "awaiting_missing_slots",
                    slots,
                ),
            )

        if matched_product.stock_quantity < slots.quantity:
            return result(
                await order_state_message(
                    (
                        f"Sản phẩm **{matched_product.name}** hiện chỉ còn "
                        f"{matched_product.stock_quantity} bình. "
                        "Bạn muốn điều chỉnh số lượng không?"
                    ),
                    "awaiting_missing_slots",
                    slots,
                )
            )

        payment_method = self._normalize_payment_method(slots.payment_method)
        if payment_method is None:
            return result(
                await order_state_message(
                    "Bạn muốn thanh toán khi nhận hàng (COD) hay chuyển khoản?",
                    "awaiting_missing_slots",
                    slots,
                )
            )

        if not slots.confirmed:
            return result(
                await order_state_message(
                    self._format_order_summary(
                        matched_product,
                        slots.quantity,
                        slots.customer_name,
                        normalized_phone,
                        slots.delivery_address,
                        payment_method,
                    ),
                    "awaiting_confirmation",
                    slots,
                ),
            )

        checkout = CheckoutRequest(
            items=[OrderItemCreate(product_id=matched_product.id, quantity=slots.quantity)],
            customer_name=slots.customer_name,
            customer_phone=normalized_phone,
            delivery_address=slots.delivery_address,
            delivery_ward=delivery_zone_match.ward,
            delivery_district=delivery_zone_match.delivery_zone,
            delivery_city="TP. Hồ Chí Minh",
            payment_method=payment_method,
            source="chatbot",
            referral_conversation_id=conversation.id,
            customer_notes="Đơn được tạo qua chat Qiki; nhân viên cần gọi lại xác nhận.",
        )
        await self.session.commit()
        order = await self._create_chat_order_with_retry(
            checkout,
            user,
            self._chat_order_idempotency_key(conversation.id, slots),
        )
        metadata = [
            {
                "type": CHAT_ORDER_METADATA_TYPE,
                "order_id": str(order.id),
                "order_number": order.order_number,
            }
        ]
        return result(
            await self._create_assistant_message(
                conversation,
                (
                    f"Đã ghi nhận đơn **{order.order_number}**. "
                    f"{self._format_order_callback_sentence()}"
                ),
                IntentCategory.PLACE_ORDER,
                confidence,
                metadata=metadata,
            ),
        )

    async def _extract_order_slots(
        self,
        content: str,
        history: Sequence[Mapping[str, str]],
        products: Sequence[ProductResponse],
    ) -> ChatOrderSlots:
        history_text = "\n".join(
            f"{item['role']}: {item['content']}" for item in history[-8:] if item.get("content")
        )
        product_lines = "\n".join(
            self._format_product_catalog_line(product) for product in products
        )
        prompt = f"""
Trích thông tin đặt sản phẩm từ lịch sử chat và tin mới. Chỉ trả về JSON hợp lệ.

Các trường:
- product: tên/brand/SKU sản phẩm khách muốn mua, hoặc null
- quantity: số lượng sản phẩm/bình, hoặc null
- customer_name: tên khách, hoặc null
- customer_phone: số điện thoại, hoặc null
- delivery_address: địa chỉ giao hàng đầy đủ gồm số nhà, tên/số đường, khu phố,
  phường, TP.HCM; với Hiệp Bình cần khu phố; hoặc null
- payment_method: "cod" hoặc "bank_transfer", hoặc null
- confirmed: true nếu khách xác nhận rõ đơn Qiki đã tóm tắt ở lượt trước; ngược lại false

Không tự suy đoán hoặc tự điền số điện thoại. Nếu tin mới có dãy số khách đưa
nhưng không chắc hợp lệ, vẫn trả nguyên dãy số đó trong customer_phone để hệ thống kiểm tra.
Chỉ chọn product từ danh sách sản phẩm có thể chọn; không dùng kiến thức ngoài catalog.

Sản phẩm có thể chọn:
{product_lines}

Lịch sử:
{history_text}

Tin mới:
{content}
""".strip()
        response = await self.llm_provider.generate(
            prompt,
            system_prompt="Bạn là bộ trích xuất JSON cho luồng đặt hàng qua chat.",
            temperature=0,
            max_tokens=512,
        )
        payload = self._parse_json_object(response.text)
        return ChatOrderSlots(
            product=self._optional_str(payload.get("product")),
            quantity=self._optional_int(payload.get("quantity")),
            customer_name=self._optional_str(payload.get("customer_name")),
            customer_phone=self._optional_str(payload.get("customer_phone")),
            delivery_address=self._optional_str(payload.get("delivery_address")),
            payment_method=self._optional_str(payload.get("payment_method")),
            confirmed=self._normalize_confirmation(payload.get("confirmed", False)),
        )

    async def _create_rag_answer(
        self,
        conversation: Conversation,
        content: str,
        history: Sequence[Mapping[str, str]],
        user: User | None,
        intent: IntentCategory,
        confidence: float,
        catalog_products: Sequence[ProductResponse] | None = None,
    ) -> Message:
        if intent == IntentCategory.SAFETY_EMERGENCY:
            product_context = None
        elif catalog_products is not None:
            product_context = self._build_product_catalog_context(catalog_products)
        else:
            product_context = self._build_product_catalog_context(
                await self.product_service.list_active_catalog(limit=50)
            )
        response = await self.rag_pipeline.query(
            content,
            conversation_history=history,
            conversation_id=conversation.id,
            user_id=user.id if user else None,
            product_context=product_context,
        )
        return await self.message_repository.create(
            {
                "conversation_id": conversation.id,
                "role": "assistant",
                "content": response.answer,
                "intent": intent.value,
                "intent_confidence": confidence,
                "llm_provider": response.llm_response.provider if response.llm_response else None,
                "llm_model": response.llm_response.model if response.llm_response else None,
                "tokens_used": response.llm_response.total_tokens
                if response.llm_response
                else None,
                "latency_ms": response.total_latency_ms,
                "retrieved_documents": self._serialize_sources(response),
                "flagged_for_review": confidence < 0.6,
            }
        )

    def _build_product_catalog_context(self, products: Sequence[ProductResponse]) -> str | None:
        if not products:
            return None

        lines = ["Bảng giá sản phẩm hiện có:"]
        for product in products:
            lines.append(self._format_product_catalog_line(product))
        return "\n".join(lines)

    @classmethod
    def _format_product_catalog_line(cls, product: ProductResponse) -> str:
        display_name = cls._format_product_display_name(product)
        price = cls._format_vnd(product.price)
        stock = (
            f"còn {product.stock_quantity} bình" if product.stock_quantity > 0 else "tạm hết hàng"
        )
        category = "nước uống" if product.category == "nuoc_uong" else "gas"
        return f"- {display_name} ({product.brand}, {category}): {price}, {stock}"

    @classmethod
    def _format_product_display_name(cls, product: ProductResponse) -> str:
        size = f"{cls._format_decimal(product.size_kg)} {product.unit}"
        normalized_name = product.name.lower().replace(" ", "")
        if size.lower().replace(" ", "") in normalized_name:
            return product.name
        return f"{product.name} {size}"

    @staticmethod
    def _format_vnd(price: Decimal) -> str:
        return f"{int(price):,}".replace(",", ".") + "đ"

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        text = format(value, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text

    @staticmethod
    def _product_to_card(product: ProductResponse) -> ProductCardResponse:
        return ProductCardResponse(
            id=product.id,
            name=product.name,
            brand=product.brand,
            size_kg=product.size_kg,
            unit=product.unit,
            price=product.price,
            image_url=str(product.image_url) if product.image_url else None,
            sku=product.sku,
            stock_quantity=product.stock_quantity,
        )

    def _select_card_products(
        self,
        query: str,
        products: Sequence[ProductResponse],
    ) -> list[ProductResponse]:
        """Pick which product cards to attach for a query.

        A specific question that names a brand and/or cylinder size returns only
        the matching products. A broad or advice-style question (no brand or
        size mentioned) returns the whole catalog so the customer can browse.
        """
        normalized_query = self._normalize_match_text(query)
        if not normalized_query:
            return list(products)
        query_tokens = set(normalized_query.split())
        category_filter = self._category_filter_from_query(normalized_query)
        candidate_products = (
            [product for product in products if product.category == category_filter]
            if category_filter
            else list(products)
        )
        if not candidate_products:
            return []

        brand_and_size: list[ProductResponse] = []
        brand_only: list[ProductResponse] = []
        size_only: list[ProductResponse] = []
        for product in candidate_products:
            normalized_brand = self._normalize_match_text(product.brand)
            brand_tokens = set(normalized_brand.split())
            distinctive_brand_tokens = brand_tokens - {"gas"}
            brand_hit = bool(distinctive_brand_tokens) and (
                bool(distinctive_brand_tokens & query_tokens)
                or normalized_brand in normalized_query
            )
            size_value = self._normalize_match_text(self._format_decimal(product.size_kg))
            unit_value = self._normalize_match_text(product.unit)
            size_hit = (
                f"{size_value}kg" in normalized_query
                or f"{size_value}{unit_value}" in normalized_query.replace(" ", "")
                or (size_value in query_tokens and unit_value in query_tokens)
            )
            if brand_hit and size_hit:
                brand_and_size.append(product)
            elif brand_hit:
                brand_only.append(product)
            elif size_hit:
                size_only.append(product)

        for group in (brand_and_size, brand_only, size_only):
            if group:
                return group
        return candidate_products

    @staticmethod
    def _category_filter_from_query(normalized_query: str) -> str | None:
        tokens = set(normalized_query.split())
        wants_water = "nuoc" in tokens
        wants_gas = "gas" in tokens
        if wants_water and not wants_gas:
            return "nuoc_uong"
        if wants_gas and not wants_water:
            return "gas"
        return None

    @classmethod
    def _is_bare_category_query(cls, query: str | None) -> bool:
        if not query:
            return False
        normalized = cls._normalize_match_text(query)
        return normalized in {"nuoc", "nuoc uong", "gas", "binh gas"}

    @classmethod
    def _format_category_product_question(cls, query: str) -> str:
        category = cls._category_filter_from_query(cls._normalize_match_text(query))
        if category == "nuoc_uong":
            return "Bạn muốn đặt loại nước uống nào? Qiki gửi các lựa chọn bên dưới nhé."
        if category == "gas":
            return "Bạn muốn đặt loại gas nào? Qiki gửi các lựa chọn bên dưới nhé."
        return "Bạn muốn đặt sản phẩm nào? Qiki gửi các lựa chọn bên dưới nhé."

    async def _create_assistant_message(
        self,
        conversation: Conversation,
        content: str,
        intent: IntentCategory,
        confidence: float,
        metadata: list[dict[str, Any]] | None = None,
    ) -> Message:
        return await self.message_repository.create(
            {
                "conversation_id": conversation.id,
                "role": "assistant",
                "content": content,
                "intent": intent.value,
                "intent_confidence": confidence,
                "latency_ms": 0,
                "retrieved_documents": metadata or [],
                "flagged_for_review": confidence < 0.6,
            }
        )

    async def _create_chat_order_with_retry(
        self,
        checkout: CheckoutRequest,
        user: User | None,
        idempotency_key: UUID,
    ) -> OrderResponse:
        last_error: BaseException | None = None
        for attempt in range(3):
            try:
                return await self.order_service.create_order(
                    checkout,
                    current_user=user,
                    idempotency_key=idempotency_key,
                    session=self.session,
                )
            except DBAPIError as exc:
                await self.session.rollback()
                if not is_serialization_failure(exc):
                    raise
                last_error = exc
                if attempt == 2:
                    raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("chat order creation failed without an exception")

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                return {}
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _optional_str(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None or value == "":
            return None
        try:
            parsed = int(str(value))
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @classmethod
    def _normalize_confirmation(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = cls._normalize_match_text(value)
            return normalized in {
                "true",
                "yes",
                "y",
                "ok",
                "okay",
                "dong y",
                "xac nhan",
                "dung",
                "dung r",
                "dung roi",
            }
        return False

    @classmethod
    def _with_phone_candidate(cls, slots: ChatOrderSlots, content: str) -> ChatOrderSlots:
        candidate = cls._extract_phone_candidate(content)
        if not candidate:
            return slots
        if slots.customer_phone and cls._validate_phone(slots.customer_phone) is not None:
            return slots
        return replace(slots, customer_phone=candidate)

    @classmethod
    def _with_order_cues(cls, slots: ChatOrderSlots, content: str) -> ChatOrderSlots:
        payment_method = slots.payment_method or cls._extract_payment_candidate(content)
        customer_name = slots.customer_name or cls._extract_name_candidate(content, payment_method)
        return replace(slots, customer_name=customer_name, payment_method=payment_method)

    @classmethod
    def _extract_payment_candidate(cls, content: str) -> str | None:
        normalized = cls._normalize_match_text(content)
        tokens = set(normalized.split())
        if "cod" in tokens or "tien mat" in normalized or "nhan hang" in normalized:
            return "cod"
        if "ck" in tokens or "chuyen khoan" in normalized or "khoan" in tokens:
            return "bank_transfer"
        return None

    @classmethod
    def _extract_name_candidate(cls, content: str, payment_method: str | None) -> str | None:
        if payment_method is None:
            return None
        text = re.sub(r"\+?\d[\d\s.-]{1,}\d", " ", content)
        text = re.sub(r"\b(cod|cash|ck)\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(tiền mặt|tien mat|chuyển khoản|chuyen khoan)\b", " ", text)
        words = re.findall(r"[A-Za-zÀ-ỹ]+", text)
        ignored = {"ok", "okay", "dong", "dung", "roi", "phai", "thanh", "toan"}
        name_words = [
            word.strip() for word in words if cls._normalize_match_text(word) not in ignored
        ]
        if not name_words or len(name_words) > 3:
            return None
        return " ".join(name_words).title()

    @staticmethod
    def _extract_phone_candidate(content: str) -> str | None:
        for match in re.finditer(r"\+?\d[\d\s.-]{1,}\d", content):
            candidate = match.group(0).strip()
            digits = re.sub(r"\D", "", candidate)
            if len(digits) >= 3:
                return "+" + digits if candidate.startswith("+") else digits
        return None

    @classmethod
    def _infer_order_slots(
        cls,
        content: str,
        products: Sequence[ProductResponse],
    ) -> ChatOrderSlots:
        matched_product = cls._match_product(content, products)
        quantity = cls._extract_quantity_candidate(content)
        return ChatOrderSlots(
            product=cls._format_product_display_name(matched_product)
            if matched_product is not None
            else None,
            quantity=quantity,
        )

    @classmethod
    def _looks_like_order_request(
        cls,
        content: str,
        products: Sequence[ProductResponse],
    ) -> bool:
        inferred = cls._infer_order_slots(content, products)
        return bool(inferred.product and inferred.quantity)

    @classmethod
    def _extract_quantity_candidate(cls, content: str) -> int | None:
        normalized = cls._normalize_match_text(content)
        digit_match = re.search(
            r"\b([1-9][0-9]?)\s*(binh|chai|can|thung)\b",
            normalized,
        )
        if digit_match:
            return int(digit_match.group(1))
        words = {
            "mot": 1,
            "hai": 2,
            "ba": 3,
            "bon": 4,
            "tu": 4,
            "nam": 5,
        }
        for word, value in words.items():
            if re.search(rf"\b{word}\s*(binh|chai|can|thung)?\b", normalized):
                return value
        return None

    @staticmethod
    def _merge_order_slots(*sources: ChatOrderSlots | None) -> ChatOrderSlots:
        merged = ChatOrderSlots()
        for source in sources:
            if source is None:
                continue
            merged = replace(
                merged,
                product=source.product or merged.product,
                quantity=source.quantity or merged.quantity,
                customer_name=source.customer_name or merged.customer_name,
                customer_phone=source.customer_phone or merged.customer_phone,
                delivery_address=source.delivery_address or merged.delivery_address,
                payment_method=source.payment_method or merged.payment_method,
                confirmed=merged.confirmed or source.confirmed,
            )
        return merged

    @staticmethod
    def _slots_to_metadata(slots: ChatOrderSlots | None) -> dict[str, Any]:
        if slots is None:
            return {}
        payload: dict[str, Any] = {}
        if slots.product:
            payload["product"] = slots.product
        if slots.quantity is not None:
            payload["quantity"] = slots.quantity
        if slots.customer_name:
            payload["customer_name"] = slots.customer_name
        if slots.customer_phone:
            payload["customer_phone"] = slots.customer_phone
        if slots.delivery_address:
            payload["delivery_address"] = slots.delivery_address
        if slots.payment_method:
            payload["payment_method"] = slots.payment_method
        return payload

    @classmethod
    def _slots_from_metadata(cls, payload: object) -> ChatOrderSlots | None:
        if not isinstance(payload, dict):
            return None
        return ChatOrderSlots(
            product=cls._optional_str(payload.get("product")),
            quantity=cls._optional_int(payload.get("quantity")),
            customer_name=cls._optional_str(payload.get("customer_name")),
            customer_phone=cls._optional_str(payload.get("customer_phone")),
            delivery_address=cls._optional_str(payload.get("delivery_address")),
            payment_method=cls._optional_str(payload.get("payment_method")),
        )

    @classmethod
    def _is_affirmation(cls, content: str) -> bool:
        normalized = cls._normalize_match_text(content)
        return normalized in {
            "dung",
            "dung r",
            "dung roi",
            "ok",
            "okay",
            "uh",
            "u",
            "phai",
            "phai roi",
            "xac nhan",
        }

    @classmethod
    def _missing_order_slots(
        cls,
        slots: ChatOrderSlots,
        matched_product: ProductResponse | None,
    ) -> list[str]:
        missing: list[str] = []
        if matched_product is None:
            missing.append("sản phẩm")
        if slots.quantity is None:
            missing.append("số lượng")
        if not slots.customer_name:
            missing.append("tên người nhận")
        if not slots.customer_phone:
            missing.append("số điện thoại")
        if not slots.delivery_address:
            missing.append(
                "địa chỉ giao hàng chi tiết (số nhà, tên/số đường, khu phố, phường, "
                "TP.HCM; với Hiệp Bình cần khu phố)"
            )
        if not slots.payment_method:
            missing.append("hình thức thanh toán")
        return missing

    @staticmethod
    def _format_missing_slot_question(missing: Sequence[str]) -> str:
        if len(missing) == 1:
            return f"Bạn cho Qiki xin thêm {missing[0]} để lên đơn nhé."
        return (
            "Bạn cho Qiki xin thêm "
            + ", ".join(missing[:-1])
            + f" và {missing[-1]} để lên đơn nhé."
        )

    @staticmethod
    def _format_invalid_phone_question(phone: str) -> str:
        return (
            f"Số **{phone}** có vẻ chưa đúng định dạng SĐT Việt Nam "
            "(10 số, đầu 03/05/07/08/09). Bạn cho Qiki xin lại SĐT nhé."
        )

    @classmethod
    def _match_product(
        cls,
        product_query: str | None,
        products: Sequence[ProductResponse],
    ) -> ProductResponse | None:
        if not product_query:
            return None
        query = cls._normalize_match_text(product_query)
        best_product: ProductResponse | None = None
        best_score = 0
        for product in products:
            fields = [
                product.name,
                product.brand,
                product.sku,
                cls._format_product_display_name(product),
                f"{cls._format_decimal(product.size_kg)}kg",
                f"{cls._format_decimal(product.size_kg)} {product.unit}",
                f"{cls._format_decimal(product.size_kg)}{product.unit}",
            ]
            haystack = " ".join(cls._normalize_match_text(field) for field in fields)
            score = 0
            if query and query in haystack:
                score += 4
            for token in query.split():
                if token in haystack:
                    score += 1
            if score > best_score:
                best_score = score
                best_product = product
        return best_product if best_score > 0 else None

    @staticmethod
    def _normalize_match_text(value: str) -> str:
        decomposed = unicodedata.normalize("NFD", value.lower())
        without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
        return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()

    @staticmethod
    def _validate_phone(phone: str) -> str | None:
        try:
            return VietnamesePhoneValidator.validate(phone)
        except ValueError:
            return None

    @classmethod
    def _normalize_payment_method(
        cls, payment_method: str
    ) -> Literal["cod", "bank_transfer"] | None:
        normalized = cls._normalize_match_text(payment_method)
        if normalized in {"cod", "cash", "tien mat"} or "nhan hang" in normalized:
            return "cod"
        if (
            normalized in {"bank transfer", "bank_transfer", "chuyen khoan", "ck"}
            or "khoan" in normalized
        ):
            return "bank_transfer"
        return None

    @classmethod
    def _format_order_callback_sentence(cls) -> str:
        now = cls._now_vn()
        if cls._is_business_open(now):
            return (
                "**Nhân viên sẽ sớm gọi điện lại xác nhận** đơn trong giờ làm việc "
                "(T2-T6 06:30-20:00, T7-CN 07:30-20:00). Cảm ơn bạn!"
            )
        return (
            "Hiện đã ngoài giờ làm việc. "
            f"Nhân viên sẽ gọi lại xác nhận đơn vào {cls._next_opening_label(now)}. "
            "Cảm ơn bạn!"
        )

    @staticmethod
    def _now_vn() -> datetime:
        return datetime.now(VN_TIMEZONE)

    @classmethod
    def _is_business_open(cls, now: datetime) -> bool:
        opening, closing = cls._business_hours_for_weekday(now.weekday())
        current = now.time().replace(tzinfo=None)
        return opening <= current < closing

    @classmethod
    def _next_opening_label(cls, now: datetime) -> str:
        for day_offset in range(8):
            candidate_date = now.date() + timedelta(days=day_offset)
            opening, closing = cls._business_hours_for_weekday(candidate_date.weekday())
            if day_offset == 0 and now.time().replace(tzinfo=None) < closing:
                next_open = datetime.combine(candidate_date, opening, tzinfo=VN_TIMEZONE)
                break
            if day_offset > 0:
                next_open = datetime.combine(candidate_date, opening, tzinfo=VN_TIMEZONE)
                break
        else:
            next_open = now + timedelta(days=1)

        time_text = next_open.strftime("%H:%M")
        if next_open.date() == now.date():
            return f"hôm nay từ {time_text}"
        if next_open.date() == now.date() + timedelta(days=1):
            prefix = "sáng mai" if next_open.time() < time(12, 0) else "ngày mai"
            return f"{prefix} từ {time_text}"
        weekday_names = [
            "thứ Hai",
            "thứ Ba",
            "thứ Tư",
            "thứ Năm",
            "thứ Sáu",
            "thứ Bảy",
            "Chủ nhật",
        ]
        return f"{weekday_names[next_open.weekday()]} từ {time_text}"

    @staticmethod
    def _business_hours_for_weekday(weekday: int) -> tuple[time, time]:
        opening = time(6, 30) if weekday < 5 else time(7, 30)
        return opening, time(20, 0)

    @classmethod
    def _format_order_summary(
        cls,
        product: ProductResponse,
        quantity: int,
        customer_name: str,
        phone: str,
        address: str,
        payment_method: Literal["cod", "bank_transfer"],
    ) -> str:
        subtotal = product.price * quantity
        payment_label = "COD" if payment_method == "cod" else "chuyển khoản"
        return "\n".join(
            [
                "Qiki tóm tắt đơn hàng của bạn:",
                f"- Sản phẩm: **{product.name}** ({product.brand})",
                f"- Số lượng: **{quantity}** bình",
                f"- Đơn giá: **{cls._format_vnd(product.price)}**",
                f"- Thành tiền tạm tính: **{cls._format_vnd(subtotal)}**",
                f"- Người nhận: **{customer_name}**",
                f"- Số điện thoại: **{phone}**",
                f"- Địa chỉ: **{address}**",
                f"- Thanh toán: **{payment_label}**",
                "",
                ORDER_CONFIRMATION_PROMPT,
            ]
        )

    @staticmethod
    def _chat_order_idempotency_key(conversation_id: UUID, slots: ChatOrderSlots) -> UUID:
        fingerprint = "|".join(
            [
                str(conversation_id),
                slots.product or "",
                str(slots.quantity or ""),
                slots.customer_phone or "",
                slots.delivery_address or "",
            ]
        )
        return uuid5(NAMESPACE_URL, f"chat-order:{fingerprint}")

    @staticmethod
    def _find_existing_chat_order(history: Sequence[Message]) -> dict[str, Any] | None:
        for message in reversed(history):
            documents = message.retrieved_documents or []
            if not isinstance(documents, list):
                continue
            for document in documents:
                if (
                    isinstance(document, dict)
                    and document.get("type") == CHAT_ORDER_METADATA_TYPE
                    and document.get("order_number")
                ):
                    return document
        return None

    @classmethod
    def _apply_order_context_intent(
        cls, intent: IntentResult, history: Sequence[Message]
    ) -> IntentResult:
        if intent.category == IntentCategory.SAFETY_EMERGENCY:
            return intent
        if not cls._is_order_in_progress(history):
            return intent
        return cls._order_context_intent(intent, "order_in_progress")

    @staticmethod
    def _order_context_intent(intent: IntentResult, reason: str) -> IntentResult:
        return IntentResult(
            category=IntentCategory.PLACE_ORDER,
            confidence=max(intent.confidence, ORDER_CONTEXT_CONFIDENCE),
            reasoning=f"{reason} override: {intent.reasoning}",
            classifier=f"{intent.classifier}+order_context",
        )

    @classmethod
    def _is_order_in_progress(cls, history: Sequence[Message]) -> bool:
        for message in reversed(history):
            if message.role != "assistant":
                continue
            documents = message.retrieved_documents or []
            if not isinstance(documents, list):
                return False
            if cls._has_metadata_type(documents, CHAT_ORDER_METADATA_TYPE):
                return False
            return cls._has_metadata_type(documents, CHAT_ORDER_STATE_METADATA_TYPE)
        return False

    @classmethod
    def _find_order_state(cls, history: Sequence[Message]) -> dict[str, Any] | None:
        for message in reversed(history):
            if message.role != "assistant":
                continue
            documents = message.retrieved_documents or []
            if not isinstance(documents, list):
                continue
            for document in documents:
                if (
                    isinstance(document, dict)
                    and document.get("type") == CHAT_ORDER_STATE_METADATA_TYPE
                ):
                    return document
        return None

    @classmethod
    def _slots_from_order_state(cls, order_state: dict[str, Any] | None) -> ChatOrderSlots | None:
        if order_state is None:
            return None
        return cls._slots_from_metadata(order_state.get("slots"))

    @classmethod
    def _order_state_metadata(
        cls,
        status: str,
        slots: ChatOrderSlots | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {"type": CHAT_ORDER_STATE_METADATA_TYPE, "status": status}
        slot_payload = cls._slots_to_metadata(slots)
        if slot_payload:
            metadata["slots"] = slot_payload
        return metadata

    @staticmethod
    def _has_metadata_type(documents: Sequence[object], metadata_type: str) -> bool:
        return any(
            isinstance(document, dict) and document.get("type") == metadata_type
            for document in documents
        )

    async def _create_handoff_message(
        self,
        conversation: Conversation,
        routing: RoutingDecision,
    ) -> Message:
        content = (
            "Cảm ơn bạn đã chia sẻ. Mình đã chuyển cuộc trò chuyện này cho nhân viên "
            "hỗ trợ để xử lý kỹ hơn."
        )
        return await self.message_repository.create(
            {
                "conversation_id": conversation.id,
                "role": "assistant",
                "content": content,
                "latency_ms": 0,
                "retrieved_documents": [],
                "flagged_for_review": routing.priority <= 1,
            }
        )

    async def _require_conversation(self, conversation_id: UUID) -> Conversation:
        conversation = await self.conversation_repository.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation not found", error_code="conversation_not_found")
        return conversation

    @staticmethod
    def _history_to_payload(messages: Sequence[Message]) -> list[dict[str, str]]:
        return [{"role": message.role, "content": message.content} for message in messages]

    @staticmethod
    def _serialize_sources(response: RAGResponse) -> list[dict[str, Any]]:
        return [
            {
                "id": str(source.id),
                "title": source.title,
                "category": source.category,
                "similarity": source.similarity,
                "source_type": source.source_type,
            }
            for source in response.sources
            if isinstance(source, RetrievedDocument)
        ]

    def _conversation_to_response(self, conversation: Conversation) -> ConversationResponse:
        return ConversationResponse(
            id=conversation.id,
            user_id=conversation.user_id,
            session_id=conversation.session_id,
            status=conversation.status,  # type: ignore[arg-type]
            assigned_to=conversation.assigned_to,
            escalated_at=conversation.escalated_at,
            escalation_reason=conversation.escalation_reason,
            resolved_at=conversation.resolved_at,
            satisfaction_rating=conversation.satisfaction_rating,
            messages=[self._message_to_response(message) for message in conversation.messages],
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )

    @staticmethod
    def _message_to_response(message: Message) -> MessageResponse:
        return MessageResponse(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role,  # type: ignore[arg-type]
            content=message.content,
            intent=message.intent,
            intent_confidence=(
                float(message.intent_confidence) if message.intent_confidence is not None else None
            ),
            llm_provider=message.llm_provider,
            llm_model=message.llm_model,
            tokens_used=message.tokens_used,
            latency_ms=message.latency_ms,
            retrieved_documents=message.retrieved_documents,
            feedback_score=message.feedback_score,
            flagged_for_review=message.flagged_for_review,
            is_emergency=message.intent == IntentCategory.SAFETY_EMERGENCY.value,
            created_at=message.created_at,
        )
