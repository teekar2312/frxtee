"""ZeniTrade AI — FastAPI application.

Production-grade trading API. Routes mirror the Next.js dashboard's
``/api/trading/*`` contract so the frontend can proxy to this backend.

Safety features:
- Pydantic request validation (no 500s on junk input)
- API token auth (ZENITRADE_API_TOKEN env) + binds 127.0.0.1 by default
- asyncio.Lock around the order critical section (race-free risk checks)
- Background position reconciliation (syncs guard with broker-side closes)
- Terminal path locked to .env (no remote executable launch)
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config import settings
from mt5_service import candles as mt5_candles
from mt5_service import close_position, connect, disconnect, positions as mt5_positions
from mt5_service import send_order, status as mt5_status, ticks as mt5_ticks
from mt5_service import get_pip_value_per_lot, get_recent_deals, modify_sl_tp
from mt5_service import partial_close, _pip_for_digits
from news_service import economic_calendar, fetch_news, aggregate_sentiment
from risk_manager import guard, size_position, near_high_impact_news, trail_stop
import ai_service
import backtest as bt
import ml_model
from notifier import add_price_alert, check_alerts, send_email, notify_async
from db import init_db, add_log, get_logs, get_trades, save_trade, close_trade, cleanup_old

# ---- structured JSON logging (for production log aggregation) --------------
import json as _json
import os as _os

class JsonFormatter(logging.Formatter):
    """Emit log records as JSON lines for ELK/Loki/CloudWatch."""
    def format(self, record):
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return _json.dumps(log_entry, default=str)

_log_format = "json" if _os.environ.get("LOG_FORMAT", "").lower() == "json" else "text"
if _log_format == "json":
    _handler = logging.StreamHandler()
    _handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[_handler])
else:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("zenitrade")

# ---- Sentry error monitoring (optional via SENTRY_DSN) -------------------
if settings.sentry_dsn:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1,
            environment="production",
        )
        log.info("Sentry error monitoring enabled")
    except ImportError:
        log.warning("sentry-sdk not installed — SENTRY_DSN set but package missing")

# ---- DB-backed log handler ------------------------------------------------
class DBLogHandler(logging.Handler):
    """Write log records to SQLite logs table.

    Captures INFO+ from 'zenitrade' logger (trade lifecycle, order events)
    and WARNING+ from other loggers (MT5, news, AI — reduce noise).
    """
    def emit(self, record):
        try:
            # only persist INFO+ from zenitrade logger, WARNING+ from others
            if record.name == "zenitrade" and record.levelno >= logging.INFO:
                add_log(record.levelname, record.name, record.getMessage())
            elif record.levelno >= logging.WARNING:
                add_log(record.levelname, record.name, record.getMessage())
        except Exception:  # noqa: BLE001
            pass  # never let logging crash the app

# attach DB handler to root logger
_db_handler = DBLogHandler(level=logging.INFO)
logging.getLogger().addHandler(_db_handler)

# ---- security: API token auth -------------------------------------------
API_TOKEN = os.environ.get("ZENITRADE_API_TOKEN", "")
# lock around order placement to prevent race conditions
_order_lock = asyncio.Lock()
_alert_task: asyncio.Task | None = None
_reconcile_task: asyncio.Task | None = None
_cleanup_task: asyncio.Task | None = None


async def _alert_loop():
    """Background task: poll ticks & check price alerts every 5s."""
    while True:
        try:
            t = await asyncio.to_thread(mt5_ticks)
            if t:
                await asyncio.to_thread(check_alerts, t)
        except Exception as exc:  # noqa: BLE001
            log.debug("alert loop: %s", exc)
        await asyncio.sleep(5)


# track which deals we've already processed (avoid double-counting P&L)
_processed_deal_tickets: set = set()


async def _reconcile_loop():
    """Background task: sync guard.open_count + daily_loss with broker every 10s.

    Broker-side closes (SL/TP hit, margin call) bypass our register_close(),
    so open_count drifts upward AND daily_loss is undercounted. This polls
    real positions + recent deal history to correct both.
    """
    while True:
        try:
            pos = await asyncio.to_thread(mt5_positions)
            real_count = len(pos)
            drift = guard.open_count - real_count
            if drift > 0:
                log.info("position reconcile: guard=%d real=%d → correcting",
                         guard.open_count, real_count)
                # fetch recently closed deals to get their P&L
                deals = await asyncio.to_thread(get_recent_deals, 15)
                for d in deals:
                    ticket = d.get("ticket")
                    if ticket and ticket not in _processed_deal_tickets:
                        _processed_deal_tickets.add(ticket)
                        pnl = d.get("profit", 0.0)
                        log.info("broker-side close detected: ticket=%s pnl=%.2f",
                                 ticket, pnl)
                        # register realized P&L for daily risk tracking
                        guard.register_close(pnl)
                        # persist to trade history DB
                        try:
                            close_trade(ticket, d.get("price", 0), pnl,
                                        d.get("pips", 0))
                        except Exception:  # noqa: BLE001
                            pass
                        # keep set bounded
                        if len(_processed_deal_tickets) > 200:
                            _processed_deal_tickets.clear()
                guard.open_count = real_count
        except Exception as exc:  # noqa: BLE001
            log.debug("reconcile loop: %s", exc)
        await asyncio.sleep(10)


async def _cleanup_loop():
    """Background task: prune old DB rows every hour to keep DB bounded."""
    while True:
        try:
            await asyncio.to_thread(cleanup_old)
        except Exception as exc:  # noqa: BLE001
            log.debug("cleanup loop: %s", exc)
        await asyncio.sleep(3600)


# track which positions have had BE applied (avoid repeated BE moves)
_be_applied: set[int] = set()
_partial_applied: set[int] = set()
# track last signal time per symbol for cooldown
_last_signal_ts: dict[str, float] = {}
_SIGNAL_COOLDOWN_SEC = 60  # min 60s between AI signals for same symbol


async def _manage_positions_loop():
    """Background task: manage open positions every 5s.

    Implements (all config-driven, not hardcoded):
    - Break-even: move SL to entry+buffer at +break_even_r_multiple (default 1.0R)
    - Trailing stop: fixed pips OR ATR-based dynamic (configurable)
    - Partial close: close partial_close_ratio at +partial_close_r_multiple
    Uses PER-POSITION SL (not global default) for R-multiple calculation.
    """
    while True:
        try:
            positions = await asyncio.to_thread(mt5_positions)
            if not positions:
                _be_applied.clear()
                _partial_applied.clear()
                await asyncio.sleep(5)
                continue

            trailing_enabled = settings.trailing_enabled
            trailing_pips = settings.trailing_pips
            use_atr = settings.trailing_use_atr
            atr_mult = settings.trailing_atr_multiplier
            be_enabled = settings.break_even_enabled
            be_r = settings.break_even_r_multiple
            be_buffer = settings.break_even_buffer_pips
            pc_enabled = settings.partial_close_enabled
            pc_r = settings.partial_close_r_multiple
            pc_ratio = settings.partial_close_ratio

            for p in positions:
                ticket = p["ticket"]
                pos_type = p["type"]
                open_price = p["openPrice"]
                current = p["currentPrice"]
                sl = p.get("sl")
                symbol = p["symbol"]
                digits = _get_digits(symbol)
                pip = _pip_for_digits(digits)

                # compute PER-POSITION SL (not global default) for R-multiple
                # SL distance from entry = |sl - open_price| / pip
                if sl and sl > 0:
                    pos_sl_pips = abs(sl - open_price) / pip
                else:
                    pos_sl_pips = settings.stop_loss_pips  # fallback

                # compute R-multiple (how far price moved in our favor, in R units)
                if pos_type == "BUY":
                    favor_pips = (current - open_price) / pip
                else:
                    favor_pips = (open_price - current) / pip
                r_multiple = favor_pips / pos_sl_pips if pos_sl_pips > 0 else 0

                # 1. Break-even: move SL to entry+buffer when price reaches +be_r
                if be_enabled and r_multiple >= be_r and ticket not in _be_applied:
                    be_buffer_price = pip * be_buffer
                    if pos_type == "BUY":
                        new_sl = open_price + be_buffer_price
                    else:
                        new_sl = open_price - be_buffer_price
                    # only move if new SL is strictly better than current
                    if sl is None or (pos_type == "BUY" and new_sl > sl) or (pos_type == "SELL" and new_sl < sl):
                        r = await asyncio.to_thread(modify_sl_tp, ticket, new_sl, None)
                        if r.get("ok"):
                            _be_applied.add(ticket)
                            log.info("break-even: ticket=%s sl=%s (R=%.2f, pos_sl=%.1fp)",
                                     ticket, new_sl, r_multiple, pos_sl_pips)
                            notify_async(
                                f"Break-even: #{ticket} {symbol}",
                                f"<p>SL moved to break-even ({new_sl}). R={r_multiple:.1f}</p>"
                                f"<p>Position SL: {pos_sl_pips:.1f} pips</p>",
                            )

                # 2. Trailing stop: fixed or ATR-based dynamic
                if trailing_enabled and r_multiple > 0:
                    # ATR-based dynamic trailing (adapts to volatility)
                    if use_atr:
                        try:
                            rates = await asyncio.to_thread(mt5_candles, symbol, "M15", 50)
                            if rates:
                                import pandas as pd
                                from indicators import atr as calc_atr
                                df = pd.DataFrame(rates)
                                atr_val = calc_atr(df, 14).dropna().iloc[-1]
                                trail_distance = atr_val * atr_mult
                            else:
                                trail_distance = trailing_pips * pip
                        except Exception:  # noqa: BLE001
                            trail_distance = trailing_pips * pip
                    else:
                        trail_distance = trailing_pips * pip

                    # compute candidate SL and check if it's strictly better
                    if pos_type == "BUY":
                        candidate = current - trail_distance
                        should_move = sl is None or candidate > sl
                    else:
                        candidate = current + trail_distance
                        should_move = sl is None or candidate < sl

                    if should_move:
                        new_sl = round(candidate, digits)
                        r = await asyncio.to_thread(modify_sl_tp, ticket, new_sl, None)
                        if r.get("ok"):
                            log.debug("trailing: ticket=%s sl→%s dist=%.1fp",
                                      ticket, new_sl, trail_distance / pip)
                        elif r.get("retcode") == 10013:
                            log.warning("trailing rejected (invalid stops): ticket=%s — "
                                        "check broker stop_level", ticket)

                # 3. Partial close at +pc_r (scale out pc_ratio)
                if pc_enabled and r_multiple >= pc_r and ticket not in _partial_applied:
                    partial_vol = round(p["volume"] * pc_ratio, 2)
                    if partial_vol >= 0.01:
                        r = await asyncio.to_thread(partial_close, ticket, partial_vol)
                        if r.get("ok"):
                            _partial_applied.add(ticket)
                            log.info("partial close: ticket=%s vol=%s pnl=%.2f remaining=%s",
                                     ticket, partial_vol, r.get("pnl", 0),
                                     r.get("remaining", 0))
                            notify_async(
                                f"Partial close: #{ticket} {symbol}",
                                f"<p>Closed {partial_vol} lot ({pc_ratio*100:.0f}%). "
                                f"P&L: ${r.get('pnl', 0):.2f}</p>"
                                f"<p>Remaining: {r.get('remaining', 0)} lot</p>",
                            )

            # cleanup tracking sets for closed positions
            active_tickets = {p["ticket"] for p in positions}
            _be_applied &= active_tickets
            _partial_applied &= active_tickets

        except Exception as exc:  # noqa: BLE001
            log.debug("manage positions loop: %s", exc)
        await asyncio.sleep(5)


def _get_digits(symbol: str) -> int:
    """Quick digits lookup for _manage_positions_loop."""
    from mt5_service import _get_symbol_info
    info = _get_symbol_info(symbol)
    return info.digits if info else 5


async def _auto_trade_loop():
    """Background task: auto-execute AI signals when autoTradeMode is enabled.

    Polls analysis for active pairs every 60s (cooldown). If signal is
    directional (BUY/SELL) with confidence >= threshold, places order.
    """
    while True:
        try:
            # auto-trade is opt-in via settings flag
            if not getattr(settings, "auto_trade_mode", False):
                await asyncio.sleep(30)
                continue

            # auto_trade_symbols is comma-separated string — split into list
            symbols_str = getattr(settings, "auto_trade_symbols", "")
            symbols = [s.strip() for s in symbols_str.split(",") if s.strip()] if symbols_str else []
            if not symbols:
                await asyncio.sleep(30)
                continue

            provider = getattr(settings, "ai_provider", "zai")
            min_confidence = getattr(settings, "auto_trade_min_confidence", 75)

            for symbol in symbols:
                # cooldown check
                now = time.time()
                last = _last_signal_ts.get(symbol, 0)
                if now - last < _SIGNAL_COOLDOWN_SEC:
                    continue

                # build context with indicators + sentiment (was empty — hallucinated)
                ctx = {"timeframe": "M15", "symbol": symbol}
                try:
                    rates = await asyncio.to_thread(mt5_candles, symbol, "M15", 100)
                    if rates:
                        import pandas as pd
                        from indicators import compute as ind_compute
                        df = pd.DataFrame(rates)
                        top10 = ["ema", "rsi", "macd", "atr", "bbands", "vwap",
                                 "stochastic", "supertrend", "psar", "cci"]
                        results = ind_compute(df, top10)
                        readings = {}
                        for k, v in results.items():
                            if isinstance(v, list) and v:
                                readings[k] = round(v[-1], 5) if isinstance(v[-1], (int, float)) else None
                        ctx["indicators"] = readings
                        ctx["current_price"] = rates[-1]["close"]
                except Exception:  # noqa: BLE001
                    pass
                try:
                    ctx["sentiment"] = _get_symbol_sentiment(symbol)
                except Exception:  # noqa: BLE001
                    pass

                # fetch analysis with real context
                result = await asyncio.to_thread(
                    ai_service.analyze, symbol, provider, ctx
                )
                signal = result.get("signal", "NEUTRAL")
                confidence = result.get("confidence", 0)

                if signal == "NEUTRAL" or confidence < min_confidence:
                    continue

                # execute signal
                side = "BUY" if "BUY" in signal else "SELL"
                _last_signal_ts[symbol] = now
                log.info("auto-trade: %s %s conf=%s%% → executing",
                         side, symbol, confidence)

                async with _order_lock:
                    equity = 10000.0
                    st = mt5_status()
                    if st.account:
                        equity = st.account.get("equity", 10000.0)
                    ok, msg = guard.can_open(equity)
                    if not ok:
                        log.warning("auto-trade blocked: %s", msg)
                        continue

                    pip_value = await asyncio.to_thread(get_pip_value_per_lot, symbol)
                    ps = size_position(equity, settings.stop_loss_pips, pip_value)
                    volume = round(max(0.01, min(ps.lot, 50.0)), 2)

                    r = await asyncio.to_thread(
                        send_order, symbol, side, volume,
                        settings.stop_loss_pips, ps.tp_pips, "AI:auto"
                    )
                    if r.get("ok"):
                        guard.register_open()
                        try:
                            save_trade(
                                ticket=r.get("ticket", 0), symbol=symbol, side=side,
                                volume=volume, open_price=r.get("price", 0),
                                comment="AI:auto", source="ai",
                            )
                        except Exception:  # noqa: BLE001
                            pass
                        notify_async(
                            f"🤖 Auto-trade: {side} {symbol}",
                            f"<p>AI signal {signal} ({confidence}% confidence)</p>"
                            f"<p>{side} {symbol} {volume} lot @ {r.get('price')}</p>"
                            f"<p>SL {settings.stop_loss_pips}p · TP {ps.tp_pips:.1f}p</p>",
                        )
                        log.info("auto-trade executed: ticket=%s", r.get("ticket"))

        except Exception as exc:  # noqa: BLE001
            log.debug("auto-trade loop: %s", exc)
        await asyncio.sleep(30)


_manage_task: asyncio.Task | None = None
_autotrade_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _alert_task, _reconcile_task, _cleanup_task, _manage_task, _autotrade_task
    log.info("ZeniTrade AI backend starting — FINEX / MT5 / AI")
    # CRITICAL: guard against multi-worker deployment that would break
    # the in-process _order_lock + guard state (daily_loss, open_count).
    # SQLite risk_state is per-worker unless using a shared DB on disk —
    # but the in-memory guard is NOT shared. Refuse to start unless ack.
    import os as _os
    workers = int(_os.environ.get("UVICORN_WORKERS", "1"))
    if workers > 1 and _os.environ.get("MULTI_WORKER_SAFE") != "1":
        raise RuntimeError(
            f"Refusing to start with {workers} workers — the order lock + risk "
            "guard are process-local. Running >1 worker silently breaks "
            "daily-loss and open-count limits (direct money risk). To override, "
            "set MULTI_WORKER_SAFE=1 (not recommended for real-money trading)."
        )
    # initialize persistence layer FIRST (risk state restore depends on it)
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001
        log.warning("DB init failed: %s — persistence disabled", exc)
    # security warning if no token set
    if not API_TOKEN:
        log.warning("⚠ ZENITRADE_API_TOKEN not set — API is unauthenticated! "
                    "Set it in .env for production.")
    # connect to MT5 on boot (auto-launch if configured)
    try:
        connect()
    except Exception as exc:  # noqa: BLE001
        log.warning("MT5 connect on boot failed: %s", exc)
    _alert_task = asyncio.create_task(_alert_loop())
    _reconcile_task = asyncio.create_task(_reconcile_loop())
    _cleanup_task = asyncio.create_task(_cleanup_loop())
    _manage_task = asyncio.create_task(_manage_positions_loop())
    _autotrade_task = asyncio.create_task(_auto_trade_loop())
    scheduler = None
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(ml_model.train, "cron", hour=2, minute=0)
        scheduler.start()
        app.state.scheduler = scheduler
    except Exception as exc:  # noqa: BLE001
        log.warning("scheduler init failed: %s", exc)
    yield
    if _alert_task:
        _alert_task.cancel()
    if _reconcile_task:
        _reconcile_task.cancel()
    if _cleanup_task:
        _cleanup_task.cancel()
    if _manage_task:
        _manage_task.cancel()
    if _autotrade_task:
        _autotrade_task.cancel()
    if scheduler:
        try:
            scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
    try:
        disconnect()
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(title="ZeniTrade AI", version="1.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# ---- rate limiter --------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_handler(request: Request, exc: RateLimitExceeded):
    # Must return a Response, not raise HTTPException (which would 500)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"ok": False, "error": f"Rate limit exceeded: {exc.detail}"},
    )


# ---- auth dependency ----------------------------------------------------
async def require_token(x_api_token: str | None = Header(default=None)):
    """Require a valid API token header when ZENITRADE_API_TOKEN is set.
    When the env var is empty (dev), all requests are allowed."""
    if API_TOKEN and x_api_token != API_TOKEN:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid API token")


# ---- Pydantic request models --------------------------------------------
class ConnectReq(BaseModel):
    login: int | None = None
    server: str | None = None
    password: str | None = None
    autoLaunch: bool | None = None
    # NOTE: `terminal` path is intentionally NOT accepted from the client —
    # it must come from the server-side .env to prevent arbitrary exec launch.


class OrderReq(BaseModel):
    symbol: str = Field(..., min_length=3, max_length=12)
    side: str = Field(..., pattern="^(BUY|SELL)$")
    volume: float | None = None  # optional; if omitted, AI sizes via risk%
    slPips: int = Field(default=10, ge=1, le=200)
    comment: str = Field(default="AI:auto", max_length=31)


class AlertReq(BaseModel):
    symbol: str = Field(..., min_length=3, max_length=12)
    condition: str = Field(..., pattern="^(above|below|cross_up|cross_down)$")
    price: float = Field(..., gt=0)


# ---- routes --------------------------------------------------------------
@app.get("/")
async def root():
    return {"app": "ZeniTrade AI", "version": "1.1.0", "status": mt5_status().__dict__}


@app.get("/health")
async def health():
    """Deep health probe: MT5 + DB + scheduler + background loops."""
    s = mt5_status()
    checks = {"mt5_connected": s.connected, "demo": s.demo}
    # DB health
    try:
        from db import _conn
        with _conn() as c:
            c.execute("SELECT 1")
        checks["db"] = True
    except Exception:  # noqa: BLE001
        checks["db"] = False
    # scheduler health
    checks["scheduler"] = hasattr(app.state, "scheduler") and app.state.scheduler.running
    # background loops alive
    checks["alert_loop"] = _alert_task is not None and not _alert_task.done()
    checks["reconcile_loop"] = _reconcile_task is not None and not _reconcile_task.done()
    all_ok = all(v for k, v in checks.items() if k != "demo")
    return {
        "ok": all_ok,
        "checks": checks,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/metrics")
async def metrics():
    """Prometheus-style metrics for observability."""
    s = mt5_status()
    try:
        from db import _conn
        with _conn() as c:
            trades = c.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            logs = c.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
            alerts = c.execute("SELECT COUNT(*) FROM alerts WHERE active=1").fetchone()[0]
    except Exception:  # noqa: BLE001
        trades = logs = alerts = 0
    return {
        "mt5_connected": int(s.connected),
        "open_positions": guard.open_count,
        "daily_loss": guard.daily_loss,
        "trade_count": trades,
        "log_count": logs,
        "active_alerts": alerts,
        "alert_loop_alive": int(_alert_task is not None and not _alert_task.done()),
        "reconcile_loop_alive": int(_reconcile_task is not None and not _reconcile_task.done()),
    }


@app.get("/api/trading/status")
async def get_status():
    return mt5_status().__dict__


@app.post("/api/trading/connect")
async def api_connect(body: ConnectReq, _auth=Depends(require_token)):
    # apply overrides EXCEPT terminal path (security)
    if body.login:
        settings.mt5_login = body.login
    if body.server:
        settings.mt5_server = body.server
    if body.password:
        settings.mt5_password = body.password
    return connect().__dict__


@app.delete("/api/trading/connect")
async def api_disconnect(_auth=Depends(require_token)):
    return disconnect().__dict__


@app.get("/api/trading/ticks")
async def api_ticks(symbols: str | None = None):
    syms = symbols.split(",") if symbols else None
    t = await asyncio.to_thread(mt5_ticks, syms)
    return {"ts": int(time.time() * 1000), "ticks": t, "demo": not t}


@app.get("/api/trading/candles")
async def api_candles(symbol: str = "EURUSD", tf: str = "M15", count: int = 120):
    count = max(1, min(count, 500))
    c = await asyncio.to_thread(mt5_candles, symbol, tf, count)
    return {"symbol": symbol, "tf": tf, "candles": c, "demo": not c}


@app.get("/api/trading/positions")
async def api_positions():
    p = await asyncio.to_thread(mt5_positions)
    return {"positions": p, "demo": not p}


@app.post("/api/trading/order")
@limiter.limit("10/minute")
async def api_order(body: OrderReq, request: Request, _auth=Depends(require_token)):
    """Place a market order with full safety enforcement."""
    async with _order_lock:
        equity = 10000.0
        st = mt5_status()
        if st.account:
            equity = st.account.get("equity", 10000.0)
        ok, msg = guard.can_open(equity)
        if not ok:
            return {"ok": False, "error": msg}

        # news blackout: refuse new entries near high-impact events
        blackout, reason = await asyncio.to_thread(near_high_impact_news, 15)
        if blackout:
            log.warning("order blocked — news blackout: %s", reason)
            return {"ok": False, "error": f"News blackout: {reason}"}

        # position-size via risk with symbol-accurate pip value
        pip_value = await asyncio.to_thread(get_pip_value_per_lot, body.symbol)
        ps = size_position(equity, body.slPips, value_per_pip_per_lot=pip_value)
        volume = body.volume if body.volume is not None else ps.lot
        volume = round(max(0.01, min(volume, 50.0)), 2)  # FINEX: 0.01–50 lot

        r = await asyncio.to_thread(
            send_order, body.symbol, body.side, volume,
            body.slPips, ps.tp_pips, body.comment,
        )
        if r.get("ok"):
            guard.register_open()
            # persist trade to DB — retry once, then log critical if still fails
            ticket = r.get("ticket", 0)
            db_saved = False
            for attempt in range(2):
                try:
                    save_trade(
                        ticket=ticket, symbol=body.symbol, side=body.side,
                        volume=volume, open_price=r.get("price", 0),
                        comment=body.comment,
                        source="ai" if "AI" in body.comment else "manual",
                    )
                    db_saved = True
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt == 0:
                        log.warning("save_trade retry for ticket %s: %s", ticket, exc)
                        await asyncio.sleep(0.5)
                    else:
                        # CRITICAL: order exists in MT5 but not in DB
                        log.error("⚠ ORPHANED TRADE: ticket=%s %s %s %s lot @ %s — "
                                  "DB save failed: %s. Trade is live but untracked!",
                                  ticket, body.side, body.symbol, volume,
                                  r.get("price"), exc)
                        notify_async(
                            f"⚠ CRITICAL: Orphaned trade #{ticket}",
                            f"<p>Order was filled on MT5 but DB persistence failed.</p>"
                            f"<p>Ticket: {ticket}<br>Symbol: {body.symbol}<br>"
                            f"Side: {body.side}<br>Volume: {volume} lot<br>"
                            f"Price: {r.get('price')}</p>"
                            f"<p>Error: {exc}</p>"
                            f"<p><b>Manual reconciliation required.</b></p>",
                        )
            notify_async(
                f"Trade opened: {body.side} {body.symbol}",
                f"<p>{body.side} {body.symbol} {volume} lot @ {r.get('price')}</p>"
                f"<p>SL {body.slPips}p · TP {ps.tp_pips:.1f}p · Risk ${ps.risk_amount:.2f}</p>"
                f"<p>Pip value: ${pip_value:.2f}/pip/lot</p>",
            )
        else:
            # structured error capture for order failures
            log.warning("order failed: symbol=%s side=%s vol=%s sl=%dp — %s",
                        body.symbol, body.side, volume, body.slPips,
                        r.get("error", "unknown"))
        return r


@app.delete("/api/trading/positions/{ticket}")
@limiter.limit("10/minute")
async def api_close(ticket: int, request: Request, _auth=Depends(require_token)):
    log.info("manual close requested: ticket=%s", ticket)
    r = await asyncio.to_thread(close_position, ticket)
    if r.get("ok"):
        # persist closed trade + register realized P&L for daily risk
        pnl = r.get("pnl", 0.0)
        pips = r.get("pips", 0.0)
        try:
            close_trade(ticket, r.get("price", 0), pnl, pips)
        except Exception:  # noqa: BLE001
            pass
        guard.register_close(pnl)
        log.info("trade closed: ticket=%s pnl=%.2f pips=%.1f", ticket, pnl, pips)
        # email notification for manual close (was missing)
        notify_async(
            f"Trade closed: #{ticket}",
            f"<p>Manual close at {r.get('price', 0)}</p>"
            f"<p>P&L: ${pnl:.2f} ({pips:.1f} pips)</p>",
        )
    else:
        log.warning("manual close failed: ticket=%s error=%s", ticket, r.get("error"))
    return r


@app.post("/api/trading/positions/{ticket}/modify")
@limiter.limit("20/minute")
async def api_modify_sl_tp(ticket: int, request: Request,
                           _auth=Depends(require_token)):
    """Modify SL/TP of an open position (trailing stop / break-even)."""
    import json as _json
    try:
        raw = await request.body()
        body = _json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001
        body = {}
    sl = body.get("sl")
    tp = body.get("tp")
    r = await asyncio.to_thread(modify_sl_tp, ticket, sl, tp)
    return r


@app.post("/api/trading/positions/{ticket}/partial")
@limiter.limit("10/minute")
async def api_partial_close(ticket: int, request: Request,
                            _auth=Depends(require_token)):
    """Partially close a position (scale-out). Body: { volume: 0.05 }."""
    import json as _json
    try:
        raw = await request.body()
        body = _json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001
        body = {}
    volume = float(body.get("volume", 0))
    if volume <= 0:
        return {"ok": False, "error": "volume must be > 0"}
    r = await asyncio.to_thread(partial_close, ticket, volume)
    if r.get("ok"):
        # register proportional P&L
        pnl = r.get("pnl", 0.0)
        if pnl < 0:
            guard.register_loss(pnl)
        log.info("partial close: ticket=%s vol=%s pnl=%.2f remaining=%s",
                 ticket, volume, pnl, r.get("remaining"))
    return r


@app.get("/api/trading/news")
async def api_news():
    # fetch news + calendar concurrently (were sequential)
    n, cal = await asyncio.gather(fetch_news(), economic_calendar())
    # attach real aggregate sentiment (was hardcoded in UI)
    sentiment = aggregate_sentiment()
    return {"news": n, "calendar": cal, "sentiment": sentiment, "demo": not n}


@app.get("/api/trading/sentiment")
async def api_sentiment(symbol: str | None = None):
    """Get aggregate sentiment, optionally filtered by symbol."""
    return aggregate_sentiment(symbol)


def _get_symbol_sentiment(symbol: str) -> dict:
    """Sync helper to get sentiment for a symbol (for AI context)."""
    return aggregate_sentiment(symbol)


@app.get("/api/trading/analysis")
async def api_analysis(symbol: str = "EURUSD", provider: str = "zai"):
    # Build technical context from real indicator data (not hallucinated)
    async def _build_context():
        ctx = {"timeframe": "M15", "symbol": symbol}
        try:
            rates = await asyncio.to_thread(mt5_candles, symbol, "M15", 100)
            if rates:
                import pandas as pd
                from indicators import compute
                df = pd.DataFrame(rates)
                # compute top 10 indicators for AI context
                top10 = ["ema", "rsi", "macd", "atr", "bbands", "vwap",
                         "stochastic", "supertrend", "psar", "cci"]
                results = compute(df, top10)
                # summarize key readings (last value only, to fit prompt budget)
                readings = {}
                for k, v in results.items():
                    if isinstance(v, list) and v:
                        readings[k] = round(v[-1], 5) if isinstance(v[-1], (int, float)) else None
                    elif isinstance(v, (int, float)):
                        readings[k] = round(v, 5)
                ctx["indicators"] = readings
                # current price + recent trend
                ctx["current_price"] = rates[-1]["close"]
                ctx["recent_high"] = max(r["high"] for r in rates[-20:])
                ctx["recent_low"] = min(r["low"] for r in rates[-20:])
        except Exception as exc:  # noqa: BLE001
            log.debug("indicator context build failed: %s", exc)
        # attach real sentiment (was hallucinated)
        try:
            ctx["sentiment"] = _get_symbol_sentiment(symbol)
        except Exception:  # noqa: BLE001
            pass
        return ctx

    # Run AI analysis (with indicator context) + ML prediction concurrently
    async def _ai():
        context = await _build_context()
        return await asyncio.to_thread(
            ai_service.analyze, symbol, provider, context
        )

    async def _ml():
        try:
            rates = await asyncio.to_thread(mt5_candles, symbol, "H1", 200)
            if rates:
                import pandas as pd
                # predict() is CPU-bound — run in thread
                return await asyncio.to_thread(
                    ml_model.predict, pd.DataFrame(rates), symbol
                )
        except Exception as exc:  # noqa: BLE001
            log.debug("ml predict skipped: %s", exc)
        return None

    result, ml_pred = await asyncio.gather(_ai(), _ml())
    if ml_pred:
        result["ml_prediction"] = ml_pred
    return {"analysis": result, "demo": result.get("provider") == "heuristic"}


@app.get("/api/trading/analysis/batch")
async def api_analysis_batch(symbols: str, provider: str = "zai"):
    """Batch analysis for multiple symbols in one request.

    Runs all pair analyses concurrently — reduces 5 round-trips to 1 for the
    multi-pair signal matrix. Returns {results: {symbol: analysis}}.
    Builds indicator context for each symbol (was empty — signals were
    hallucinated from symbol name only).
    """
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()][:10]

    async def _build_ctx(sym: str) -> dict:
        """Build indicator + sentiment context for a symbol."""
        ctx = {"timeframe": "M15", "symbol": sym}
        try:
            rates = await asyncio.to_thread(mt5_candles, sym, "M15", 100)
            if rates:
                import pandas as pd
                from indicators import compute
                df = pd.DataFrame(rates)
                top10 = ["ema", "rsi", "macd", "atr", "bbands", "vwap",
                         "stochastic", "supertrend", "psar", "cci"]
                results = compute(df, top10)
                readings = {}
                for k, v in results.items():
                    if isinstance(v, list) and v:
                        readings[k] = round(v[-1], 5) if isinstance(v[-1], (int, float)) else None
                    elif isinstance(v, (int, float)):
                        readings[k] = round(v, 5)
                ctx["indicators"] = readings
                ctx["current_price"] = rates[-1]["close"]
                ctx["recent_high"] = max(r["high"] for r in rates[-20:])
                ctx["recent_low"] = min(r["low"] for r in rates[-20:])
        except Exception as exc:  # noqa: BLE001
            log.debug("batch context build failed for %s: %s", sym, exc)
        # attach sentiment
        try:
            ctx["sentiment"] = _get_symbol_sentiment(sym)
        except Exception:  # noqa: BLE001
            pass
        return ctx

    async def _analyze_one(sym: str):
        try:
            context = await _build_ctx(sym)
            ai_result, ml_pred = await asyncio.gather(
                asyncio.to_thread(ai_service.analyze, sym, provider, context),
                _ml_for_symbol(sym),
            )
            if ml_pred:
                ai_result["ml_prediction"] = ml_pred
            return sym, ai_result
        except Exception as exc:  # noqa: BLE001
            log.debug("batch analyze %s failed: %s", sym, exc)
            return sym, None

    async def _ml_for_symbol(sym: str):
        try:
            rates = await asyncio.to_thread(mt5_candles, sym, "H1", 200)
            if rates:
                import pandas as pd
                return await asyncio.to_thread(ml_model.predict, pd.DataFrame(rates), sym)
        except Exception:  # noqa: BLE001
            pass
        return None

    pairs = await asyncio.gather(*[_analyze_one(s) for s in sym_list])
    results = dict(pairs)
    return {"results": results, "provider": provider, "demo": False}


@app.get("/api/trading/ml/info")
async def api_ml_info():
    """Return real model metadata for the ML panel UI."""
    return ml_model.model_info()


@app.get("/api/trading/ai/config")
async def api_ai_config():
    """Return current AI provider config (models + confidence thresholds).
    Frontend reads this to sync its UI with backend state."""
    return {
        "models": {
            "zai": settings.zai_model,
            "groq": settings.groq_model,
            "google": settings.google_model,
            "local": settings.ollama_model,
        },
        "ai_min_confidence": settings.ai_min_confidence,
        "auto_trade_min_confidence": settings.auto_trade_min_confidence,
        "auto_trade_mode": settings.auto_trade_mode,
        "auto_trade_symbols": settings.auto_trade_symbols,
        "active_provider": getattr(settings, "ai_provider", "zai"),
        "api_keys_set": {
            "zai": bool(settings.zai_api_key),
            "groq": bool(settings.groq_api_key),
            "google": bool(settings.google_api_key),
            "local": True,
        },
    }


@app.post("/api/trading/ai/config")
@limiter.limit("5/minute")
async def api_ai_config_update(request: Request,
                               _auth=Depends(require_token)):
    """Update AI model config at runtime (no restart needed).

    Frontend sends {models: {zai: "glm-4.6", ...}, ai_min_confidence: 65, ...}
    and backend applies immediately to settings singleton.
    """
    import json as _json
    try:
        raw = await request.body()
        body = _json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001
        body = {}
    updated = []
    if "models" in body:
        models = body["models"]
        if "zai" in models:
            settings.zai_model = models["zai"]; updated.append(f"zai={models['zai']}")
        if "groq" in models:
            settings.groq_model = models["groq"]; updated.append(f"groq={models['groq']}")
        if "google" in models:
            settings.google_model = models["google"]; updated.append(f"google={models['google']}")
        if "local" in models:
            settings.ollama_model = models["local"]; updated.append(f"ollama={models['local']}")
    if "ai_min_confidence" in body:
        settings.ai_min_confidence = int(body["ai_min_confidence"])
        updated.append(f"ai_min_confidence={settings.ai_min_confidence}")
    if "auto_trade_min_confidence" in body:
        settings.auto_trade_min_confidence = int(body["auto_trade_min_confidence"])
        updated.append(f"auto_trade_min_confidence={settings.auto_trade_min_confidence}")
    if "active_provider" in body:
        settings.ai_provider = body["active_provider"]
        updated.append(f"provider={body['active_provider']}")
    if "auto_trade_mode" in body:
        settings.auto_trade_mode = bool(body["auto_trade_mode"])
        updated.append(f"auto_trade_mode={settings.auto_trade_mode}")
        log.info("🤖 auto-trade %s", "ENABLED" if settings.auto_trade_mode else "DISABLED")
    if "auto_trade_symbols" in body:
        settings.auto_trade_symbols = body["auto_trade_symbols"]
        updated.append(f"auto_trade_symbols={settings.auto_trade_symbols}")

    log.info("AI config updated: %s", ", ".join(updated))
    return {"ok": True, "updated": updated, "config": {
        "models": {
            "zai": settings.zai_model,
            "groq": settings.groq_model,
            "google": settings.google_model,
            "local": settings.ollama_model,
        },
        "ai_min_confidence": settings.ai_min_confidence,
        "auto_trade_min_confidence": settings.auto_trade_min_confidence,
    }}


@app.get("/api/trading/backtest")
async def api_backtest(symbol: str = "EURUSD", trades: int = 120):
    trades = max(10, min(trades, 500))
    return await asyncio.to_thread(bt.run, symbol=symbol, trades=trades)


@app.get("/api/trading/logs")
async def api_logs(level: str = "ALL", q: str | None = None):
    """Return logs from DB (persisted across restarts). Falls back to demo."""
    try:
        logs = get_logs(limit=200, level=level, q=q)
        return {"logs": logs, "demo": False}
    except Exception:  # noqa: BLE001
        return {"logs": [], "demo": True}


@app.get("/api/trading/trades")
async def api_trades():
    """Return trade history from DB."""
    try:
        trades = get_trades(limit=200)
        return {"trades": trades, "demo": False}
    except Exception:  # noqa: BLE001
        return {"trades": [], "demo": True}


@app.get("/api/trading/export")
async def api_export():
    """Export trades as CSV."""
    import csv as _csv
    import io as _io
    try:
        trades = get_trades(limit=1000)
        if not trades:
            return {"csv": "", "demo": True}
        output = _io.StringIO()
        writer = _csv.DictWriter(output, fieldnames=[
            "ticket", "symbol", "side", "volume", "open_price", "close_price",
            "pnl", "pips", "open_time", "close_time", "comment", "source"
        ])
        writer.writeheader()
        for t in trades:
            writer.writerow({k: t.get(k, "") for k in writer.fieldnames})
        return {"csv": output.getvalue(), "demo": False}
    except Exception as exc:  # noqa: BLE001
        log.warning("export failed: %s", exc)
        return {"csv": "", "demo": True}


# ---- New feature endpoints ----
from trading_analytics import (
    compute_strength, check_correlation_risk, parameter_sweep,
    create_journal_entry, analyze_order_flow,
)


@app.get("/api/trading/strength")
async def api_strength():
    """Currency strength meter — relative strength of 8 majors."""
    t = await asyncio.to_thread(mt5_ticks)
    if not t:
        return {"currencies": [], "demo": True}
    strengths = compute_strength(t)
    return {"currencies": strengths, "demo": False}


@app.get("/api/trading/correlation")
async def api_correlation():
    """Check correlation risk for open positions."""
    pos = await asyncio.to_thread(mt5_positions)
    open_symbols = [p["symbol"] for p in pos]
    has_risk, reason = check_correlation_risk(open_symbols)
    return {"has_risk": has_risk, "reason": reason, "open_symbols": open_symbols}


@app.get("/api/trading/sweep")
async def api_sweep(symbol: str = "EURUSD"):
    """Parameter sweep / grid search for optimal indicator params."""
    rates = await asyncio.to_thread(mt5_candles, symbol, "H1", 500)
    if not rates:
        return {"best_params": None, "demo": True}
    result = await asyncio.to_thread(parameter_sweep, symbol, rates)
    return {**result, "demo": False}


@app.get("/api/trading/journal/{ticket}")
async def api_journal(ticket: int):
    """Get trade journal entries for a ticket."""
    try:
        logs = get_logs(limit=50, q=f"#{ticket}")
        return {"entries": logs, "demo": False}
    except Exception:  # noqa: BLE001
        return {"entries": [], "demo": True}


@app.get("/api/trading/orderflow")
async def api_orderflow(symbol: str = "EURUSD"):
    """Order flow / volume profile analysis."""
    rates = await asyncio.to_thread(mt5_candles, symbol, "M15", 100)
    if not rates:
        return {"demo": True}
    result = await asyncio.to_thread(analyze_order_flow, rates, 50)
    return {**result, "demo": False, "symbol": symbol}


@app.get("/api/trading/tax-report")
async def api_tax_report(year: int | None = None):
    """Tax/performance report — summary of trades by year."""
    import datetime as _dt
    target_year = year or _dt.date.today().year
    try:
        trades = get_trades(limit=10000)
        year_trades = [t for t in trades if t.get("close_time") and
                       str(t.get("close_time", "")).startswith(str(target_year))]
        closed = [t for t in year_trades if t.get("pnl") is not None]
        total_pnl = sum(t.get("pnl", 0) for t in closed)
        wins = [t for t in closed if t.get("pnl", 0) > 0]
        losses = [t for t in closed if t.get("pnl", 0) < 0]
        total_volume = sum(t.get("volume", 0) for t in closed)
        return {
            "year": target_year,
            "total_trades": len(closed),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "total_pnl": round(total_pnl, 2),
            "total_volume": round(total_volume, 2),
            "avg_win": round(sum(t["pnl"] for t in wins) / len(wins), 2) if wins else 0,
            "avg_loss": round(sum(t["pnl"] for t in losses) / len(losses), 2) if losses else 0,
            "demo": False,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "demo": True}


@app.post("/api/trading/accounts/switch")
@limiter.limit("5/minute")
async def api_switch_account(request: Request,
                             _auth=Depends(require_token)):
    """Switch MT5 account (multi-account support)."""
    import json as _json
    try:
        raw = await request.body()
        body = _json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001
        body = {}
    login = body.get("login")
    password = body.get("password")
    server = body.get("server")
    if not all([login, password, server]):
        return {"ok": False, "error": "login, password, server required"}
    settings.mt5_login = int(login)
    settings.mt5_password = password
    settings.mt5_server = server
    r = connect()
    return r.__dict__


@app.post("/api/trading/alerts")
async def api_add_alert(body: AlertReq, _auth=Depends(require_token)):
    a = add_price_alert(body.symbol, body.condition, body.price)
    return {"alert": a}


@app.post("/api/trading/email/test")
@limiter.limit("3/minute")
async def api_email_test(request: Request, _auth=Depends(require_token)):
    ok = await send_email(
        "ZeniTrade test email",
        "<p>This is a test notification from ZeniTrade AI.</p>",
    )
    return {"ok": ok}


@app.post("/api/trading/ml/train")
@limiter.limit("1/hour")
async def api_ml_train(request: Request, symbol: str = "EURUSD", _auth=Depends(require_token)):
    await asyncio.to_thread(ml_model.train, symbol)
    return {"ok": True, "message": f"training complete on {symbol}"}


if __name__ == "__main__":
    import uvicorn
    # bind 127.0.0.1 by default for safety; override via HOST env for remote access
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
