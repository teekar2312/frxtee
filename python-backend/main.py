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
from mt5_service import get_pip_value_per_lot, get_recent_deals
from news_service import economic_calendar, fetch_news
from risk_manager import guard, size_position, near_high_impact_news
import ai_service
import backtest as bt
import ml_model
from notifier import add_price_alert, check_alerts, send_email
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
    """Write WARNING+ log records to the SQLite logs table."""
    def emit(self, record):
        try:
            add_log(record.levelname, record.name, record.getMessage())
        except Exception:  # noqa: BLE001
            pass  # never let logging crash the app

# attach DB handler to root logger (WARNING+ only to avoid spam)
_db_handler = DBLogHandler(level=logging.WARNING)
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _alert_task, _reconcile_task, _cleanup_task
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
                        await send_email(
                            f"⚠ CRITICAL: Orphaned trade #{ticket}",
                            f"<p>Order was filled on MT5 but DB persistence failed.</p>"
                            f"<p>Ticket: {ticket}<br>Symbol: {body.symbol}<br>"
                            f"Side: {body.side}<br>Volume: {volume} lot<br>"
                            f"Price: {r.get('price')}</p>"
                            f"<p>Error: {exc}</p>"
                            f"<p><b>Manual reconciliation required.</b></p>",
                        )
            await send_email(
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
    r = await asyncio.to_thread(close_position, ticket)
    if r.get("ok"):
        # persist closed trade + register realized P&L for daily risk
        pnl = r.get("pnl", 0.0)
        try:
            close_trade(ticket, r.get("price", 0), pnl, r.get("pips", 0))
        except Exception:  # noqa: BLE001
            pass
        guard.register_close(pnl)
    return r


@app.get("/api/trading/news")
async def api_news():
    # fetch news + calendar concurrently (were sequential)
    n, cal = await asyncio.gather(fetch_news(), economic_calendar())
    return {"news": n, "calendar": cal, "demo": not n}


@app.get("/api/trading/analysis")
async def api_analysis(symbol: str = "EURUSD", provider: str = "zai"):
    # Run AI analysis + ML prediction concurrently (independent computations)
    async def _ai():
        return await asyncio.to_thread(
            ai_service.analyze, symbol, provider, {"timeframe": "M15"}
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
    """
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()][:10]  # cap at 10

    async def _analyze_one(sym: str):
        try:
            ai_result, ml_pred = await asyncio.gather(
                asyncio.to_thread(ai_service.analyze, sym, provider, {"timeframe": "M15"}),
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
    return {"results": results, "provider": provider, "demo": True}


@app.get("/api/trading/ml/info")
async def api_ml_info():
    """Return real model metadata for the ML panel UI."""
    return ml_model.model_info()


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
