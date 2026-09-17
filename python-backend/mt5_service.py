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


_state: dict[str, Any] = {"connected": False, "account": None, "terminal": None}


def _launch_terminal() -> bool:
    """Launch terminal64.exe and wait until the MT5 RPC is reachable."""
    path = settings.mt5_terminal_path
    if not os.path.exists(path):
        log.error("MT5 terminal not found at %s", path)
        return False
    log.info("Auto-launching MT5 terminal: %s", path)
    try:
        subprocess.Popen([path])
    except Exception as exc:
        log.error("Failed to launch terminal: %s", exc)
        return False
    # wait up to 30s for the RPC to come online
    for _ in range(30):
        if mt5.initialize():  # type: ignore
            return True
        time.sleep(1)
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


def ticks(symbols: list[str] | None = None) -> list[dict]:
    if not _state["connected"]:
        return []
    out = []
    for sym in (symbols or ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]):
        t = mt5.symbol_info_tick(sym)  # type: ignore
        info = mt5.symbol_info(sym)  # type: ignore
        if not t or not info:
            continue
        pip = _pip_for_digits(info.digits)
        out.append({
            "symbol": sym, "bid": t.bid, "ask": t.ask,
            "spreadPips": (t.ask - t.bid) / pip,
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
    This re-checks and reconnects once before giving up.
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
        log.warning("MT5 connection stale — attempting reconnect")
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
               tp_pips: float, comment: str = "AI:auto") -> dict:
    if not _ensure_connected():
        return {"ok": False, "error": "MT5 not connected"}
    info = mt5.symbol_info(symbol)  # type: ignore
    if not info:
        return {"ok": False, "error": f"symbol {symbol} not found"}
    tick = mt5.symbol_info_tick(symbol)  # type: ignore
    pip = _pip_for_digits(info.digits)
    price = tick.ask if side == "BUY" else tick.bid
    sl = price - sl_pips * pip if side == "BUY" else price + sl_pips * pip
    tp = price + tp_pips * pip if side == "BUY" else price - tp_pips * pip
    # deviation scales with instrument volatility (pips → points)
    deviation = int(max(10, sl_pips * 5))
    req = {
        "action": mt5.TRADE_ACTION_DEAL,  # type: ignore
        "symbol": symbol, "volume": volume, "type": (
            mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL  # type: ignore
        ),
        "price": price, "sl": round(sl, info.digits), "tp": round(tp, info.digits),
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
    return {
        "ok": True, "ticket": r.order, "price": r.price,
        "volume": filled, "requested_volume": volume,
        "partial": filled < volume,
    }


def close_position(ticket: int) -> dict:
    if not _ensure_connected():
        return {"ok": False, "error": "MT5 not connected"}
    pos = mt5.positions_get(ticket=ticket)  # type: ignore
    if not pos:
        return {"ok": False, "error": "position not found"}
    p = pos[0]
    info = mt5.symbol_info(p.symbol)  # type: ignore
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
