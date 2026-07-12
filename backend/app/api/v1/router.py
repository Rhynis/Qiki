"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin_dashboard,
    admin_users,
    auth,
    conversations,
    knowledge_base,
    orders,
    price_alerts,
    products,
    rag,
    review,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(products.router, tags=["Products"])
api_router.include_router(orders.router, tags=["Orders"])
api_router.include_router(admin_dashboard.router, tags=["Admin"])
api_router.include_router(admin_users.router, tags=["Admin"])
api_router.include_router(knowledge_base.router, tags=["Knowledge Base"])
api_router.include_router(rag.router, tags=["RAG"])
api_router.include_router(conversations.router, tags=["Conversations"])
api_router.include_router(review.router, tags=["Review"])
api_router.include_router(price_alerts.router, tags=["Price Alerts"])
