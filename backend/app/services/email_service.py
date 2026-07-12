"""Transactional email delivery helpers."""

from __future__ import annotations

import base64
import html as html_lib
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

# Brand constants for the shared email layout (orange matches the site's --primary).
BRAND_NAME = "Gas Quốc Cường"
BRAND_TAGLINE = "Trợ lý gas Qiki"
BRAND_HOTLINE = "090 3026306"
BRAND_ORANGE = "#F97316"
_FONT_STACK = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def render_email_layout(
    title: str,
    body_html: str,
    *,
    cta_label: str | None = None,
    cta_url: str | None = None,
) -> str:
    """Wrap email body content in the shared branded HTML shell (inline CSS only).

    Renders a centered ~600px white card on a light background with a brand
    header, the given body, an optional orange CTA button (plus a raw-link
    fallback for clients that strip buttons), and a muted fine-print footer.
    Table + max-width layout so it survives Gmail/Outlook (no <style>, no flexbox).
    """
    cta_block = ""
    if cta_label and cta_url:
        safe_href = html_lib.escape(cta_url, quote=True)
        cta_block = (
            '<div style="margin:24px 0 8px">'
            f'<a href="{safe_href}" '
            f'style="display:inline-block;background-color:{BRAND_ORANGE};color:#ffffff;'
            "text-decoration:none;font-weight:600;font-size:16px;padding:13px 30px;"
            'border-radius:8px">'
            f"{html_lib.escape(cta_label)}</a></div>"
            '<div style="font-size:13px;line-height:1.6;color:#94a3b8;word-break:break-all">'
            f"Nếu nút không hoạt động, hãy mở liên kết: {html_lib.escape(cta_url)}</div>"
        )
    return (
        '<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        f'<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:{_FONT_STACK};'
        'color:#0f172a">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background-color:#f4f4f5">'
        '<tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;max-width:600px;background-color:#ffffff;border:1px solid #e4e4e7;'
        'border-radius:12px">'
        '<tr><td style="padding:28px 32px 18px;border-bottom:1px solid #f1f5f9">'
        f'<div style="font-size:22px;font-weight:700;color:{BRAND_ORANGE}">{BRAND_NAME}</div>'
        f'<div style="font-size:13px;color:#64748b;margin-top:3px">{BRAND_TAGLINE}</div>'
        "</td></tr>"
        '<tr><td style="padding:26px 32px 30px">'
        f'<h1 style="font-size:20px;font-weight:600;margin:0 0 14px;color:#0f172a">{title}</h1>'
        f'<div style="font-size:15px;line-height:1.65;color:#334155">{body_html}</div>'
        f"{cta_block}"
        "</td></tr>"
        '<tr><td style="padding:18px 32px 26px;border-top:1px solid #f1f5f9;'
        'font-size:12px;line-height:1.6;color:#94a3b8">'
        "Nếu bạn không yêu cầu, vui lòng bỏ qua email này.<br>"
        f"{BRAND_NAME} · Hotline {BRAND_HOTLINE}"
        "</td></tr>"
        "</table></td></tr></table></body></html>"
    )


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
    body_html = (
        '<p style="margin:0 0 16px">Dạ chào bạn,</p>'
        '<p style="margin:0 0 16px">Mã xác minh email cho tài khoản của bạn là:</p>'
        f'<div style="font-size:32px;font-weight:700;letter-spacing:8px;color:{BRAND_ORANGE};'
        "background-color:#fff7ed;border:1px solid #fed7aa;border-radius:10px;"
        f'padding:16px 0;text-align:center;margin:0 0 18px">{code}</div>'
        f'<p style="margin:0;color:#64748b;font-size:14px">Mã có hiệu lực trong '
        f"{ttl_minutes} phút.</p>"
    )
    html = render_email_layout("Xác minh email", body_html)
    return subject, text, html


def render_price_alert_confirm(confirm_url: str, *, unsubscribe_url: str) -> tuple[str, str, str]:
    """Build the Vietnamese double-opt-in confirmation email: (subject, text, html)."""
    subject = "Xác nhận đăng ký nhận thông báo giá gas"
    text = (
        "Dạ chào bạn,\n\n"
        "Bạn vừa đăng ký nhận email thông báo khi Gas Quốc Cường thay đổi giá gas.\n"
        f"Vui lòng mở liên kết sau để xác nhận đăng ký: {confirm_url}\n\n"
        "Nếu bạn không đăng ký, hãy bỏ qua email này hoặc hủy tại: "
        f"{unsubscribe_url}"
    )
    body_html = (
        '<p style="margin:0 0 16px">Dạ chào bạn,</p>'
        '<p style="margin:0 0 16px">Bạn vừa đăng ký nhận email thông báo mỗi khi '
        "Gas Quốc Cường cập nhật giá gas. Nhấn nút bên dưới để xác nhận đăng ký.</p>"
        '<p style="margin:0;color:#64748b;font-size:14px">Nếu bạn không đăng ký, '
        f'vui lòng bỏ qua email này hoặc <a href="{html_lib.escape(unsubscribe_url, quote=True)}" '
        'style="color:#64748b">hủy đăng ký</a>.</p>'
    )
    html = render_email_layout(
        "Xác nhận đăng ký nhận giá gas",
        body_html,
        cta_label="Xác nhận đăng ký",
        cta_url=confirm_url,
    )
    return subject, text, html


def render_price_alert_notification(
    price_rows: Sequence[tuple[str, str]], *, unsubscribe_url: str
) -> tuple[str, str, str]:
    """Build the Vietnamese price-change notification email: (subject, text, html).

    ``price_rows`` is a sequence of (product display name, formatted price)
    pairs already rendered by the caller.
    """
    subject = "Cập nhật bảng giá gas Gas Quốc Cường"
    text_lines = "\n".join(f"- {name}: {price}" for name, price in price_rows)
    text = (
        "Dạ chào bạn,\n\n"
        "Gas Quốc Cường vừa cập nhật bảng giá gas. Giá mới như sau:\n"
        f"{text_lines}\n\n"
        f"Liên hệ đặt hàng: hotline {BRAND_HOTLINE}.\n"
        f"Hủy nhận thông báo giá: {unsubscribe_url}"
    )
    rows_html = "".join(
        "<tr>"
        f'<td style="padding:8px 10px;border-bottom:1px solid #f1f5f9">{html_lib.escape(name)}</td>'
        '<td style="padding:8px 10px;border-bottom:1px solid #f1f5f9;text-align:right;'
        f'font-weight:600;color:{BRAND_ORANGE};white-space:nowrap">{html_lib.escape(price)}</td>'
        "</tr>"
        for name, price in price_rows
    )
    body_html = (
        '<p style="margin:0 0 16px">Dạ chào bạn,</p>'
        '<p style="margin:0 0 16px">Gas Quốc Cường vừa cập nhật bảng giá gas. '
        "Giá mới như sau:</p>"
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="border-collapse:collapse;font-size:15px;margin:0 0 18px">'
        f"{rows_html}"
        "</table>"
        '<p style="margin:0;color:#64748b;font-size:14px">Liên hệ đặt hàng: hotline '
        f"{BRAND_HOTLINE}.</p>"
    )
    html = render_email_layout(
        "Bảng giá gas mới",
        body_html,
        cta_label="Hủy nhận thông báo",
        cta_url=unsubscribe_url,
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
