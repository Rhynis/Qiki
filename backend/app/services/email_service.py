"""Transactional email delivery helpers."""

from __future__ import annotations

import base64
import logging
from collections.abc import Sequence
from email.message import EmailMessage

import aiosmtplib
import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

RESEND_EMAILS_URL = "https://api.resend.com/emails"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def render_email_otp(code: str, *, ttl_minutes: int) -> tuple[str, str, str]:
    """Build the Vietnamese email-verification message: (subject, text, html).

    The caller passes a freshly generated code; this function never logs it.
    """
    subject = "Mã xác minh email Gas Quốc Cường"
    text = (
        "Dạ chào bạn,\n\n"
        "Mã xác minh email cho tài khoản Gas Quốc Cường của bạn là: "
        f"{code}\n\n"
        f"Mã có hiệu lực trong {ttl_minutes} phút. "
        "Nếu bạn không yêu cầu, vui lòng bỏ qua email này."
    )
    html = (
        "<p>Dạ chào bạn,</p>"
        "<p>Mã xác minh email cho tài khoản Gas Quốc Cường của bạn là:</p>"
        f'<p style="font-size:24px;font-weight:bold;letter-spacing:4px">{code}</p>'
        f"<p>Mã có hiệu lực trong {ttl_minutes} phút. "
        "Nếu bạn không yêu cầu, vui lòng bỏ qua email này.</p>"
    )
    return subject, text, html


class EmailService:
    """Send transactional emails through Gmail SMTP, Resend, or the Gmail API."""

    def __init__(self, settings: Settings | None = None) -> None:
        resolved_settings = settings or get_settings()
        self.provider = resolved_settings.EMAIL_PROVIDER
        self.api_key = resolved_settings.RESEND_API_KEY
        self.email_from = resolved_settings.EMAIL_FROM
        self.smtp_host = resolved_settings.SMTP_HOST
        self.smtp_port = resolved_settings.SMTP_PORT
        self.smtp_username = resolved_settings.SMTP_USERNAME
        self.smtp_password = resolved_settings.SMTP_PASSWORD
        self.gmail_client_id = resolved_settings.GMAIL_CLIENT_ID
        self.gmail_client_secret = resolved_settings.GMAIL_CLIENT_SECRET
        self.gmail_refresh_token = resolved_settings.GMAIL_REFRESH_TOKEN
        self.timeout = 10.0

    async def send_email(
        self,
        *,
        to: str | Sequence[str],
        subject: str,
        html: str,
        text: str,
    ) -> bool:
        """Send one transactional email, returning whether delivery was requested.

        Dispatches to the configured provider. Missing credentials or send errors
        are logged and turned into ``False`` so a caller (e.g. password reset) never
        crashes.
        """
        recipients = [to] if isinstance(to, str) else list(to)
        if self.provider == "smtp":
            return await self._send_via_smtp(recipients, subject, html, text)
        if self.provider == "gmail_api":
            return await self._send_via_gmail_api(recipients, subject, html, text)
        return await self._send_via_resend(recipients, subject, html, text)

    def _build_mime_message(
        self, recipients: list[str], subject: str, html: str, text: str
    ) -> EmailMessage:
        """Build a multipart (text + HTML) message. From must equal EMAIL_FROM."""
        message = EmailMessage()
        message["From"] = self.email_from
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        return message

    async def _send_via_smtp(
        self, recipients: list[str], subject: str, html: str, text: str
    ) -> bool:
        if not (self.smtp_username and self.smtp_password):
            logger.info("email_send_skipped_missing_smtp_credentials", extra={"subject": subject})
            return False

        message = self._build_mime_message(recipients, subject, html, text)

        try:
            await aiosmtplib.send(
                message,
                recipients=recipients,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                start_tls=True,
                timeout=self.timeout,
            )
        except (aiosmtplib.SMTPException, OSError):
            logger.exception(
                "email_send_failed",
                extra={"subject": subject, "recipient_count": len(recipients)},
            )
            return False
        return True

    async def _send_via_resend(
        self, recipients: list[str], subject: str, html: str, text: str
    ) -> bool:
        if not self.api_key:
            logger.info("email_send_skipped_missing_api_key", extra={"subject": subject})
            return False

        payload = {
            "from": self.email_from,
            "to": recipients,
            "subject": subject,
            "html": html,
            "text": text,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(RESEND_EMAILS_URL, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError:
            logger.exception(
                "email_send_failed",
                extra={"subject": subject, "recipient_count": len(recipients)},
            )
            return False
        return True

    async def _send_via_gmail_api(
        self, recipients: list[str], subject: str, html: str, text: str
    ) -> bool:
        """Send via the Gmail API over HTTPS (port 443) for SMTP-blocked hosts.

        Exchanges the OAuth refresh token for a short-lived access token, then
        posts the base64url-encoded MIME message. Credentials are read from env
        and never logged.
        """
        if not (self.gmail_client_id and self.gmail_client_secret and self.gmail_refresh_token):
            logger.info("email_send_skipped_missing_gmail_credentials", extra={"subject": subject})
            return False

        message = self._build_mime_message(recipients, subject, html, text)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                token_response = await client.post(
                    GMAIL_TOKEN_URL,
                    data={
                        "client_id": self.gmail_client_id,
                        "client_secret": self.gmail_client_secret,
                        "refresh_token": self.gmail_refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
                token_response.raise_for_status()
                access_token = token_response.json()["access_token"]

                send_response = await client.post(
                    GMAIL_SEND_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"raw": raw},
                )
                send_response.raise_for_status()
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            # Any transport/auth/parse failure must degrade to False, never raise,
            # so the password-reset / email-OTP endpoints can't 500.
            logger.exception(
                "email_send_failed",
                extra={"subject": subject, "recipient_count": len(recipients)},
            )
            return False
        return True
