"""User and authentication schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.input_validation import VietnamesePhoneValidator


def validate_password_strength(password: str) -> str:
    """Validate password strength for local accounts."""
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")
    if len(password) > 128:
        raise ValueError("Password must be at most 128 characters")
    if not any(char.isupper() for char in password):
        raise ValueError("Password must include at least one uppercase letter")
    if not any(char.isdigit() for char in password):
        raise ValueError("Password must include at least one digit")
    return password


class UserBase(BaseModel):
    """Shared user fields. Phone-first: email is optional, phone is the identifier."""

    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.lower() if value else None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return VietnamesePhoneValidator.validate(value)


class UserCreate(UserBase):
    """Registration payload. Phone is required; email is optional."""

    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("Phone number is required")
        return VietnamesePhoneValidator.validate(value)

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


class ProfileUpdate(BaseModel):
    """Self-service profile update payload (PATCH /auth/me).

    All fields are optional; only fields present in the request are applied, so a
    partial update never clears an unrelated field.
    """

    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = None
    address: str | None = None
    delivery_ward: str | None = Field(default=None, max_length=100)
    delivery_city: str | None = Field(default=None, max_length=100)
    delivery_notes: str | None = None

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
    email_verified: bool = False
    address: str | None = None
    delivery_ward: str | None = None
    delivery_city: str | None = None
    delivery_notes: str | None = None
    created_at: datetime


class LoginRequest(BaseModel):
    """Login payload. The identifier is a phone number or, for back-compat, an email."""

    identifier: str = Field(min_length=1)
    password: str

    @field_validator("identifier")
    @classmethod
    def strip_identifier(cls, value: str) -> str:
        return value.strip()


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


class EmailOtpRequest(BaseModel):
    """Request an email-verification OTP for the given email."""

    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class EmailOtpVerify(BaseModel):
    """Submit an email-verification OTP code."""

    email: EmailStr
    code: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        normalized = value.strip()
        if not (len(normalized) == 6 and normalized.isdigit()):
            raise ValueError("OTP code must be 6 digits")
        return normalized
