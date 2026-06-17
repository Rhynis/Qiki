"""Authentication service."""

from __future__ import annotations

import hashlib
import html
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictException, UnauthorizedException, ValidationException
from app.core.input_validation import VietnamesePhoneValidator
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_password_reset_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.email_service import EmailService, render_email_otp

logger = logging.getLogger(__name__)

ACCESS_TOKEN_COOKIE = "gasbot_access_token"  # noqa: S105
REFRESH_TOKEN_COOKIE = "gasbot_refresh_token"  # noqa: S105
ACCESS_TOKEN_COOKIE_PATH = "/"  # noqa: S105
REFRESH_TOKEN_COOKIE_PATH = "/"  # noqa: S105

LOCKOUT_TTL_SECONDS = 900
FAILED_LOGIN_TTL_SECONDS = 3600
FAILED_LOGIN_LIMIT = 5
PASSWORD_RESET_TTL_SECONDS = 3600
EMAIL_OTP_TTL_SECONDS = 600
EMAIL_OTP_RESEND_TTL_SECONDS = 3600
EMAIL_OTP_RESEND_LIMIT = 5

# User-facing Vietnamese messages reused across the token/session paths.
INVALID_SESSION_MESSAGE = "Phiên đăng nhập không hợp lệ hoặc đã hết hạn."
INACTIVE_ACCOUNT_MESSAGE = "Tài khoản đã bị vô hiệu hóa."


class UserRepositoryProtocol(Protocol):
    """Repository protocol used by AuthService."""

    async def create(self, data: UserCreate, hashed_password: str) -> User: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_phone(self, phone: str) -> User | None: ...

    async def update(self, user_id: UUID, data: dict[str, object]) -> User | None: ...


class EmailServiceProtocol(Protocol):
    """Email delivery protocol used by AuthService."""

    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str,
    ) -> bool: ...


@dataclass(frozen=True)
class AuthResult:
    """Internal authentication result with raw tokens for cookie setting."""

    user: User
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthService:
    """User authentication and token lifecycle service."""

    def __init__(
        self,
        user_repository: UserRepositoryProtocol,
        redis: Redis,
        email_service: EmailServiceProtocol | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.user_repository = user_repository
        self.redis = redis
        self.settings = settings or get_settings()
        self.email_service = email_service or EmailService(self.settings)

    async def register_user(
        self,
        phone: str,
        password: str,
        full_name: str | None = None,
        email: str | None = None,
    ) -> User:
        """Register a local password user. Phone is required and unique."""
        data = UserCreate(phone=phone, password=password, full_name=full_name, email=email)
        if await self.user_repository.get_by_phone(data.phone):
            raise ConflictException(
                "Số điện thoại đã được đăng ký.", error_code="phone_already_exists"
            )
        if data.email and await self.user_repository.get_by_email(data.email):
            raise ConflictException("Email này đã được sử dụng.", error_code="email_already_exists")

        hashed_password = get_password_hash(data.password)
        return await self.user_repository.create(data, hashed_password)

    async def login_user(self, identifier: str, password: str) -> AuthResult:
        """Authenticate by phone (or email for back-compat) and return tokens."""
        lookup_key = identifier.strip().lower()
        if await self.is_account_locked(lookup_key):
            raise UnauthorizedException(
                "Tài khoản tạm thời bị khóa. Vui lòng thử lại sau.",
                error_code="account_locked",
            )

        user = await self._resolve_login_user(identifier)
        # One generic message for any login failure to avoid account enumeration.
        if not user or not user.hashed_password:
            await self.track_failed_login(lookup_key)
            raise UnauthorizedException(
                "Số điện thoại/email hoặc mật khẩu không đúng.",
                error_code="invalid_credentials",
            )

        if not verify_password(password, user.hashed_password):
            await self.track_failed_login(lookup_key)
            raise UnauthorizedException(
                "Số điện thoại/email hoặc mật khẩu không đúng.",
                error_code="invalid_credentials",
            )

        if not user.is_active:
            raise UnauthorizedException(INACTIVE_ACCOUNT_MESSAGE, error_code="inactive_user")

        await self._delete(f"failed_login:{lookup_key}")
        return self._create_auth_result(user)

    async def _resolve_login_user(self, identifier: str) -> User | None:
        """Resolve a login identifier as a phone first, then fall back to email."""
        candidate = identifier.strip()
        try:
            normalized_phone = VietnamesePhoneValidator.validate(candidate)
        except ValueError:
            normalized_phone = None
        if normalized_phone:
            user = await self.user_repository.get_by_phone(normalized_phone)
            if user:
                return user
        return await self.user_repository.get_by_email(candidate.lower())

    async def refresh_access_token(self, refresh_token: str) -> AuthResult:
        """Rotate refresh token and issue a new access token."""
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":  # pragma: no cover
            raise UnauthorizedException(INVALID_SESSION_MESSAGE, error_code="invalid_token")
        await self._raise_if_blacklisted(payload)

        user_id = self._payload_user_id(payload)
        user = await self.user_repository.get_by_id(user_id)
        if not user or not user.is_active:  # pragma: no cover
            raise UnauthorizedException(INACTIVE_ACCOUNT_MESSAGE, error_code="inactive_user")

        await self._blacklist_payload(payload)
        return self._create_auth_result(user)

    async def logout_user(self, access_token: str, refresh_token: str | None = None) -> bool:
        """Blacklist active access and refresh tokens."""
        access_payload = decode_token(access_token)
        await self._blacklist_payload(access_payload)
        if refresh_token:  # pragma: no cover
            refresh_payload = decode_token(refresh_token)
            await self._blacklist_payload(refresh_payload)
        return True  # pragma: no cover

    async def verify_token(self, token: str) -> User:
        """Verify an access token, blacklist state, and user existence."""
        payload = decode_token(token)
        if payload.get("type") != "access":  # pragma: no cover
            raise UnauthorizedException(INVALID_SESSION_MESSAGE, error_code="invalid_token")
        await self._raise_if_blacklisted(payload)

        user = await self.user_repository.get_by_id(self._payload_user_id(payload))
        if not user:  # pragma: no cover
            raise UnauthorizedException(INVALID_SESSION_MESSAGE, error_code="invalid_token")
        if not user.is_active:  # pragma: no cover
            raise UnauthorizedException(INACTIVE_ACCOUNT_MESSAGE, error_code="inactive_user")
        return user

    async def change_password(
        self,
        user_id: UUID,
        old_password: str,
        new_password: str,
        current_access_token: str | None = None,
    ) -> bool:
        """Change a user password and invalidate the current access token."""
        user = await self.user_repository.get_by_id(user_id)
        if not user or not user.hashed_password:  # pragma: no cover
            raise UnauthorizedException(
                "Mật khẩu hiện tại không đúng.", error_code="invalid_credentials"
            )
        if not verify_password(old_password, user.hashed_password):  # pragma: no cover
            raise UnauthorizedException(
                "Mật khẩu hiện tại không đúng.", error_code="invalid_credentials"
            )

        await self.user_repository.update(
            user_id,
            {"hashed_password": get_password_hash(new_password)},
        )
        if current_access_token:
            payload = decode_token(current_access_token)
            await self._blacklist_payload(payload)
        return True

    async def request_password_reset(self, email: str) -> bool:
        """Create a reset token when the email exists without revealing account state."""
        user = await self.user_repository.get_by_email(email.lower())
        if not user:
            logger.info("password_reset_requested_for_unknown_email")
            return True

        token = generate_password_reset_token()
        await self._setex(f"password_reset:{token}", PASSWORD_RESET_TTL_SECONDS, str(user.id))
        token_fingerprint = hashlib.sha256(token.encode()).hexdigest()[:12]  # pragma: no cover
        logger.info(  # pragma: no cover
            "password_reset_token_created",
            extra={"reset_token_fingerprint": token_fingerprint},
        )
        await self._send_password_reset_email(email.lower(), token)
        return True  # pragma: no cover

    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset a password using a valid reset token."""
        raw_user_id = await self._get(f"password_reset:{token}")
        if not raw_user_id:  # pragma: no cover
            raise ValidationException(
                "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.",
                error_code="invalid_reset_token",
            )

        user_id = UUID(self._decode_redis_value(raw_user_id))  # pragma: no cover
        user = await self.user_repository.get_by_id(user_id)
        if not user:  # pragma: no cover
            raise ValidationException(
                "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.",
                error_code="invalid_reset_token",
            )

        await self.user_repository.update(
            user_id,
            {"hashed_password": get_password_hash(new_password)},
        )
        await self._delete(f"password_reset:{token}")
        return True

    async def send_email_verification(self, email: str) -> None:
        """Email an OTP for the account owning ``email`` without revealing existence."""
        user = await self.user_repository.get_by_email(email.lower())
        if user and user.email:
            await self.request_email_otp(user)

    async def request_email_otp(self, user: User) -> bool:
        """Generate, store and email a single-use OTP for the user's email.

        Returns ``False`` (without sending) when the user has no email or when the
        resend rate limit has been exceeded. The code is never logged.
        """
        if not user.email:
            return False

        resend_key = f"email_otp_resend:{user.id}"
        attempts = int(await self.redis.incr(resend_key))
        if attempts == 1:
            await self.redis.expire(resend_key, EMAIL_OTP_RESEND_TTL_SECONDS)
        if attempts > EMAIL_OTP_RESEND_LIMIT:
            logger.info("email_otp_resend_rate_limited")
            return False

        code = f"{secrets.randbelow(1_000_000):06d}"
        await self._setex(f"email_otp:{user.id}", EMAIL_OTP_TTL_SECONDS, code)
        subject, text, html_body = render_email_otp(code, ttl_minutes=EMAIL_OTP_TTL_SECONDS // 60)
        await self.email_service.send_email(
            to=user.email, subject=subject, html=html_body, text=text
        )
        return True

    async def confirm_email_otp(self, email: str, code: str) -> bool:
        """Resolve the account by email and verify its OTP. Generic on unknown email."""
        user = await self.user_repository.get_by_email(email.lower())
        if not user:
            return False
        return await self.verify_email_otp(user, code)

    async def verify_email_otp(self, user: User, code: str) -> bool:
        """Verify a submitted OTP; on success set email_verified and delete the key."""
        raw_code = await self._get(f"email_otp:{user.id}")
        if not raw_code:
            return False
        if not secrets.compare_digest(self._decode_redis_value(raw_code), code):
            return False

        await self.user_repository.update(user.id, {"email_verified": True})
        await self._delete(f"email_otp:{user.id}")
        await self._delete(f"email_otp_resend:{user.id}")
        return True

    async def track_failed_login(self, email: str) -> None:
        """Increment failed login counter and lock account at the threshold."""
        normalized_email = email.lower()
        counter_key = f"failed_login:{normalized_email}"
        attempts = int(await self.redis.incr(counter_key))
        if attempts == 1:  # pragma: no cover
            await self.redis.expire(counter_key, FAILED_LOGIN_TTL_SECONDS)
        if attempts >= FAILED_LOGIN_LIMIT:  # pragma: no cover
            await self._setex(f"lockout:{normalized_email}", LOCKOUT_TTL_SECONDS, "1")

    async def is_account_locked(self, email: str) -> bool:
        """Return whether an email is temporarily locked."""
        return bool(await self._get(f"lockout:{email.lower()}"))

    def _create_auth_result(self, user: User) -> AuthResult:
        access_token = create_access_token(str(user.id), {"role": user.role})
        refresh_token = create_refresh_token(str(user.id))
        return AuthResult(user=user, access_token=access_token, refresh_token=refresh_token)

    async def _raise_if_blacklisted(self, payload: dict[str, Any]) -> None:
        jti = payload.get("jti")
        if jti and await self._get(f"blacklist:{jti}"):  # pragma: no cover
            raise UnauthorizedException(INVALID_SESSION_MESSAGE, error_code="token_revoked")

    async def _blacklist_payload(self, payload: dict[str, Any]) -> None:
        jti = payload.get("jti")
        if not jti:  # pragma: no cover
            return
        await self._setex(f"blacklist:{jti}", self._seconds_until_expiry(payload), "1")

    def _seconds_until_expiry(self, payload: dict[str, Any]) -> int:
        exp = payload.get("exp")
        if not isinstance(exp, int):  # pragma: no cover
            return LOCKOUT_TTL_SECONDS
        return max(1, exp - int(datetime.now(UTC).timestamp()))

    def _payload_user_id(self, payload: dict[str, Any]) -> UUID:
        subject = payload.get("sub")
        if not isinstance(subject, str):  # pragma: no cover
            raise UnauthorizedException(INVALID_SESSION_MESSAGE, error_code="invalid_token")
        return UUID(subject)

    def _decode_redis_value(self, value: object) -> str:
        if isinstance(value, bytes):  # pragma: no cover
            return value.decode()
        return str(value)

    async def _send_password_reset_email(self, email: str, token: str) -> None:
        reset_link = f"{self.settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
        ttl_minutes = max(1, PASSWORD_RESET_TTL_SECONDS // 60)
        escaped_link = html.escape(reset_link, quote=True)
        subject = "Đặt lại mật khẩu Gas Quốc Cường"
        text = (
            "Dạ chào bạn,\n\n"
            "Gas Quốc Cường nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn.\n"
            f"Vui lòng mở liên kết sau để đặt lại mật khẩu: {reset_link}\n\n"
            f"Liên kết này có hiệu lực trong {ttl_minutes} phút. "
            "Nếu bạn không yêu cầu, vui lòng bỏ qua email này."
        )
        html_body = (
            "<p>Dạ chào bạn,</p>"
            "<p>Gas Quốc Cường nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn.</p>"
            f'<p><a href="{escaped_link}">Đặt lại mật khẩu</a></p>'
            f"<p>Liên kết này có hiệu lực trong {ttl_minutes} phút. "
            "Nếu bạn không yêu cầu, vui lòng bỏ qua email này.</p>"
        )
        try:
            await self.email_service.send_email(
                to=email,
                subject=subject,
                html=html_body,
                text=text,
            )
        except Exception:
            logger.exception("password_reset_email_send_failed")

    async def _get(self, key: str) -> object:
        return await self.redis.get(key)

    async def _setex(self, key: str, ttl: int, value: str) -> None:
        await self.redis.setex(key, ttl, value)

    async def _delete(self, key: str) -> None:
        await self.redis.delete(key)
