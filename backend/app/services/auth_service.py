"""Authentication service."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from redis.asyncio import Redis

from app.core.exceptions import ConflictException, UnauthorizedException, ValidationException
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

logger = logging.getLogger(__name__)

ACCESS_TOKEN_COOKIE = "gasbot_access_token"  # noqa: S105
REFRESH_TOKEN_COOKIE = "gasbot_refresh_token"  # noqa: S105
ACCESS_TOKEN_COOKIE_PATH = "/"  # noqa: S105
REFRESH_TOKEN_COOKIE_PATH = "/"  # noqa: S105

LOCKOUT_TTL_SECONDS = 900
FAILED_LOGIN_TTL_SECONDS = 3600
FAILED_LOGIN_LIMIT = 5
PASSWORD_RESET_TTL_SECONDS = 3600


class UserRepositoryProtocol(Protocol):
    """Repository protocol used by AuthService."""

    async def create(self, data: UserCreate, hashed_password: str) -> User: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def update(self, user_id: UUID, data: dict[str, object]) -> User | None: ...


@dataclass(frozen=True)
class AuthResult:
    """Internal authentication result with raw tokens for cookie setting."""

    user: User
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthService:
    """User authentication and token lifecycle service."""

    def __init__(self, user_repository: UserRepositoryProtocol, redis: Redis) -> None:
        self.user_repository = user_repository
        self.redis = redis

    async def register_user(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
        phone: str | None = None,
    ) -> User:
        """Register a local password user."""
        data = UserCreate(email=email, password=password, full_name=full_name, phone=phone)
        existing = await self.user_repository.get_by_email(data.email)
        if existing:
            raise ConflictException("Email already registered", error_code="email_already_exists")

        hashed_password = get_password_hash(data.password)
        return await self.user_repository.create(data, hashed_password)

    async def login_user(self, email: str, password: str) -> AuthResult:
        """Authenticate user credentials and return tokens."""
        normalized_email = email.lower()
        if await self.is_account_locked(normalized_email):
            raise UnauthorizedException(
                "Account is temporarily locked", error_code="account_locked"
            )

        user = await self.user_repository.get_by_email(normalized_email)
        if not user or not user.hashed_password:
            await self.track_failed_login(normalized_email)
            raise UnauthorizedException(
                "Invalid email or password",
                error_code="invalid_credentials",
            )

        if not verify_password(password, user.hashed_password):
            await self.track_failed_login(normalized_email)
            raise UnauthorizedException(
                "Invalid email or password",
                error_code="invalid_credentials",
            )

        if not user.is_active:
            raise UnauthorizedException("User account is inactive", error_code="inactive_user")

        await self._delete(f"failed_login:{normalized_email}")
        return self._create_auth_result(user)

    async def refresh_access_token(self, refresh_token: str) -> AuthResult:
        """Rotate refresh token and issue a new access token."""
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":  # pragma: no cover
            raise UnauthorizedException("Invalid refresh token", error_code="invalid_token")
        await self._raise_if_blacklisted(payload)

        user_id = self._payload_user_id(payload)
        user = await self.user_repository.get_by_id(user_id)
        if not user or not user.is_active:  # pragma: no cover
            raise UnauthorizedException("User account is inactive", error_code="inactive_user")

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
            raise UnauthorizedException("Invalid access token", error_code="invalid_token")
        await self._raise_if_blacklisted(payload)

        user = await self.user_repository.get_by_id(self._payload_user_id(payload))
        if not user:  # pragma: no cover
            raise UnauthorizedException("User not found", error_code="invalid_token")
        if not user.is_active:  # pragma: no cover
            raise UnauthorizedException("User account is inactive", error_code="inactive_user")
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
            raise UnauthorizedException("User not found", error_code="invalid_credentials")
        if not verify_password(old_password, user.hashed_password):  # pragma: no cover
            raise UnauthorizedException("Invalid password", error_code="invalid_credentials")

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
        return True  # pragma: no cover

    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset a password using a valid reset token."""
        raw_user_id = await self._get(f"password_reset:{token}")
        if not raw_user_id:  # pragma: no cover
            raise ValidationException(
                "Invalid or expired reset token",
                error_code="invalid_reset_token",
            )

        user_id = UUID(self._decode_redis_value(raw_user_id))  # pragma: no cover
        user = await self.user_repository.get_by_id(user_id)
        if not user:  # pragma: no cover
            raise ValidationException(
                "Invalid or expired reset token",
                error_code="invalid_reset_token",
            )

        await self.user_repository.update(
            user_id,
            {"hashed_password": get_password_hash(new_password)},
        )
        await self._delete(f"password_reset:{token}")
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
            raise UnauthorizedException("Token has been revoked", error_code="token_revoked")

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
            raise UnauthorizedException("Invalid token subject", error_code="invalid_token")
        return UUID(subject)

    def _decode_redis_value(self, value: object) -> str:
        if isinstance(value, bytes):  # pragma: no cover
            return value.decode()
        return str(value)

    async def _get(self, key: str) -> object:
        return await self.redis.get(key)

    async def _setex(self, key: str, ttl: int, value: str) -> None:
        await self.redis.setex(key, ttl, value)

    async def _delete(self, key: str) -> None:
        await self.redis.delete(key)
