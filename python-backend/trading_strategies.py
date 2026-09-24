"""7 Trading Strategies — each with entry/exit rules + risk management.

Each strategy implements:
  evaluate(df, indicators) -> {signal, confidence, entry, sl, tp, reason}

Strategies can be selected manually (UI) or auto-selected by AI based
on market conditions (trend vs range vs momentum).
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd
from typing import Any

log = logging.getLogger("strategies")


def evaluate(strategy_id: str, df: pd.DataFrame, indicators: dict) -> dict:
    """Dispatch to the selected strategy. Returns signal dict."""
    fn = STRATEGY_REGISTRY.get(strategy_id)
    if not fn:
        return {"signal": "NEUTRAL", "confidence": 0, "reason": f"unknown strategy: {strategy_id}"}
    try:
        return fn(df, indicators)
    except Exception as exc:  # noqa: BLE001
        log.warning("strategy %s error: %s", strategy_id, exc)
        return {"signal": "NEUTRAL", "confidence": 0, "reason": f"strategy error: {exc}"}


# ---- Helper ----
def _last(series, default=0):
    """Get last non-NaN value from a pandas Series or list."""
    if isinstance(series, pd.Series):
        s = series.dropna()
        return float(s.iloc[-1]) if len(s) > 0 else default
    elif isinstance(series, list):
        vals = [v for v in series if v is not None and not (isinstance(v, float) and np.isnan(v))]
        return float(vals[-1]) if vals else default
    return float(series) if series is not None and not np.isnan(series) else default


def _prev(series, default=0):
    """Get second-to-last value."""
    if isinstance(series, pd.Series):
        s = series.dropna()
        return float(s.iloc[-2]) if len(s) >= 2 else default
    elif isinstance(series, list):
        vals = [v for v in series if v is not None and not (isinstance(v, float) and np.isnan(v))]
        return float(vals[-2]) if len(vals) >= 2 else default
    return default


# ============================================================
# 1. Moving Average Ribbon (5-8-13 SMA)
# ============================================================
def ma_ribbon(df: pd.DataFrame, ind: dict) -> dict:
    """5-8-13 SMA ribbon — enter when aligned with clear spacing."""
    sma5 = ind.get("sma_5")
    sma8 = ind.get("sma_8")
    sma13 = ind.get("sma_13")
    close = _last(df["close"])

    if not all([sma5, sma8, smina13 := sma13]):
        return {"signal": "NEUTRAL", "confidence": 0, "reason": "insufficient SMA data"}

    s5, s8, s13 = _last(sma5), _last(sma8), _last(sma13)
    spacing_up = s5 > s8 > s13 and (s5 - s13) > (s13 * 0.0003)  # clear spacing
    spacing_dn = s5 < s8 < s13 and (s13 - s5) > (s13 * 0.0003)

    pip = 0.0001 if close < 50 else 0.01
    if spacing_up:
        return {
            "signal": "BUY", "confidence": 75,
            "entry": close, "sl": s13 - 3 * pip, "tp": close + 15 * pip,
            "reason": f"MA ribbon bullish: 5>{s5:.5f} > 8>{s8:.5f} > 13>{s13:.5f}",
        }
    if spacing_dn:
        return {
            "signal": "SELL", "confidence": 75,
            "entry": close, "sl": s13 + 3 * pip, "tp": close - 15 * pip,
            "reason": f"MA ribbon bearish: 5<{s5:.5f} < 8<{s8:.5f} < 13<{s13:.5f}",
        }
    return {"signal": "NEUTRAL", "confidence": 0, "reason": "MA ribbon compressed/flat"}


# ============================================================
# 2. Momentum Scalping (RSI + MACD)
# ============================================================
def momentum_scalp(df: pd.DataFrame, ind: dict) -> dict:
    """RSI crosses 40/60 + MACD confirmation."""
    rsi_val = _last(ind.get("rsi"))
    rsi_prev = _prev(ind.get("rsi"))
    macd_val = _last(ind.get("macd_main"))
    macd_sig = _last(ind.get("macd_signal"))
    close = _last(df["close"])

    if not rsi_val:
        return {"signal": "NEUTRAL", "confidence": 0, "reason": "no RSI data"}

    pip = 0.0001 if close < 50 else 0.01
    macd_positive = macd_val > macd_sig if macd_val and macd_sig else False
    macd_negative = macd_val < macd_sig if macd_val and macd_sig else False

    # Buy: RSI crosses above 40, MACD positive
    if rsi_prev < 40 and rsi_val >= 40 and macd_positive:
        return {
            "signal": "BUY", "confidence": 70,
            "entry": close, "sl": close - 10 * pip, "tp": close + 15 * pip,
            "reason": f"RSI crossed above 40 ({rsi_val:.1f}), MACD positive",
        }
    # Sell: RSI crosses below 60, MACD negative
    if rsi_prev > 60 and rsi_val <= 60 and macd_negative:
        return {
            "signal": "SELL", "confidence": 70,
            "entry": close, "sl": close + 10 * pip, "tp": close - 15 * pip,
            "reason": f"RSI crossed below 60 ({rsi_val:.1f}), MACD negative",
        }
    return {"signal": "NEUTRAL", "confidence": 0, "reason": f"RSI {rsi_val:.1f} no cross signal"}


# ============================================================
# 3. Pivot Point Bounce
# ============================================================
def pivot_bounce(df: pd.DataFrame, ind: dict) -> dict:
    """Buy at support bounce, sell at resistance rejection."""
    high = _last(df["high"])
    low = _last(df["low"])
    close = _last(df["close"])

    # Calculate daily pivot
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low  # resistance 1
    s1 = 2 * pivot - high  # support 1
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)

    pip = 0.0001 if close < 50 else 0.01

    # Buy: price near S1 and bouncing
    if abs(close - s1) < 5 * pip and close > s1:
        return {
            "signal": "BUY", "confidence": 68,
            "entry": close, "sl": s2, "tp": pivot,
            "reason": f"Price bouncing off S1 ({s1:.5f}), target pivot ({pivot:.5f})",
        }
    # Sell: price near R1 and rejecting
    if abs(close - r1) < 5 * pip and close < r1:
        return {
            "signal": "SELL", "confidence": 68,
            "entry": close, "sl": r2, "tp": pivot,
            "reason": f"Price rejecting at R1 ({r1:.5f}), target pivot ({pivot:.5f})",
        }
    return {"signal": "NEUTRAL", "confidence": 0, "reason": "price mid-range, no pivot signal"}


# ============================================================
# 4. EMA Crossover (9/21 + ATR)
# ============================================================
def ema_crossover(df: pd.DataFrame, ind: dict) -> dict:
    """9 EMA crosses 21 EMA, confirmed by ATR-based volume."""
    ema9 = _last(ind.get("ema_9"))
    ema21 = _last(ind.get("ema_21"))
    ema9_prev = _prev(ind.get("ema_9"))
    ema21_prev = _prev(ind.get("ema_21"))
    atr_val = _last(ind.get("atr"))
    close = _last(df["close"])

    if not all([ema9, ema21]):
        return {"signal": "NEUTRAL", "confidence": 0, "reason": "no EMA data"}

    atr_dist = atr_val or (close * 0.001)  # fallback
    # bullish cross: 9 was below 21, now above
    if ema9_prev < ema21_prev and ema9 > ema21:
        return {
            "signal": "BUY", "confidence": 72,
            "entry": close, "sl": close - atr_dist, "tp": close + 1.5 * atr_dist,
            "reason": f"9 EMA crossed above 21 EMA, ATR={atr_dist:.5f}",
        }
    # bearish cross
    if ema9_prev > ema21_prev and ema9 < ema21:
        return {
            "signal": "SELL", "confidence": 72,
            "entry": close, "sl": close + atr_dist, "tp": close - 1.5 * atr_dist,
            "reason": f"9 EMA crossed below 21 EMA, ATR={atr_dist:.5f}",
        }
    return {"signal": "NEUTRAL", "confidence": 0, "reason": "no EMA cross detected"}


# ============================================================
# 5. RMI Trend Sync (RSI variant + Supertrend)
# ============================================================
def rmi_trend_sync(df: pd.DataFrame, ind: dict) -> dict:
    """RMI (RSI modified) + Supertrend alignment."""
    rsi_val = _last(ind.get("rsi"))
    st_val = _last(ind.get("supertrend"))
    st_prev = _prev(ind.get("supertrend"))
    close = _last(df["close"])

    if not rsi_val or not st_val:
        return {"signal": "NEUTRAL", "confidence": 0, "reason": "no RSI/Supertrend data"}

    pip = 0.0001 if close < 50 else 0.01
    price_above_st = close > st_val
    price_below_st = close < st_val

    # Buy: RSI above oversold (30) + price above Supertrend
    if rsi_val > 30 and rsi_val < 55 and price_above_st:
        return {
            "signal": "BUY", "confidence": 73,
            "entry": close, "sl": st_val, "tp": close + 15 * pip,
            "reason": f"RMI={rsi_val:.1f} (above oversold) + price above Supertrend ({st_val:.5f})",
        }
    # Sell: RSI below overbought (70) + price below Supertrend
    if rsi_val < 70 and rsi_val > 45 and price_below_st:
        return {
            "signal": "SELL", "confidence": 73,
            "entry": close, "sl": st_val, "tp": close - 15 * pip,
            "reason": f"RMI={rsi_val:.1f} (below overbought) + price below Supertrend ({st_val:.5f})",
        }
    return {"signal": "NEUTRAL", "confidence": 0, "reason": f"RMI={rsi_val:.1f}, ST={st_val:.5f} no sync"}


# ============================================================
# 6. Linear Regression Channel + Bollinger Bands
# ============================================================
def linreg_channel(df: pd.DataFrame, ind: dict) -> dict:
    """Buy at lower band, sell at upper band — range-bound strategy."""
    bb_upper = _last(ind.get("bbands_main"))  # fallback if not available
    bb_lower = _last(ind.get("bbands_signal"))
    close = _last(df["close"])

    # Use Bollinger Bands as channel proxy
    bb_h = _last(ind.get("bbands_main"))
    bb_l = _last(ind.get("bbands_signal"))

    # Try direct bbands values
    bbands = ind.get("bbands")
    if isinstance(bbands, dict):
        bb_h = _last(bbands.get("upper"))
        bb_l = _last(bbands.get("lower"))

    if not bb_h or not bb_l:
        # compute from close
        mid = df["close"].rolling(20).mean()
        sd = df["close"].rolling(20).std()
        bb_h = _last(mid + 2 * sd)
        bb_l = _last(mid - 2 * sd)

    pip = 0.0001 if close < 50 else 0.01

    # Buy: price touches lower band
    if abs(close - bb_l) < 3 * pip and close > bb_l:
        return {
            "signal": "BUY", "confidence": 65,
            "entry": close, "sl": bb_l - 5 * pip, "tp": bb_h,
            "reason": f"Price at lower band ({bb_l:.5f}), target upper ({bb_h:.5f})",
        }
    # Sell: price touches upper band
    if abs(close - bb_h) < 3 * pip and close < bb_h:
        return {
            "signal": "SELL", "confidence": 65,
            "entry": close, "sl": bb_h + 5 * pip, "tp": bb_l,
            "reason": f"Price at upper band ({bb_h:.5f}), target lower ({bb_l:.5f})",
        }
    return {"signal": "NEUTRAL", "confidence": 0, "reason": "price mid-channel"}


# ============================================================
# 7. EMA/RSI Filter
# ============================================================
def ema_rsi_filter(df: pd.DataFrame, ind: dict) -> dict:
    """Price above fast EMA + RSI>50 = buy. Below + RSI<50 = sell."""
    ema_fast = _last(ind.get("ema_9"))  # use 9 EMA as fast
    rsi_val = _last(ind.get("rsi"))
    close = _last(df["close"])

    if not ema_fast or not rsi_val:
        return {"signal": "NEUTRAL", "confidence": 0, "reason": "no EMA/RSI data"}

    pip = 0.0001 if close < 50 else 0.01

    # Buy: price above fast EMA + RSI > 50
    if close > ema_fast and rsi_val > 50:
        # Check for recent EMA cross (confidence boost)
        ema_prev = _prev(ind.get("ema_9"))
        cross_boost = close > ema_fast and ema_prev and close < ema_prev + pip
        conf = 78 if cross_boost else 65
        return {
            "signal": "BUY", "confidence": conf,
            "entry": close, "sl": ema_fast - 3 * pip, "tp": close + 10 * pip,
            "reason": f"Price above EMA9 ({ema_fast:.5f}), RSI={rsi_val:.1f} > 50",
        }
    # Sell: price below fast EMA + RSI < 50
    if close < ema_fast and rsi_val < 50:
        ema_prev = _prev(ind.get("ema_9"))
        cross_boost = close < ema_fast and ema_prev and close > ema_prev - pip
        conf = 78 if cross_boost else 65
        return {
            "signal": "SELL", "confidence": conf,
            "entry": close, "sl": ema_fast + 3 * pip, "tp": close - 10 * pip,
            "reason": f"Price below EMA9 ({ema_fast:.5f}), RSI={rsi_val:.1f} < 50",
        }
    return {"signal": "NEUTRAL", "confidence": 0, "reason": f"EMA/RSI not aligned (RSI={rsi_val:.1f})"}


# ============================================================
# Strategy Registry
# ============================================================
STRATEGY_REGISTRY = {
    "ma_ribbon": ma_ribbon,
    "momentum_scalp": momentum_scalp,
    "pivot_bounce": pivot_bounce,
    "ema_crossover": ema_crossover,
    "rmi_trend_sync": rmi_trend_sync,
    "linreg_channel": linreg_channel,
    "ema_rsi_filter": ema_rsi_filter,
}

# Strategy metadata for UI
STRATEGY_INFO = [
    {
        "id": "ma_ribbon", "name": "Moving Average Ribbon",
        "desc": "5-8-13 SMAs — enter when aligned with spacing",
        "timeframe": "M2", "market": "Trending",
        "entry": "Long: MAs align upward. Short: MAs align downward",
        "exit": "TP at swing high/low. Exit if MAs compress",
        "risk": "Stop 2-3 ticks below 13 SMA. Max 0.5% risk",
    },
    {
        "id": "momentum_scalp", "name": "Momentum Scalping",
        "desc": "RSI crosses 40/60 + MACD confirmation",
        "timeframe": "M1", "market": "High-volume",
        "entry": "Buy: RSI > 40 + MACD positive. Sell: RSI < 60 + MACD negative",
        "exit": "Exit at momentum weakness. Close at OB/OS levels",
        "risk": "Stops within 0.1%. Scale out in thirds. No lunch hour",
    },
    {
        "id": "pivot_bounce", "name": "Pivot Point",
        "desc": "Buy at support bounce, sell at resistance reject",
        "timeframe": "M1-M2", "market": "Range",
        "entry": "Buy at S1 bounce. Sell at R1 rejection. First touch only",
        "exit": "TP at next pivot. 3-5 min max hold",
        "risk": "Stop at previous pivot. Reduce size in volatility",
    },
    {
        "id": "ema_crossover", "name": "EMA Crossover",
        "desc": "9/21 EMA crossover + ATR for dynamic SL/TP",
        "timeframe": "M5", "market": "Trending",
        "entry": "Long: 9 EMA crosses above 21. Short: 9 below 21",
        "exit": "TP at 1.5x ATR. Exit if EMAs flatten",
        "risk": "Stop at 1x ATR. Max 5 trades/hour. Reduce near close",
    },
    {
        "id": "rmi_trend_sync", "name": "RMI Trend Sync",
        "desc": "RSI + Supertrend alignment for trend confirmation",
        "timeframe": "M5-M15", "market": "Trending",
        "entry": "Buy: RSI > 30 + price > Supertrend. Sell: RSI < 70 + price < ST",
        "exit": "Exit on RMI reversal. Close on ST cross. Partial profits",
        "risk": "Stop when Supertrend changes. Scale with trend strength",
    },
    {
        "id": "linreg_channel", "name": "Linear Regression Channel",
        "desc": "Buy at lower band, sell at upper band (range-bound)",
        "timeframe": "M2-M5", "market": "Range",
        "entry": "Buy at lower band + upward slope. Sell at upper + downward",
        "exit": "Exit at opposite band. Close if slope changes",
        "risk": "Stop outside channel. Smaller size in wide channels",
    },
    {
        "id": "ema_rsi_filter", "name": "EMA/RSI Filter",
        "desc": "Price above EMA + RSI>50 = buy. Below + RSI<50 = sell",
        "timeframe": "M1", "market": "Liquid",
        "entry": "Buy: Price > fast EMA, RSI > 50. Sell: Price < EMA, RSI < 50",
        "exit": "Exit on EMA cross. Close when RSI crosses 50",
        "risk": "Stop at recent swing. Reduce at RSI extremes",
    },
]
