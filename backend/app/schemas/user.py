"""User and authentication schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.input_validation import VietnamesePhoneValidator


def validate_password_strength(password: str) -> str:
    """Validate password length for local accounts."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(password) > 128:
        raise ValueError("Password must be at most 128 characters")
    return password


class UserBase(BaseModel):
    """Shared user fields."""

    email: EmailStr
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return VietnamesePhoneValidator.validate(value)


class UserCreate(UserBase):
    """Registration payload."""

    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserUpdate(BaseModel):
    """User profile update payload."""

    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = None
    address: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return VietnamesePhoneValidator.validate(value)


class UserResponse(UserBase):
    """Public user response without password fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    """Login payload."""

    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class LoginResponse(BaseModel):
    """Login response. Tokens are set in httpOnly cookies."""

    token_type: str = "bearer"
    user: UserResponse


class TokenRefreshRequest(BaseModel):
    """Optional refresh-token payload for non-cookie clients."""

    refresh_token: str | None = None


class TokenRefreshResponse(BaseModel):
    """Refresh response. Rotated tokens are set in httpOnly cookies."""

    token_type: str = "bearer"
    user: UserResponse


class PasswordChangeRequest(BaseModel):
    """Password change payload."""

    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password_strength(value)


class PasswordResetRequest(BaseModel):
    """Password reset request payload."""

    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation payload."""

    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password_strength(value)
