"""Tests for transactional email delivery."""

from email.message import EmailMessage
from typing import Any

import aiosmtplib
import pytest

from app.core.config import Settings
from app.services.email_service import EmailService

pytestmark = pytest.mark.asyncio

RESET_LINK = "http://localhost:3000/reset-password?token=abc123"


def _smtp_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "EMAIL_PROVIDER": "smtp",
        "SMTP_USERNAME": "shop@gmail.com",
        "SMTP_PASSWORD": "app-password",
        "EMAIL_FROM": "Gas Quốc Cường <shop@gmail.com>",
    }
    base.update(overrides)
    return Settings(**base)


def _message_bodies(message: EmailMessage) -> list[str]:
    return [
        part.get_content()
        for part in message.walk()
        if part.get_content_type() in {"text/plain", "text/html"}
    ]


async def test_email_service_noops_without_resend_api_key() -> None:
    service = EmailService(Settings(EMAIL_PROVIDER="resend", RESEND_API_KEY=""))

    result = await service.send_email(
        to="user@example.com",
        subject="Test",
        html="<p>Hello</p>",
        text="Hello",
    )

    assert result is False


async def test_email_service_smtp_sends(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_send(message: EmailMessage, **kwargs: Any) -> None:
        captured["message"] = message
        captured["kwargs"] = kwargs

    monkeypatch.setattr("app.services.email_service.aiosmtplib.send", fake_send)
    service = EmailService(_smtp_settings())

    result = await service.send_email(
        to="customer@example.com",
        subject="Đặt lại mật khẩu",
        html=f'<p><a href="{RESET_LINK}">Đặt lại mật khẩu</a></p>',
        text=f"Mở liên kết: {RESET_LINK}",
    )

    assert result is True
    message = captured["message"]
    assert message["To"] == "customer@example.com"
    assert message["From"] == "Gas Quốc Cường <shop@gmail.com>"
    assert any(RESET_LINK in body for body in _message_bodies(message))

    kwargs = captured["kwargs"]
    assert kwargs["hostname"] == "smtp.gmail.com"
    assert kwargs["port"] == 587
    assert kwargs["start_tls"] is True
    assert kwargs["username"] == "shop@gmail.com"
    assert kwargs["password"] == "app-password"
    assert kwargs["recipients"] == ["customer@example.com"]


async def test_email_service_smtp_noop_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def fake_send(*_args: Any, **_kwargs: Any) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("app.services.email_service.aiosmtplib.send", fake_send)
    service = EmailService(_smtp_settings(SMTP_USERNAME="", SMTP_PASSWORD=""))

    result = await service.send_email(
        to="customer@example.com",
        subject="Test",
        html="<p>Hi</p>",
        text="Hi",
    )

    assert result is False
    assert called is False


async def test_email_service_smtp_failure_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_send(*_args: Any, **_kwargs: Any) -> None:
        raise aiosmtplib.SMTPException("smtp boom")

    monkeypatch.setattr("app.services.email_service.aiosmtplib.send", fake_send)
    service = EmailService(_smtp_settings())

    result = await service.send_email(
        to="customer@example.com",
        subject="Test",
        html="<p>Hi</p>",
        text="Hi",
    )

    assert result is False
