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
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://finnhub.io/api/v1/news",
                params={"category": "forex", "token": settings.finnhub_api_key}
            )
            if r.status_code == 429:
                log.warning("Finnhub rate limit (429) — backing off 60s")
                # set cache to expire in 60s to avoid hammering
                CACHE["ts"] = datetime.now(timezone.utc).timestamp() + 60
                return []
            r.raise_for_status()
            items = r.json()
            return [{
                "id": f"fh-{i.get('id')}",
                "source": "Finnhub",
                "title": i.get("headline", ""),
                "summary": i.get("summary", "")[:240],
                "symbols": _extract_symbols(i.get("related", "")),
                "sentiment": _infer_sentiment(i.get("headline", "")),
                "impact": "medium",
                "category": "breaking_news",
                "publishedAt": datetime.fromtimestamp(i.get("datetime", 0), timezone.utc).isoformat(),
                "url": i.get("url"),
            } for i in items[:20]]
    except Exception as exc:  # noqa: BLE001
        log.warning("Finnhub fetch failed: %s", exc)
        return []


async def _marketaux() -> list[dict]:
    if not settings.marketaux_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://api.marketaux.com/v1/news/all",
                params={"api_token": settings.marketaux_api_key,
                        "filter_entities": "true", "language": "en", "limit": 20},
            )
            if r.status_code == 429:
                log.warning("MARKETAUX rate limit (429) — backing off 300s")
                CACHE["ts"] = datetime.now(timezone.utc).timestamp() + 300
                return []
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
    except Exception as exc:  # noqa: BLE001
        log.warning("MARKETAUX fetch failed: %s", exc)
        return []


def _extract_symbols(related: str) -> list[str]:
    """Extract and normalize symbols to our 14 trading pairs."""
    raw = [s.strip().upper() for s in (related or "").split(",") if s.strip()]
    # map common formats: EUR/USD → EURUSD, EUR-USD → EURUSD
    normalized = []
    for s in raw[:4]:
        s = s.replace("/", "").replace("-", "")
        # if it looks like a 6-char pair, keep it
        if len(s) == 6 and s.isalpha():
            normalized.append(s)
        elif s in ("XAU", "XAG", "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD", "CHF"):
            normalized.append(s)
    return normalized[:4]


def _infer_sentiment(headline: str) -> str:
    """Infer sentiment from headline keywords (Finnhub has no sentiment)."""
    h = headline.lower()
    positive_words = ["rally", "surge", "beat", "strong", "gain", "bullish", "upside",
                       "rises", "jumps", "soars", "optimism", "recovery", "growth"]
    negative_words = ["slide", "drop", "fall", "miss", "weak", "bearish", "downside",
                      "loss", "crash", "plunge", "fear", "risk", "concern", "warning"]
    pos = sum(1 for w in positive_words if w in h)
    neg = sum(1 for w in negative_words if w in h)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


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
    """Demo calendar WITH time field (required for near_high_impact_news)."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    return [
        {"event": "US CPI (YoY)", "country": "US", "actual": None, "estimate": "3.4%",
         "impact": "high", "time": (now + timedelta(hours=2)).isoformat()},
        {"event": "Core CPI (MoM)", "country": "US", "actual": None, "estimate": "0.3%",
         "impact": "high", "time": (now + timedelta(hours=2)).isoformat()},
        {"event": "BoE Rate Decision", "country": "GB", "actual": None, "estimate": "5.25%",
         "impact": "high", "time": (now + timedelta(hours=6)).isoformat()},
    ]


# ---- currency → symbol mapping for sentiment ----
_CURRENCY_MAP = {
    "EURUSD": ["EUR", "USD"], "GBPUSD": ["GBP", "USD"], "USDJPY": ["USD", "JPY"],
    "USDCHF": ["USD", "CHF"], "AUDUSD": ["AUD", "USD"], "USDCAD": ["USD", "CAD"],
    "NZDUSD": ["NZD", "USD"], "EURGBP": ["EUR", "GBP"], "EURJPY": ["EUR", "JPY"],
    "GBPJPY": ["GBP", "JPY"], "AUDJPY": ["AUD", "JPY"], "EURAUD": ["EUR", "AUD"],
    "XAUUSD": ["XAU", "USD"], "XAGUSD": ["XAG", "USD"],
}
# country code → currency
_COUNTRY_CURRENCY = {
    "US": "USD", "EU": "EUR", "GB": "GBP", "JP": "JPY", "CH": "CHF",
    "AU": "AUD", "CA": "CAD", "NZ": "NZD",
}


def aggregate_sentiment(symbol: str | None = None) -> dict:
    """Aggregate news sentiment per symbol with time-weighted decay.

    Returns {score: -1..+1, summary: str, bullish: %, bearish: %, neutral: %,
    count: int}. If symbol given, filters to that pair's currencies.
    """
    try:
        news = CACHE.get("news", [])
        if not news:
            return {"score": 0.0, "summary": "neutral", "bullish": 33,
                    "bearish": 33, "neutral": 34, "count": 0}
        # filter by symbol if given
        if symbol:
            currencies = _CURRENCY_MAP.get(symbol, [])
            news = [n for n in news if
                    any(c in str(n.get("symbols", [])) for c in currencies) or
                    _COUNTRY_CURRENCY.get(str(n.get("country", "")).upper()) in currencies]
        if not news:
            return {"score": 0.0, "summary": "neutral", "bullish": 33,
                    "bearish": 33, "neutral": 34, "count": 0}

        # time-weighted sentiment (newer = higher weight)
        now = datetime.now(timezone.utc).timestamp()
        total_weight = 0.0
        weighted_score = 0.0
        counts = {"positive": 0, "negative": 0, "neutral": 0}

        for n in news[:50]:  # last 50 items
            sent = n.get("sentiment", "neutral")
            pub = n.get("publishedAt", "")
            # parse time
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                age_hours = max(0, (now - dt.timestamp()) / 3600)
            except Exception:  # noqa: BLE001
                age_hours = 12  # default
            # decay: 1.0 at 0h, 0.1 at 24h, 0.01 at 48h
            weight = max(0.01, 1.0 / (1.0 + age_hours / 6.0))
            score = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}.get(sent, 0.0)
            weighted_score += score * weight
            total_weight += weight
            counts[sent] = counts.get(sent, 0) + 1

        avg_score = weighted_score / total_weight if total_weight > 0 else 0.0
        total = sum(counts.values())
        bullish_pct = round(counts["positive"] / total * 100) if total else 33
        bearish_pct = round(counts["negative"] / total * 100) if total else 33
        neutral_pct = 100 - bullish_pct - bearish_pct
        summary = "bullish" if avg_score > 0.2 else "bearish" if avg_score < -0.2 else "neutral"

        return {
            "score": round(avg_score, 2),
            "summary": summary,
            "bullish": bullish_pct,
            "bearish": bearish_pct,
            "neutral": neutral_pct,
            "count": total,
        }
    except Exception as exc:  # noqa: BLE001
        log.debug("aggregate_sentiment failed: %s", exc)
        return {"score": 0.0, "summary": "neutral", "bullish": 33,
                "bearish": 33, "neutral": 34, "count": 0}
