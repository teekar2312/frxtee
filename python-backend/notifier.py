"""Notification channels — email (SMTP), Telegram, Discord.

All channels are fire-and-forget via _spawn() to never block trading loops.
Configure via .env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DISCORD_WEBHOOK_URL.
"""
from __future__ import annotations

import logging
import asyncio
import time
from email.mime.text import MIMEText
from typing import Any

import httpx

from config import settings

log = logging.getLogger("notify")

_pending_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


async def send_email(subject: str, body: str, retries: int = 2) -> bool:
    if not settings.smtp_user or not settings.email_to:
        return False
    msg = MIMEText(body, "html")
    msg["From"] = settings.smtp_user
    msg["To"] = settings.email_to
    msg["Subject"] = subject
    import aiosmtplib
    for attempt in range(retries + 1):
        try:
            await aiosmtplib.send(
                msg, hostname=settings.smtp_host, port=settings.smtp_port,
                username=settings.smtp_user, password=settings.smtp_password,
                start_tls=settings.smtp_port != 465,
                use_tls=settings.smtp_port == 465,
            )
            log.info("email sent: %s", subject)
            return True
        except Exception as exc:
            if attempt < retries:
                await asyncio.sleep(2)
            else:
                log.error("email failed: %s", exc)
                return False
    return False


async def send_telegram(text: str) -> bool:
    """Send message via Telegram bot."""
    token = getattr(settings, "telegram_bot_token", "")
    chat_id = getattr(settings, "telegram_chat_id", "")
    if not token or not chat_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            if r.status_code == 200:
                log.info("telegram sent: %s", text[:60])
                return True
            log.warning("telegram failed: %d %s", r.status_code, r.text[:100])
            return False
    except Exception as exc:
        log.error("telegram error: %s", exc)
        return False


async def send_discord(text: str) -> bool:
    """Send message via Discord webhook."""
    webhook = getattr(settings, "discord_webhook_url", "")
    if not webhook:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(webhook, json={"content": text[:2000]})
            if r.status_code in (200, 204):
                log.info("discord sent: %s", text[:60])
                return True
            log.warning("discord failed: %d", r.status_code)
            return False
    except Exception as exc:
        log.error("discord error: %s", exc)
        return False


def notify_async(subject: str, body: str, channels: str = "email") -> None:
    """Fire-and-forget notification to multiple channels.

    channels: comma-separated "email,telegram,discord" (default: email only)
    """
    ch_list = [c.strip() for c in channels.split(",")]
    if "email" in ch_list:
        _spawn(send_email(subject, body))
    # telegram/discord get plain text (strip HTML)
    plain = subject + "\n" + body.replace("<p>", "").replace("</p>", "\n").replace("<br>", "\n")
    plain = plain.replace("<b>", "").replace("</b>", "").replace("<p>", "").strip()
    if "telegram" in ch_list:
        _spawn(send_telegram(f"🔔 {subject}\n{plain}"))
    if "discord" in ch_list:
        _spawn(send_discord(f"🔔 **{subject}**\n{plain}"))
