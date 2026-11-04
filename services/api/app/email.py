"""Transactional email through Resend (https://resend.com/docs/api-reference/emails/send-email)."""

from dataclasses import dataclass
from html import escape

import httpx

from app.config import get_settings

RESEND_URL = "https://api.resend.com/emails"


@dataclass
class EmailResult:
    ok: bool
    message_id: str | None = None
    error: str | None = None
    retryable: bool = True


class EmailNotConfigured(Exception):
    pass


def send_email(*, to: str, subject: str, html: str, text: str, idempotency_key: str) -> EmailResult:
    settings = get_settings()
    if not settings.resend_api_key:
        raise EmailNotConfigured("RESEND_API_KEY is not set")
    payload: dict[str, object] = {
        "from": settings.email_from, "to": [to], "subject": subject, "html": html, "text": text,
    }
    if settings.email_reply_to:
        payload["reply_to"] = settings.email_reply_to
    try:
        response = httpx.post(
            RESEND_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Idempotency-Key": idempotency_key,
            },
            timeout=settings.email_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        return EmailResult(False, error=f"{type(exc).__name__}: {exc}"[:500])
    if response.is_success:
        return EmailResult(True, message_id=str(response.json().get("id") or "") or None)
    # 4xx (bad address, unverified domain) won't fix itself; 429 and 5xx are worth retrying.
    retryable = response.status_code == 429 or response.status_code >= 500
    return EmailResult(False, error=f"{response.status_code}: {response.text[:400]}", retryable=retryable)


def render(*, heading: str, body: str, cta_label: str | None, cta_url: str | None) -> tuple[str, str]:
    """A small branded HTML email plus its plain-text twin."""
    button = (
        f'<p style="margin:28px 0 0"><a href="{escape(cta_url, quote=True)}" '
        'style="display:inline-block;background:#83a281;color:#ffffff;text-decoration:none;'
        'padding:12px 22px;border-radius:999px;font-weight:600;font-size:15px">'
        f"{escape(cta_label)}</a></p>"
        if cta_label and cta_url else ""
    )
    paragraphs = "".join(
        f'<p style="margin:12px 0 0;font-size:16px;line-height:1.55;color:#3b4a3a">{escape(p)}</p>'
        for p in body.split("\n") if p.strip()
    )
    html = (
        '<!doctype html><html><body style="margin:0;background:#f5f7f2;padding:32px 16px;'
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif\">"
        '<div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:20px;padding:32px">'
        '<p style="margin:0 0 20px;font-family:Georgia,serif;font-size:20px;color:#1b231c">'
        'Back<em style="color:#4f6d4d">It</em></p>'
        f'<h1 style="margin:0;font-family:Georgia,serif;font-weight:400;font-size:28px;line-height:1.2;'
        f'color:#1b231c">{escape(heading)}</h1>'
        f"{paragraphs}{button}"
        "</div>"
        '<p style="max-width:520px;margin:16px auto 0;font-size:12px;color:#6b7a69;text-align:center">'
        "You get this because you have an account on backit.club.</p>"
        "</body></html>"
    )
    text = f"{heading}\n\n{body}" + (f"\n\n{cta_label}: {cta_url}" if cta_label and cta_url else "")
    return html, text
