"""Admin conversation mining insights endpoint."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_staff
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.insights import ConversationInsights
from app.services.insights_service import InsightsService

router = APIRouter()


def get_insights_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InsightsService:
    """Build the request-scoped insights service."""
    return InsightsService(session)


@router.get(
    "/admin/insights",
    response_model=ConversationInsights,
    summary="Get conversation mining insights",
)
@limiter.limit("30/minute")
async def get_conversation_insights(
    request: Request,
    staff: Annotated[User, Depends(get_current_staff)],
    service: Annotated[InsightsService, Depends(get_insights_service)],
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
    top_limit: Annotated[int, Query(ge=1, le=50)] = 10,
    gap_limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationInsights:
    """Return aggregated conversation insights for staff over a period."""
    del request, staff
    return await service.get_insights(
        period_start=date_from,
        period_end=date_to,
        top_limit=top_limit,
        gap_limit=gap_limit,
    )
