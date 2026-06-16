"""Admin user management endpoints."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_admin
from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User

router = APIRouter()

UserRole = Literal["customer", "staff", "admin"]


class AdminUserResponse(BaseModel):
    """User management response without password fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr | None
    full_name: str | None
    phone: str | None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminUserListResponse(BaseModel):
    """Paginated admin user list."""

    items: list[AdminUserResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class AdminUserRoleUpdate(BaseModel):
    """Role update payload."""

    role: UserRole


class AdminUserStatusUpdate(BaseModel):
    """Activation status update payload."""

    is_active: bool = Field(description="Whether the user account is active")


async def _get_user_or_404(session: AsyncSession, user_id: UUID) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise NotFoundException("User not found", error_code="user_not_found")
    return user


async def _count_admins(session: AsyncSession, *, active_only: bool = False) -> int:
    statement = select(func.count()).select_from(User).where(User.role == "admin")
    if active_only:
        statement = statement.where(User.is_active.is_(True))
    result = await session.execute(statement)
    return int(result.scalar_one())


async def _ensure_admin_change_is_safe(
    session: AsyncSession,
    target: User,
    *,
    new_role: str | None = None,
    new_is_active: bool | None = None,
) -> None:
    if target.role != "admin":
        return
    if new_role is not None and new_role != "admin" and await _count_admins(session) <= 1:
        raise ValidationException(
            "Cannot demote the final admin user",
            error_code="final_admin_required",
        )
    if (
        new_is_active is False
        and target.is_active
        and await _count_admins(session, active_only=True) <= 1
    ):
        raise ValidationException(
            "Cannot deactivate the final active admin user",
            error_code="final_admin_required",
        )


@router.get(
    "/admin/users",
    response_model=AdminUserListResponse,
    summary="List users",
)
@limiter.limit("60/minute")
async def list_admin_users(
    request: Request,
    admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    email: Annotated[str | None, Query(max_length=255)] = None,
    role: Annotated[UserRole | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminUserListResponse:
    """Return users with admin-only filtering and pagination."""
    del request, admin
    filters: list[ColumnElement[bool]] = []
    if email:
        filters.append(User.email.ilike(f"%{email.lower()}%"))
    if role:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))

    count_statement = select(func.count()).select_from(User).where(*filters)
    list_statement = (
        select(User)
        .where(*filters)
        .order_by(User.created_at.desc(), User.email.asc())
        .offset(skip)
        .limit(limit)
    )

    total = int((await session.execute(count_statement)).scalar_one())
    users = list((await session.execute(list_statement)).scalars().all())
    page = (skip // limit) + 1
    return AdminUserListResponse(
        items=[AdminUserResponse.model_validate(user) for user in users],
        total=total,
        page=page,
        limit=limit,
        has_more=skip + len(users) < total,
    )


@router.patch(
    "/admin/users/{user_id}/role",
    response_model=AdminUserResponse,
    summary="Update user role",
)
@limiter.limit("30/minute")
async def update_admin_user_role(
    request: Request,
    user_id: UUID,
    payload: AdminUserRoleUpdate,
    admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    """Update another user's role as an admin."""
    del request
    if user_id == admin.id:
        raise ForbiddenException(
            "Admins cannot change their own role",
            error_code="self_role_change_forbidden",
        )

    user = await _get_user_or_404(session, user_id)
    await _ensure_admin_change_is_safe(session, user, new_role=payload.role)
    user.role = payload.role
    await session.commit()
    await session.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.patch(
    "/admin/users/{user_id}/status",
    response_model=AdminUserResponse,
    summary="Update user activation status",
)
@limiter.limit("30/minute")
async def update_admin_user_status(
    request: Request,
    user_id: UUID,
    payload: AdminUserStatusUpdate,
    admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    """Activate or deactivate another user as an admin."""
    del request
    if user_id == admin.id:
        raise ForbiddenException(
            "Admins cannot change their own status",
            error_code="self_status_change_forbidden",
        )

    user = await _get_user_or_404(session, user_id)
    await _ensure_admin_change_is_safe(session, user, new_is_active=payload.is_active)
    user.is_active = payload.is_active
    await session.commit()
    await session.refresh(user)
    return AdminUserResponse.model_validate(user)
