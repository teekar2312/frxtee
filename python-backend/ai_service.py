"""AI service — multi-provider inference (Z.AI, Groq, Google AI Studio, Ollama).

Provider is selected manually in the dashboard. Each provider implements the
same `analyze()` interface returning a structured analysis dict.
"""
from __future__ import annotations

import json
import logging
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
and breaking news. Return STRICT JSON only with keys:
signal (STRONG BUY|BUY|NEUTRAL|SELL|STRONG SELL), confidence (0-100),
summary (string <= 240 chars), dimensions (list of {id,label,score 0-100,note}),
riskScore (0-100). Do not include any text outside the JSON."""


def analyze(symbol: str, provider: str, context: dict | None = None) -> dict[str, Any]:
    """Run analysis with the chosen provider. Falls back to a rule-based
    heuristic if no provider/keys configured."""
    user_msg = f"Analyze {symbol} for a scalping setup (TF M15/H1). " \
               f"Market context: {json.dumps(context or {})[:800]}"
    try:
        if provider == "zai":
            return _call_zai(user_msg)
        if provider == "groq":
            return _call_groq(user_msg)
        if provider == "google":
            return _call_google(user_msg)
        if provider == "local":
            return _call_ollama(user_msg)
    except Exception as exc:
        log.error("AI provider %s failed: %s — using heuristic", provider, exc)
    return _heuristic(symbol)


# ---------- Z.AI (z-ai-web-dev-sdk compatible HTTP) ----------
def _call_zai(user_msg: str) -> dict:
    # z-ai-web-dev-sdk exposes an OpenAI-compatible endpoint on the device.
    base = os.environ.get("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4")
    key = settings.zai_api_key
    if not key:
        return _heuristic("EURUSD")
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
    return _parse(r.json()["choices"][0]["message"]["content"])


# ---------- Groq (OpenAI-compatible) ----------
def _call_groq(user_msg: str) -> dict:
    if not settings.groq_api_key:
        return _heuristic("EURUSD")
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
    return _parse(resp.choices[0].message.content)


# ---------- Google AI Studio ----------
def _call_google(user_msg: str) -> dict:
    if not settings.google_api_key:
        return _heuristic("EURUSD")
    import google.generativeai as genai
    genai.configure(api_key=settings.google_api_key)
    model = genai.GenerativeModel("gemini-1.5-pro", system_instruction=SYSTEM_PROMPT)
    resp = model.generate_content(user_msg + "\nReturn JSON only.")
    return _parse(resp.text)


# ---------- Local AI (Ollama) ----------
def _call_ollama(user_msg: str) -> dict:
    import ollama
    client = ollama.Client(host=settings.ollama_url)
    resp = client.chat(
        model="llama3",
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": user_msg}],
        format="json",
        options={"temperature": 0.2},
    )
    return _parse(resp["message"]["content"])


def _parse(content: str) -> dict:
    """Parse possibly-fenced JSON from LLM output."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        d = json.loads(text)
    except Exception:
        return _heuristic("EURUSD")
    d.setdefault("provider", "ai")
    return d


def _heuristic(symbol: str) -> dict:
    """Deterministic fallback when no AI key configured."""
    import hashlib
    h = int(hashlib.md5(symbol.encode()).hexdigest(), 16)
    signals = ["STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"]
    sig = signals[h % 5]
    conf = 55 + (h % 40)
    dims = [
        {"id": i, "label": lab, "score": (h >> (k % 8)) % 100, "note": "heuristic"}
        for k, (i, lab) in enumerate(ANALYSIS_DIMENSIONS)
    ]
    return {
        "signal": sig, "confidence": conf, "riskScore": 100 - conf,
        "summary": f"Heuristic {sig} bias on {symbol} (no AI key configured).",
        "dimensions": dims, "provider": "heuristic",
    }


import os  # noqa: E402  (kept late to avoid top import noise)
