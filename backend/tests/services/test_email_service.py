"""Tests for transactional email delivery."""

import pytest

from app.core.config import Settings
from app.services.email_service import EmailService

pytestmark = pytest.mark.asyncio


async def test_email_service_noops_without_resend_api_key() -> None:
    service = EmailService(Settings(RESEND_API_KEY=""))

    result = await service.send_email(
        to="user@example.com",
        subject="Test",
        html="<p>Hello</p>",
        text="Hello",
    )

    assert result is False
