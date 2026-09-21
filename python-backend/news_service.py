"""News service — Finnhub + MARKETAUX + economic calendar polling."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from config import settings

log = logging.getLogger("news")

CACHE: dict = {"news": [], "ts": 0.0, "calendar": [], "cal_ts": 0.0}
# prevent thundering herd on cache expiry
_news_lock = asyncio.Lock()
_cal_lock = asyncio.Lock()
_CAL_CACHE_TTL = 300  # 5 min for calendar (less volatile than news)


async def fetch_news() -> list[dict]:
    """Aggregate headlines from Finnhub + MARKETAUX, cached 60s.
    Uses a lock to prevent thundering herd on cache expiry."""
    if datetime.now(timezone.utc).timestamp() - CACHE["ts"] < 60 and CACHE["news"]:
        return CACHE["news"]
    async with _news_lock:
        # double-check after acquiring lock (another request may have refreshed)
        if datetime.now(timezone.utc).timestamp() - CACHE["ts"] < 60 and CACHE["news"]:
            return CACHE["news"]
        tasks = [_finnhub(), _marketaux()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: list[dict] = []
        for res in results:
            if isinstance(res, Exception):
                log.warning("news source error: %s", res)
                continue
            out.extend(res)
        out.sort(key=lambda n: n.get("publishedAt", ""), reverse=True)
        CACHE["news"] = out
        CACHE["ts"] = datetime.now(timezone.utc).timestamp()
        return out


async def _finnhub() -> list[dict]:
    if not settings.finnhub_api_key:
        return []
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            "https://finnhub.io/api/v1/news", params={"category": "forex", "token": settings.finnhub_api_key}
        )
        r.raise_for_status()
        items = r.json()
        return [{
            "id": f"fh-{i.get('id')}",
            "source": "Finnhub",
            "title": i.get("headline", ""),
            "summary": i.get("summary", "")[:240],
            "symbols": _extract_symbols(i.get("related", "")),
            "sentiment": "neutral",
            "impact": "medium",
            "category": "breaking_news",
            "publishedAt": datetime.fromtimestamp(i.get("datetime", 0), timezone.utc).isoformat(),
            "url": i.get("url"),
        } for i in items[:20]]


async def _marketaux() -> list[dict]:
    if not settings.marketaux_api_key:
        return []
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            "https://api.marketaux.com/v1/news/all",
            params={"api_token": settings.marketaux_api_key,
                    "filter_entities": "true", "language": "en", "limit": 20},
        )
        r.raise_for_status()
        items = r.json().get("data", [])
        out = []
        for i in items:
            ents = i.get("entities", []) or []
            syms = [e.get("symbol") for e in ents if e.get("symbol")]
            out.append({
                "id": f"mx-{i.get('uuid')}",
                "source": "MARKETAUX",
                "title": i.get("title", ""),
                "summary": i.get("description", "")[:240],
                "symbols": syms,
                "sentiment": _sentiment(i.get("entities", [])),
                "impact": "medium",
                "category": "breaking_news",
                "publishedAt": i.get("published_at"),
                "url": i.get("url"),
            })
        return out


def _extract_symbols(related: str) -> list[str]:
    return [s for s in (related or "").split(",") if s][:4]


def _sentiment(entities: list) -> str:
    scores = [e.get("sentiment_score") for e in entities if e.get("sentiment_score") is not None]
    if not scores:
        return "neutral"
    avg = sum(scores) / len(scores)
    return "positive" if avg > 0.1 else "negative" if avg < -0.1 else "neutral"


async def economic_calendar() -> list[dict]:
    """High-impact upcoming events. Cached 5 min with thundering-herd lock."""
    now_ts = datetime.now(timezone.utc).timestamp()
    if now_ts - CACHE["cal_ts"] < _CAL_CACHE_TTL and CACHE["calendar"]:
        return CACHE["calendar"]
    async with _cal_lock:
        # double-check after acquiring lock
        now_ts = datetime.now(timezone.utc).timestamp()
        if now_ts - CACHE["cal_ts"] < _CAL_CACHE_TTL and CACHE["calendar"]:
            return CACHE["calendar"]
        if not settings.finnhub_api_key:
            cal = _demo_calendar()
        else:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            try:
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.get(
                        "https://finnhub.io/api/v1/calendar/economic",
                        params={"from": today, "to": today, "token": settings.finnhub_api_key},
                    )
                    r.raise_for_status()
                    cal = r.json().get("economicCalendar", [])[:10]
            except Exception as exc:  # noqa: BLE001
                log.warning("calendar fetch failed: %s — using demo", exc)
                cal = _demo_calendar()
        CACHE["calendar"] = cal
        CACHE["cal_ts"] = now_ts
        return cal


def _demo_calendar() -> list[dict]:
    return [
        {"event": "US CPI (YoY)", "country": "US", "actual": None, "estimate": "3.4%", "impact": "high"},
        {"event": "Core CPI (MoM)", "country": "US", "actual": None, "estimate": "0.3%", "impact": "high"},
        {"event": "BoE Rate Decision", "country": "GB", "actual": None, "estimate": "5.25%", "impact": "high"},
    ]
