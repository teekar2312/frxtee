"""AI service — multi-provider inference (Z.AI, Groq, Google AI Studio, Ollama).

Provider is selected manually in the dashboard. Each provider implements the
same `analyze()` interface returning a structured analysis dict.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from config import settings

log = logging.getLogger("ai")

ANALYSIS_DIMENSIONS = [
    ("central_bank", "Kebijakan Bank Sentral"),
    ("economic_data", "Data Ekonomi Utama"),
    ("politics", "Kondisi Politik & Geopolitik"),
    ("fiscal", "Kebijakan Fiskal & Ekonomi"),
    ("commodities", "Harga Komoditas"),
    ("sentiment", "Sentimen Pasar"),
    ("breaking_news", "Berita Dadakan"),
]

SYSTEM_PROMPT = """You are an elite forex/metal trading analyst.
Analyze the given symbol across 7 dimensions: central bank policy, key economic
data, politics & geopolitics, fiscal policy, commodity prices, market sentiment,
and breaking news. Return STRICT JSON only with these EXACT keys (camelCase):
symbol (string), signal (STRONG BUY|BUY|NEUTRAL|SELL|STRONG SELL),
confidence (integer 0-100), summary (string <= 240 chars),
dimensions (array of 7 objects {id, label, score 0-100, note}),
riskScore (integer 0-100), suggestedEntry (number), suggestedSL (number),
suggestedTP (number), provider (string). Do not include any text outside JSON.
The 7 dimension ids must be: central_bank, economic_data, politics, fiscal,
commodities, sentiment, breaking_news."""


def analyze(symbol: str, provider: str, context: dict | None = None) -> dict[str, Any]:
    """Run analysis with the chosen provider. Falls back to a rule-based
    heuristic if no provider/keys configured."""
    user_msg = f"Analyze {symbol} for a scalping setup (TF M15/H1). " \
               f"Market context: {json.dumps(context or {})[:800]}"
    try:
        if provider == "zai":
            return _call_zai(symbol, user_msg)
        if provider == "groq":
            return _call_groq(symbol, user_msg)
        if provider == "google":
            return _call_google(symbol, user_msg)
        if provider == "local":
            return _call_ollama(symbol, user_msg)
    except Exception as exc:
        log.error("AI provider %s failed: %s — using heuristic", provider, exc)
    return _heuristic(symbol)


# ---------- Z.AI (z-ai-web-dev-sdk compatible HTTP) ----------
def _call_zai(symbol: str, user_msg: str) -> dict:
    # z-ai-web-dev-sdk exposes an OpenAI-compatible endpoint.
    base = os.environ.get("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4")
    key = settings.zai_api_key
    if not key:
        return _heuristic(symbol)
    r = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "glm-4.6", "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]},
        timeout=30,
    )
    r.raise_for_status()
    return _parse(r.json()["choices"][0]["message"]["content"], symbol)


# ---------- Groq (OpenAI-compatible) ----------
def _call_groq(symbol: str, user_msg: str) -> dict:
    if not settings.groq_api_key:
        return _heuristic(symbol)
    from openai import OpenAI
    client = OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.2,
        timeout=30,
    )
    return _parse(resp.choices[0].message.content, symbol)


# ---------- Google AI Studio ----------
def _call_google(symbol: str, user_msg: str) -> dict:
    if not settings.google_api_key:
        return _heuristic(symbol)
    import google.generativeai as genai
    genai.configure(api_key=settings.google_api_key)
    model = genai.GenerativeModel("gemini-1.5-pro", system_instruction=SYSTEM_PROMPT)
    resp = model.generate_content(user_msg + "\nReturn JSON only.")
    return _parse(resp.text, symbol)


# ---------- Local AI (Ollama) ----------
def _call_ollama(symbol: str, user_msg: str) -> dict:
    import ollama
    client = ollama.Client(host=settings.ollama_url)
    resp = client.chat(
        model="llama3",
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": user_msg}],
        format="json",
        options={"temperature": 0.2},
    )
    return _parse(resp["message"]["content"], symbol)


def _parse(content: str, symbol: str) -> dict:
    """Parse possibly-fenced JSON from LLM output, then normalize to the
    exact contract the frontend expects (11 camelCase fields)."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        d = json.loads(text)
    except Exception:
        return _heuristic(symbol)
    return _normalize(d, symbol)


# snake_case keys commonly emitted by LLMs → camelCase the frontend expects
_SNAKE_REMAP = {
    "suggested_entry": "suggestedEntry",
    "suggested_sl": "suggestedSL",
    "suggested_tp": "suggestedTP",
    "risk_score": "riskScore",
    "generated_at": "generatedAt",
}


def _normalize(d: dict, symbol: str) -> dict:
    """Guarantee all 11 AIAnalysisResult fields exist and are camelCase.
    Coerces types where possible; backfills from heuristic for any missing
    numeric field so the UI never receives undefined."""
    out: dict[str, Any] = {}
    # apply snake_case remap first
    for k, v in d.items():
        out[_SNAKE_REMAP.get(k, k)] = v
    # inject / backfill required fields
    out.setdefault("symbol", symbol)
    out.setdefault("provider", "ai")
    out.setdefault("generatedAt", datetime.now(timezone.utc).isoformat())
    if "signal" not in out:
        out["signal"] = "NEUTRAL"
    if not isinstance(out.get("confidence"), (int, float)):
        out["confidence"] = 50
    if not isinstance(out.get("riskScore"), (int, float)):
        out["riskScore"] = 50
    if not isinstance(out.get("summary"), str):
        out["summary"] = f"AI analysis for {symbol}."
    if not isinstance(out.get("dimensions"), list) or len(out.get("dimensions", [])) == 0:
        out["dimensions"] = [
            {"id": i, "label": lab, "score": 50, "note": "n/a"}
            for i, lab in ANALYSIS_DIMENSIONS
        ]
    # backfill entry/SL/TP from a heuristic base if the LLM omitted them
    base = _heuristic(symbol)
    for field in ("suggestedEntry", "suggestedSL", "suggestedTP"):
        if not isinstance(out.get(field), (int, float)):
            out[field] = base[field]
    return out


def _heuristic(symbol: str) -> dict:
    """Deterministic fallback when no AI key configured. Returns ALL 11
    fields matching the frontend AIAnalysisResult contract."""
    h = int(hashlib.md5(symbol.encode()).hexdigest(), 16)
    signals = ["STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"]
    sig = signals[h % 5]
    conf = 55 + (h % 40)
    dims = [
        {"id": i, "label": lab, "score": (h >> (k % 8)) % 100, "note": "heuristic"}
        for k, (i, lab) in enumerate(ANALYSIS_DIMENSIONS)
    ]
    # base price + pip for entry/SL/TP generation
    pip = 0.01 if ("JPY" in symbol or symbol.startswith("XAG")) else (
        0.1 if symbol.startswith("XAU") else 0.0001
    )
    base = {
        "EURUSD": 1.0865, "GBPUSD": 1.2710, "USDJPY": 151.42,
        "USDCHF": 0.9012, "AUDUSD": 0.6584, "USDCAD": 1.3621,
        "NZDUSD": 0.6012, "EURGBP": 0.8550, "EURJPY": 164.55,
        "GBPJPY": 192.48, "AUDJPY": 99.66, "EURAUD": 1.6500,
        "XAUUSD": 2338.5, "XAGUSD": 27.42,
    }.get(symbol, 1.0)
    direction = 1 if "BUY" in sig else (-1 if "SELL" in sig else 0)
    entry = base + direction * pip * 2
    sl = entry - direction * pip * 10
    tp = entry + direction * pip * 15
    return {
        "symbol": symbol,
        "signal": sig,
        "confidence": conf,
        "riskScore": 100 - conf,
        "summary": f"Heuristic {sig} bias on {symbol} (no AI key configured).",
        "dimensions": dims,
        "suggestedEntry": entry,
        "suggestedSL": sl,
        "suggestedTP": tp,
        "provider": "heuristic",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
