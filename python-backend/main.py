"""ZeniTrade AI — FastAPI application.

Routes mirror the Next.js dashboard's `/api/trading/*` contract so the
frontend can proxy to this backend seamlessly.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from mt5_service import candles as mt5_candles
from mt5_service import close_position, connect, disconnect, positions as mt5_positions
from mt5_service import send_order, status as mt5_status, ticks as mt5_ticks
from news_service import economic_calendar, fetch_news
from risk_manager import guard, size_position, trail_stop
import ai_service
import backtest as bt
import ml_model
from notifier import add_price_alert, check_alerts, send_email

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("zenitrade")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("ZeniTrade AI backend starting — FINEX / MT5 / AI")
    # connect to MT5 on boot (auto-launch if configured)
    try:
        connect()
    except Exception as exc:
        log.warning("MT5 connect on boot failed: %s", exc)
    # schedule nightly retrain
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        sched = AsyncIOScheduler()
        sched.add_job(ml_model.train, "cron", hour=2, minute=0)
        sched.start()
        app.state.scheduler = sched
    except Exception as exc:
        log.warning("scheduler init failed: %s", exc)
    yield
    try:
        disconnect()
    except Exception:
        pass


app = FastAPI(title="ZeniTrade AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"app": "ZeniTrade AI", "status": mt5_status().__dict__}


@app.get("/api/trading/status")
async def status():
    s = mt5_status()
    return s.__dict__


@app.post("/api/trading/connect")
async def api_connect(body: dict | None = None):
    body = body or {}
    # override settings if provided
    if body.get("login"):
        settings.mt5_login = int(body["login"])
    if body.get("server"):
        settings.mt5_server = body["server"]
    if body.get("terminal"):
        settings.mt5_terminal_path = body["terminal"]
    return connect().__dict__


@app.delete("/api/trading/connect")
async def api_disconnect():
    return disconnect().__dict__


@app.get("/api/trading/ticks")
async def api_ticks(symbols: str | None = None):
    syms = symbols.split(",") if symbols else None
    t = mt5_ticks(syms)
    return {"ts": int(asyncio.get_event_loop().time() * 1000), "ticks": t, "demo": not t}


@app.get("/api/trading/candles")
async def api_candles(symbol: str = "EURUSD", tf: str = "M15", count: int = 120):
    c = mt5_candles(symbol, tf, count)
    return {"symbol": symbol, "tf": tf, "candles": c, "demo": not c}


@app.get("/api/trading/positions")
async def api_positions():
    p = mt5_positions()
    return {"positions": p, "demo": not p}


@app.post("/api/trading/order")
async def api_order(body: dict):
    equity = 10000.0
    if mt5_status().account:
        equity = mt5_status().account.get("equity", 10000.0)
    ok, msg = guard.can_open(equity)
    if not ok:
        return {"ok": False, "error": msg}
    ps = size_position(equity, int(body.get("slPips", 10)))
    r = send_order(
        body["symbol"], body["side"], ps.lot,
        int(body.get("slPips", 10)), ps.tp_pips, body.get("comment", "AI:auto"),
    )
    if r.get("ok"):
        guard.register_open()
        await send_email(
            f"Trade opened: {body['side']} {body['symbol']}",
            f"<p>{body['side']} {body['symbol']} {ps.lot} lot @ {r.get('price')}</p>"
            f"<p>SL {ps.sl_pips}p · TP {ps.tp_pips}p · Risk ${ps.risk_amount:.2f}</p>",
        )
    return r


@app.delete("/api/trading/positions/{ticket}")
async def api_close(ticket: int):
    r = close_position(ticket)
    if r.get("ok"):
        guard.register_close()
    return r


@app.get("/api/trading/news")
async def api_news():
    n = await fetch_news()
    cal = await economic_calendar()
    return {"news": n, "calendar": cal, "demo": not n}


@app.get("/api/trading/analysis")
async def api_analysis(symbol: str = "EURUSD", provider: str = "zai"):
    result = ai_service.analyze(symbol, provider, {"timeframe": "M15"})
    # attach ML prediction if model available
    try:
        rates = mt5_candles(symbol, "H1", 200)
        if rates:
            import pandas as pd
            pred = ml_model.predict(pd.DataFrame(rates))
            result["ml_prediction"] = pred
    except Exception as exc:
        log.debug("ml predict skipped: %s", exc)
    return {"analysis": result, "demo": result.get("provider") == "heuristic"}


@app.get("/api/trading/backtest")
async def api_backtest(symbol: str = "EURUSD", trades: int = 120):
    return bt.run(symbol=symbol, trades=trades)


@app.get("/api/trading/logs")
async def api_logs():
    # in production, read from a log handler / db
    return {"logs": [], "demo": True}


@app.post("/api/trading/alerts")
async def api_add_alert(body: dict):
    a = add_price_alert(body["symbol"], body["condition"], float(body["price"]))
    return {"alert": a}


@app.post("/api/trading/email/test")
async def api_email_test(body: dict | None = None):
    ok = await send_email(
        "ZeniTrade test email",
        "<p>This is a test notification from ZeniTrade AI.</p>",
    )
    return {"ok": ok}


@app.post("/api/trading/ml/train")
async def api_ml_train(symbol: str = "EURUSD"):
    ml_model.train(symbol)
    return {"ok": True, "message": "training complete"}


# background task: poll ticks & check alerts every 5s
async def _alert_loop():
    while True:
        try:
            t = mt5_ticks()
            if t:
                check_alerts(t)
        except Exception as exc:
            log.debug("alert loop: %s", exc)
        await asyncio.sleep(5)


@app.on_event("startup")
async def _start_alerts():
    asyncio.create_task(_alert_loop())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
