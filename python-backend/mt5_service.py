"""MetaTrader 5 service — connect (with auto-launch), market data, order execution.

Runs ONLY on Windows (MT5 terminal). All MT5 calls are wrapped so the API
still responds gracefully if MT5 is unavailable.
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from typing import Any

from config import settings

log = logging.getLogger("mt5")

try:
    import MetaTrader5 as mt5  # type: ignore
    MT5_AVAILABLE = True
except Exception as exc:  # not on Windows or not installed
    mt5 = None  # type: ignore
    MT5_AVAILABLE = False
    log.warning("MetaTrader5 not available (%s) — running in simulation mode", exc)


@dataclass
class MT5Status:
    connected: bool
    demo: bool
    terminal: str | None
    account: dict | None
    message: str


# ---- symbol_info cache (static data — no need to refetch every tick) -------
_symbol_info_cache: dict[str, any] = {}
_pip_value_cache: dict[str, float] = {}


def _get_symbol_info(symbol: str):
    """Cached symbol_info — digits/filling_mode/etc are static per session.
    Ensures the symbol is selected in Market Watch first."""
    if symbol in _symbol_info_cache:
        return _symbol_info_cache[symbol]
    if not MT5_AVAILABLE:
        return None
    # symbol must be visible in Market Watch before symbol_info works
    try:
        mt5.symbol_select(symbol, True)  # type: ignore
    except Exception:  # noqa: BLE001
        pass
    info = mt5.symbol_info(symbol)  # type: ignore
    if info:
        _symbol_info_cache[symbol] = info
    return info


def get_pip_value_per_lot(symbol: str) -> float:
    """Get the monetary value of 1 pip movement for 1.0 lot.

    Uses MT5's trade_tick_value (exact, broker-provided) × pip_size.
    Falls back to a sensible default per instrument class if unavailable.
    """
    if symbol in _pip_value_cache:
        return _pip_value_cache[symbol]
    info = _get_symbol_info(symbol)
    if info:
        pip = _pip_for_digits(info.digits)
        point = info.point if hasattr(info, "point") else (10 ** -info.digits)
        tick_value = getattr(info, "trade_tick_value", None) or getattr(info, "tick_value", None)
        if tick_value and point and pip:
            # value per pip = (pip / point) * tick_value
            val = (pip / point) * tick_value
            _pip_value_cache[symbol] = val
            return val
    # fallback defaults by instrument class
    if symbol.startswith("XAU"):
        val = 10.0  # gold: ~$10/pip/lot at standard contract
    elif symbol.startswith("XAG"):
        val = 50.0  # silver
    elif "JPY" in symbol:
        val = 9.13  # approx for USDJPY at ~145
    else:
        val = 10.0  # standard FX pair
    _pip_value_cache[symbol] = val
    return val


def get_margin_level() -> float | None:
    """Get current margin level (equity / margin * 100). None if not connected."""
    if not _state["connected"] or not MT5_AVAILABLE:
        return None
    try:
        info = mt5.account_info()  # type: ignore
        if info and info.margin > 0:
            return (info.equity / info.margin) * 100
        return 9999.0  # no margin used = very healthy
    except Exception:  # noqa: BLE001
        return None


def get_recent_deals(minutes: int = 10) -> list[dict]:
    """Get deals closed in the last N minutes (for reconcile P&L tracking)."""
    if not _state["connected"] or not MT5_AVAILABLE:
        return []
    try:
        from datetime import datetime, timezone, timedelta
        utc_to = datetime.now(timezone.utc)
        utc_from = utc_to - timedelta(minutes=minutes)
        deals = mt5.history_deals_get(utc_from, utc_to)  # type: ignore
        if not deals:
            return []
        out = []
        for d in deals:
            if d.entry != 1:  # DEAL_ENTRY_OUT = position closed
                continue
            out.append({
                "ticket": d.position_id,
                "symbol": d.symbol,
                "volume": d.volume,
                "price": d.price,
                "profit": d.profit,
                "time": d.time,
            })
        return out
    except Exception as exc:  # noqa: BLE001
        log.debug("history_deals_get failed: %s", exc)
        return []


_state: dict[str, Any] = {"connected": False, "account": None, "terminal": None}


def _launch_terminal() -> bool:
    """Launch terminal64.exe and wait until the MT5 RPC is reachable."""
    path = settings.mt5_terminal_path
    if not os.path.exists(path):
        log.error("MT5 terminal not found at %s", path)
        return False
    # validate it's actually an executable (not a directory or text file)
    if not os.path.isfile(path) or not path.lower().endswith(".exe"):
        log.error("MT5 terminal path is not a valid .exe: %s", path)
        return False
    log.info("Auto-launching MT5 terminal: %s", path)
    try:
        subprocess.Popen([path])
    except Exception as exc:
        log.error("Failed to launch terminal: %s", exc)
        return False
    # wait up to 60s (configurable) for the RPC to come online
    max_wait = int(os.environ.get("MT5_LAUNCH_TIMEOUT", "60"))
    for _ in range(max_wait):
        if mt5.initialize():  # type: ignore
            return True
        time.sleep(1)
    log.error("MT5 terminal did not come online within %ds", max_wait)
    return False


def connect() -> MT5Status:
    """Connect to MT5, auto-launching the terminal if configured."""
    if not MT5_AVAILABLE:
        return MT5Status(False, True, None, None, "MetaTrader5 library not installed")
    if not mt5.initialize():  # type: ignore
        if settings.mt5_auto_launch:
            if not _launch_terminal():
                return MT5Status(False, True, None, None, "MT5 terminal launch failed")
        else:
            return MT5Status(False, True, None, None, "MT5 initialize() failed")
    authorized = mt5.login(  # type: ignore
        login=settings.mt5_login,
        password=settings.mt5_password,
        server=settings.mt5_server,
    )
    if not authorized:
        return MT5Status(False, True, None, None, f"MT5 login failed @ {settings.mt5_server}")
    info = mt5.account_info()  # type: ignore
    _state["connected"] = True
    _state["account"] = {
        "login": info.login,
        "server": settings.mt5_server,
        "leverage": f"1:{info.leverage}",
        "currency": info.currency,
        "balance": info.balance,
        "equity": info.equity,
    }
    _state["terminal"] = settings.mt5_terminal_path
    log.info("Connected to %s as %s", settings.mt5_server, settings.mt5_login)
    return MT5Status(True, False, _state["terminal"], _state["account"], "connected")


def disconnect() -> MT5Status:
    if MT5_AVAILABLE:
        try:
            mt5.shutdown()  # type: ignore
        except Exception:
            pass
    _state["connected"] = False
    _state["account"] = None
    return MT5Status(False, True, None, None, "disconnected")


def status() -> MT5Status:
    return MT5Status(
        connected=_state["connected"],
        demo=not _state["connected"],
        terminal=_state["terminal"],
        account=_state["account"],
        message="connected" if _state["connected"] else "demo mode",
    )


# ---------- market data ----------
TF_MAP = {
    "M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1", "W1": "TIMEFRAME_W1", "MN": "TIMEFRAME_MN1",
}


def _pip_for_digits(digits: int) -> float:
    """Pip size by symbol digit count.
    5-digit (EURUSD) and 3-digit (USDJPY) → point is 1e-5/1e-3, pip = 10 points.
    4-digit and 2-digit (JPY legacy) → pip = point.
    XAUUSD (2 digits) → pip = 0.1 (10 points). XAGUSD (3 digits) → pip = 0.01.
    """
    if digits in (5, 3):
        return 10 ** -(digits - 1)   # 5→1e-4, 3→1e-2
    if digits == 2:                 # XAUUSD-style metals
        return 0.1
    return 10 ** -digits           # 4→1e-4 (rare)


def _filling_mode(info) -> int:
    """Pick a filling mode the broker accepts (FOK preferred, else IOC, else RETURN)."""
    mode = getattr(info, "filling_mode", 1)
    if MT5_AVAILABLE:
        if mode & 1:        # bit 0 → FOK supported
            return mt5.ORDER_FILLING_FOK  # type: ignore[attr-defined]
        if mode & 2:        # bit 1 → IOC supported
            return mt5.ORDER_FILLING_IOC  # type: ignore[attr-defined]
        return mt5.ORDER_FILLING_RETURN  # type: ignore[attr-defined]
    return 1


# ---- daily open cache (for changePct computation, refreshed once/day) ----
_daily_open_cache: dict[str, float] = {}
_daily_open_date: str = ""


def _get_daily_open(symbol: str) -> float | None:
    """Get today's open price for a symbol (cached per UTC day)."""
    global _daily_open_date
    from datetime import date as _date
    today = _date.today().isoformat()
    if today != _daily_open_date:
        _daily_open_cache.clear()
        _daily_open_date = today
    if symbol in _daily_open_cache:
        return _daily_open_cache[symbol]
    if not MT5_AVAILABLE:
        return None
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 1)  # type: ignore
        if rates and len(rates) > 0:
            open_price = float(rates[0]["open"])
            _daily_open_cache[symbol] = open_price
            return open_price
    except Exception:  # noqa: BLE001
        pass
    return None


def ticks(symbols: list[str] | None = None) -> list[dict]:
    if not _state["connected"]:
        return []
    out = []
    for sym in (symbols or ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]):
        t = mt5.symbol_info_tick(sym)  # type: ignore
        info = _get_symbol_info(sym)  # cached — avoids 14 RPCs per tick cycle
        if not t or not info:
            continue
        pip = _pip_for_digits(info.digits)
        # compute changePct vs daily open
        daily_open = _get_daily_open(sym)
        change_pct = ((t.bid - daily_open) / daily_open * 100) if daily_open else 0.0
        out.append({
            "symbol": sym, "bid": t.bid, "ask": t.ask,
            "spreadPips": (t.ask - t.bid) / pip,
            "changePct": round(change_pct, 3),
            "digits": info.digits, "ts": int(t.time_msc),
        })
    return out


def candles(symbol: str, tf: str = "M15", count: int = 120) -> list[dict]:
    if not _state["connected"]:
        return []
    tf_const = getattr(mt5, TF_MAP.get(tf, "TIMEFRAME_M15"), mt5.TIMEFRAME_M15)  # type: ignore
    rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, count)  # type: ignore
    if rates is None:
        return []
    return [
        {"time": int(r["time"]), "open": r["open"], "high": r["high"],
         "low": r["low"], "close": r["close"], "volume": int(r["tick_volume"])}
        for r in rates
    ]


def positions() -> list[dict]:
    if not _state["connected"]:
        return []
    pos = mt5.positions_get() or []  # type: ignore
    out = []
    for p in pos:
        out.append({
            "ticket": p.ticket, "symbol": p.symbol,
            "type": "BUY" if p.type == 0 else "SELL",
            "volume": p.volume, "openPrice": p.price_open,
            "currentPrice": p.price_current, "sl": p.sl, "tp": p.tp,
            "profit": p.profit, "pips": 0.0,
            "openTime": str(p.time), "comment": p.comment,
        })
    return out


def _ensure_connected() -> bool:
    """Re-validate MT5 connection; attempt one reconnect if stale.

    Broker-side disconnects (network drop, terminal restart) leave
    _state["connected"]=True but subsequent MT5 calls fail with vague errors.
    This re-checks and reconnects once before giving up. Shuts down the old
    terminal handle first to prevent leaks.
    """
    if not MT5_AVAILABLE:
        return False
    if _state["connected"]:
        # cheap health probe: can we fetch account info?
        try:
            if mt5.account_info() is not None:  # type: ignore
                return True
        except Exception:  # noqa: BLE001
            pass
        log.warning("MT5 connection stale — shutting down + reconnecting")
        try:
            mt5.shutdown()  # type: ignore — release stale terminal handle
        except Exception:  # noqa: BLE001
            pass
        _symbol_info_cache.clear()  # stale cache after reconnect
    ok = connect()
    return ok.connected


# human-readable MT5 retcode mapping (common ones)
RETCODE_MAP = {
    10004: "Requote — price moved, retry",
    10006: "Request rejected by broker",
    10007: "Cancelled by client",
    10008: "Partial fill — order partially executed",
    10009: "Order placed",
    10010: "Only part of request executed",
    10013: "Invalid stops (SL/TP too close)",
    10014: "Invalid volume",
    10015: "Invalid price",
    10016: "Off-quote — no price for SL/TP",
    10018: "Market closed",
    10019: "Not enough money",
    10021: "Price expired — no fresh quote",
    10027: "Autotrading disabled by client",
    10030: "Unsupported filling mode",
}


def _retcode_msg(retcode: int) -> str:
    return RETCODE_MAP.get(retcode, f"retcode {retcode}")


def send_order(symbol: str, side: str, volume: float, sl_pips: float,
               tp_pips: float, comment: str = "AI:auto",
               max_spread_pips: float = 5.0) -> dict:
    if not _ensure_connected():
        return {"ok": False, "error": "MT5 not connected"}
    info = _get_symbol_info(symbol)  # cached
    if not info:
        return {"ok": False, "error": f"symbol {symbol} not found"}
    tick = mt5.symbol_info_tick(symbol)  # type: ignore
    pip = _pip_for_digits(info.digits)
    # spread filter — refuse if spread too wide (news spike protection)
    spread_pips = (tick.ask - tick.bid) / pip
    if max_spread_pips > 0 and spread_pips > max_spread_pips:
        return {"ok": False, "error": f"Spread too wide ({spread_pips:.1f}p > {max_spread_pips}p) — likely news volatility"}
    price = tick.ask if side == "BUY" else tick.bid

    # ---- broker stops_level guard ------------------------------------------
    # Brokers reject SL/TP closer than trade_stops_level * point. If the
    # requested sl_pips/tp_pips are too tight, the broker silently drops them
    # — leaving the position with NO stops. We bump to the broker minimum.
    stops_level = getattr(info, "trade_stops_level", 0) or 0
    min_stop_pips = (stops_level * (info.point if hasattr(info, "point") else 10 ** -info.digits)) / pip
    eff_sl_pips = max(sl_pips, min_stop_pips + 1)
    eff_tp_pips = max(tp_pips, min_stop_pips + 1)
    if eff_sl_pips != sl_pips or eff_tp_pips != tp_pips:
        log.warning("⚠ SL/TP too tight for %s (stops_level=%d points=%.1fp) — "
                    "bumped SL %s→%sp, TP %s→%sp",
                    symbol, stops_level, min_stop_pips,
                    sl_pips, eff_sl_pips, tp_pips, eff_tp_pips)

    sl = price - eff_sl_pips * pip if side == "BUY" else price + eff_sl_pips * pip
    tp = price + eff_tp_pips * pip if side == "BUY" else price - eff_tp_pips * pip
    sl_rounded = round(sl, info.digits)
    tp_rounded = round(tp, info.digits)
    # deviation scales with instrument volatility (pips → points)
    deviation = int(max(10, eff_sl_pips * 5))
    req = {
        "action": mt5.TRADE_ACTION_DEAL,  # type: ignore
        "symbol": symbol, "volume": volume, "type": (
            mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL  # type: ignore
        ),
        "price": price, "sl": sl_rounded, "tp": tp_rounded,
        "deviation": deviation, "magic": 99001, "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,  # type: ignore
        "type_filling": _filling_mode(info),
    }
    r = mt5.order_send(req)  # type: ignore
    if r is None:
        return {"ok": False, "error": "order_send returned None (check MT5 logs)"}
    # treat DONE + DONE_PARTIAL as success; report filled volume
    success = r.retcode in (
        mt5.TRADE_RETCODE_DONE,  # type: ignore
        getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10008),
    )
    if not success:
        return {"ok": False, "error": _retcode_msg(r.retcode), "retcode": r.retcode}
    filled = getattr(r, "volume_order", volume) or volume

    # verify SL/TP were actually set — log for debugging
    log.info("order filled: ticket=%s price=%s vol=%s sl=%s tp=%s retcode=%s",
             r.order, r.price, filled, sl_rounded, tp_rounded, r.retcode)

    # CRITICAL: sometimes MT5 accepts the order but ignores SL/TP if
    # stops_level is too close. Check the actual position's SL/TP.
    import time as _time
    _time.sleep(0.3)  # small delay for position to register
    pos_check = mt5.positions_get(ticket=r.order)  # type: ignore
    broker_sl = sl_rounded
    broker_tp = tp_rounded
    if pos_check:
        p = pos_check[0]
        broker_sl = float(p.sl) if p.sl else 0.0
        broker_tp = float(p.tp) if p.tp else 0.0
        if p.sl == 0 or p.tp == 0:
            log.warning("⚠ SL/TP not set on position! broker sl=%s tp=%s — re-applying",
                        p.sl, p.tp)
            # try to set SL/TP via modify
            modify_sl_tp(r.order, sl_rounded, tp_rounded)
            # re-read after modify attempt
            pos_recheck = mt5.positions_get(ticket=r.order)  # type: ignore
            if pos_recheck:
                broker_sl = float(pos_recheck[0].sl) if pos_recheck[0].sl else 0.0
                broker_tp = float(pos_recheck[0].tp) if pos_recheck[0].tp else 0.0
                if pos_recheck[0].sl == 0 or pos_recheck[0].tp == 0:
                    log.error("❌ SL/TP STILL not set on position %s after modify! "
                              "Broker may reject stops near price. Intended SL=%s TP=%s "
                              "will be enforced by manage loop via DB fallback.",
                              r.order, sl_rounded, tp_rounded)
        else:
            log.info("position verified: ticket=%s sl=%s tp=%s OK",
                     r.order, p.sl, p.tp)
    # Always return the INTENDED sl/tp so callers can persist them as a
    # fallback for the manage loop (in case broker drops them later).
    return {
        "ok": True, "ticket": r.order, "price": r.price,
        "volume": filled, "requested_volume": volume,
        "partial": filled < volume,
        "sl": sl_rounded, "tp": tp_rounded,
        "broker_sl": broker_sl, "broker_tp": broker_tp,
    }


def close_position(ticket: int) -> dict:
    if not _ensure_connected():
        return {"ok": False, "error": "MT5 not connected"}
    pos = mt5.positions_get(ticket=ticket)  # type: ignore
    if not pos:
        # Position no longer exists — broker already closed it (SL/TP hit
        # broker-side). This is SUCCESS, not an error. Return ok=True with
        # already_closed=True so callers don't retry pointlessly.
        log.info("close_position: ticket=%s not found — broker already closed it", ticket)
        return {"ok": True, "already_closed": True, "price": 0.0,
                "pnl": 0.0, "pips": 0.0, "volume": 0.0}
    p = pos[0]
    info = _get_symbol_info(p.symbol)  # cached
    tick = mt5.symbol_info_tick(p.symbol)  # type: ignore
    side = "SELL" if p.type == 0 else "BUY"
    close_price = tick.bid if side == "SELL" else tick.ask
    req = {
        "action": mt5.TRADE_ACTION_DEAL,  # type: ignore
        "symbol": p.symbol, "volume": p.volume,
        "type": mt5.ORDER_TYPE_SELL if side == "SELL" else mt5.ORDER_TYPE_BUY,  # type: ignore
        "position": ticket,
        "price": close_price,
        "deviation": 20, "magic": 99001, "comment": "close",
        "type_time": mt5.ORDER_TIME_GTC,  # type: ignore
        "type_filling": _filling_mode(info),
    }
    r = mt5.order_send(req)  # type: ignore
    if r is None:
        return {"ok": False, "error": "order_send returned None"}
    if r.retcode != mt5.TRADE_RETCODE_DONE:  # type: ignore
        return {"ok": False, "error": _retcode_msg(r.retcode), "retcode": r.retcode}
    # compute realized P&L + pips for risk tracking + trade history
    pip = _pip_for_digits(info.digits)
    pips = ((close_price - p.price_open) / pip if side == "SELL"
            else (p.price_open - close_price) / pip)
    pnl = getattr(p, "profit", 0.0) or 0.0
    return {
        "ok": True, "retcode": r.retcode, "price": close_price,
        "pnl": float(pnl), "pips": float(pips), "volume": p.volume,
    }


def modify_sl_tp(ticket: int, sl: float | None = None, tp: float | None = None) -> dict:
    """Modify SL/TP of an open position (for trailing stop / break-even).

    Only modifies fields that are not None. Returns ok=True on success.
    """
    if not _ensure_connected():
        return {"ok": False, "error": "MT5 not connected"}
    pos = mt5.positions_get(ticket=ticket)  # type: ignore
    if not pos:
        return {"ok": False, "error": "position not found"}
    p = pos[0]
    info = _get_symbol_info(p.symbol)  # type: ignore
    if not info:
        return {"ok": False, "error": "symbol info not found"}

    # keep existing SL/TP if not overriding
    new_sl = sl if sl is not None else p.sl
    new_tp = tp if tp is not None else p.tp
    # round to symbol digits
    if new_sl:
        new_sl = round(new_sl, info.digits)
    if new_tp:
        new_tp = round(new_tp, info.digits)

    req = {
        "action": mt5.TRADE_ACTION_SLTP,  # type: ignore
        "symbol": p.symbol,
        "position": ticket,
        "sl": new_sl,
        "tp": new_tp,
    }
    r = mt5.order_send(req)  # type: ignore
    if r is None:
        return {"ok": False, "error": "order_send returned None"}
    if r.retcode != mt5.TRADE_RETCODE_DONE:  # type: ignore
        return {"ok": False, "error": _retcode_msg(r.retcode), "retcode": r.retcode}
    log.info("SL/TP modified: ticket=%s sl=%s tp=%s", ticket, new_sl, new_tp)
    return {"ok": True, "ticket": ticket, "sl": new_sl, "tp": new_tp}


def partial_close(ticket: int, volume: float) -> dict:
    """Partially close a position (scale-out). Closes `volume` lots.

    Returns ok=True with realized pnl proportional to closed volume.
    """
    if not _ensure_connected():
        return {"ok": False, "error": "MT5 not connected"}
    pos = mt5.positions_get(ticket=ticket)  # type: ignore
    if not pos:
        return {"ok": False, "error": "position not found"}
    p = pos[0]
    if volume >= p.volume:
        # full close — delegate to close_position
        return close_position(ticket)
    info = _get_symbol_info(p.symbol)  # type: ignore
    if not info:
        return {"ok": False, "error": "symbol info not found"}
    tick = mt5.symbol_info_tick(p.symbol)  # type: ignore
    side = "SELL" if p.type == 0 else "BUY"
    close_price = tick.bid if side == "SELL" else tick.ask
    req = {
        "action": mt5.TRADE_ACTION_DEAL,  # type: ignore
        "symbol": p.symbol, "volume": volume,
        "type": mt5.ORDER_TYPE_SELL if side == "SELL" else mt5.ORDER_TYPE_BUY,  # type: ignore
        "position": ticket,
        "price": close_price,
        "deviation": 20, "magic": 99001, "comment": "partial_close",
        "type_time": mt5.ORDER_TIME_GTC,  # type: ignore
        "type_filling": _filling_mode(info),
    }
    r = mt5.order_send(req)  # type: ignore
    if r is None:
        return {"ok": False, "error": "order_send returned None"}
    if r.retcode != mt5.TRADE_RETCODE_DONE:  # type: ignore
        return {"ok": False, "error": _retcode_msg(r.retcode), "retcode": r.retcode}
    pip = _pip_for_digits(info.digits)
    pips = ((close_price - p.price_open) / pip if side == "SELL"
            else (p.price_open - close_price) / pip)
    # proportional P&L for partial volume
    pnl_ratio = volume / p.volume
    pnl = float(getattr(p, "profit", 0.0) or 0.0) * pnl_ratio
    log.info("partial close: ticket=%s vol=%s pnl=%.2f", ticket, volume, pnl)
    return {"ok": True, "price": close_price, "pnl": pnl, "pips": float(pips),
            "volume_closed": volume, "remaining": p.volume - volume}
