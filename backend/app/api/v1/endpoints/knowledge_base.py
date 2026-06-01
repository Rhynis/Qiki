"""Knowledge base endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_admin, get_current_staff
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.rag.embeddings import EmbeddingService
from app.rag.jina_embeddings import JinaEmbeddingService
from app.rag.text_processor import VietnameseTextProcessor
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseImportResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResult,
    KnowledgeBaseStatistics,
    KnowledgeBaseUpdate,
    KnowledgeCategory,
)
from app.services.knowledge_base_service import KnowledgeBaseService

router = APIRouter()


def get_knowledge_base_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeBaseService:
    """Build a request-scoped knowledge base service."""
    return KnowledgeBaseService(
        KnowledgeBaseRepository(session),
        EmbeddingService(),
        JinaEmbeddingService(),
        VietnameseTextProcessor(),
    )


@router.get(
    "/admin/knowledge-base",
    response_model=KnowledgeBaseListResponse,
    summary="List knowledge base documents",
)
@limiter.limit("60/minute")
async def list_knowledge_base(
    request: Request,
    admin: Annotated[User, Depends(get_current_admin)],
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
    category: Annotated[KnowledgeCategory | None, Query()] = None,
    active_only: bool = True,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> KnowledgeBaseListResponse:
    """List knowledge base documents for admin users."""
    del request
    return await service.list_documents(
        admin,
        skip=skip,
        limit=limit,
        category=category,
        active_only=active_only,
    )


@router.post(
    "/admin/knowledge-base",
    status_code=status.HTTP_201_CREATED,
    response_model=KnowledgeBaseResponse,
    summary="Create knowledge base document",
)
@limiter.limit("30/minute")
async def create_knowledge_base_document(
    request: Request,
    payload: KnowledgeBaseCreate,
    admin: Annotated[User, Depends(get_current_admin)],
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> KnowledgeBaseResponse:
    """Create one document and generate its embedding."""
    del request
    return await service.create_document(payload, admin)


@router.get(
    "/admin/knowledge-base/statistics",
    response_model=KnowledgeBaseStatistics,
    summary="Get knowledge base statistics",
)
@limiter.limit("60/minute")
async def knowledge_base_statistics(
    request: Request,
    admin: Annotated[User, Depends(get_current_admin)],
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> KnowledgeBaseStatistics:
    """Return knowledge base counts by category."""
    del request
    return await service.get_statistics(admin)


@router.post(
    "/admin/knowledge-base/import",
    response_model=KnowledgeBaseImportResponse,
    summary="Import knowledge base documents",
)
@limiter.limit("10/minute")
async def import_knowledge_base_documents(
    request: Request,
    admin: Annotated[User, Depends(get_current_admin)],
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
    file: Annotated[UploadFile, File()],
    category: Annotated[KnowledgeCategory | None, Query()] = None,
) -> KnowledgeBaseImportResponse:
    """Import documents from an uploaded CSV, JSON, TXT, or Markdown file."""
    del request
    return await service.bulk_import_from_file(file, category, admin)


@router.get(
    "/admin/knowledge-base/{kb_id}",
    response_model=KnowledgeBaseResponse,
    summary="Get knowledge base document",
)
@limiter.limit("60/minute")
async def get_knowledge_base_document(
    request: Request,
    kb_id: UUID,
    admin: Annotated[User, Depends(get_current_admin)],
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> KnowledgeBaseResponse:
    """Return one knowledge base document."""
    del request
    return await service.get_document(kb_id, admin)


@router.patch(
    "/admin/knowledge-base/{kb_id}",
    response_model=KnowledgeBaseResponse,
    summary="Update knowledge base document",
)
@limiter.limit("30/minute")
async def update_knowledge_base_document(
    request: Request,
    kb_id: UUID,
    payload: KnowledgeBaseUpdate,
    admin: Annotated[User, Depends(get_current_admin)],
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> KnowledgeBaseResponse:
    """Update a document and regenerate embedding if content changed."""
    del request
    return await service.update_document(kb_id, payload, admin)


@router.delete(
    "/admin/knowledge-base/{kb_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete knowledge base document",
)
@limiter.limit("30/minute")
async def delete_knowledge_base_document(
    request: Request,
    kb_id: UUID,
    admin: Annotated[User, Depends(get_current_admin)],
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> Response:
    """Soft-delete a knowledge base document."""
    del request
    await service.delete_document(kb_id, admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/knowledge-base/search",
    response_model=list[KnowledgeBaseSearchResult],
    summary="Search knowledge base",
)
@limiter.limit("60/minute")
async def search_knowledge_base(
    request: Request,
    payload: KnowledgeBaseSearchRequest,
    staff: Annotated[User, Depends(get_current_staff)],
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> list[KnowledgeBaseSearchResult]:
    """Search knowledge base documents for retrieval testing."""
    del request, staff
    return await service.search_documents(
        payload.query,
        top_k=payload.top_k,
        category=payload.category,
        use_hybrid=payload.use_hybrid,
    )
