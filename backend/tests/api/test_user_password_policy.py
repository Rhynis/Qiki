"""Tests for user password policy schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.user import PasswordResetConfirm, UserCreate, validate_password_strength


def test_validate_password_strength_accepts_six_char_password_with_uppercase_and_digit() -> None:
    assert validate_password_strength("Abc123") == "Abc123"


def test_validate_password_strength_rejects_five_character_password() -> None:
    with pytest.raises(ValueError, match="Password must be at least 6 characters"):
        validate_password_strength("Abc12")


def test_validate_password_strength_rejects_missing_uppercase() -> None:
    with pytest.raises(ValueError, match="Password must include at least one uppercase letter"):
        validate_password_strength("abc123")


def test_validate_password_strength_rejects_missing_digit() -> None:
    with pytest.raises(ValueError, match="Password must include at least one digit"):
        validate_password_strength("Abcdef")


def test_register_schema_accepts_six_char_password_with_uppercase_and_digit() -> None:
    payload = UserCreate(
        email="user@example.com",
        password="Abc123",
        full_name="Nguyen Van A",
        phone="0901234567",
    )

    assert payload.password == "Abc123"


def test_password_reset_schema_accepts_six_char_password_with_uppercase_and_digit() -> None:
    payload = PasswordResetConfirm(token="reset-token", new_password="Abc123")

    assert payload.new_password == "Abc123"


def test_password_reset_schema_rejects_five_character_password() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PasswordResetConfirm(token="reset-token", new_password="Abc12")

    assert "Password must be at least 6 characters" in str(exc_info.value)
