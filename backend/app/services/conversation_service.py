"""Conversation orchestration service for chatbot and staff messages."""

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.input_validation import VietnamesePhoneValidator
from app.intent.base import BaseIntentClassifier
from app.intent.categories import IntentCategory
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
ORDER_CONFIRMATION_PROMPT = "Bạn xác nhận đặt đơn này không?"


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

        catalog_products: list[ProductResponse] | None = None
        product_cards: list[ProductCardResponse] = []
        if intent.category in {IntentCategory.PRODUCT_INQUIRY, IntentCategory.PLACE_ORDER}:
            catalog_products = await self.product_service.list_active_catalog(limit=50)
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
            assistant_message = await self._handle_chat_order(
                conversation,
                request.content,
                history,
                history_payload,
                user,
                intent.confidence,
                catalog_products or [],
            )
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
    ) -> Message:
        existing_order = self._find_existing_chat_order(history)
        if existing_order:
            order_number = str(existing_order.get("order_number", ""))
            return await self._create_assistant_message(
                conversation,
                (
                    f"Đơn **{order_number}** đã được ghi nhận trước đó. "
                    "Nhân viên sẽ sớm gọi điện lại xác nhận với bạn trong giờ làm việc."
                ),
                IntentCategory.PLACE_ORDER,
                confidence,
                metadata=[existing_order],
            )

        slots = await self._extract_order_slots(content, history_payload, products)
        matched_product = self._match_product(slots.product, products)
        missing = self._missing_order_slots(slots, matched_product)
        if missing:
            return await self._create_assistant_message(
                conversation,
                self._format_missing_slot_question(missing),
                IntentCategory.PLACE_ORDER,
                confidence,
            )

        assert slots.quantity is not None
        assert slots.customer_name is not None
        assert slots.customer_phone is not None
        assert slots.delivery_address is not None
        assert slots.payment_method is not None
        assert matched_product is not None

        delivery_zone_match = resolve_ward_delivery_zone(slots.delivery_address)
        if delivery_zone_match is None:
            return await self._create_assistant_message(
                conversation,
                (
                    "Hiện Gas Quốc Cường chỉ giao trong khu vực Bình Thạnh và Thủ Đức. "
                    "Địa chỉ này chưa thuộc khu vực Qiki có thể nhận đơn qua chat. "
                    "Bạn có thể gọi 090 3026306 để được nhân viên hỗ trợ thêm."
                ),
                IntentCategory.PLACE_ORDER,
                confidence,
            )

        normalized_phone = self._validate_phone(slots.customer_phone)
        if normalized_phone is None:
            return await self._create_assistant_message(
                conversation,
                "Bạn cho Qiki xin số điện thoại hợp lệ để nhân viên gọi xác nhận đơn nhé.",
                IntentCategory.PLACE_ORDER,
                confidence,
            )

        if matched_product.stock_quantity < slots.quantity:
            return await self._create_assistant_message(
                conversation,
                (
                    f"Sản phẩm **{matched_product.name}** hiện chỉ còn "
                    f"{matched_product.stock_quantity} bình. Bạn muốn điều chỉnh số lượng không?"
                ),
                IntentCategory.PLACE_ORDER,
                confidence,
            )

        payment_method = self._normalize_payment_method(slots.payment_method)
        if payment_method is None:
            return await self._create_assistant_message(
                conversation,
                "Bạn muốn thanh toán khi nhận hàng (COD) hay chuyển khoản?",
                IntentCategory.PLACE_ORDER,
                confidence,
            )

        if not slots.confirmed:
            return await self._create_assistant_message(
                conversation,
                self._format_order_summary(
                    matched_product,
                    slots.quantity,
                    slots.customer_name,
                    normalized_phone,
                    slots.delivery_address,
                    payment_method,
                ),
                IntentCategory.PLACE_ORDER,
                confidence,
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
        return await self._create_assistant_message(
            conversation,
            (
                f"Đã ghi nhận đơn **{order.order_number}**. "
                "**Nhân viên sẽ sớm gọi điện lại xác nhận** với bạn trong giờ làm việc "
                "(T2-T6 06:30-20:00, T7-CN 07:30-20:00). Cảm ơn bạn!"
            ),
            IntentCategory.PLACE_ORDER,
            confidence,
            metadata=metadata,
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
Trích thông tin đặt gas từ lịch sử chat và tin mới. Chỉ trả về JSON hợp lệ.

Các trường:
- product: tên/brand/SKU sản phẩm khách muốn mua, hoặc null
- quantity: số lượng bình, hoặc null
- customer_name: tên khách, hoặc null
- customer_phone: số điện thoại, hoặc null
- delivery_address: địa chỉ giao hàng đầy đủ, hoặc null
- payment_method: "cod" hoặc "bank_transfer", hoặc null
- confirmed: true nếu khách xác nhận rõ đơn Qiki đã tóm tắt ở lượt trước; ngược lại false

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
        return f"- {display_name} ({product.brand}): {price}, {stock}"

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
        return format(value.normalize(), "f").rstrip("0").rstrip(".")

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

        brand_and_size: list[ProductResponse] = []
        brand_only: list[ProductResponse] = []
        size_only: list[ProductResponse] = []
        for product in products:
            normalized_brand = self._normalize_match_text(product.brand)
            brand_tokens = set(normalized_brand.split())
            distinctive_brand_tokens = brand_tokens - {"gas"}
            brand_hit = bool(distinctive_brand_tokens) and (
                bool(distinctive_brand_tokens & query_tokens)
                or normalized_brand in normalized_query
            )
            size_value = self._normalize_match_text(self._format_decimal(product.size_kg))
            size_hit = f"{size_value}kg" in normalized_query or size_value in query_tokens
            if brand_hit and size_hit:
                brand_and_size.append(product)
            elif brand_hit:
                brand_only.append(product)
            elif size_hit:
                size_only.append(product)

        for group in (brand_and_size, brand_only, size_only):
            if group:
                return group
        return list(products)

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
            return normalized in {"true", "yes", "y", "ok", "okay", "dong y", "xac nhan", "dung"}
        return False

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
            missing.append("địa chỉ giao hàng")
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
            normalized in {"bank transfer", "bank_transfer", "chuyen khoan"}
            or "khoan" in normalized
        ):
            return "bank_transfer"
        return None

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
