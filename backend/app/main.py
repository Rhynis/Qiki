"""FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from redis.asyncio import Redis
from redis.exceptions import RedisError
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import GasBotException
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import limiter
from app.core.security_middleware import (
    AuditLogMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from app.db.session import check_db_health

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize and close application resources."""
    configure_logging()
    if settings.is_production and settings.SENTRY_DSN:
        sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)

    app.state.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    # LangGraph checkpointer pool (ADR-0002): separate psycopg pool to the same
    # Postgres instance, only opened when the agent is enabled so the default
    # (off) deployment has zero extra startup cost or connections.
    agent_checkpointer_pool: AsyncConnectionPool | None = None
    if settings.AGENT_ENABLED:
        agent_checkpointer_pool = AsyncConnectionPool(
            settings.langgraph_db_uri,
            kwargs={
                # prepare_threshold=None disables server-side prepared
                # statements — required for Supabase's Supavisor pooler in
                # transaction-pooling mode, the psycopg equivalent of
                # asyncpg's statement_cache_size=0 in db/session.py (same
                # underlying pooler constraint).
                "prepare_threshold": None,
                "row_factory": dict_row,
                # checkpointer.setup() runs CREATE INDEX CONCURRENTLY, which
                # Postgres refuses inside a transaction block; psycopg
                # defaults to autocommit=False (implicit transactions), so
                # this must be explicit. AsyncPostgresSaver.from_conn_string()
                # sets the same flag for the same reason.
                "autocommit": True,
            },
            min_size=1,
            max_size=5,
            open=False,
        )
        await agent_checkpointer_pool.open()
        checkpointer = AsyncPostgresSaver(conn=agent_checkpointer_pool)
        await checkpointer.setup()
        app.state.agent_checkpointer = checkpointer
        logger.info("agent_checkpointer_ready")

    logger.info("application_started", environment=settings.ENVIRONMENT)

    yield

    if agent_checkpointer_pool is not None:
        await agent_checkpointer_pool.close()
    await app.state.redis.aclose()
    logger.info("application_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    app = FastAPI(
        title="Gas Quốc Cường API",
        description="Simple gas LPG sales website with Vietnamese AI chatbot",
        version="0.1.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )

    app.state.limiter = limiter

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(GasBotException)
    async def gasbot_exception_handler(
        request: Request,
        exc: GasBotException,
    ) -> JSONResponse:
        """Return normalized application errors."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": exc.error_code,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Return normalized validation errors."""
        return JSONResponse(
            status_code=422,
            content={
                "detail": jsonable_encoder(exc.errors()),
                "error_code": "request_validation_error",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        """Return normalized rate limit errors."""
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded",
                "error_code": "rate_limited",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    # HEAD is allowed so lightweight uptime checks (e.g. UptimeRobot free tier, which only
    # sends HEAD) get a 200 instead of 405 — GET returns the JSON body as before.
    @app.api_route("/health", methods=["GET", "HEAD"], tags=["Health"])
    async def health() -> dict[str, str]:
        """Basic health check endpoint."""
        return {"status": "ok"}

    @app.get("/health/detailed", tags=["Health"])
    async def detailed_health(request: Request) -> dict[str, Any]:
        """Detailed health check endpoint."""
        redis_ok = False
        try:
            redis_ok = await request.app.state.redis.ping()
        except RedisError:
            redis_ok = False

        database_ok = await check_db_health()
        status = "healthy" if database_ok and redis_ok else "degraded"
        return {
            "status": status,
            "database": "ok" if database_ok else "error",
            "redis": "ok" if redis_ok else "error",
            "llm_provider": settings.LLM_PROVIDER,
            "llm_model": settings.OLLAMA_MODEL
            if settings.LLM_PROVIDER == "ollama"
            else settings.GEMINI_MODEL,
            "is_local_demo": settings.is_local_demo,
        }

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
