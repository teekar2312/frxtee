"""Notifier — async email (SMTP) + in-app price alert engine."""
from __future__ import annotations

import asyncio
import logging
import time
from email.mime.text import MIMEText

import aiosmtplib

from config import settings

log = logging.getLogger("notify")

PRICE_ALERTS: list[dict] = []
# hold strong refs to fire-and-forget tasks so the GC doesn't kill them
_pending_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    """Schedule a coroutine and track it until completion."""
    task = asyncio.create_task(coro)
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


async def send_email(subject: str, body: str) -> bool:
    if not settings.smtp_user or not settings.email_to:
        log.info("email skipped (not configured): %s", subject)
        return False
    msg = MIMEText(body, "html")
    msg["From"] = settings.smtp_user
    msg["To"] = settings.email_to
    msg["Subject"] = subject
    try:
        await aiosmtplib.send(
            msg, hostname=settings.smtp_host, port=settings.smtp_port,
            username=settings.smtp_user, password=settings.smtp_password,
            start_tls=True,
        )
        log.info("email sent: %s -> %s", subject, settings.email_to)
        return True
    except Exception as exc:
        log.error("email failed: %s", exc)
        return False


def add_price_alert(symbol: str, condition: str, price: float) -> dict:
    alert = {
        "id": f"pa-{len(PRICE_ALERTS)+1}", "symbol": symbol, "condition": condition,
        "price": price, "active": True, "triggered": False,
        "createdAt": time.time(),
    }
    PRICE_ALERTS.append(alert)
    return alert


def check_alerts(ticks: list[dict]) -> list[dict]:
    """Check current prices against alerts; return triggered alerts."""
    triggered = []
    for a in PRICE_ALERTS:
        if not a["active"] or a["triggered"]:
            continue
        t = next((x for x in ticks if x["symbol"] == a["symbol"]), None)
        if not t:
            continue
        hit = (
            (a["condition"] == "above" and t["bid"] > a["price"])
            or (a["condition"] == "below" and t["bid"] < a["price"])
            or (a["condition"] == "cross_up" and t["bid"] > a["price"])
            or (a["condition"] == "cross_down" and t["bid"] < a["price"])
        )
        if hit:
            a["triggered"] = True
            triggered.append(a)
            _spawn(send_email(
                f"Price alert: {a['symbol']} {a['condition']} {a['price']}",
                f"<p>Alert triggered: <b>{a['symbol']}</b> {a['condition']} {a['price']}.</p><p>Current bid: {t['bid']}</p>",
            ))
    return triggered
