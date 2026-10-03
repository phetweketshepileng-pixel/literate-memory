"""Sends transactional email (sign-up verification, password reset).

Railway's Hobby plan blocks outbound SMTP, so mail goes over HTTPS through
Brevo's transactional API (free tier: 300 emails/day). Configure with:
    BREVO_API_KEY    Brevo > SMTP & API > API keys
    EMAIL_FROM       a sender address verified in Brevo
    EMAIL_FROM_NAME  shown as the sender (default "Ascend")
When not configured, nothing is sent and send_email() returns False, so the
app keeps working (owners can still use PASSWORD_RESET_CODE).
"""
from __future__ import annotations

import html
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def email_configured() -> bool:
    return bool(settings.BREVO_API_KEY and settings.EMAIL_FROM)


async def send_email(to: str, subject: str, text_body: str, button_label: str | None = None,
                     button_url: str | None = None) -> bool:
    if not email_configured():
        logger.warning("Email not configured (BREVO_API_KEY / EMAIL_FROM); not sending '%s'", subject)
        return False
    payload = {
        "sender": {"email": settings.EMAIL_FROM, "name": settings.EMAIL_FROM_NAME},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": text_body + (f"\n\n{button_url}" if button_url else ""),
        "htmlContent": render_html(text_body, button_label, button_url),
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(settings.BREVO_API_URL, json=payload,
                                  headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"})
        if r.status_code >= 300:
            logger.error("Brevo refused email '%s' (%s): %s", subject, r.status_code, r.text[:300])
            return False
        return True
    except httpx.HTTPError as exc:
        logger.error("Could not reach Brevo for '%s': %s", subject, exc)
        return False


def render_html(text_body: str, button_label: str | None, button_url: str | None) -> str:
    paras = "".join(f'<p style="margin:0 0 14px">{html.escape(p)}</p>' for p in text_body.split("\n\n") if p.strip())
    button = ""
    if button_label and button_url:
        u = html.escape(button_url, quote=True)
        button = (f'<p style="margin:22px 0"><a href="{u}" style="background:#226B45;color:#fff;text-decoration:none;'
                  f'padding:11px 20px;border-radius:6px;font-weight:600;display:inline-block">{html.escape(button_label)}</a></p>'
                  f'<p style="margin:0 0 14px;font-size:12px;color:#506056">Or copy this link into your browser:<br>{u}</p>')
    return ('<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.5;color:#10251A;max-width:520px;margin:0 auto;padding:24px">'
            '<div style="font-family:Georgia,serif;font-size:22px;margin-bottom:18px">Ascend</div>'
            f'{paras}{button}<p style="margin:24px 0 0;font-size:12px;color:#506056">If you didn\'t ask for this, you can ignore this email.</p></div>')
