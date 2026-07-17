"""Admin-in-chat endpoint: manage the catalog through Qiki (admin only)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_admin
from app.core.rate_limit import limiter
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.admin_chat import AdminChatRequest, AdminChatResponse
from app.services.admin_chat_service import AdminChatService
from app.services.product_service import ProductService

router = APIRouter()


def get_admin_chat_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> AdminChatService:
    """Build the request-scoped admin-chat service."""
    product_repository = ProductRepository(session)
    return AdminChatService(
        product_service=ProductService(product_repository),
        product_repository=product_repository,
        audit_repository=AdminAuditRepository(session),
        redis=redis,
    )


@router.post(
    "/admin/chat",
    response_model=AdminChatResponse,
    summary="Send an admin management instruction to Qiki",
)
@limiter.limit("30/minute")
async def admin_chat(
    request: Request,
    payload: AdminChatRequest,
    # Resolve the admin gate BEFORE the service dependency so a non-admin is
    # rejected without building the DB/Redis-backed service.
    admin: Annotated[User, Depends(get_current_admin)],
    service: Annotated[AdminChatService, Depends(get_admin_chat_service)],
) -> AdminChatResponse:
    """Parse/confirm/execute an admin catalog command. Admin role required."""
    del request
    return await service.handle(payload, admin)
