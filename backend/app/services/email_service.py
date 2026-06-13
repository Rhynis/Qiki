"""Transactional email delivery helpers."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

RESEND_EMAILS_URL = "https://api.resend.com/emails"


class EmailService:
    """Send transactional emails through Resend."""

    def __init__(self, settings: Settings | None = None) -> None:
        resolved_settings = settings or get_settings()
        self.api_key = resolved_settings.RESEND_API_KEY
        self.email_from = resolved_settings.EMAIL_FROM
        self.timeout = 10.0

    async def send_email(
        self,
        *,
        to: str | Sequence[str],
        subject: str,
        html: str,
        text: str,
    ) -> bool:
        """Send one transactional email, returning whether delivery was requested."""
        recipients = [to] if isinstance(to, str) else list(to)
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
