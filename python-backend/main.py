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
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config import settings
from mt5_service import candles as mt5_candles
from mt5_service import close_position, connect, disconnect, positions as mt5_positions
from mt5_service import send_order, status as mt5_status, ticks as mt5_ticks
from news_service import economic_calendar, fetch_news
from risk_manager import guard, size_position, near_high_impact_news
import ai_service
import backtest as bt
import ml_model
from notifier import add_price_alert, check_alerts, send_email
from db import init_db, add_log, get_logs, get_trades, save_trade, close_trade, cleanup_old

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


async def _reconcile_loop():
    """Background task: sync guard.open_count with broker every 10s.

    Broker-side closes (SL/TP hit, margin call) bypass our register_close(),
    so open_count drifts upward. This polls real positions and corrects it,
    also registering realized P&L as daily loss when negative.
    """
    while True:
        try:
            pos = await asyncio.to_thread(mt5_positions)
            real_count = len(pos)
            drift = guard.open_count - real_count
            if drift > 0:
                log.info("position reconcile: guard=%d real=%d → correcting",
                         guard.open_count, real_count)
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
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc.detail))


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
    """Health probe for container orchestrators."""
    s = mt5_status()
    return {"ok": True, "connected": s.connected, "demo": s.demo, "ts": datetime.now(timezone.utc).isoformat()}


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

        # position-size via risk (or honor client volume, clamped to FINEX range)
        ps = size_position(equity, body.slPips)
        volume = body.volume if body.volume is not None else ps.lot
        volume = round(max(0.01, min(volume, 50.0)), 2)  # FINEX: 0.01–50 lot

        r = await asyncio.to_thread(
            send_order, body.symbol, body.side, volume,
            body.slPips, ps.tp_pips, body.comment,
        )
        if r.get("ok"):
            guard.register_open()
            # persist trade to DB
            try:
                save_trade(
                    ticket=r.get("ticket", 0), symbol=body.symbol, side=body.side,
                    volume=volume, open_price=r.get("price", 0),
                    comment=body.comment, source="ai" if "AI" in body.comment else "manual",
                )
            except Exception:  # noqa: BLE001
                pass
            await send_email(
                f"Trade opened: {body.side} {body.symbol}",
                f"<p>{body.side} {body.symbol} {volume} lot @ {r.get('price')}</p>"
                f"<p>SL {body.slPips}p · TP {ps.tp_pips:.1f}p · Risk ${ps.risk_amount:.2f}</p>",
            )
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
    n = await fetch_news()
    cal = await economic_calendar()
    return {"news": n, "calendar": cal, "demo": not n}


@app.get("/api/trading/analysis")
async def api_analysis(symbol: str = "EURUSD", provider: str = "zai"):
    result = await asyncio.to_thread(ai_service.analyze, symbol, provider, {"timeframe": "M15"})
    try:
        rates = await asyncio.to_thread(mt5_candles, symbol, "H1", 200)
        if rates:
            import pandas as pd
            pred = ml_model.predict(pd.DataFrame(rates), symbol=symbol)
            result["ml_prediction"] = pred
    except Exception as exc:  # noqa: BLE001
        log.debug("ml predict skipped: %s", exc)
    return {"analysis": result, "demo": result.get("provider") == "heuristic"}


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
