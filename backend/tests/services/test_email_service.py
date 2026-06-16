"""Tests for transactional email delivery."""

import base64
from email.message import EmailMessage
from typing import Any

import aiosmtplib
import httpx
import pytest

from app.core.config import Settings
from app.services.email_service import EmailService, render_email_otp

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


def _gmail_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "EMAIL_PROVIDER": "gmail_api",
        "EMAIL_FROM": "Gas Quốc Cường <shop@gmail.com>",
        "GMAIL_CLIENT_ID": "client-id",
        "GMAIL_CLIENT_SECRET": "client-secret",
        "GMAIL_REFRESH_TOKEN": "refresh-token",
    }
    base.update(overrides)
    return Settings(**base)


def _install_fake_httpx(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_on: str | None = None,
    token_json: Any = None,
) -> list[dict[str, Any]]:
    """Patch httpx.AsyncClient with a fake recording POST calls. Returns the call log."""
    calls: list[dict[str, Any]] = []
    token_body: Any = token_json if token_json is not None else {"access_token": "ya29.test"}

    class FakeResponse:
        def __init__(self, *, json_data: Any, raise_error: bool) -> None:
            self._json = json_data
            self._raise = raise_error

        def raise_for_status(self) -> None:
            if self._raise:
                raise httpx.HTTPError("boom")

        def json(self) -> Any:
            return self._json

    class FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> bool:
            return False

        async def post(self, url: str, **kwargs: Any) -> FakeResponse:
            calls.append({"url": url, **kwargs})
            if "oauth2.googleapis.com" in url:
                return FakeResponse(json_data=token_body, raise_error=fail_on == "token")
            return FakeResponse(json_data={"id": "msg-1"}, raise_error=fail_on == "send")

    monkeypatch.setattr("app.services.email_service.httpx.AsyncClient", FakeAsyncClient)
    return calls


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


async def test_render_email_otp_includes_code_and_expiry() -> None:
    subject, text, html = render_email_otp("123456", ttl_minutes=10)

    assert subject == "Mã xác minh email Gas Quốc Cường"
    assert "123456" in text
    assert "123456" in html
    assert "10 phút" in text
    assert "10 phút" in html


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


async def test_gmail_api_sends(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_httpx(monkeypatch)
    service = EmailService(_gmail_settings())

    result = await service.send_email(
        to="customer@example.com",
        subject="Reset your password",
        html="<p>Hi</p>",
        text="Hi",
    )

    assert result is True
    assert len(calls) == 2
    token_call, send_call = calls

    assert token_call["url"] == "https://oauth2.googleapis.com/token"
    assert token_call["data"]["refresh_token"] == "refresh-token"
    assert token_call["data"]["grant_type"] == "refresh_token"
    assert token_call["data"]["client_id"] == "client-id"

    assert send_call["url"] == "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
    assert send_call["headers"]["Authorization"] == "Bearer ya29.test"
    decoded = base64.urlsafe_b64decode(send_call["json"]["raw"]).decode()
    assert "customer@example.com" in decoded
    assert "Reset your password" in decoded
    assert "shop@gmail.com" in decoded  # From == EMAIL_FROM


async def test_gmail_api_noop_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_httpx(monkeypatch)
    service = EmailService(_gmail_settings(GMAIL_REFRESH_TOKEN=""))

    result = await service.send_email(
        to="customer@example.com", subject="Test", html="<p>Hi</p>", text="Hi"
    )

    assert result is False
    assert calls == []


async def test_gmail_api_token_error_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_httpx(monkeypatch, fail_on="token")
    service = EmailService(_gmail_settings())

    result = await service.send_email(
        to="customer@example.com", subject="Test", html="<p>Hi</p>", text="Hi"
    )

    assert result is False


async def test_gmail_api_send_error_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_httpx(monkeypatch, fail_on="send")
    service = EmailService(_gmail_settings())

    result = await service.send_email(
        to="customer@example.com", subject="Test", html="<p>Hi</p>", text="Hi"
    )

    assert result is False
    # The token exchange succeeded, then the send failed and was swallowed.
    assert len(calls) == 2


async def test_gmail_api_unexpected_token_shape_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A non-object token response must not raise (indexing it would TypeError).
    _install_fake_httpx(monkeypatch, token_json=["unexpected"])
    service = EmailService(_gmail_settings())

    result = await service.send_email(
        to="customer@example.com", subject="Test", html="<p>Hi</p>", text="Hi"
    )

    assert result is False
