"""Currency Strength Meter — real-time relative strength of 8 major currencies.

Computes strength by aggregating % change across all pairs involving each
currency. Stronger currency = buy candidate vs weaker currency.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("strength")

# 8 major currencies
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD"]

# which pairs contain each currency
_PAIRS_BY_CURRENCY: dict[str, list[str]] = {
    "USD": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD"],
    "EUR": ["EURUSD", "EURGBP", "EURJPY", "EURAUD"],
    "GBP": ["GBPUSD", "EURGBP", "GBPJPY"],
    "JPY": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY"],
    "CHF": ["USDCHF"],
    "AUD": ["AUDUSD", "AUDJPY", "EURAUD"],
    "CAD": ["USDCAD"],
    "NZD": ["NZDUSD"],
}


def compute_strength(ticks: list[dict]) -> list[dict]:
    """Compute currency strength from tick changePct data.

    Returns list of {currency, strength, pairs, direction} sorted by strength.
    Strength = average changePct across pairs containing this currency.
    For pairs where currency is quote (XXXccy), invert the sign.
    """
    strength_map: dict[str, list[float]] = {c: [] for c in CURRENCIES}

    for t in ticks:
        symbol = t.get("symbol", "")
        change = t.get("changePct", 0)
        if not symbol or change == 0:
            continue

        # determine base and quote currencies
        if symbol.startswith("XAU"):
            base, quote = "XAU", "USD"
        elif symbol.startswith("XAG"):
            base, quote = "XAG", "USD"
        else:
            base, quote = symbol[:3], symbol[3:]

        # base currency strength = +change (if pair goes up, base is strong)
        if base in strength_map:
            strength_map[base].append(change)
        # quote currency strength = -change (if pair goes up, quote is weak)
        if quote in strength_map:
            strength_map[quote].append(-change)

    results = []
    for ccy in CURRENCIES:
        values = strength_map[ccy]
        avg = sum(values) / len(values) if values else 0
        direction = "bullish" if avg > 0.1 else "bearish" if avg < -0.1 else "neutral"
        results.append({
            "currency": ccy,
            "strength": round(avg, 3),
            "direction": direction,
            "pairCount": len(values),
        })

    results.sort(key=lambda x: x["strength"], reverse=True)
    return results


# ---- Correlation Risk ----
# simplified correlation matrix (1-week typical, not computed live)
_CORRELATION_THRESHOLD = 0.7
_KNOWN_CORRELATIONS: dict[str, list[str]] = {
    "EURUSD": ["EURGBP", "EURJPY", "EURAUD"],  # EUR-denominated
    "GBPUSD": ["EURGBP", "GBPJPY"],
    "USDJPY": ["EURJPY", "GBPJPY", "AUDJPY"],  # JPY-denominated
    "AUDUSD": ["AUDJPY", "EURAUD"],
}


def check_correlation_risk(open_symbols: list[str]) -> tuple[bool, str]:
    """Check if open positions have correlated risk.

    Returns (has_risk, reason). If any pair in open_symbols has a
    correlated pair also open, that's correlated exposure.
    """
    for sym in open_symbols:
        correlated = _KNOWN_CORRELATIONS.get(sym, [])
        for corr in correlated:
            if corr in open_symbols and corr != sym:
                return True, f"{sym} and {corr} are correlated — combined risk is higher than individual"
    return False, "ok"


# ---- Parameter Sweep ----
def parameter_sweep(symbol: str, rates: list[dict]) -> dict:
    """Grid search EMA/RSI parameters to find best combination.

    Returns {best_params, best_sharpe, all_results}.
    """
    import pandas as pd
    import numpy as np
    from indicators import ema, rsi, macd
    from risk_manager import size_position

    if not rates or len(rates) < 200:
        return {"best_params": None, "best_sharpe": -999, "all_results": []}

    df = pd.DataFrame(rates)
    pip = 0.01 if "JPY" in symbol else (0.1 if symbol.startswith("XAU") else 0.0001)
    vpp = 8.0 if symbol.startswith("XAU") else 10.0

    ema_options = [10, 15, 20, 25, 30]
    rsi_options = [10, 14, 20]
    results = []

    for ema_f in ema_options:
        for ema_s in [e for e in ema_options if e > ema_f]:
            for rsi_p in rsi_options:
                try:
                    df["ema_f"] = ema(df, ema_f)
                    df["ema_s"] = ema(df, ema_s)
                    df["rsi"] = rsi(df, rsi_p)

                    equity = 10000
                    wins = losses = 0
                    gross_win = gross_loss = 0.0
                    equity_curve = [equity]

                    for i in range(50, len(df) - 6, 6):
                        row = df.iloc[i]
                        bull = row["ema_f"] > row["ema_s"] and row["rsi"] > 50
                        bear = row["ema_f"] < row["ema_s"] and row["rsi"] < 50
                        if not (bull or bear):
                            continue
                        side = "BUY" if bull else "SELL"
                        entry = row["close"]
                        exit_ = df.iloc[i + 5]["close"]
                        pips = (exit_ - entry) / pip if side == "BUY" else (entry - exit_) / pip
                        pips_net = pips - 0.8  # spread
                        ps = size_position(equity, 10)
                        pnl = pips_net * ps.lot * vpp - 2 * ps.lot
                        equity += pnl
                        equity_curve.append(equity)
                        if pnl >= 0:
                            wins += 1
                            gross_win += pnl
                        else:
                            losses += 1
                            gross_loss += abs(pnl)

                    total = wins + losses
                    if total < 5:
                        continue
                    win_rate = wins / total * 100
                    pf = gross_win / gross_loss if gross_loss else gross_win
                    # simple sharpe
                    rets = np.diff(equity_curve) / equity_curve[:-1] if len(equity_curve) > 1 else [0]
                    sharpe = (np.mean(rets) / (np.std(rets) or 1)) * (252 ** 0.5) if len(rets) > 1 else 0

                    results.append({
                        "ema_fast": ema_f, "ema_slow": ema_s, "rsi_period": rsi_p,
                        "win_rate": round(win_rate, 1), "profit_factor": round(pf, 2),
                        "sharpe": round(float(sharpe), 2), "trades": total,
                        "net_profit": round(equity - 10000, 2),
                    })
                except Exception:
                    continue

    results.sort(key=lambda x: x["sharpe"], reverse=True)
    best = results[0] if results else None
    return {"best_params": best, "best_sharpe": best["sharpe"] if best else -999, "all_results": results[:10]}


# ---- Trade Journal ----
def create_journal_entry(ticket: int, symbol: str, side: str, entry_price: float,
                         volume: float, sl_pips: int, confidence: int,
                         indicators_snapshot: dict, signal: str) -> dict:
    """Create a trade journal entry with context for later review."""
    from db import add_log
    import json
    entry = {
        "ticket": ticket,
        "symbol": symbol,
        "side": side,
        "entry_price": entry_price,
        "volume": volume,
        "sl_pips": sl_pips,
        "confidence": confidence,
        "signal": signal,
        "indicators": indicators_snapshot,
        "timestamp": __import__("time").time(),
    }
    # store as TRADE-level log with structured data
    add_log("TRADE", "journal",
            f"ENTRY #{ticket} {side} {symbol} {volume}lot @ {entry_price} "
            f"| signal={signal} conf={confidence}% sl={sl_pips}p | "
            f"indicators={json.dumps(indicators_snapshot)[:200]}")
    return entry


# ---- Order Flow / Volume Profile Analysis ----
def analyze_order_flow(rates: list[dict], lookback: int = 50) -> dict:
    """Analyze tick volume patterns to detect institutional order flow.

    Returns {volume_trend, poc_price (point of control), value_area_high, value_area_low}.
    """
    if not rates or len(rates) < 20:
        return {"volume_trend": "unknown", "poc_price": None}

    import numpy as np
    recent = rates[-lookback:] if len(rates) >= lookback else rates

    # volume trend
    half = len(recent) // 2
    vol_first = sum(r["volume"] for r in recent[:half])
    vol_second = sum(r["volume"] for r in recent[half:])
    if vol_second > vol_first * 1.2:
        vol_trend = "increasing"  # institutional accumulation
    elif vol_second < vol_first * 0.8:
        vol_trend = "decreasing"  # distribution / fade
    else:
        vol_trend = "stable"

    # simple volume profile (POC = price with highest volume)
    price_vol: dict[float, float] = {}
    for r in recent:
        typical_price = (r["high"] + r["low"] + r["close"]) / 3
        # round to nearest pip
        pip = 0.01 if r["close"] > 50 else 0.0001
        bucket = round(typical_price / pip) * pip
        price_vol[bucket] = price_vol.get(bucket, 0) + r["volume"]

    if not price_vol:
        return {"volume_trend": vol_trend, "poc_price": None}

    poc_price = max(price_vol, key=price_vol.get)
    total_vol = sum(price_vol.values())
    # value area (70% of volume around POC)
    sorted_prices = sorted(price_vol.keys(), key=lambda p: -price_vol[p])
    va_vol = 0
    va_prices = []
    for p in sorted_prices:
        va_vol += price_vol[p]
        va_prices.append(p)
        if va_vol >= total_vol * 0.7:
            break

    return {
        "volume_trend": vol_trend,
        "poc_price": round(poc_price, 5),
        "value_area_high": round(max(va_prices), 5) if va_prices else None,
        "value_area_low": round(min(va_prices), 5) if va_prices else None,
        "total_volume": total_vol,
    }
