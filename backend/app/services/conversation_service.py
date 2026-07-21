"""Conversation orchestration service for chatbot and staff messages."""

import json
import re
import unicodedata
from asyncio import shield
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, time, timedelta, timezone
from decimal import Decimal
from time import monotonic
from typing import Any, Literal, cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundException
from app.core.input_validation import VietnamesePhoneValidator
from app.core.language import detect_language
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
from app.services.address_lookup import resolve_ward_delivery_zone, validate_khu_pho
from app.services.order_service import OrderService, is_serialization_failure
from app.services.product_query import (
    ProductQuery,
    filter_products,
    parse_product_query,
)
from app.services.product_service import ProductService
from app.services.routing_service import RoutingDecision, RoutingService

CHAT_ORDER_METADATA_TYPE = "chat_order"
CHAT_ORDER_STATE_METADATA_TYPE = "chat_order_state"
# Structured note for staff follow-up (call-back / delivery time) stored in a
# message's retrieved_documents, surfaced as-is via the admin conversation payload.
CHAT_FOLLOWUP_NOTE_METADATA_TYPE = "chat_followup_note"
ORDER_CONFIRMATION_PROMPT = "Bạn xác nhận đặt đơn này không?"
ORDER_CONTEXT_CONFIDENCE = 0.9
ORDER_STATE_TTL = timedelta(minutes=30)
VN_TIMEZONE = timezone(timedelta(hours=7))
GENERIC_PRODUCT_MATCH_TOKENS = {
    "binh",
    "gas",
    "chai",
    "can",
    "thung",
    "lit",
    "nuoc",
    "uong",
    "kg",
}
ADDRESS_MARKER_TOKENS = {
    "duong",
    "phuong",
    "quan",
    "hem",
    "ngo",
    "xa",
    "ap",
    "kp",
    "tphcm",
    "tp",
}
ADDRESS_MARKER_PHRASES = ("khu pho", "thanh pho", "so nha")
AMBIGUOUS_DELIVERY_PERIODS = {"sang", "trua", "chieu", "toi", "dem"}
# Accent-stripped buổi keyword -> display label for follow-up time windows.
FOLLOWUP_PERIOD_LABELS = {"sang": "sáng", "trua": "trưa", "chieu": "chiều", "toi": "tối"}

# Accent-stripped cues that mark an "enumerate the options" request. A list query
# is answered as a compact deterministic price list (no cards); a browse query is
# allowed to fall back to the whole (category) catalog as cards.
CATALOG_LIST_CUES = (
    "cac loai",
    "nhung loai",
    "loai nao",
    "cac hang",
    "nhung hang",
    "danh sach",
    "tat ca",
    "menu",
    "co nhung",
    "gom nhung",
    "bao nhieu loai",
    "co gi",
)
CATALOG_BROWSE_CUES = (*CATALOG_LIST_CUES, "san pham")

# Deterministic first-message greeting (no LLM call) shown when a chat opens.
# Kept consistent with the Qiki persona in system_chatbot_vi.txt.
GREETING_INTRO_VI = (
    "Mình là Qiki, trợ lý ảo của Cửa hàng Gas Quốc Cường. "
    "Mình có thể giúp bạn tìm sản phẩm, xem giá, đặt gas hoặc nước uống, "
    "tra cứu thông tin giao hàng và giải đáp thắc mắc về gas. "
    "Bạn cần Qiki hỗ trợ gì hôm nay?"
)
GREETING_INTRO_EN = (
    "I'm Qiki, the virtual assistant of Gas Quốc Cường Store. "
    "I can help you find products, check prices, order gas or drinking water, "
    "look up delivery info, and answer your gas-related questions. "
    "How can Qiki help you today?"
)


@dataclass(frozen=True)
class ChatOrderItem:
    """One product line in a chat order."""

    product: str | None = None
    quantity: int | None = None


@dataclass(frozen=True)
class ChatOrderSlots:
    """Order details extracted from chat history."""

    items: tuple[ChatOrderItem, ...] = ()
    customer_name: str | None = None
    customer_phone: str | None = None
    delivery_address: str | None = None
    delivery_notes: str | None = None
    payment_method: str | None = None
    confirmed: bool = False


@dataclass(frozen=True)
class ChatOrderResult:
    """Assistant reply plus contextual product cards for an order turn."""

    message: Message
    card_products: list[ProductResponse]


@dataclass
class RagStreamPlan:
    """Descriptor for a RAG answer that should be streamed token-by-token."""

    content: str
    history: list[dict[str, str]]
    catalog_products: list[ProductResponse] | None
    intent: IntentCategory
    confidence: float
    locale: str


@dataclass
class ResponsePlan:
    """The outcome of planning a customer turn, shared by the blocking and
    streaming endpoints so the (complex) decision tree lives in one place.

    Exactly one of ``assistant_message`` (a deterministic reply already persisted)
    or ``rag_stream`` (a RAG answer still to be generated/streamed) is set.
    """

    user_message: Message
    conversation: Conversation
    product_cards: list[ProductCardResponse]
    assistant_message: Message | None
    rag_stream: RagStreamPlan | None


@dataclass
class StreamDelta:
    """A chunk of assistant text to append to the current bubble."""

    text: str


@dataclass
class StreamDone:
    """Terminal event carrying the fully-persisted turn (message + products)."""

    response: SendMessageResponse


StreamEvent = StreamDelta | StreamDone


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
        locale: str | None = None,
    ) -> ConversationResponse:
        """Start a new conversation, greeting the customer as the first message.

        ``locale`` is the storefront UI language; the greeting follows it so an
        English UI is greeted in English, and it biases the reply language of any
        initial message that is otherwise ambiguous.
        """
        ui_locale: Literal["vi", "en"] = "en" if locale == "en" else "vi"
        conversation = await self.conversation_repository.create(
            {
                "user_id": user.id if user else None,
                "session_id": session_id or str(uuid4()),
                "status": "active",
            }
        )
        await self.message_repository.create(
            {
                "conversation_id": conversation.id,
                "role": "assistant",
                "content": self._build_greeting(user, ui_locale),
            }
        )
        if initial_message:
            await self.send_message(
                conversation.id,
                SendMessageRequest(
                    content=initial_message,
                    session_id=conversation.session_id,
                    locale=ui_locale,
                ),
                user,
            )
        # Re-read so the response includes the greeting (and any initial-message turn).
        conversation = await self._require_conversation(conversation.id)
        return self._conversation_to_response(conversation)

    @staticmethod
    def _build_greeting(user: User | None, language: str = "vi") -> str:
        """Build the deterministic opening message in the given language (no LLM)."""
        name = user.full_name if user and user.full_name else None
        if language == "en":
            salutation = f"Hello {name}!" if name else "Hello there!"
            return f"{salutation} {GREETING_INTRO_EN}"
        salutation = f"Chào bạn {name}!" if name else "Chào bạn!"
        return f"{salutation} {GREETING_INTRO_VI}"

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
        """Handle a customer message and optional assistant reply (blocking)."""
        plan = await self._plan_response(conversation_id, request, user)
        assistant_message = plan.assistant_message
        if plan.rag_stream is not None:
            assistant_message = await self._create_rag_answer(
                plan.conversation,
                plan.rag_stream.content,
                plan.rag_stream.history,
                user,
                plan.rag_stream.intent,
                plan.rag_stream.confidence,
                catalog_products=plan.rag_stream.catalog_products,
                locale=plan.rag_stream.locale,
            )
        conversation = await self._require_conversation(plan.conversation.id)
        return SendMessageResponse(
            user_message=self._message_to_response(plan.user_message),
            assistant_message=(
                self._message_to_response(assistant_message) if assistant_message else None
            ),
            conversation=self._conversation_to_response(conversation),
            products=plan.product_cards,
        )

    async def stream_message(
        self,
        conversation_id: UUID,
        request: SendMessageRequest,
        user: User | None,
    ) -> AsyncIterator[StreamEvent]:
        """Plan a turn, stream the RAG answer token-by-token, then persist it.

        Deterministic branches (safety, greeting, price, order, handoff,
        clarification) are already instant and are emitted as a single delta;
        only the open-ended RAG answer streams. Safety never reaches the LLM
        (query_stream returns the fixed constant).
        """
        plan = await self._plan_response(conversation_id, request, user)
        assistant_message = plan.assistant_message
        if plan.rag_stream is None:
            if assistant_message is not None and assistant_message.content:
                yield StreamDelta(assistant_message.content)
        else:
            rag_stream = plan.rag_stream
            start_time = monotonic()
            sources: list[RetrievedDocument] = []
            chunks: list[str] = []
            generation: dict[str, Any] = {}
            product_context = await self._resolve_product_context(
                rag_stream.content,
                rag_stream.intent,
                rag_stream.catalog_products,
            )
            try:
                async for delta in self.rag_pipeline.query_stream(
                    rag_stream.content,
                    conversation_history=rag_stream.history,
                    product_context=product_context,
                    language=detect_language(
                        rag_stream.content,
                        default="en" if rag_stream.locale == "en" else "vi",
                    ),
                    sources_sink=sources,
                    generation_sink=generation,
                ):
                    if not delta:
                        continue
                    chunks.append(delta)
                    yield StreamDelta(delta)
            finally:
                # Persist even if the client disconnects mid-stream (the loop is
                # interrupted by GeneratorExit/CancelledError at a yield) so a
                # partial reply is never lost from history. Shielded so a task
                # cancellation cannot abort the DB write.
                if chunks:
                    assistant_message = await shield(
                        self._persist_streamed_answer(
                            plan.conversation,
                            "".join(chunks),
                            rag_stream.intent,
                            rag_stream.confidence,
                            int((monotonic() - start_time) * 1000),
                            sources,
                            llm_provider=generation.get("provider"),
                            llm_model=generation.get("model"),
                            tokens_used=generation.get("total_tokens"),
                        )
                    )
        conversation = await self._require_conversation(plan.conversation.id)
        yield StreamDone(
            SendMessageResponse(
                user_message=self._message_to_response(plan.user_message),
                assistant_message=(
                    self._message_to_response(assistant_message) if assistant_message else None
                ),
                conversation=self._conversation_to_response(conversation),
                products=plan.product_cards,
            )
        )

    async def _plan_response(
        self,
        conversation_id: UUID,
        request: SendMessageRequest,
        user: User | None,
    ) -> ResponsePlan:
        """Run the full decision tree for a turn (shared by both endpoints).

        Persists the user message and any deterministic assistant reply. For the
        open-ended RAG branch it returns a ``RagStreamPlan`` (not the answer) so the
        caller can block on ``query`` or stream via ``query_stream``.
        """
        conversation = await self._require_conversation(conversation_id)
        history = await self.message_repository.get_recent(conversation_id, limit=10)
        history_payload = self._history_to_payload(history)
        intent = await self.intent_classifier.classify(request.content, history_payload)
        intent = self._apply_order_context_intent(intent, history)
        if (
            intent.category != IntentCategory.SAFETY_EMERGENCY
            and self._extract_ambiguous_delivery_time_window(request.content)
            and self._is_order_in_progress(history)
        ):
            intent = self._order_context_intent(intent, "ambiguous_delivery_time")
        if intent.category != IntentCategory.SAFETY_EMERGENCY and self._is_explicit_human_request(
            request.content
        ):
            intent = IntentResult(
                category=IntentCategory.COMPLAINT,
                confidence=max(intent.confidence, ORDER_CONTEXT_CONFIDENCE),
                reasoning=f"explicit_human_request override: {intent.reasoning}",
                classifier=f"{intent.classifier}+explicit_human_request",
            )
        if (
            intent.category != IntentCategory.SAFETY_EMERGENCY
            and self._find_existing_chat_order(history)
            and self._is_post_order_change_request(request.content)
        ):
            intent = self._order_context_intent(intent, "post_order_change")

        catalog_products: list[ProductResponse] | None = None
        if self._should_load_catalog_for_intent(intent):
            catalog_products = await self.product_service.list_active_catalog(limit=50)
        catalog_override = (
            self._catalog_product_intent_override(request.content, catalog_products)
            if intent.category != IntentCategory.SAFETY_EMERGENCY and catalog_products
            else None
        )
        if catalog_override == IntentCategory.PLACE_ORDER:
            intent = self._order_context_intent(intent, "catalog_product_order")
        elif catalog_override == IntentCategory.PRODUCT_INQUIRY:
            intent = IntentResult(
                category=IntentCategory.PRODUCT_INQUIRY,
                confidence=max(intent.confidence, ORDER_CONTEXT_CONFIDENCE),
                reasoning=f"catalog_product_inquiry override: {intent.reasoning}",
                classifier=f"{intent.classifier}+catalog_product_inquiry",
            )

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

        should_ask_clarification = self._should_ask_intent_clarification(intent)

        # Capture a call-back / delivery-time follow-up for staff before falling
        # through to handoff/RAG, but never while an order is being handled.
        followup_note: dict[str, Any] | None = None
        if (
            intent.category != IntentCategory.SAFETY_EMERGENCY
            and not self._is_order_in_progress(history)
            and not self._find_existing_chat_order(history)
        ):
            followup_note = self._detect_followup_request(request.content, intent.category)

        product_cards: list[ProductCardResponse] = []
        product_inquiry_message: str | None = None
        if intent.category == IntentCategory.PRODUCT_INQUIRY and not should_ask_clarification:
            assert catalog_products is not None
            product_inquiry_message = await self._price_inquiry_message(
                request.content,
                catalog_products,
            )
            if product_inquiry_message is None:
                product_inquiry_message = self._gas_size_inquiry_message(
                    request.content,
                    catalog_products,
                )
            if product_inquiry_message is None:
                # A deterministic "list the options" reply wins over card grids so
                # a size/water enumeration does not dump the whole catalog as cards.
                product_inquiry_message = self._catalog_list_message(
                    request.content,
                    catalog_products,
                )
            if product_inquiry_message is None:
                card_products = self._select_card_products(request.content, catalog_products)
                product_cards = [self._product_to_card(product) for product in card_products]

        assistant_message: Message | None
        rag_stream: RagStreamPlan | None = None
        if intent.category == IntentCategory.SAFETY_EMERGENCY:
            # Safety stays deterministic (the pipeline returns the fixed constant
            # with no LLM call), so it is a ready message, not a streamed one.
            assistant_message = await self._create_rag_answer(
                conversation,
                request.content,
                history_payload,
                user,
                intent.category,
                intent.confidence,
                locale=request.locale,
            )
        elif followup_note is not None:
            assistant_message = await self._create_followup_message(
                conversation, followup_note, intent
            )
        elif routing.requires_human:
            assistant_message = await self._create_handoff_message(conversation, routing)
        elif should_ask_clarification:
            assistant_message = await self._create_intent_clarification_message(
                conversation,
                intent.category,
                intent.confidence,
            )
        elif product_inquiry_message is not None:
            assistant_message = await self._create_assistant_message(
                conversation,
                product_inquiry_message,
                intent.category,
                intent.confidence,
            )
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
            # The only open-ended branch: defer generation so the caller can stream.
            assistant_message = None
            rag_stream = RagStreamPlan(
                content=request.content,
                history=list(history_payload),
                catalog_products=catalog_products,
                locale=request.locale or "vi",
                intent=intent.category,
                confidence=intent.confidence,
            )

        return ResponsePlan(
            user_message=user_message,
            conversation=conversation,
            product_cards=product_cards,
            assistant_message=assistant_message,
            rag_stream=rag_stream,
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
        """List staff conversations, auto-closing stale ones first (lazy sweep)."""
        await self._close_stale_conversations()
        conversations, total = await self.conversation_repository.list_for_staff(
            staff.id,
            status_filter,
            skip,
            limit,
        )
        return [self._conversation_to_response(item) for item in conversations], total

    async def _close_stale_conversations(self) -> int:
        """Move conversations inactive for CONVERSATION_STALE_DAYS to 'closed'."""
        stale_days = get_settings().CONVERSATION_STALE_DAYS
        cutoff = datetime.now(UTC) - timedelta(days=stale_days)
        return await self.conversation_repository.close_stale(cutoff)

    async def set_conversation_status(
        self, conversation_id: UUID, status: str
    ) -> ConversationResponse:
        """Set a conversation status directly (staff action)."""
        return self._conversation_to_response(
            await self.conversation_repository.set_status(conversation_id, status)
        )

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
        if existing_order and self._is_post_order_change_request(content):
            return ChatOrderResult(
                message=await self._create_post_order_change_message(
                    conversation,
                    content,
                    existing_order,
                    confidence,
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
            metadata_extra: dict[str, Any] | None = None,
        ) -> Message:
            return await self._create_assistant_message(
                conversation,
                content,
                IntentCategory.PLACE_ORDER,
                confidence,
                metadata=[self._order_state_metadata(status, state_slots, metadata_extra)],
            )

        conversation_history = await self.message_repository.list_by_conversation(
            conversation.id,
            skip=0,
            limit=200,
        )
        order_state = self._find_order_state(history, content)
        previous_slots = self._slots_from_order_state(order_state)
        extracted_slots = await self._extract_order_slots(content, history_payload, products)
        inferred_slots = self._infer_order_slots(content, products)
        incoming_slots = self._combine_current_message_slots(
            inferred_slots,
            extracted_slots,
            content,
            products,
        )
        candidate_items = incoming_slots.items
        candidate_item = candidate_items[0] if candidate_items else None
        contact_slots = replace(incoming_slots, items=())
        order_state_status = str(order_state.get("status", "")) if order_state else ""
        base_slots = previous_slots or ChatOrderSlots()
        normalized_content = self._normalize_match_text(content)
        confirm_resolved_order = False
        handled_product_choice = False
        ambiguous_time_window = self._extract_ambiguous_delivery_time_window(content)
        if order_state is not None and self._is_order_cancel_request(normalized_content):
            return result(
                await order_state_message(
                    "Dạ Qiki đã huỷ đơn. Khi nào cần đặt lại bạn cứ nhắn Qiki nhé.",
                    "order_cancelled",
                )
            )
        if order_state is not None and ambiguous_time_window:
            return result(
                await order_state_message(
                    (
                        f"Bạn muốn giao khoảng **{ambiguous_time_window}** "
                        "buổi sáng hay buổi tối ạ?"
                    ),
                    "awaiting_missing_slots",
                    base_slots,
                )
            )
        if order_state_status == "awaiting_product_choice":
            pending_item = self._pending_item_from_state(order_state) or next(
                (item for item in base_slots.items if self._is_incomplete_add_item(item)),
                None,
            )
            if pending_item and self._is_incomplete_add_item(pending_item):
                if self._is_cancel_add_request(normalized_content):
                    slots = self._drop_incomplete_add_items(base_slots)
                    handled_product_choice = True
                elif self._is_affirmation(content):
                    slots = self._drop_incomplete_add_items(base_slots)
                    confirm_resolved_order = True
                    handled_product_choice = True
                else:
                    picked_product = (
                        self._match_product(content, products)
                        if self._query_mentions_product_brand(normalized_content, products)
                        else None
                    )
                    if picked_product is not None:
                        resolved_item = ChatOrderItem(
                            product=self._format_product_display_name(picked_product),
                            quantity=pending_item.quantity,
                        )
                        slots = self._append_order_items(
                            self._drop_incomplete_add_items(base_slots),
                            (resolved_item,),
                            products,
                        )
                        handled_product_choice = True
                    else:
                        requested_size = self._extract_gas_size_choice(
                            normalized_content,
                            products,
                        )
                        if requested_size is not None:
                            size_products = self._gas_products_for_size(products, requested_size)
                            if not size_products:
                                return result(
                                    await order_state_message(
                                        self._gas_size_inquiry_message(
                                            f"gas {normalized_content}",
                                            products,
                                        )
                                        or "Dạ bạn chọn loại gas 6, 12 hoặc 45 kg giúp Qiki nhé.",
                                        "awaiting_product_choice",
                                        base_slots,
                                        {"pending_item": self._items_to_metadata((pending_item,))},
                                    )
                                )
                            return result(
                                await order_state_message(
                                    (
                                        f"Dạ Qiki gửi các lựa chọn gas "
                                        f"{self._format_decimal(requested_size)} kg bên dưới nhé."
                                    ),
                                    "awaiting_product_choice",
                                    base_slots,
                                    {"pending_item": self._items_to_metadata((pending_item,))},
                                ),
                                size_products,
                            )
        if handled_product_choice:
            slots = self._merge_order_slots(slots, contact_slots)
        elif order_state_status == "awaiting_product_change_confirmation":
            previous_items = self._previous_items_from_state(order_state, previous_slots)
            original_slots = replace(base_slots, items=previous_items, confirmed=False)
            pending_item = self._pending_item_from_state(order_state) or self._pending_change_item(
                previous_items,
                base_slots.items,
                products,
            )
            payment_method = self._extract_payment_candidate(content)
            if payment_method:
                slots = replace(original_slots, payment_method=payment_method, confirmed=False)
            elif (
                self._is_negation(content)
                and self._has_add_cue(normalized_content)
                and pending_item
            ):
                slots = self._append_order_item(original_slots, pending_item)
            elif self._is_affirmation(content):
                slots = replace(base_slots, confirmed=False)
            elif self._is_negation(content) or self._is_keep_previous_product_request(content):
                slots = original_slots
            elif self._has_add_cue(normalized_content) and (candidate_items or pending_item):
                items_to_append = (
                    candidate_items
                    if candidate_items
                    else ((pending_item,) if pending_item else ())
                )
                slots = self._append_order_items(
                    original_slots,
                    items_to_append,
                    products,
                )
            elif candidate_item and candidate_item.product:
                pending_slots = self._replace_first_matching_item(
                    original_slots,
                    candidate_item,
                    products,
                )
                return result(
                    await order_state_message(
                        self._format_product_change_question(
                            self._format_order_item_label(self._first_order_item(original_slots)),
                            pending_slots,
                        ),
                        "awaiting_product_change_confirmation",
                        pending_slots,
                        {
                            "previous_items": self._items_to_metadata(previous_items),
                            "pending_item": self._items_to_metadata((candidate_item,)),
                        },
                    )
                )
            else:
                return result(
                    await order_state_message(
                        self._format_pending_change_clarification(),
                        "awaiting_product_change_confirmation",
                        base_slots,
                        {
                            "previous_items": self._items_to_metadata(previous_items),
                            "pending_item": self._items_to_metadata((pending_item,))
                            if pending_item
                            else [],
                        },
                    )
                )
            slots = self._merge_order_slots(slots, contact_slots)
        elif order_state_status == "awaiting_add_or_replace":
            pending_item = self._pending_item_from_state(order_state) or candidate_item
            payment_method = self._extract_payment_candidate(content)
            if payment_method:
                slots = replace(base_slots, payment_method=payment_method, confirmed=False)
            elif pending_item and self._has_add_cue(normalized_content):
                slots = self._append_order_items(base_slots, (pending_item,), products)
            elif pending_item and (
                self._has_replace_cue(normalized_content) or self._is_affirmation(content)
            ):
                slots = self._replace_first_matching_item(base_slots, pending_item, products)
            elif self._is_negation(content):
                slots = replace(base_slots, confirmed=False)
            elif candidate_item and candidate_item.product:
                return result(
                    await order_state_message(
                        self._format_add_or_replace_question(
                            self._first_order_item(base_slots),
                            candidate_item,
                        ),
                        "awaiting_add_or_replace",
                        base_slots,
                        {"pending_item": self._items_to_metadata((candidate_item,))},
                    )
                )
            else:
                return result(
                    await order_state_message(
                        "Bạn nhắn **thêm** để đặt thêm, hoặc **đổi** để thay sản phẩm nhé.",
                        "awaiting_add_or_replace",
                        base_slots,
                        {"pending_item": self._items_to_metadata((pending_item,))}
                        if pending_item
                        else None,
                    )
                )
            slots = self._merge_order_slots(slots, contact_slots)
        else:
            slots = self._merge_order_slots(previous_slots, contact_slots)
            if candidate_items:
                operation = self._detect_order_items_operation(
                    content,
                    previous_slots,
                    candidate_items,
                    products,
                )
                if operation in {"set", None}:
                    slots = self._with_order_items(slots, candidate_items)
                    if previous_slots is None or not previous_slots.items:
                        slots = replace(slots, confirmed=incoming_slots.confirmed)
                elif operation == "add":
                    slots = self._append_order_items(slots, candidate_items, products)
                elif operation == "replace":
                    if not slots.items:
                        slots = self._with_order_items(slots, candidate_items)
                    else:
                        candidate_item = candidate_items[0]
                        pending_slots = self._replace_first_matching_item(
                            slots,
                            candidate_item,
                            products,
                        )
                        return result(
                            await order_state_message(
                                self._format_product_change_question(
                                    self._format_order_item_label(self._first_order_item(slots)),
                                    pending_slots,
                                ),
                                "awaiting_product_change_confirmation",
                                pending_slots,
                                {
                                    "previous_items": self._items_to_metadata(slots.items),
                                    "pending_item": self._items_to_metadata((candidate_item,)),
                                },
                            )
                        )
                elif operation == "remove":
                    candidate_item = candidate_items[0]
                    slots = self._remove_order_item(slots, candidate_item, products)
                elif operation == "merge_existing":
                    for item in candidate_items:
                        slots = self._merge_existing_item(slots, item, products)
                elif operation == "ambiguous":
                    candidate_item = candidate_items[0]
                    return result(
                        await order_state_message(
                            self._format_add_or_replace_question(
                                self._first_order_item(slots),
                                candidate_item,
                            ),
                            "awaiting_add_or_replace",
                            slots,
                            {"pending_item": self._items_to_metadata((candidate_item,))},
                        )
                    )
        slots = self._with_phone_candidate(slots, content)
        slots = self._with_order_cues(slots, content)
        slots = self._with_delivery_time_candidate(slots, content)
        if order_state_status in {
            "awaiting_reused_contact_confirmation",
            "awaiting_account_contact_confirmation",
        }:
            slots = replace(slots, confirmed=False)
        elif order_state_status == "awaiting_confirmation":
            slots = replace(
                slots,
                confirmed=self._is_affirmation(content) or confirm_resolved_order,
            )
        elif confirm_resolved_order:
            slots = replace(slots, confirmed=True)
        else:
            slots = replace(slots, confirmed=False)
        bare_category_item = next(
            (item for item in slots.items if self._is_bare_category_query(item.product)),
            None,
        )
        if bare_category_item:
            if self._is_bare_gas_item(bare_category_item):
                inquiry_message = self._gas_size_inquiry_message("gas", products)
                if inquiry_message:
                    return result(
                        await order_state_message(
                            inquiry_message,
                            "awaiting_product_choice",
                            slots,
                            {
                                "pending_item": self._items_to_metadata(
                                    (bare_category_item,),
                                )
                            },
                        )
                    )
            return result(
                await order_state_message(
                    self._format_category_product_question(bare_category_item.product or ""),
                    "awaiting_product_choice",
                    slots,
                    {"pending_item": self._items_to_metadata((bare_category_item,))},
                ),
                category_cards(bare_category_item.product),
            )

        matched_items = self._match_order_items(slots.items, products)
        matched_order_products = self._matched_order_products(matched_items)
        unmatched_item = next(
            (item for item, product in matched_items if item.product and product is None),
            None,
        )
        if unmatched_item is not None:
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
        reusable_contact_slots = self._find_reusable_contact_slots(conversation_history)
        if self._should_confirm_reusable_contact(
            order_state,
            slots,
            matched_items,
            reusable_contact_slots,
        ):
            reused_slots = self._merge_order_slots(slots, reusable_contact_slots)
            return result(
                await order_state_message(
                    self._format_reusable_contact_question(reusable_contact_slots),
                    "awaiting_reused_contact_confirmation",
                    reused_slots,
                )
            )
        account_contact_slots = self._account_default_contact_slots(user)
        if self._should_confirm_account_contact(
            order_state,
            slots,
            matched_items,
            account_contact_slots,
        ):
            # Account defaults only FILL gaps: anything the customer typed in this
            # message (e.g. a one-off delivery address) must win over the saved
            # profile, so account_contact_slots goes first and slots last.
            account_slots = self._merge_order_slots(account_contact_slots, slots)
            return result(
                await order_state_message(
                    self._format_account_contact_question(
                        account_contact_slots,
                        include_saved_address=not slots.delivery_address,
                    ),
                    "awaiting_account_contact_confirmation",
                    account_slots,
                )
            )
        slots = self._merge_order_slots(self._account_default_contact_slots(user), slots)
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
        missing = self._missing_order_slots(slots, matched_items)
        if missing:
            if order_state is not None and self._is_unproductive_order_turn(
                content,
                base_slots,
                slots,
                candidate_items,
            ):
                return result(
                    await order_state_message(
                        self._format_order_offtopic_message(missing),
                        "awaiting_missing_slots",
                        slots,
                    )
                )
            return result(
                await order_state_message(
                    self._format_missing_slot_question(missing),
                    "awaiting_missing_slots",
                    slots,
                )
            )

        assert slots.customer_name is not None
        assert slots.customer_phone is not None
        assert slots.delivery_address is not None
        assert slots.payment_method is not None
        assert normalized_phone is not None
        assert matched_order_products

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

        khu_pho_validation = validate_khu_pho(slots.delivery_address)
        if khu_pho_validation.status == "missing":
            return result(
                await order_state_message(
                    (
                        "Bạn cho Qiki xin thêm **số khu phố** giúp nhé "
                        f"(P. {khu_pho_validation.ward_display} có khu phố "
                        f"1–{khu_pho_validation.khu_pho_max})."  # noqa: RUF001
                    ),
                    "awaiting_missing_slots",
                    slots,
                )
            )
        if khu_pho_validation.status == "out_of_range":
            return result(
                await order_state_message(
                    (
                        f"Dạ P. {khu_pho_validation.ward_display} chỉ có khu phố "
                        f"1–{khu_pho_validation.khu_pho_max} thôi ạ, "  # noqa: RUF001
                        "bạn kiểm tra lại số khu phố giúp Qiki nhé."
                    ),
                    "awaiting_missing_slots",
                    slots,
                )
            )

        for item, product in matched_order_products:
            assert item.quantity is not None
            if product.stock_quantity < item.quantity:
                return result(
                    await order_state_message(
                        (
                            f"Sản phẩm **{product.name}** hiện chỉ còn "
                            f"{product.stock_quantity} bình. "
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
                        matched_order_products,
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
            items=[
                OrderItemCreate(product_id=product.id, quantity=item.quantity or 0)
                for item, product in matched_order_products
            ],
            customer_name=slots.customer_name,
            customer_phone=normalized_phone,
            delivery_address=slots.delivery_address,
            delivery_ward=delivery_zone_match.ward,
            delivery_district=delivery_zone_match.delivery_zone,
            delivery_city="TP. Hồ Chí Minh",
            delivery_notes=self._delivery_notes_with_water_fee(
                slots.delivery_notes,
                matched_order_products,
            ),
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
        metadata: list[dict[str, Any]] = [
            {
                "type": CHAT_ORDER_METADATA_TYPE,
                "order_id": str(order.id),
                "order_number": order.order_number,
                "slots": self._slots_to_metadata(
                    replace(
                        slots,
                        customer_phone=normalized_phone,
                        payment_method=payment_method,
                    )
                ),
            }
        ]
        delivery_note = self._order_delivery_followup_note(slots.delivery_notes)
        if delivery_note:
            metadata.append(delivery_note)
        return result(
            await self._create_assistant_message(
                conversation,
                (
                    f"Đã ghi nhận đơn **{order.order_number}**. "
                    f"{self._format_order_callback_sentence(slots.delivery_notes)}"
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
- items: danh sách tất cả sản phẩm khách nhắc trong tin mới, mỗi item gồm:
  product: tên/brand/SKU sản phẩm khách muốn mua, hoặc null
  quantity: số lượng sản phẩm/bình, hoặc null
- product, quantity: legacy fallback nếu chỉ có một sản phẩm
- customer_name: tên khách, hoặc null
- customer_phone: số điện thoại, hoặc null
- delivery_address: địa chỉ giao hàng đầy đủ gồm số nhà, tên/số đường, khu phố,
  phường; hoặc null. Không hỏi khách thành phố, mặc định là TP.HCM.
- delivery_notes: khung giờ giao khách đề xuất, hoặc null
- payment_method: "cod" hoặc "bank_transfer", hoặc null
- confirmed: true nếu khách xác nhận rõ đơn Qiki đã tóm tắt ở lượt trước; ngược lại false

Không tự suy đoán hoặc tự điền số điện thoại. Nếu tin mới có dãy số khách đưa
nhưng không chắc hợp lệ, vẫn trả nguyên dãy số đó trong customer_phone để hệ thống kiểm tra.
Chỉ chọn product từ danh sách sản phẩm có thể chọn; không dùng kiến thức ngoài catalog.
Không lặp lại sản phẩm cũ trong lịch sử nếu tin mới không nhắc lại sản phẩm đó.

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
        extracted_items = self._items_from_metadata(payload.get("items"))
        if not extracted_items:
            extracted_item = ChatOrderItem(
                product=self._optional_str(payload.get("product")),
                quantity=self._optional_int(payload.get("quantity")),
            )
            if extracted_item.product or extracted_item.quantity is not None:
                extracted_items = (extracted_item,)
        return ChatOrderSlots(
            items=extracted_items,
            customer_name=self._optional_str(payload.get("customer_name")),
            customer_phone=self._optional_str(payload.get("customer_phone")),
            delivery_address=self._optional_str(payload.get("delivery_address")),
            delivery_notes=self._optional_str(payload.get("delivery_notes")),
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
        locale: str | None = None,
    ) -> Message:
        product_context = await self._resolve_product_context(content, intent, catalog_products)
        response = await self.rag_pipeline.query(
            content,
            conversation_history=history,
            conversation_id=conversation.id,
            user_id=user.id if user else None,
            product_context=product_context,
            language=detect_language(content, default="en" if locale == "en" else "vi"),
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

    async def _resolve_product_context(
        self,
        content: str,
        intent: IntentCategory,
        catalog_products: Sequence[ProductResponse] | None,
    ) -> str | None:
        """Build the query-aware catalog context injected into a RAG answer.

        Shared by the blocking and streaming answer paths so both inject the same
        deterministic price context (#239). Safety turns inject nothing.
        """
        if intent == IntentCategory.SAFETY_EMERGENCY:
            return None
        products = (
            catalog_products
            if catalog_products is not None
            else await self.product_service.list_active_catalog(limit=50)
        )
        return self._query_aware_catalog_context(content, products)

    async def _persist_streamed_answer(
        self,
        conversation: Conversation,
        content: str,
        intent: IntentCategory,
        confidence: float,
        latency_ms: int,
        sources: Sequence[RetrievedDocument],
        llm_provider: str | None = None,
        llm_model: str | None = None,
        tokens_used: int | None = None,
    ) -> Message:
        """Persist a streamed RAG answer with the same fields as a blocking one.

        ``llm_provider`` / ``llm_model`` / ``tokens_used`` come from the stream
        (the provider that actually served, via the fallback chain, plus reported
        usage) so streamed rows are attributed the same way as blocking ones.
        """
        return await self.message_repository.create(
            {
                "conversation_id": conversation.id,
                "role": "assistant",
                "content": content,
                "intent": intent.value,
                "intent_confidence": confidence,
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "tokens_used": tokens_used,
                "latency_ms": latency_ms,
                "retrieved_documents": [
                    {
                        "id": str(source.id),
                        "title": source.title,
                        "category": source.category,
                        "similarity": source.similarity,
                        "source_type": source.source_type,
                    }
                    for source in sources
                ],
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

    def _query_aware_catalog_context(
        self, content: str, catalog_products: Sequence[ProductResponse]
    ) -> str | None:
        """Narrow the injected catalog to the products the message targets."""
        brands = sorted({product.brand for product in catalog_products})
        query = parse_product_query(content, brands)
        if query.is_specific():
            narrowed = cast(list[ProductResponse], filter_products(catalog_products, query))
            if narrowed:
                return self._build_product_catalog_context(narrowed)
        return self._build_product_catalog_context(catalog_products)

    async def _price_inquiry_message(
        self, content: str, catalog_products: Sequence[ProductResponse]
    ) -> str | None:
        """Answer a superlative/range price question deterministically.

        Handles cheapest / most-expensive / around / under / over price intents
        by resolving the matching products via a SQL query (price-ordered) so the
        answer is correct regardless of the generator's list-scanning ability.
        Specific single-product price questions are left to the product cards and
        the query-aware RAG context. Returns None when there is no such intent.
        """
        brands = sorted({product.brand for product in catalog_products})
        query = parse_product_query(content, brands)
        if query.price_kind is None:
            return None
        matches = await self.product_service.find_products(query)
        if not matches:
            return (
                "Dạ hiện cửa hàng chưa có loại phù hợp với yêu cầu của bạn. "
                "Bạn tham khảo bảng giá bên dưới giúp Qiki nhé ạ."
            )
        if query.price_kind == "cheapest":
            return self._superlative_price_message(query, matches[0], "rẻ nhất")
        if query.price_kind == "most_expensive":
            return self._superlative_price_message(query, matches[-1], "đắt nhất")
        return self._price_range_message(query, matches)

    def _superlative_price_message(
        self, query: ProductQuery, product: ProductResponse, label: str
    ) -> str:
        scope = self._price_scope_label(query)
        name = self._format_product_display_name(product)
        return (
            f"Dạ loại {scope} {label} là {name} ({product.brand}), "
            f"giá {self._format_vnd(product.price)} ạ."
        )

    def _price_range_message(self, query: ProductQuery, matches: Sequence[ProductResponse]) -> str:
        scope = self._price_scope_label(query)
        amount = self._format_vnd(query.price_value) if query.price_value is not None else ""
        phrase = {
            "around": f"tầm {amount}",
            "under": f"dưới {amount}",
            "over": f"trên {amount}",
        }.get(query.price_kind or "", amount)
        options = "; ".join(
            f"{self._format_product_display_name(product)} ({self._format_vnd(product.price)})"
            for product in matches[:5]
        )
        return f"Dạ loại {scope} {phrase} có: {options} ạ."

    def _price_scope_label(self, query: ProductQuery) -> str:
        parts: list[str] = []
        if query.category == "nuoc_uong":
            parts.append("nước")
        elif query.category == "gas" or query.size_kg is not None:
            parts.append("gas")
        if query.size_kg is not None:
            unit = "lít" if query.category == "nuoc_uong" else "kg"
            parts.append(f"{self._format_decimal(query.size_kg)}{unit}")
        return " ".join(parts) if parts else "sản phẩm"

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

    @classmethod
    def _gas_size_inquiry_message(
        cls,
        query: str,
        products: Sequence[ProductResponse],
    ) -> str | None:
        sizes = cls._available_gas_sizes(products)
        if len(sizes) < 2:
            return None
        normalized_query = cls._normalize_match_text(query)
        if cls._category_filter_from_query(normalized_query) != "gas":
            return None
        requested_size = cls._extract_gas_size_query(normalized_query)
        size_options = cls._format_size_options(sizes)
        if requested_size is not None and requested_size not in set(sizes):
            return (
                f"Dạ cửa hàng chỉ có gas loại {size_options} kg thôi ạ. "
                "Bạn chọn loại nào giúp Qiki nhé."
            )
        if requested_size is None and not cls._query_mentions_product_brand(
            normalized_query,
            products,
        ):
            return (
                f"Cửa hàng Gas Quốc Cường có gas loại {size_options} kg. "
                "Bạn muốn loại bao nhiêu kg ạ?"
            )
        return None

    @classmethod
    def _available_gas_sizes(cls, products: Sequence[ProductResponse]) -> list[Decimal]:
        return sorted({product.size_kg for product in products if product.category == "gas"})

    @classmethod
    def _catalog_list_message(
        cls,
        query: str,
        catalog_products: Sequence[ProductResponse],
    ) -> str | None:
        """Answer an "enumerate the options" query as a compact price list (no LLM).

        Fires only for a list-style query (an enumeration cue) that resolves to a
        gas size (6/12/45) or the water category and does NOT name a specific
        single brand. Returns a header + one ``- {display_name} - {price}`` line
        per product (sorted by brand then price) + a one-line advisory. Prices are
        read straight from ``catalog_products`` (deterministic pricing, #239).
        A specific single-brand price question falls through unchanged.
        """
        normalized_query = cls._normalize_weight_units(cls._normalize_match_text(query))
        if not cls._is_catalog_list_query(normalized_query):
            return None
        if cls._query_mentions_product_brand(normalized_query, catalog_products):
            return None

        requested_size = cls._extract_gas_size_query(normalized_query)
        if requested_size is not None:
            if requested_size not in set(cls._available_gas_sizes(catalog_products)):
                return None
            items = [
                product
                for product in catalog_products
                if product.category == "gas" and product.size_kg == requested_size
            ]
            header = (
                f"Cửa hàng Gas Quốc Cường có các loại gas "
                f"{cls._format_decimal(requested_size)}kg sau:"
            )
        elif cls._category_filter_from_query(normalized_query) == "nuoc_uong":
            items = [product for product in catalog_products if product.category == "nuoc_uong"]
            header = "Cửa hàng Gas Quốc Cường có các loại nước uống sau:"
        else:
            return None

        if not items:
            return None
        ordered = sorted(
            items, key=lambda product: (cls._normalize_match_text(product.brand), product.price)
        )
        lines = [
            f"- {cls._format_product_display_name(product)} - {cls._format_vnd(product.price)}"
            for product in ordered
        ]
        advisory = "Bạn muốn đặt hãng/màu nào để Qiki báo giá và lên đơn nhé?"
        return "\n".join([header, *lines, advisory])

    @staticmethod
    def _is_catalog_list_query(normalized_query: str) -> bool:
        return any(cue in normalized_query for cue in CATALOG_LIST_CUES)

    @staticmethod
    def _normalize_weight_units(normalized_query: str) -> str:
        """Rewrite colloquial gas-weight units ('12 kí/ký/ki/ky') to '12kg'.

        Runs on accent-stripped text, where 'kí'/'ký' have already lost their
        diacritics ('ki'/'ky'). A digit must precede the unit so unrelated words
        are never touched.
        """
        return re.sub(r"\b([1-9][0-9]?)\s*(?:kg|ki|ky)\b", r"\1kg", normalized_query)

    @classmethod
    def _extract_gas_size_query(cls, normalized_query: str) -> Decimal | None:
        normalized = cls._normalize_weight_units(normalized_query)
        match = re.search(r"\b([1-9][0-9]?)\s*kg\b", normalized)
        if not match:
            return None
        return Decimal(match.group(1))

    @classmethod
    def _extract_gas_size_choice(
        cls,
        normalized_query: str,
        products: Sequence[ProductResponse],
    ) -> Decimal | None:
        requested_size = cls._extract_gas_size_query(normalized_query)
        if requested_size is not None:
            return requested_size
        match = re.fullmatch(r"(?:loai\s*)?([1-9][0-9]?)", normalized_query)
        if not match:
            return None
        return Decimal(match.group(1))

    @staticmethod
    def _gas_products_for_size(
        products: Sequence[ProductResponse],
        size: Decimal,
    ) -> list[ProductResponse]:
        return [
            product for product in products if product.category == "gas" and product.size_kg == size
        ]

    @classmethod
    def _format_size_options(cls, sizes: Sequence[Decimal]) -> str:
        return ", ".join(cls._format_decimal(size) for size in sizes)

    @classmethod
    def _query_mentions_product_brand(
        cls,
        normalized_query: str,
        products: Sequence[ProductResponse],
    ) -> bool:
        query_tokens = set(normalized_query.split())
        for product in products:
            if product.category != "gas":
                continue
            normalized_brand = cls._normalize_match_text(product.brand)
            brand_tokens = set(normalized_brand.split())
            distinctive_brand_tokens = brand_tokens - {"gas"}
            if distinctive_brand_tokens and (
                bool(distinctive_brand_tokens & query_tokens)
                or normalized_brand in normalized_query
            ):
                return True
        return False

    def _select_card_products(
        self,
        query: str,
        products: Sequence[ProductResponse],
    ) -> list[ProductResponse]:
        """Pick which product cards to attach for a query.

        A specific question that names a brand and/or cylinder size returns only
        the matching products. The whole (category) catalog is returned ONLY for
        an explicit browse/enumeration query (a bare category or a browse cue);
        any other unmatched query returns ``[]`` so unrelated follow-ups (e.g.
        "cảm ơn Qiki") never re-emit catalog cards.
        """
        normalized_query = self._normalize_weight_units(self._normalize_match_text(query))
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
        # The sticky-card bug: an unrelated follow-up ("cảm ơn", "ok") names no
        # brand/size/category, so candidate_products is the WHOLE catalog. Return
        # it only when the query resolves a category (a genuine category inquiry)
        # or is an explicit browse request; otherwise return nothing.
        if category_filter is not None or self._is_browse_query(normalized_query):
            return candidate_products
        return []

    @classmethod
    def _is_browse_query(cls, normalized_query: str) -> bool:
        """True for a bare category ("gas"/"nước") or an explicit browse cue."""
        if cls._is_bare_category_query(normalized_query):
            return True
        return any(cue in normalized_query for cue in CATALOG_BROWSE_CUES)

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
    def _is_bare_gas_item(cls, item: ChatOrderItem) -> bool:
        normalized = cls._normalize_match_text(item.product or "")
        return (
            cls._is_bare_category_query(normalized)
            and cls._category_filter_from_query(normalized) == "gas"
        )

    @classmethod
    def _is_incomplete_add_item(cls, item: ChatOrderItem) -> bool:
        return item.product is None or cls._is_bare_gas_item(item)

    @classmethod
    def _format_category_product_question(cls, query: str) -> str:
        category = cls._category_filter_from_query(cls._normalize_match_text(query))
        if category == "nuoc_uong":
            return "Bạn muốn đặt loại nước uống nào? Qiki gửi các lựa chọn bên dưới nhé."
        if category == "gas":
            return "Bạn muốn đặt loại gas nào? Qiki gửi các lựa chọn bên dưới nhé."
        return "Bạn muốn đặt sản phẩm nào? Qiki gửi các lựa chọn bên dưới nhé."

    @staticmethod
    def _should_load_catalog_for_intent(intent: IntentResult) -> bool:
        return intent.category != IntentCategory.SAFETY_EMERGENCY

    @staticmethod
    def _should_ask_intent_clarification(intent: IntentResult) -> bool:
        return intent.confidence < 0.6 and intent.category not in {
            IntentCategory.SAFETY_EMERGENCY,
            IntentCategory.COMPLAINT,
            IntentCategory.PLACE_ORDER,
        }

    async def _create_intent_clarification_message(
        self,
        conversation: Conversation,
        intent: IntentCategory,
        confidence: float,
    ) -> Message:
        return await self._create_assistant_message(
            conversation,
            (
                "Qiki chưa rõ ý bạn. Bạn muốn **đặt hàng**, "
                "**hỏi giá/sản phẩm**, hay **hỏi thông tin cửa hàng** ạ?"
            ),
            intent,
            confidence,
        )

    async def _create_post_order_change_message(
        self,
        conversation: Conversation,
        content: str,
        existing_order: Mapping[str, Any],
        confidence: float,
    ) -> Message:
        order_number = self._optional_str(existing_order.get("order_number")) or "đơn trước"
        change_text = self._format_post_order_change_text(content)
        metadata = dict(existing_order)
        metadata["post_order_change_request"] = content
        payment_method = self._extract_payment_candidate(content)
        if payment_method:
            metadata["requested_payment_method"] = payment_method
        return await self._create_assistant_message(
            conversation,
            (
                f"Đơn **{order_number}** đã ghi nhận. "
                f"Qiki đã lưu yêu cầu {change_text}; "
                "nhân viên sẽ xác nhận lại khi gọi cho bạn nhé."
            ),
            IntentCategory.PLACE_ORDER,
            confidence,
            metadata=[metadata],
        )

    @classmethod
    def _format_post_order_change_text(cls, content: str) -> str:
        payment_method = cls._extract_payment_candidate(content)
        if payment_method == "bank_transfer":
            return "đổi sang **chuyển khoản**"
        if payment_method == "cod":
            return "đổi sang **thanh toán khi nhận hàng (COD)**"
        return "thay đổi thông tin đơn"

    @classmethod
    def _is_post_order_change_request(cls, content: str) -> bool:
        normalized = cls._normalize_match_text(content)
        if cls._extract_payment_candidate(content) and any(
            phrase in normalized
            for phrase in {"doi", "doi sang", "chuyen sang", "thay doi", "sua", "cap nhat"}
        ):
            return True
        return any(
            phrase in normalized
            for phrase in {
                "doi thong tin",
                "sua thong tin",
                "cap nhat thong tin",
                "doi hinh thuc",
                "sua hinh thuc",
            }
        )

    @classmethod
    def _is_explicit_human_request(cls, content: str) -> bool:
        normalized = cls._normalize_match_text(content)
        return any(
            phrase in normalized
            for phrase in {
                "gap nhan vien",
                "gap nguoi that",
                "cho gap nhan vien",
                "cho gap nguoi that",
                "goi nhan vien",
                "goi nguoi that",
                "chuyen nhan vien",
                "chuyen nguoi that",
                "can nhan vien",
                "keu nhan vien",
                "keu nguoi",
                "noi chuyen voi nhan vien",
                "gap nguoi",
                "can gap nguoi",
                "muon gap nhan vien",
            }
        )

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
        explicit_name = cls._extract_name_candidate(content, payment_method)
        customer_name = explicit_name or slots.customer_name
        return replace(slots, customer_name=customer_name, payment_method=payment_method)

    @classmethod
    def _with_delivery_time_candidate(cls, slots: ChatOrderSlots, content: str) -> ChatOrderSlots:
        delivery_notes = slots.delivery_notes or cls._extract_delivery_time_candidate(content)
        return replace(slots, delivery_notes=delivery_notes)

    @staticmethod
    def _extract_delivery_time_candidate(content: str) -> str | None:
        patterns = [
            r"\bgiao\s+((?:sáng|sang|trưa|trua|chiều|chieu|tối|toi)\s+(?:nay|mai))\b",
            r"\bgiao\s+((?:sau|trước|truoc)\s+\d{1,2}\s*h(?:\d{2})?)\b",
            r"\b((?:sáng|sang|trưa|trua|chiều|chieu|tối|toi)\s+(?:nay|mai))\b",
            r"\b((?:sau|trước|truoc)\s+\d{1,2}\s*h(?:\d{2})?)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, content.lower(), flags=re.IGNORECASE)
            if match:
                return match.group(1).strip(" .,;:!?")
        return None

    @classmethod
    def _extract_ambiguous_delivery_time_window(cls, content: str) -> str | None:
        normalized = cls._normalize_match_text(content)
        if set(normalized.split()) & AMBIGUOUS_DELIVERY_PERIODS:
            return None
        decomposed = unicodedata.normalize("NFD", content.lower().replace("đ", "d"))
        raw = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
        match = re.search(
            r"\b(\d{1,2})\s*(?:h|g(?:io)?)?\s*(?:-|den)\s*(\d{1,2})\s*h?\b",
            raw,
        )
        if not match:
            return None
        start = int(match.group(1))
        end = int(match.group(2))
        if not (1 <= start <= 12 and 1 <= end <= 12):
            return None
        return f"{start}-{end}h"

    # --- Staff follow-up notes (call-back / delivery time) --------------------

    @classmethod
    def _detect_followup_request(
        cls, content: str, intent_category: IntentCategory
    ) -> dict[str, Any] | None:
        """Detect a call-back / delivery-time follow-up and build a structured note.

        Returns None when the message is not a follow-up request. A call-back or a
        decline phrase is a strong signal (fires regardless of intent); a bare
        delivery time only fires when the turn is not an order placement, so real
        orders are not intercepted.
        """
        normalized = cls._normalize_match_text(content)
        tokens = set(normalized.split())
        declined = cls._is_callback_decline(normalized)
        wants_callback = cls._mentions_callback(normalized)
        mentions_delivery = "giao" in tokens
        window_text, period = cls._extract_followup_window(content)

        if declined:
            note_type = "delivery_window" if mentions_delivery and window_text else "callback"
            return cls._build_followup_note(note_type, window_text, period, declined=True)
        if wants_callback and window_text:
            return cls._build_followup_note("callback", window_text, period, declined=False)
        if mentions_delivery and window_text and intent_category != IntentCategory.PLACE_ORDER:
            return cls._build_followup_note("delivery_window", window_text, period, declined=False)
        return None

    @staticmethod
    def _mentions_callback(normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in (
                "goi lai",
                "goi cho",
                "goi minh",
                "goi tui",
                "goi em",
                "goi gium",
                "goi giup",
                "call lai",
                "lien he lai",
            )
        )

    @staticmethod
    def _is_callback_decline(normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in (
                "khong can goi",
                "khoi goi",
                "dung goi",
                "khong goi lai",
                "khong phai goi",
                "khong can lien he",
            )
        )

    @classmethod
    def _extract_followup_window(cls, content: str) -> tuple[str | None, str | None]:
        """Return (window_text, period) for a time window — e.g. ("7-8h sáng mai", "sáng").

        period is the buổi (sáng/trưa/chiều/tối) when stated, else None (ambiguous).
        """
        decomposed = unicodedata.normalize("NFD", content.lower().replace("đ", "d"))
        ascii_text = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")

        hours_text: str | None = None
        range_match = re.search(
            r"\b(\d{1,2})\s*(?:h|gio?)?\s*(?:-|den)\s*(\d{1,2})\s*h?\b", ascii_text
        )
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if 1 <= start <= 24 and 1 <= end <= 24:
                hours_text = f"{start}-{end}h"
        if hours_text is None:
            single = re.search(r"\b(\d{1,2})\s*h(\d{2})?\b", ascii_text)
            if single:
                hour = int(single.group(1))
                if 1 <= hour <= 24:
                    minutes = single.group(2)
                    hours_text = f"{hour}h{minutes}" if minutes else f"{hour}h"
        if hours_text is None:
            return None, None

        tokens = set(ascii_text.split())
        period = next(
            (label for key, label in FOLLOWUP_PERIOD_LABELS.items() if key in tokens), None
        )
        day = "mai" if "mai" in tokens else None
        parts = [hours_text]
        if period:
            parts.append(period)
        if day:
            parts.append(day)
        return " ".join(parts), period

    @classmethod
    def _build_followup_note(
        cls,
        note_type: str,
        window_text: str | None,
        period: str | None,
        declined: bool,
    ) -> dict[str, Any]:
        note: dict[str, Any] = {
            "type": CHAT_FOLLOWUP_NOTE_METADATA_TYPE,
            "note_type": note_type,
            "declined_callback": declined,
        }
        if window_text:
            note["time_window"] = window_text
        if period:
            note["period"] = period
        note["staff_reminder"] = cls._format_followup_reminder(note_type, window_text, declined)
        return note

    @staticmethod
    def _format_followup_reminder(note_type: str, window_text: str | None, declined: bool) -> str:
        if note_type == "delivery_window" and window_text:
            base = f"Giao {window_text}"
            return f"{base} (khách không cần gọi lại)" if declined else base
        if declined:
            return "Khách không cần gọi lại"
        if window_text:
            return f"Gọi lại {window_text}"
        return "Khách yêu cầu gọi lại"

    @classmethod
    def _format_followup_reply(cls, note: dict[str, Any]) -> str:
        window = note.get("time_window")
        period = note.get("period")
        declined = bool(note.get("declined_callback"))
        if note.get("note_type") == "delivery_window":
            if window and not period:
                return (
                    f"Dạ Qiki ghi nhận giao khoảng **{window}** — bạn muốn buổi sáng hay "
                    "buổi tối ạ? Nhân viên sẽ giao đúng khung giờ."
                )
            note_text = f"giao **{window}**" if window else "khung giờ giao bạn đề xuất"
            tail = " Qiki sẽ không gọi lại nữa nhé." if declined else ""
            return (
                f"Dạ Qiki đã ghi chú {note_text}, nhân viên sẽ giao đúng khung giờ.{tail} "
                "Cảm ơn bạn!"
            )
        if declined:
            return "Dạ Qiki đã ghi nhận bạn không cần gọi lại ạ. Cảm ơn bạn!"
        if window and not period:
            return (
                f"Dạ Qiki ghi nhận gọi lại khoảng **{window}** — bạn muốn buổi sáng hay "
                "buổi tối ạ?"
            )
        window_text = f"**{window}**" if window else "sớm nhất"
        return (
            f"Dạ Qiki đã ghi chú gọi lại {window_text}, nhân viên sẽ gọi lại cho bạn. Cảm ơn bạn!"
        )

    async def _create_followup_message(
        self,
        conversation: Conversation,
        note: dict[str, Any],
        intent: IntentResult,
    ) -> Message:
        """Persist a follow-up acknowledgement carrying the structured note + flag."""
        return await self.message_repository.create(
            {
                "conversation_id": conversation.id,
                "role": "assistant",
                "content": self._format_followup_reply(note),
                "intent": intent.category.value,
                "intent_confidence": intent.confidence,
                "latency_ms": 0,
                "retrieved_documents": [note],
                "flagged_for_review": True,
            }
        )

    @classmethod
    def _order_delivery_followup_note(cls, delivery_notes: str | None) -> dict[str, Any] | None:
        """Build a structured delivery-window note from an order's delivery_notes."""
        if not delivery_notes:
            return None
        window_text, period = cls._extract_followup_window(delivery_notes)
        return cls._build_followup_note(
            "delivery_window", window_text or delivery_notes.strip(), period, declined=False
        )

    @classmethod
    def _extract_payment_candidate(cls, content: str) -> str | None:
        normalized = cls._normalize_match_text(content)
        tokens = set(normalized.split())
        if (
            "cod" in tokens
            or "tien mat" in normalized
            or "nhan hang" in normalized
            or "thanh toan khi nhan" in normalized
            or "tra khi nhan" in normalized
            or "ship cod" in normalized
            or "giao tra tien" in normalized
            or "nhan hang tra tien" in normalized
        ):
            return "cod"
        if (
            "ck" in tokens
            or "banking" in tokens
            or "bank" in tokens
            or "chuyen khoan" in normalized
            or "khoan" in tokens
        ):
            return "bank_transfer"
        return None

    @classmethod
    def _extract_name_candidate(cls, content: str, payment_method: str | None) -> str | None:
        explicit_name = cls._extract_explicit_name_candidate(content)
        if explicit_name is not None:
            return explicit_name
        leading_name = cls._extract_leading_name_before_address(content)
        if leading_name is not None:
            return leading_name
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

    @classmethod
    def _extract_explicit_name_candidate(cls, content: str) -> str | None:
        match = re.search(
            r"\b(?:tên|ten|mình tên|minh ten|tôi tên|toi ten|người nhận|nguoi nhan)\s+"
            r"([A-Za-zÀ-ỹ][A-Za-zÀ-ỹ\s'.-]{0,40})",
            content,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        candidate = cls._clean_name_candidate(match.group(1))
        return candidate.title() if candidate else None

    @classmethod
    def _extract_leading_name_before_address(cls, content: str) -> str | None:
        address = cls._extract_delivery_address_candidate(content)
        if not address:
            return None
        address_index = content.lower().find(address.lower())
        if address_index <= 0:
            return None
        prefix = content[:address_index].strip(" ,.;:-")
        prefix = re.sub(r"\+?\d[\d\s.-]{1,}\d", " ", prefix)
        prefix = re.sub(r"\b(?:tên|ten|mình|minh|tôi|toi|là|la)\b", " ", prefix, flags=re.I)
        candidate = cls._clean_name_candidate(prefix)
        return candidate.title() if candidate else None

    @classmethod
    def _clean_name_candidate(cls, value: str) -> str | None:
        words = re.findall(r"[A-Za-zÀ-ỹ]+", value)
        ignored = {
            "ok",
            "okay",
            "giao",
            "dat",
            "dathang",
            "don",
            "dia",
            "chi",
            "sdt",
            "so",
            "phone",
        }
        name_words = [
            word.strip() for word in words if cls._normalize_match_text(word) not in ignored
        ]
        if not name_words or len(name_words) > 3:
            return None
        return " ".join(name_words)

    @staticmethod
    def _extract_phone_candidate(content: str) -> str | None:
        for match in re.finditer(r"\+?\d[\d\s.-]{1,}\d", content):
            candidate = match.group(0).strip()
            digits = re.sub(r"\D", "", candidate)
            if len(digits) >= 3:
                return "+" + digits if candidate.startswith("+") else digits
        return None

    @classmethod
    def _extract_delivery_address_candidate(cls, content: str) -> str | None:
        text = content
        match = re.search(
            r"(?P<address>\b\d+[A-Za-zÀ-ỹ0-9\s,./-]*?"
            r"(?:đường|duong|hẻm|hem|khu\s*phố|khu\s*pho|kp\.?|phường|phuong|p\.)"
            r"[A-Za-zÀ-ỹ0-9\s,./-]*)",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            marker_match = re.search(
                r"\b(?:địa chỉ|dia chi)\s+(.+)$",
                text,
                flags=re.IGNORECASE,
            )
            if not marker_match:
                return None
            candidate = marker_match.group(1)
        else:
            candidate = match.group("address")
        candidate = cls._strip_trailing_payment_words(candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip(" ,.;:-")
        return candidate or None

    @staticmethod
    def _strip_trailing_payment_words(value: str) -> str:
        return re.sub(
            r"\s*(?:,|\.|;|-)?\s*"
            r"(?:ck|cod|cash|banking|bank|chuyển khoản|chuyen khoan|tiền mặt|tien mat|"
            r"thanh toán khi nhận|thanh toan khi nhan|trả khi nhận|tra khi nhan|ship cod)"
            r"\s*$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

    @classmethod
    def _infer_order_slots(
        cls,
        content: str,
        products: Sequence[ProductResponse],
    ) -> ChatOrderSlots:
        items: list[ChatOrderItem] = []
        for segment in cls._split_order_item_segments(content):
            if cls._segment_looks_like_address(segment):
                continue
            category_item = cls._category_order_item_from_segment(segment)
            if category_item is not None:
                items = list(cls._merge_candidate_items(tuple(items), category_item, products))
                continue
            matched_product = cls._match_product(segment, products)
            quantity = cls._extract_quantity_candidate(segment)
            if matched_product is not None and quantity is None:
                quantity = cls._extract_leading_quantity_candidate(segment)
            if matched_product is not None and quantity is None:
                matched_product = None
            if matched_product is None and quantity is None:
                continue
            item = ChatOrderItem(
                product=cls._format_product_display_name(matched_product)
                if matched_product is not None
                else None,
                quantity=quantity,
            )
            items = list(cls._merge_candidate_items(tuple(items), item, products))

        if not items and not cls._segment_looks_like_address(content):
            matched_product = cls._match_product(content, products)
            quantity = cls._extract_quantity_candidate(content)
            if matched_product is not None and quantity is None:
                quantity = cls._extract_leading_quantity_candidate(content)
            if matched_product is not None and quantity is None:
                matched_product = None
            if matched_product is not None or quantity is not None:
                items.append(
                    ChatOrderItem(
                        product=cls._format_product_display_name(matched_product)
                        if matched_product is not None
                        else None,
                        quantity=quantity,
                    )
                )
        return ChatOrderSlots(items=tuple(items))

    @classmethod
    def _segment_looks_like_address(cls, segment: str) -> bool:
        normalized = cls._normalize_match_text(segment)
        tokens = set(normalized.split())
        return bool(tokens & ADDRESS_MARKER_TOKENS) or any(
            phrase in normalized for phrase in ADDRESS_MARKER_PHRASES
        )

    @classmethod
    def _split_order_item_segments(cls, content: str) -> tuple[str, ...]:
        normalized = cls._normalize_match_text(content)
        if not normalized:
            return ()
        parts = re.split(
            r"\b(?:cong them|lay them|them vao|them|va|voi)\b|[,+]",
            normalized,
        )
        segments = tuple(part.strip() for part in parts if part.strip())
        return segments or (normalized,)

    @classmethod
    def _category_order_item_from_segment(cls, segment: str) -> ChatOrderItem | None:
        normalized = cls._normalize_match_text(segment)
        quantity = cls._extract_leading_quantity_candidate(normalized)
        if quantity is not None:
            normalized = re.sub(r"^\s*[1-9][0-9]?\b", "", normalized, count=1).strip()
        tokens = [
            token
            for token in normalized.split()
            if token
            not in {
                "a",
                "dat",
                "di",
                "khi",
                "mua",
                "lay",
                "cho",
                "toi",
                "minh",
                "can",
                "muon",
                "luon",
                "nhe",
                "nua",
                "them",
                "voi",
            }
        ]
        category_text = " ".join(tokens)
        if not cls._is_bare_category_query(category_text):
            return None
        category = cls._category_filter_from_query(category_text)
        product = "nước uống" if category == "nuoc_uong" else "gas"
        return ChatOrderItem(product=product, quantity=quantity)

    @classmethod
    def _combine_current_message_slots(
        cls,
        inferred_slots: ChatOrderSlots,
        extracted_slots: ChatOrderSlots,
        content: str,
        products: Sequence[ProductResponse],
    ) -> ChatOrderSlots:
        items = inferred_slots.items
        for extracted_item in extracted_slots.items:
            if extracted_item.product:
                extracted_product = cls._match_product(extracted_item.product, products)
                mentioned = cls._is_product_mentioned_in_content(
                    content, extracted_product
                ) or cls._is_product_mentioned_in_content(content, extracted_item.product)
                if (
                    len(items) == 1
                    and cls._is_bare_category_query(items[0].product)
                    and extracted_product is not None
                    and not cls._is_bare_category_query(extracted_item.product)
                    and mentioned
                ):
                    items = ()
                if not mentioned:
                    continue
            items = cls._merge_candidate_items(items, extracted_item, products)
        return ChatOrderSlots(
            items=items,
            customer_name=extracted_slots.customer_name,
            customer_phone=extracted_slots.customer_phone,
            delivery_address=cls._sanitize_delivery_address(
                cls._select_delivery_address(
                    extracted_slots.delivery_address,
                    cls._extract_delivery_address_candidate(content),
                ),
                content,
            ),
            delivery_notes=extracted_slots.delivery_notes,
            payment_method=extracted_slots.payment_method,
            confirmed=extracted_slots.confirmed,
        )

    @classmethod
    def _select_delivery_address(
        cls,
        extracted_address: str | None,
        inferred_address: str | None,
    ) -> str | None:
        if not inferred_address:
            return extracted_address
        if not extracted_address:
            return inferred_address
        extracted_zone = resolve_ward_delivery_zone(extracted_address)
        inferred_zone = resolve_ward_delivery_zone(inferred_address)
        if inferred_zone is not None and extracted_zone is None:
            return inferred_address
        if (
            inferred_zone is not None
            and extracted_zone is not None
            and len(inferred_address) > len(extracted_address)
        ):
            return inferred_address
        return extracted_address

    @classmethod
    def _sanitize_delivery_address(cls, address: str | None, content: str) -> str | None:
        """Drop non-address fragments a single-message order leaks into the address.

        When the captured address still carries the product, a "tên <name>" segment,
        the phone number, or a payment cue, prefer the address segment isolated from
        the message. A clean address (e.g. from the multi-turn flow) is unchanged.
        """
        if not address or not cls._address_has_non_address_noise(address):
            return address
        segment = cls._address_segment_from_content(content)
        if segment and not cls._address_has_non_address_noise(segment):
            return segment
        return address

    @classmethod
    def _address_segment_from_content(cls, content: str) -> str | None:
        """Join the comma/semicolon/newline parts of a message that look like an address."""
        parts = [
            part.strip(" .;:-")
            for part in re.split(r"[,\n;]+", content)
            if cls._segment_looks_like_address(part)
        ]
        if not parts:
            return None
        joined = cls._strip_trailing_payment_words(", ".join(part for part in parts if part))
        return re.sub(r"\s+", " ", joined).strip(" ,.;:-") or None

    @classmethod
    def _address_has_non_address_noise(cls, address: str) -> bool:
        """Detect order fragments (name/phone/payment/product) inside an address blob.

        Vietnamese place names contain "Bình" (Bình Thạnh, Bình Lợi Trung), so product
        noise is detected via gas/kg/lít tokens, never via "binh".
        """
        normalized = cls._normalize_match_text(address)
        tokens = set(normalized.split())
        if {"ten", "sdt"} & tokens:
            return True
        if re.search(r"\d{9,}", re.sub(r"[\s.\-]", "", address)):
            return True
        if {"ck", "cod", "cash", "banking", "bank", "gas", "kg", "lit"} & tokens:
            return True
        return any(phrase in normalized for phrase in ("chuyen khoan", "tien mat", "thanh toan"))

    @classmethod
    def _merge_candidate_items(
        cls,
        current: tuple[ChatOrderItem, ...],
        incoming_item: ChatOrderItem,
        products: Sequence[ProductResponse],
    ) -> tuple[ChatOrderItem, ...]:
        if not current:
            return (incoming_item,)
        matching_index = cls._find_matching_item_index(current, incoming_item, products)
        if matching_index is None:
            return (*current, incoming_item)
        items = list(current)
        current_item = items[matching_index]
        items[matching_index] = ChatOrderItem(
            product=current_item.product or incoming_item.product,
            quantity=current_item.quantity
            if current_item.quantity is not None
            else incoming_item.quantity,
        )
        return tuple(items)

    @classmethod
    def _is_product_mentioned_in_content(
        cls,
        content: str,
        product_or_query: ProductResponse | str | None,
    ) -> bool:
        if product_or_query is None:
            return False
        normalized_content = cls._normalize_match_text(content)
        candidates: tuple[str, ...]
        if isinstance(product_or_query, ProductResponse):
            candidates = (
                product_or_query.name,
                product_or_query.brand,
                product_or_query.sku,
                cls._format_product_display_name(product_or_query),
                f"{cls._format_decimal(product_or_query.size_kg)}kg",
                f"{cls._format_decimal(product_or_query.size_kg)} {product_or_query.unit}",
            )
        else:
            candidates = (product_or_query,)
        for candidate in candidates:
            normalized_candidate = cls._normalize_match_text(candidate)
            if not normalized_candidate:
                continue
            if normalized_candidate in normalized_content:
                return True
            candidate_tokens = {token for token in normalized_candidate.split() if len(token) >= 3}
            if candidate_tokens and candidate_tokens.issubset(set(normalized_content.split())):
                return True
        return False

    @classmethod
    def _looks_like_order_request(
        cls,
        content: str,
        products: Sequence[ProductResponse],
    ) -> bool:
        return cls._catalog_product_intent_override(content, products) == IntentCategory.PLACE_ORDER

    @classmethod
    def _catalog_product_intent_override(
        cls,
        content: str,
        products: Sequence[ProductResponse],
    ) -> IntentCategory | None:
        normalized = cls._normalize_match_text(content)
        if cls._is_bare_category_query(normalized):
            return None
        matched_product = cls._match_product(content, products)
        if matched_product is None:
            return None
        quantity = cls._extract_quantity_candidate(content)
        if quantity is None:
            quantity = cls._extract_leading_quantity_candidate(content)
        has_question = cls._has_product_question_cue(normalized)
        if has_question:
            return IntentCategory.PRODUCT_INQUIRY
        if (
            quantity
            or cls._has_order_action_cue(normalized)
            or cls._is_short_catalog_product_phrase(normalized, matched_product)
        ):
            return IntentCategory.PLACE_ORDER
        return None

    @classmethod
    def _extract_quantity_candidate(cls, content: str) -> int | None:
        normalized = cls._normalize_match_text(content)
        digit_match = re.search(
            r"\b([1-9][0-9]?)\s*(binh|chai|can|thung|nuoc|gas)\b",
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
    def _extract_leading_quantity_candidate(content: str) -> int | None:
        match = re.match(r"\s*([1-9][0-9]?)\b", content)
        return int(match.group(1)) if match else None

    @staticmethod
    def _has_order_action_cue(normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in {
                "dat",
                "mua",
                "lay",
                "doi qua",
                "doi sang",
                "chuyen qua",
                "chuyen sang",
            }
        )

    @staticmethod
    def _has_product_question_cue(normalized: str) -> bool:
        return any(
            re.search(rf"\b{re.escape(phrase)}\b", normalized)
            for phrase in {
                "gia",
                "bao nhieu",
                "co ban",
                "con hang",
                "loai nao",
                "san pham nao",
            }
        )

    @classmethod
    def _is_short_catalog_product_phrase(cls, normalized: str, product: ProductResponse) -> bool:
        if cls._has_product_question_cue(normalized):
            return False
        compact = normalized.replace(" ", "")
        candidates = {
            cls._normalize_match_text(product.brand),
            cls._normalize_match_text(product.name),
            cls._normalize_match_text(cls._format_product_display_name(product)),
            cls._normalize_match_text(product.sku),
        }
        if compact in {candidate.replace(" ", "") for candidate in candidates if candidate}:
            return True
        normalized_brand = cls._normalize_match_text(product.brand)
        if normalized_brand and normalized.startswith(normalized_brand):
            size_value = cls._normalize_match_text(cls._format_decimal(product.size_kg))
            unit_value = cls._normalize_match_text(product.unit)
            compact_normalized = normalized.replace(" ", "")
            return (
                f"{size_value}kg" in compact_normalized
                or f"{size_value}{unit_value}" in compact_normalized
            )
        return False

    @staticmethod
    def _merge_order_slots(*sources: ChatOrderSlots | None) -> ChatOrderSlots:
        merged = ChatOrderSlots()
        for source in sources:
            if source is None:
                continue
            merged = replace(
                merged,
                items=ConversationService._merge_order_items(merged.items, source.items),
                customer_name=source.customer_name or merged.customer_name,
                customer_phone=source.customer_phone or merged.customer_phone,
                delivery_address=source.delivery_address or merged.delivery_address,
                delivery_notes=source.delivery_notes or merged.delivery_notes,
                payment_method=source.payment_method or merged.payment_method,
                confirmed=merged.confirmed or source.confirmed,
            )
        return merged

    @staticmethod
    def _merge_order_items(
        current: tuple[ChatOrderItem, ...],
        incoming: tuple[ChatOrderItem, ...],
    ) -> tuple[ChatOrderItem, ...]:
        if not incoming:
            return current
        if not current:
            return incoming
        merged = list(current)
        for incoming_item in incoming:
            incoming_key = ConversationService._normalize_match_text(incoming_item.product or "")
            matching_index = next(
                (
                    index
                    for index, item in enumerate(merged)
                    if incoming_key
                    and ConversationService._normalize_match_text(item.product or "")
                    == incoming_key
                ),
                None,
            )
            if matching_index is None:
                merged.append(incoming_item)
                continue
            current_item = merged[matching_index]
            merged[matching_index] = ChatOrderItem(
                product=incoming_item.product or current_item.product,
                quantity=incoming_item.quantity or current_item.quantity,
            )
        return tuple(merged)

    @classmethod
    def _slots_to_metadata(cls, slots: ChatOrderSlots | None) -> dict[str, Any]:
        if slots is None:
            return {}
        payload: dict[str, Any] = {}
        item_payload = cls._items_to_metadata(slots.items)
        if item_payload:
            payload["items"] = item_payload
        if slots.customer_name:
            payload["customer_name"] = slots.customer_name
        if slots.customer_phone:
            payload["customer_phone"] = slots.customer_phone
        if slots.delivery_address:
            payload["delivery_address"] = slots.delivery_address
        if slots.delivery_notes:
            payload["delivery_notes"] = slots.delivery_notes
        if slots.payment_method:
            payload["payment_method"] = slots.payment_method
        return payload

    @classmethod
    def _items_to_metadata(cls, items: Sequence[ChatOrderItem]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for item in items:
            data: dict[str, Any] = {}
            if item.product:
                data["product"] = item.product
            if item.quantity is not None:
                data["quantity"] = item.quantity
            if data:
                payload.append(data)
        return payload

    @classmethod
    def _items_from_metadata(cls, payload: object) -> tuple[ChatOrderItem, ...]:
        if not isinstance(payload, list):
            return ()
        items: list[ChatOrderItem] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            parsed = ChatOrderItem(
                product=cls._optional_str(item.get("product")),
                quantity=cls._optional_int(item.get("quantity")),
            )
            if parsed.product or parsed.quantity is not None:
                items.append(parsed)
        return tuple(items)

    @classmethod
    def _slots_from_metadata(cls, payload: object) -> ChatOrderSlots | None:
        if not isinstance(payload, dict):
            return None
        items = cls._items_from_metadata(payload.get("items"))
        if not items:
            legacy_item = ChatOrderItem(
                product=cls._optional_str(payload.get("product")),
                quantity=cls._optional_int(payload.get("quantity")),
            )
            if legacy_item.product or legacy_item.quantity is not None:
                items = (legacy_item,)
        return ChatOrderSlots(
            items=items,
            customer_name=cls._optional_str(payload.get("customer_name")),
            customer_phone=cls._optional_str(payload.get("customer_phone")),
            delivery_address=cls._optional_str(payload.get("delivery_address")),
            delivery_notes=cls._optional_str(payload.get("delivery_notes")),
            payment_method=cls._optional_str(payload.get("payment_method")),
        )

    @classmethod
    def _find_reusable_contact_slots(cls, history: Sequence[Message]) -> ChatOrderSlots | None:
        for message in reversed(history):
            documents = message.retrieved_documents or []
            if not isinstance(documents, list):
                continue
            for document in documents:
                if not isinstance(document, dict):
                    continue
                slots = cls._slots_from_metadata(document.get("slots"))
                if slots is not None and cls._has_reusable_contact_slots(slots):
                    return ChatOrderSlots(
                        customer_name=slots.customer_name,
                        customer_phone=slots.customer_phone,
                        delivery_address=slots.delivery_address,
                    )
        return None

    @staticmethod
    def _has_reusable_contact_slots(slots: ChatOrderSlots) -> bool:
        return bool(slots.customer_name or slots.customer_phone or slots.delivery_address)

    @staticmethod
    def _account_default_contact_slots(user: User | None) -> ChatOrderSlots | None:
        if user is None:
            return None
        # Reuse the saved default delivery info (same source checkout prefills from)
        # so an authenticated customer is not asked for name/phone/address again.
        return ChatOrderSlots(
            customer_name=user.full_name,
            customer_phone=user.phone,
            delivery_address=user.address,
            delivery_notes=user.delivery_notes,
        )

    @classmethod
    def _should_confirm_account_contact(
        cls,
        order_state: dict[str, Any] | None,
        slots: ChatOrderSlots,
        matched_items: Sequence[tuple[ChatOrderItem, ProductResponse | None]],
        account_slots: ChatOrderSlots | None,
    ) -> bool:
        return (
            order_state is None
            and bool(matched_items)
            and all(
                product is not None and item.quantity is not None for item, product in matched_items
            )
            and account_slots is not None
            and cls._has_reusable_contact_slots(account_slots)
            and not slots.customer_name
            and not slots.customer_phone
        )

    @classmethod
    def _format_account_contact_question(
        cls,
        slots: ChatOrderSlots | None,
        *,
        include_saved_address: bool = True,
    ) -> str:
        if slots is None:
            return "Bạn cho Qiki xin tên người nhận và số điện thoại để lên đơn nhé."
        parts: list[str] = []
        if slots.customer_name:
            parts.append(f"tên người nhận là **{slots.customer_name}** (theo tài khoản)")
        if slots.customer_phone:
            parts.append(f"số **{cls._format_phone_display(slots.customer_phone)}**")
        # Only offer the saved address when the customer did not type a new one.
        if include_saved_address and slots.delivery_address:
            parts.append(f"giao tới địa chỉ đã lưu **{slots.delivery_address}**")
        detail = ", ".join(parts) if parts else "thông tin tài khoản"
        return f"Dạ {detail} phải không ạ? Nếu khác bạn cho Qiki biết nhé."

    @classmethod
    def _should_confirm_reusable_contact(
        cls,
        order_state: dict[str, Any] | None,
        slots: ChatOrderSlots,
        matched_items: Sequence[tuple[ChatOrderItem, ProductResponse | None]],
        reusable_contact_slots: ChatOrderSlots | None,
    ) -> bool:
        return (
            order_state is None
            and bool(matched_items)
            and all(
                product is not None and item.quantity is not None for item, product in matched_items
            )
            and reusable_contact_slots is not None
            and cls._has_reusable_contact_slots(reusable_contact_slots)
            and not cls._has_reusable_contact_slots(slots)
        )

    @classmethod
    def _format_reusable_contact_question(cls, slots: ChatOrderSlots | None) -> str:
        if slots is None:
            return "Bạn vẫn dùng thông tin giao hàng như lần trước phải không ạ?"
        parts: list[str] = []
        if slots.customer_name:
            parts.append(f"người nhận **{slots.customer_name}**")
        if slots.customer_phone:
            parts.append(f"số **{cls._format_phone_display(slots.customer_phone)}**")
        if slots.delivery_address:
            parts.append(f"giao tới **{slots.delivery_address}**")
        detail = ", ".join(parts) if parts else "thông tin giao hàng cũ"
        return (
            f"Bạn vẫn dùng {detail} như lần trước phải không ạ? "
            "Nếu khác bạn gửi lại giúp Qiki nhé."
        )

    @staticmethod
    def _first_order_item(slots: ChatOrderSlots | None) -> ChatOrderItem | None:
        return slots.items[0] if slots and slots.items else None

    @staticmethod
    def _with_order_items(
        slots: ChatOrderSlots,
        items: Sequence[ChatOrderItem],
    ) -> ChatOrderSlots:
        return replace(slots, items=tuple(items), confirmed=False)

    @classmethod
    def _drop_incomplete_add_items(cls, slots: ChatOrderSlots) -> ChatOrderSlots:
        items = tuple(item for item in slots.items if not cls._is_incomplete_add_item(item))
        return replace(slots, items=items, confirmed=False)

    @classmethod
    def _pending_item_from_state(cls, order_state: dict[str, Any] | None) -> ChatOrderItem | None:
        if order_state is None:
            return None
        items = cls._items_from_metadata(order_state.get("pending_item"))
        return items[0] if items else None

    @classmethod
    def _previous_items_from_state(
        cls,
        order_state: dict[str, Any] | None,
        fallback_slots: ChatOrderSlots | None,
    ) -> tuple[ChatOrderItem, ...]:
        if order_state is not None:
            previous_items = cls._items_from_metadata(order_state.get("previous_items"))
            if previous_items:
                return previous_items
            previous_product = cls._optional_str(order_state.get("previous_product"))
            if previous_product:
                fallback_item = cls._first_order_item(fallback_slots)
                return (
                    ChatOrderItem(
                        product=previous_product,
                        quantity=fallback_item.quantity if fallback_item else None,
                    ),
                )
        return fallback_slots.items if fallback_slots else ()

    @classmethod
    def _detect_order_item_operation(
        cls,
        content: str,
        previous_slots: ChatOrderSlots | None,
        candidate_item: ChatOrderItem | None,
        products: Sequence[ProductResponse],
    ) -> str | None:
        if candidate_item is None or not candidate_item.product:
            return None
        normalized = cls._normalize_match_text(content)
        if cls._has_remove_cue(normalized):
            return "remove"
        if cls._has_add_cue(normalized):
            return "add"
        if cls._has_replace_cue(normalized):
            return "replace"
        previous_items = previous_slots.items if previous_slots else ()
        if not previous_items:
            return "set"
        if cls._find_matching_item_index(previous_items, candidate_item, products) is not None:
            return "merge_existing"
        return "ambiguous"

    @classmethod
    def _detect_order_items_operation(
        cls,
        content: str,
        previous_slots: ChatOrderSlots | None,
        candidate_items: Sequence[ChatOrderItem],
        products: Sequence[ProductResponse],
    ) -> str | None:
        product_items = tuple(item for item in candidate_items if item.product)
        if not product_items:
            return None
        normalized = cls._normalize_match_text(content)
        if cls._has_remove_cue(normalized):
            return "remove"
        if cls._has_add_cue(normalized):
            return "add"
        if cls._has_replace_cue(normalized):
            return "replace"
        previous_items = previous_slots.items if previous_slots else ()
        if not previous_items:
            return "set"
        if all(
            cls._find_matching_item_index(previous_items, item, products) is not None
            for item in product_items
        ):
            return "merge_existing"
        if len(product_items) == 1:
            return cls._detect_order_item_operation(
                content,
                previous_slots,
                product_items[0],
                products,
            )
        return "ambiguous"

    @staticmethod
    def _has_add_cue(normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in {
                "them",
                "them vao",
                "them mot",
                "them 1",
                "lay them",
                "cong them",
                "co them",
                "va ",
            }
        )

    @staticmethod
    def _is_cancel_add_request(normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in {
                "thoi khong them",
                "thoi ko them",
                "khong them nua",
                "ko them nua",
                "khoi them",
                "khong lay them",
                "ko lay them nua",
                "khong lay them nua",
                "khoi lay them",
            }
        )

    @staticmethod
    def _has_replace_cue(normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in {
                "doi",
                "doi sang",
                "doi qua",
                "doi thanh",
                "thay",
                "thay bang",
            }
        )

    @staticmethod
    def _has_remove_cue(normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in {
                "bo",
                "xoa",
                "huy",
            }
        )

    @staticmethod
    def _is_order_cancel_request(normalized: str) -> bool:
        return normalized in {
            "huy",
            "huy don",
            "huy dat",
            "thoi khong dat",
            "khong dat nua",
            "dung dat",
            "khong mua nua",
        } or any(
            phrase in normalized
            for phrase in {
                "huy don",
                "huy dat",
                "thoi khong dat",
                "khong dat nua",
                "dung dat",
                "khong mua nua",
            }
        )

    @classmethod
    def _is_negation(cls, content: str) -> bool:
        normalized = cls._normalize_match_text(content)
        return normalized in {
            "ko",
            "khong",
            "k",
            "ko phai",
            "khong phai",
            "thoi",
            "khong doi",
            "giu nguyen",
        } or any(
            phrase in normalized
            for phrase in {
                "ko phai",
                "khong phai",
                "khong doi",
                "giu nguyen",
            }
        )

    @classmethod
    def _find_matching_item_index(
        cls,
        items: Sequence[ChatOrderItem],
        candidate_item: ChatOrderItem,
        products: Sequence[ProductResponse],
    ) -> int | None:
        candidate_product = cls._match_product(candidate_item.product, products)
        if candidate_product is None:
            return None
        for index, item in enumerate(items):
            item_product = cls._match_product(item.product, products)
            if item_product is not None and item_product.id == candidate_product.id:
                return index
        return None

    @classmethod
    def _replace_first_matching_item(
        cls,
        slots: ChatOrderSlots,
        candidate_item: ChatOrderItem,
        products: Sequence[ProductResponse],
    ) -> ChatOrderSlots:
        items = list(slots.items)
        if not items:
            return cls._with_order_items(slots, (candidate_item,))
        matching_index = cls._find_matching_item_index(items, candidate_item, products)
        replace_index = matching_index if matching_index is not None else 0
        existing = items[replace_index]
        items[replace_index] = ChatOrderItem(
            product=candidate_item.product or existing.product,
            quantity=candidate_item.quantity or existing.quantity,
        )
        return cls._with_order_items(slots, items)

    @classmethod
    def _merge_existing_item(
        cls,
        slots: ChatOrderSlots,
        candidate_item: ChatOrderItem,
        products: Sequence[ProductResponse],
    ) -> ChatOrderSlots:
        items = list(slots.items)
        matching_index = cls._find_matching_item_index(items, candidate_item, products)
        if matching_index is None:
            return cls._with_order_items(slots, [*items, candidate_item])
        existing = items[matching_index]
        items[matching_index] = ChatOrderItem(
            product=candidate_item.product or existing.product,
            quantity=candidate_item.quantity or existing.quantity,
        )
        return cls._with_order_items(slots, items)

    @staticmethod
    def _append_order_item(slots: ChatOrderSlots, candidate_item: ChatOrderItem) -> ChatOrderSlots:
        return replace(slots, items=(*slots.items, candidate_item), confirmed=False)

    @classmethod
    def _append_order_items(
        cls,
        slots: ChatOrderSlots,
        candidate_items: Sequence[ChatOrderItem],
        products: Sequence[ProductResponse],
    ) -> ChatOrderSlots:
        merged_items = slots.items
        for candidate_item in candidate_items:
            merged_items = cls._merge_candidate_items(merged_items, candidate_item, products)
        return replace(slots, items=merged_items, confirmed=False)

    @classmethod
    def _remove_order_item(
        cls,
        slots: ChatOrderSlots,
        candidate_item: ChatOrderItem,
        products: Sequence[ProductResponse],
    ) -> ChatOrderSlots:
        matching_index = cls._find_matching_item_index(slots.items, candidate_item, products)
        if matching_index is None:
            return slots
        return cls._with_order_items(
            slots,
            [item for index, item in enumerate(slots.items) if index != matching_index],
        )

    @classmethod
    def _format_order_item_label(cls, item: ChatOrderItem | None) -> str:
        return item.product if item and item.product else "sản phẩm mới"

    @classmethod
    def _format_add_or_replace_question(
        cls,
        old_item: ChatOrderItem | None,
        new_item: ChatOrderItem,
    ) -> str:
        old_label = cls._format_order_item_label(old_item) or "sản phẩm ban đầu"
        new_label = cls._format_order_item_label(new_item)
        return (
            f"Bạn muốn **thêm** {new_label} vào đơn, hay **đổi** "
            f"{old_label} sang {new_label}? Bạn nhắn 'thêm' hoặc 'đổi' giúp Qiki nhé."
        )

    @classmethod
    def _format_pending_change_clarification(cls) -> str:
        return (
            "Bạn nhắn **đúng** để đổi, **không** để giữ nguyên, " "hoặc **thêm** để đặt thêm nhé."
        )

    @classmethod
    def _pending_change_item(
        cls,
        previous_items: Sequence[ChatOrderItem],
        pending_items: Sequence[ChatOrderItem],
        products: Sequence[ProductResponse],
    ) -> ChatOrderItem | None:
        for pending_item in pending_items:
            if cls._find_matching_item_index(previous_items, pending_item, products) is None:
                return pending_item
        return pending_items[0] if pending_items else None

    @classmethod
    def _should_confirm_product_change(
        cls,
        previous_slots: ChatOrderSlots | None,
        incoming_slots: ChatOrderSlots,
        products: Sequence[ProductResponse],
    ) -> bool:
        previous_item = cls._first_order_item(previous_slots)
        incoming_item = cls._first_order_item(incoming_slots)
        if (
            not previous_item
            or not previous_item.product
            or not incoming_item
            or not incoming_item.product
        ):
            return False
        old_product = cls._match_product(previous_item.product, products)
        new_product = cls._match_product(incoming_item.product, products)
        return (
            old_product is not None and new_product is not None and old_product.id != new_product.id
        )

    @classmethod
    def _format_product_change_question(
        cls,
        previous_product: str | None,
        pending_slots: ChatOrderSlots | None,
    ) -> str:
        new_product = cls._format_order_item_label(cls._first_order_item(pending_slots))
        old_product = previous_product or "sản phẩm ban đầu"
        return (
            f"Bạn muốn đổi sang **{new_product}** thay cho "
            f"**{old_product}** ban đầu phải không ạ?"
        )

    @classmethod
    def _is_keep_previous_product_request(cls, content: str) -> bool:
        normalized = cls._normalize_match_text(content)
        return any(
            phrase in normalized
            for phrase in {
                "giu cu",
                "giu san pham cu",
                "lay cu",
                "lay san pham cu",
                "khong doi",
                "khong doi nua",
            }
        )

    @classmethod
    def _is_affirmation(cls, content: str) -> bool:
        normalized = cls._normalize_match_text(content)
        if normalized in {
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
        }:
            return True
        return any(
            phrase in normalized
            for phrase in (
                "dung roi",
                "phai roi",
                "xac nhan",
                "dong y",
                "chot don",
            )
        )

    @classmethod
    def _missing_order_slots(
        cls,
        slots: ChatOrderSlots,
        matched_items: Sequence[tuple[ChatOrderItem, ProductResponse | None]],
    ) -> list[str]:
        missing: list[str] = []
        if not slots.items or any(product is None for _item, product in matched_items):
            missing.append("sản phẩm")
        if any(item.quantity is None for item in slots.items):
            missing.append("số lượng")
        if not slots.customer_name:
            missing.append("tên người nhận")
        if not slots.customer_phone:
            missing.append("số điện thoại")
        if not slots.delivery_address:
            missing.append("địa chỉ giao hàng chi tiết (số nhà, tên/số đường, khu phố, phường)")
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
    def _format_order_offtopic_message(missing: Sequence[str]) -> str:
        missing_text = (
            missing[0] if len(missing) == 1 else (", ".join(missing[:-1]) + f" và {missing[-1]}")
        )
        return (
            "Qiki chưa rõ ý bạn ạ. "
            f"Mình đang chờ {missing_text} để hoàn tất đơn - bạn gửi giúp nhé, "
            "hoặc nhắn **huỷ** nếu muốn dừng đặt hàng."
        )

    @classmethod
    def _is_unproductive_order_turn(
        cls,
        content: str,
        previous_slots: ChatOrderSlots,
        slots: ChatOrderSlots,
        candidate_items: Sequence[ChatOrderItem],
    ) -> bool:
        if candidate_items:
            return False
        normalized = cls._normalize_match_text(content)
        if (
            cls._is_order_cancel_request(normalized)
            or cls._is_affirmation(content)
            or cls._is_negation(content)
            or cls._has_add_cue(normalized)
            or cls._has_replace_cue(normalized)
            or cls._has_remove_cue(normalized)
        ):
            return False
        return not cls._order_slots_progressed(previous_slots, slots)

    @staticmethod
    def _order_slots_progressed(previous_slots: ChatOrderSlots, slots: ChatOrderSlots) -> bool:
        if len(previous_slots.items) != len(slots.items):
            return True
        for previous_item, item in zip(previous_slots.items, slots.items, strict=True):
            if previous_item.product != item.product or previous_item.quantity != item.quantity:
                return True
        return any(
            getattr(previous_slots, field) != getattr(slots, field)
            for field in (
                "customer_name",
                "customer_phone",
                "delivery_address",
                "delivery_notes",
                "payment_method",
                "confirmed",
            )
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
            haystack_tokens = set(haystack.split())
            query_tokens = query.split()
            specific_token_hit = any(
                token not in GENERIC_PRODUCT_MATCH_TOKENS
                and not token.isdigit()
                and len(token) >= 2
                and token in haystack_tokens
                for token in query_tokens
            )
            if not specific_token_hit:
                continue
            score = 0
            if query and query in haystack:
                score += 4
            for token in query_tokens:
                if token.isdigit() or len(token) < 2:
                    continue
                if token in haystack_tokens:
                    score += 1
            if score > best_score:
                best_score = score
                best_product = product
        return best_product if best_score > 0 else None

    @classmethod
    def _match_order_items(
        cls,
        items: Sequence[ChatOrderItem],
        products: Sequence[ProductResponse],
    ) -> list[tuple[ChatOrderItem, ProductResponse | None]]:
        return [(item, cls._match_product(item.product, products)) for item in items]

    @staticmethod
    def _matched_order_products(
        matched_items: Sequence[tuple[ChatOrderItem, ProductResponse | None]],
    ) -> list[tuple[ChatOrderItem, ProductResponse]]:
        return [(item, product) for item, product in matched_items if product is not None]

    @staticmethod
    def _normalize_match_text(value: str) -> str:
        decomposed = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
        without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
        return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()

    @staticmethod
    def _validate_phone(phone: str) -> str | None:
        try:
            return VietnamesePhoneValidator.validate(phone)
        except ValueError:
            return None

    @staticmethod
    def _format_phone_display(phone: str) -> str:
        if phone.startswith("+84"):
            return "0" + phone[3:]
        return phone

    @classmethod
    def _normalize_payment_method(
        cls, payment_method: str
    ) -> Literal["cod", "bank_transfer"] | None:
        normalized = cls._normalize_match_text(payment_method)
        if normalized in {"cod", "cash", "tien mat"} or "nhan hang" in normalized:
            return "cod"
        if (
            normalized
            in {"bank transfer", "bank_transfer", "chuyen khoan", "ck", "bank", "banking"}
            or "khoan" in normalized
        ):
            return "bank_transfer"
        return None

    @classmethod
    def _format_order_callback_sentence(cls, delivery_notes: str | None = None) -> str:
        now = cls._now_vn()
        if delivery_notes:
            if cls._is_business_open(now):
                return (
                    "Qiki đã ghi chú giao theo khung giờ bạn đề xuất "
                    f"(**{delivery_notes}**), nhân viên sẽ gọi lại xác nhận sớm nhất. "
                    "Cảm ơn bạn!"
                )
            return (
                "Hiện đã ngoài giờ làm việc. "
                "Qiki đã ghi chú giao theo khung giờ bạn đề xuất "
                f"(**{delivery_notes}**), ngày mai nhân viên sẽ gọi lại xác nhận sớm nhất. "
                "Cảm ơn bạn!"
            )
        if cls._is_business_open(now):
            return (
                "**Nhân viên sẽ liên hệ lại xác nhận đơn trong thời gian sớm nhất.** " "Cảm ơn bạn!"
            )
        return (
            "Hiện đã ngoài giờ làm việc. "
            "**Ngày mai nhân viên sẽ gọi lại xác nhận đơn và hẹn giờ giao "
            "trong thời gian sớm nhất.** "
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
        items: Sequence[tuple[ChatOrderItem, ProductResponse]],
        customer_name: str,
        phone: str,
        address: str,
        payment_method: Literal["cod", "bank_transfer"],
    ) -> str:
        product_subtotal = sum(
            (product.price * (item.quantity or 0) for item, product in items),
            Decimal("0"),
        )
        water_quantity = cls._water_item_quantity(items)
        water_delivery_fee = cls._water_delivery_fee(items)
        subtotal = product_subtotal + water_delivery_fee
        payment_label = "COD" if payment_method == "cod" else "chuyển khoản"
        lines = ["Qiki tóm tắt đơn hàng của bạn:"]
        for item, product in items:
            quantity = item.quantity or 0
            line_total = product.price * quantity
            lines.append(
                f"- {product.name} ({product.brand}) × {quantity} — {cls._format_vnd(line_total)}"  # noqa: RUF001
            )
        if water_delivery_fee:
            lines.append(
                f"- Phí giao nước: +{cls._format_vnd(water_delivery_fee)} "
                f"(5k/bình × {water_quantity} bình nước)"  # noqa: RUF001
            )
        lines.extend(
            [
                f"- Tạm tính: **{cls._format_vnd(subtotal)}**",
                f"- Người nhận: **{customer_name}**",
                f"- Số điện thoại: **{cls._format_phone_display(phone)}**",
                f"- Địa chỉ: **{address}**",
                f"- Thanh toán: **{payment_label}**",
            ]
        )
        if water_delivery_fee:
            lines.append("- Ghi chú: Phí lên lầu +5.000đ/lầu (nếu có), nhân viên báo khi giao.")
        lines.extend(["", ORDER_CONFIRMATION_PROMPT])
        return "\n".join(lines)

    @staticmethod
    def _water_item_quantity(items: Sequence[tuple[ChatOrderItem, ProductResponse]]) -> int:
        return sum(item.quantity or 0 for item, product in items if product.category == "nuoc_uong")

    @classmethod
    def _water_delivery_fee(cls, items: Sequence[tuple[ChatOrderItem, ProductResponse]]) -> Decimal:
        return Decimal("5000") * cls._water_item_quantity(items)

    @classmethod
    def _delivery_notes_with_water_fee(
        cls,
        delivery_notes: str | None,
        items: Sequence[tuple[ChatOrderItem, ProductResponse]],
    ) -> str | None:
        if cls._water_delivery_fee(items) <= 0:
            return delivery_notes
        fee_note = "[Phí giao nước +5k/bình; lên lầu +5k/lầu]"
        return f"{fee_note} {delivery_notes}".strip() if delivery_notes else fee_note

    @classmethod
    def _chat_order_idempotency_key(cls, conversation_id: UUID, slots: ChatOrderSlots) -> UUID:
        item_fingerprint = "|".join(
            f"{item.product or ''}:{item.quantity or ''}"
            for item in sorted(
                slots.items, key=lambda item: (item.product or "", item.quantity or 0)
            )
        )
        fingerprint = "|".join(
            [
                str(conversation_id),
                item_fingerprint,
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
            if cls._has_metadata_type(documents, CHAT_ORDER_STATE_METADATA_TYPE):
                return cls._is_order_state_fresh(message)
            return False
        return False

    @classmethod
    def _find_order_state(
        cls, history: Sequence[Message], content: str = ""
    ) -> dict[str, Any] | None:
        for message in reversed(history):
            if message.role != "assistant":
                continue
            documents = message.retrieved_documents or []
            if not isinstance(documents, list):
                continue
            if cls._has_metadata_type(documents, CHAT_ORDER_METADATA_TYPE):
                # An order was already created. A fresh order intent must not
                # replay the completed order, so stop here. Only a bare
                # re-confirmation reuses the prior state, keeping a duplicate
                # confirmation idempotent on the same order.
                if cls._is_affirmation(content):
                    continue
                return None
            for document in documents:
                if (
                    isinstance(document, dict)
                    and document.get("type") == CHAT_ORDER_STATE_METADATA_TYPE
                ):
                    if not cls._is_order_state_fresh(message):
                        return None
                    if document.get("status") == "order_cancelled":
                        return None
                    return document
        return None

    @staticmethod
    def _is_order_state_fresh(message: Message) -> bool:
        created_at = getattr(message, "created_at", None)
        if not isinstance(created_at, datetime):
            return True
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return (datetime.now(UTC) - created_at) <= ORDER_STATE_TTL

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
        metadata_extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {"type": CHAT_ORDER_STATE_METADATA_TYPE, "status": status}
        slot_payload = cls._slots_to_metadata(slots)
        if slot_payload:
            metadata["slots"] = slot_payload
        if metadata_extra:
            metadata.update(metadata_extra)
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
            code=conversation.code,
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
