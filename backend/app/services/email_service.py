"""Transactional email delivery helpers."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from email.message import EmailMessage

import aiosmtplib
import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

RESEND_EMAILS_URL = "https://api.resend.com/emails"


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
    """Send transactional emails through Gmail SMTP or Resend, selected by config."""

    def __init__(self, settings: Settings | None = None) -> None:
        resolved_settings = settings or get_settings()
        self.provider = resolved_settings.EMAIL_PROVIDER
        self.api_key = resolved_settings.RESEND_API_KEY
        self.email_from = resolved_settings.EMAIL_FROM
        self.smtp_host = resolved_settings.SMTP_HOST
        self.smtp_port = resolved_settings.SMTP_PORT
        self.smtp_username = resolved_settings.SMTP_USERNAME
        self.smtp_password = resolved_settings.SMTP_PASSWORD
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
        return await self._send_via_resend(recipients, subject, html, text)

    async def _send_via_smtp(
        self, recipients: list[str], subject: str, html: str, text: str
    ) -> bool:
        if not (self.smtp_username and self.smtp_password):
            logger.info("email_send_skipped_missing_smtp_credentials", extra={"subject": subject})
            return False

        message = EmailMessage()
        message["From"] = self.email_from
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")

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
