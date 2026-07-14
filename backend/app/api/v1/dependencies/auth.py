"""Authentication dependencies."""

from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, Header
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, GasBotException, UnauthorizedException
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import ACCESS_TOKEN_COOKIE, AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> AuthService:
    """Build the auth service from request-scoped dependencies."""
    return AuthService(UserRepository(session), redis)


async def get_current_access_token(
    cookie_token: Annotated[str | None, Cookie(alias=ACCESS_TOKEN_COOKIE)] = None,
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Read access token from httpOnly cookie first, then Bearer header."""
    if cookie_token:
        return cookie_token
    if bearer_token:
        return bearer_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1]
    raise UnauthorizedException("Authentication required", error_code="not_authenticated")


async def get_current_user(
    token: Annotated[str, Depends(get_current_access_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    """Return the user for a valid, non-blacklisted access token."""
    return await auth_service.verify_token(token)


async def get_current_active_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the current user when active."""
    if not user.is_active:
        raise UnauthorizedException("User account is inactive", error_code="inactive_user")
    return user


async def get_current_admin(user: Annotated[User, Depends(get_current_active_user)]) -> User:
    """Require admin role."""
    if not user.is_admin():
        raise ForbiddenException("Admin role required", error_code="admin_required")
    return user


async def get_current_staff(user: Annotated[User, Depends(get_current_active_user)]) -> User:
    """Require staff or admin role."""
    if not user.is_staff():
        raise ForbiddenException("Staff role required", error_code="staff_required")
    return user


async def get_current_driver(user: Annotated[User, Depends(get_current_active_user)]) -> User:
    """Require driver or admin role (admins can view the driver section)."""
    if not user.is_driver():
        raise ForbiddenException("Driver role required", error_code="driver_required")
    return user


async def get_current_user_optional(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    cookie_token: Annotated[str | None, Cookie(alias=ACCESS_TOKEN_COOKIE)] = None,
) -> User | None:
    """Return current user when auth succeeds; otherwise allow guest access."""
    selected_token = cookie_token or token
    if not selected_token:
        return None
    try:
        return await auth_service.verify_token(selected_token)
    except GasBotException:
        return None


def validate_idempotency_key(
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> UUID:
    """Extract and validate the required checkout idempotency key."""
    return idempotency_key
