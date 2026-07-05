"""Authentication endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Request, Response, status

from app.api.v1.dependencies.auth import (
    get_auth_service,
    get_current_access_token,
    get_current_active_user,
)
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedException, ValidationException
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.user import (
    EmailOtpRequest,
    EmailOtpVerify,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    ProfileUpdate,
    TokenRefreshRequest,
    TokenRefreshResponse,
    UserCreate,
    UserResponse,
)
from app.services.auth_service import (
    ACCESS_TOKEN_COOKIE,
    ACCESS_TOKEN_COOKIE_PATH,
    INVALID_SESSION_MESSAGE,
    REFRESH_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE_PATH,
    AuthResult,
    AuthService,
)

router = APIRouter()
settings = get_settings()
_COOKIE_SAMESITE: Literal["lax"] = "lax"


def _set_auth_cookies(response: Response, result: AuthResult) -> None:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        result.access_token,
        httponly=True,
        secure=settings.is_production,
        samesite=_COOKIE_SAMESITE,
        path=ACCESS_TOKEN_COOKIE_PATH,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        result.refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite=_COOKIE_SAMESITE,
        path=REFRESH_TOKEN_COOKIE_PATH,
    )


def _delete_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        ACCESS_TOKEN_COOKIE, path=ACCESS_TOKEN_COOKIE_PATH, samesite=_COOKIE_SAMESITE
    )
    response.delete_cookie(
        REFRESH_TOKEN_COOKIE, path=REFRESH_TOKEN_COOKIE_PATH, samesite=_COOKIE_SAMESITE
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Register a customer account",
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    payload: UserCreate,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    """Create a new customer account."""
    return await auth_service.register_user(
        phone=payload.phone,
        password=payload.password,
        full_name=payload.full_name,
        email=payload.email,
    )


@router.post("/login", response_model=LoginResponse, summary="Log in with phone and password")
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    """Authenticate credentials and set auth cookies."""
    result = await auth_service.login_user(payload.identifier, payload.password)
    _set_auth_cookies(response, result)
    return LoginResponse(user=UserResponse.model_validate(result.user))


@router.post("/refresh", response_model=TokenRefreshResponse, summary="Refresh auth cookies")
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    payload: Annotated[TokenRefreshRequest | None, Body()] = None,
) -> TokenRefreshResponse:
    """Rotate refresh token from cookie or optional body."""
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not refresh_token and payload:
        refresh_token = payload.refresh_token
    if not refresh_token:
        raise UnauthorizedException(INVALID_SESSION_MESSAGE, error_code="not_authenticated")
    result = await auth_service.refresh_access_token(refresh_token)
    _set_auth_cookies(response, result)
    return TokenRefreshResponse(user=UserResponse.model_validate(result.user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Log out")
@limiter.limit("30/minute")
async def logout(
    request: Request,
    token: Annotated[str, Depends(get_current_access_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    """Blacklist the active access token and clear auth cookies."""
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    await auth_service.logout_user(token, refresh_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _delete_auth_cookies(response)
    return response


@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    payload: PasswordChangeRequest,
    token: Annotated[str, Depends(get_current_access_token)],
    user: Annotated[User, Depends(get_current_active_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    """Change password and revoke the current access token."""
    await auth_service.change_password(user.id, payload.old_password, payload.new_password, token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _delete_auth_cookies(response)
    return response


@router.post("/password/reset-request", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, str]:
    """Request a password reset without revealing whether the email exists."""
    await auth_service.request_password_reset(payload.email)
    return {"detail": "Nếu email tồn tại, hướng dẫn đặt lại mật khẩu đã được gửi."}


@router.post("/password/reset", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    payload: PasswordResetConfirm,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, str]:
    """Reset password using a valid reset token."""
    await auth_service.reset_password(payload.token, payload.new_password)
    return {"detail": "Mật khẩu đã được cập nhật."}


@router.post("/email/otp-request", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def request_email_otp(
    request: Request,
    payload: EmailOtpRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, str]:
    """Email a verification code without revealing whether the email exists."""
    await auth_service.send_email_verification(payload.email)
    return {"detail": "Nếu email hợp lệ, mã xác minh đã được gửi."}


@router.post("/email/otp-verify", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def verify_email_otp(
    request: Request,
    payload: EmailOtpVerify,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, bool]:
    """Verify an email with its OTP code. Generic failure avoids enumeration."""
    verified = await auth_service.confirm_email_otp(payload.email, payload.code)
    if not verified:
        raise ValidationException(
            "Mã xác minh không đúng hoặc đã hết hạn",
            error_code="invalid_email_otp",
        )
    return {"verified": True}


@router.get("/me", response_model=UserResponse, summary="Get current user")
@limiter.limit("60/minute")
async def me(
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Return current authenticated user."""
    return user


@router.patch("/me", response_model=UserResponse, summary="Update current user profile")
@limiter.limit("30/minute")
async def update_me(
    request: Request,
    payload: ProfileUpdate,
    user: Annotated[User, Depends(get_current_active_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    """Update the caller's profile and default delivery info.

    Only fields present in the request are applied (partial update), so saving
    one field never clears another.
    """
    changes = payload.model_dump(exclude_unset=True)
    return await auth_service.update_profile(user.id, changes)
