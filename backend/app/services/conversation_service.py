"""Conversation orchestration service for chatbot and staff messages."""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.core.exceptions import NotFoundException
from app.intent.base import BaseIntentClassifier
from app.intent.categories import IntentCategory
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
from app.schemas.product import ProductResponse
from app.services.product_service import ProductService
from app.services.routing_service import RoutingDecision, RoutingService


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
    ) -> None:
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository
        self.intent_classifier = intent_classifier
        self.routing_service = routing_service
        self.rag_pipeline = rag_pipeline
        self.product_service = product_service

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
            product_cards = [self._product_to_card(product) for product in catalog_products]

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
        size = f"{cls._format_decimal(product.size_kg)}kg"
        normalized_name = product.name.lower().replace(" ", "")
        if size.lower() in normalized_name:
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
            price=product.price,
            image_url=str(product.image_url) if product.image_url else None,
            sku=product.sku,
            stock_quantity=product.stock_quantity,
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
