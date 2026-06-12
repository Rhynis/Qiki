"""Tests for user password policy schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.user import PasswordResetConfirm, UserCreate, validate_password_strength


def test_validate_password_strength_accepts_simple_eight_character_password() -> None:
    assert validate_password_strength("matkhau1") == "matkhau1"


def test_validate_password_strength_rejects_seven_character_password() -> None:
    with pytest.raises(ValueError, match="Password must be at least 8 characters"):
        validate_password_strength("1234567")


def test_register_schema_accepts_simple_eight_character_password() -> None:
    payload = UserCreate(
        email="user@example.com",
        password="matkhau1",
        full_name="Nguyen Van A",
        phone="0901234567",
    )

    assert payload.password == "matkhau1"


def test_password_reset_schema_accepts_simple_eight_character_password() -> None:
    payload = PasswordResetConfirm(token="reset-token", new_password="matkhau1")

    assert payload.new_password == "matkhau1"


def test_password_reset_schema_rejects_seven_character_password() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PasswordResetConfirm(token="reset-token", new_password="1234567")

    assert "Password must be at least 8 characters" in str(exc_info.value)
