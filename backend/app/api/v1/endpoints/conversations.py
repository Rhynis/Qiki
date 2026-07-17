"""Conversation management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_staff, get_current_user_optional
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.intent.base import BaseIntentClassifier
from app.intent.classifiers import (
    EmbeddingIntentClassifier,
    HybridIntentClassifier,
    LLMIntentClassifier,
)
from app.llm.base import BaseLLMProvider
from app.llm.dependencies import get_llm_provider, get_prompt_library
from app.llm.prompts.templates import PromptLibrary
from app.models.user import User
from app.rag.dependencies import get_embedding_service, get_rag_pipeline
from app.rag.embeddings import EmbeddingService
from app.rag.pipeline import RAGPipeline
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.user_repository import UserRepository
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationResponse,
    ConversationStatusUpdate,
    FeedbackRequest,
    ResolveRequest,
    SendMessageRequest,
    SendMessageResponse,
    StaffMessageRequest,
    TransferRequest,
)
from app.schemas.message import MessageListResponse, MessageResponse
from app.services.conversation_service import ConversationService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.routing_service import RoutingService

router = APIRouter()


def get_intent_classifier(
    embedding_service: Annotated[EmbeddingService, Depends(get_embedding_service)],
    llm_provider: Annotated[BaseLLMProvider, Depends(get_llm_provider)],
    prompt_library: Annotated[PromptLibrary, Depends(get_prompt_library)],
) -> BaseIntentClassifier:
    """Build the hybrid intent classifier."""
    embedding = EmbeddingIntentClassifier(embedding_service)
    llm = LLMIntentClassifier(llm_provider, prompt_library)
    return HybridIntentClassifier(embedding, llm, confidence_threshold=0.7)


def get_conversation_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    intent_classifier: Annotated[BaseIntentClassifier, Depends(get_intent_classifier)],
    rag_pipeline: Annotated[RAGPipeline, Depends(get_rag_pipeline)],
    llm_provider: Annotated[BaseLLMProvider, Depends(get_llm_provider)],
) -> ConversationService:
    """Build the request-scoped conversation service."""
    return ConversationService(
        conversation_repository=ConversationRepository(session),
        message_repository=MessageRepository(session),
        intent_classifier=intent_classifier,
        routing_service=RoutingService(UserRepository(session)),
        rag_pipeline=rag_pipeline,
        product_service=ProductService(ProductRepository(session)),
        order_service=OrderService(OrderRepository(session), ProductRepository(session)),
        llm_provider=llm_provider,
        session=session,
    )


@router.post(
    "/conversations/start",
    response_model=ConversationResponse,
    summary="Start a chatbot conversation",
)
@limiter.limit("20/minute")
async def start_conversation(
    request: Request,
    payload: ConversationCreateRequest,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
) -> ConversationResponse:
    """Start a customer conversation."""
    del request
    return await service.start_conversation(
        user=current_user,
        session_id=payload.session_id,
        initial_message=payload.initial_message,
        locale=payload.locale,
    )


@router.get(
    "/conversations/active",
    response_model=ConversationResponse | None,
    summary="Get active conversation for a session",
)
async def get_active_conversation(
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    session_id: Annotated[str | None, Query(max_length=100)] = None,
) -> ConversationResponse | None:
    """Return the active conversation for a user or anonymous session."""
    return await service.get_active_conversation(user=current_user, session_id=session_id)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get a conversation",
)
async def get_conversation(
    conversation_id: UUID,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationResponse:
    """Return a conversation by ID."""
    return await service.get_conversation(conversation_id)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="List conversation messages",
)
async def list_messages(
    conversation_id: UUID,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> MessageListResponse:
    """List messages for a conversation."""
    items = await service.list_messages(conversation_id, skip=skip, limit=limit)
    return MessageListResponse(items=items, total=len(items), skip=skip, limit=limit)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
    summary="Send a customer message",
)
@limiter.limit("10/minute")
async def send_message(
    request: Request,
    conversation_id: UUID,
    payload: SendMessageRequest,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
) -> SendMessageResponse:
    """Send a customer message and return the bot response."""
    del request
    return await service.send_message(conversation_id, payload, user=current_user)


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/feedback",
    response_model=MessageResponse,
    summary="Submit message feedback",
)
async def submit_feedback(
    conversation_id: UUID,
    message_id: UUID,
    payload: FeedbackRequest,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> MessageResponse:
    """Submit feedback for an assistant message."""
    del conversation_id
    return await service.submit_feedback(message_id, payload.score)


@router.post(
    "/conversations/{conversation_id}/resolve",
    response_model=ConversationResponse,
    summary="Resolve a conversation",
)
async def resolve_conversation(
    conversation_id: UUID,
    payload: ResolveRequest,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationResponse:
    """Resolve a customer conversation."""
    return await service.resolve_conversation(conversation_id, payload.satisfaction_rating)


@router.get(
    "/staff/conversations/assigned",
    response_model=ConversationListResponse,
    summary="List assigned staff conversations",
)
async def list_staff_conversations(
    staff: Annotated[User, Depends(get_current_staff)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ConversationListResponse:
    """List conversations assigned to staff."""
    items, total = await service.list_staff_conversations(staff, status, skip, limit)
    return ConversationListResponse(items=items, total=total, skip=skip, limit=limit)


@router.post(
    "/staff/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    summary="Send a staff message",
)
async def staff_send_message(
    conversation_id: UUID,
    payload: StaffMessageRequest,
    staff: Annotated[User, Depends(get_current_staff)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> MessageResponse:
    """Send a staff reply."""
    return await service.staff_send_message(conversation_id, payload.content, staff)


@router.patch(
    "/staff/conversations/{conversation_id}/status",
    response_model=ConversationResponse,
    summary="Set a conversation status",
)
async def set_conversation_status(
    conversation_id: UUID,
    payload: ConversationStatusUpdate,
    staff: Annotated[User, Depends(get_current_staff)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationResponse:
    """Set a conversation status directly (staff action)."""
    del staff
    return await service.set_conversation_status(conversation_id, payload.status)


@router.post(
    "/staff/conversations/{conversation_id}/transfer",
    response_model=ConversationResponse,
    summary="Transfer a staff conversation",
)
async def transfer_conversation(
    conversation_id: UUID,
    payload: TransferRequest,
    staff: Annotated[User, Depends(get_current_staff)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationResponse:
    """Transfer a staff conversation."""
    del staff
    return await service.transfer_conversation(conversation_id, payload.staff_id)
