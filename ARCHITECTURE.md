# Architecture — ZeniTrade AI

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (User)                         │
│  Next.js Dashboard (:3000)                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │Dashboard │ │ Trading  │ │AI Engine │ │ Strategy  │  │
│  │  View    │ │  View    │ │  View    │ │ Builder   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
│       │             │            │              │        │
│       └─────────────┴────────────┴──────────────┘        │
│                     TanStack Query                       │
│              (polling 2.5s–60s + AbortSignal)            │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP (relative URLs)
                         ▼
┌─────────────────────────────────────────────────────────┐
│              Next.js API Routes (:3000)                   │
│  /api/trading/ticks    /api/trading/order               │
│  /api/trading/candles  /api/trading/positions/[ticket]  │
│  /api/trading/analysis /api/trading/alerts              │
│  /api/trading/news     /api/trading/email/test          │
│  /api/trading/status   /api/trading/ml/train            │
│  /api/trading/trades   /api/trading/export               │
│  /api/trading/strength /api/trading/correlation         │
│  /api/trading/sweep    /api/trading/orderflow           │
│  /api/trading/tax-report                                 │
│                                                          │
│  proxyBackend() — try Python backend → demo fallback    │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP (with X-API-Token)
                         ▼
┌─────────────────────────────────────────────────────────┐
│           Python FastAPI Backend (:8000)                  │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │              main.py (FastAPI)                    │    │
│  │  Auth · Rate Limit · CORS · Lifespan             │    │
│  │  25+ endpoints (all under /api/trading/)          │    │
│  └──┬──────┬──────┬──────┬──────┬──────┬──────┬────┘    │
│     │      │      │      │      │      │      │          │
│     ▼      ▼      ▼      ▼      ▼      ▼      ▼          │
│  ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌────┐│
│  │ mt5  ││ ai   ││ ml   ││ risk ││ news ││  db  ││noti││
│  │ svc  ││ svc  ││ model││ mgr  ││ svc  ││      ││fier││
│  └──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└─┬──┘│
│     │       │       │       │       │       │      │    │
│     ▼       ▼       ▼       ▼       ▼       ▼      ▼    │
│  ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌───┐│
│  │ MT5  ││ AI   ││ ML   ││ risk ││ news ││  db  ││noti││
│  │terml ││ svc  ││model ││ mgr  ││ svc  ││      ││fier││
│  └──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└─┬──┘│
│     │       │       │       │       │       │      │    │
│     ▼       ▼       ▼       ▼       ▼       ▼      ▼    │
│  ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌───┐│
│  │ MT5  ││Groq  ││XGBst ││guard ││Apify ││SQLite││SMTP││
│  │terml ││ cloud││joblib││daily ││ Forex││ WAL  ││TG  ││
│  │      ││Local ││per-  ││loss  ││Fctry ││      ││Disc││
│  │      ││Ollama││symbol││      ││+Fin- ││      ││    │
│  │      ││      ││      ││      ││nhub  ││      ││    │
│  └──────┘└──────┘└──────┘└──────┘└──────┘└──────┘└───┘│
│                                                          │
│  Background Loops (asyncio):                             │
│  ├── _alert_loop (5s) — check price alerts              │
│  ├── _reconcile_loop (10s) — sync positions + P&L        │
│  ├── _manage_positions_loop (5s) — trailing + BE         │
│  ├── _auto_trade_loop (30s) — AI signal execution        │
│  └── _cleanup_loop (1h) — DB retention                   │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼ (optional)
┌─────────────────────────────────────────────────────────┐
│           WebSocket Pusher (:3003)                        │
│  Socket.io — pushes ticks/positions/alerts <50ms        │
│  Frontend connects via io("/?XTransformPort=3003")      │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

### Tick Data (real-time)
```
MT5 terminal → mt5_service.ticks() → /api/trading/ticks → Next.js proxy
  → TanStack Query (2.5s poll) → Dashboard ticker tape + chart
  → (optional) ws-pusher → socket.io → <50ms push
```

### AI Analysis (on-demand)
```
User clicks "Re-analyze" or auto-trade triggers:
  1. /analysis endpoint builds context:
     - Fetch M15 candles (100 bars)
     - Compute 10 indicators (EMA, RSI, MACD, ATR, BBands, VWAP, Stoch, Supertrend, PSAR, CCI)
     - Fetch aggregate sentiment (time-weighted, currency-filtered)
  2. ai_service.analyze(symbol, provider, context):
     - Provider cascade (only Groq + Local supported):
         provider=groq  → [groq, local]
         provider=local  → [local, groq]
       Each provider is tried in order; on failure (timeout, OOM, no key),
       the next is tried. If both fail, a rule-based heuristic returns
       a NEUTRAL signal.
     - Local provider uses a lightweight prompt (top-5 indicators) with
       bounded context window (OLLAMA_NUM_CTX) + configurable timeout
       (OLLAMA_TIMEOUT) so a slow CPU model cleanly falls through to Groq.
     - Prompt: formatted indicator values + sentiment + price
     - Returns: signal, confidence, entry/SL/TP, 7 dimensions
  3. ml_model.predict(df, symbol):
     - Loads per-symbol model file: models/trade_classifier_{symbol}.joblib
     - Per-symbol in-memory cache (mtime-based invalidation)
     - Symbol guard (refuses to predict a symbol the model wasn't trained on)
     - Returns: direction, probability, drift score (per-symbol tracking)
  4. Response: { analysis, ml_prediction, demo }
```

### Order Execution
```
User clicks BUY/SELL or auto-trade:
  1. POST /api/trading/order
  2. _order_lock (asyncio.Lock — race protection)
  3. guard.can_open(equity):
     - Daily risk check (persisted to DB)
     - Margin level check (>60%)
     - Drawdown check (<10%)
     - Weekend gap check
     - News blackout check (±15min)
  4. get_pip_value_per_lot(symbol) — dynamic, from trade_tick_value
  5. size_position(equity, sl_pips, pip_value) — accurate lot sizing
  6. Volume clamp [0.01, 50]
  7. send_order() with spread filter (>5pips = reject):
     - Stop-level clamp (broker min distance — eff_sl/tp adjusted if too tight)
     - Partial fill handling (DONE_PARTIAL = success)
     - Retcode mapping (human-readable errors)
     - Position ticket vs order ticket FIX:
         r.order is the ORDER ticket, but positions_get(ticket=r.order)
         works because MT5 maps order→position. We re-fetch the actual
         position_id from positions_get so DB rows match what
         close_position(ticket) will be called with later.
     - send_order() ALWAYS returns the intended sl/tp (sl_rounded, tp_rounded)
       so callers can persist them to DB as a fallback — even if the broker
       silently drops them because stops were too close.
  8. On success:
     - guard.register_open()
     - save_trade() to DB (retry + orphaned-trade alert) — stores intended
       SL/TP for the DB-fallback in manage loop
     - notify_async() — email/Telegram/Discord
  9. _manage_positions_loop (5s) manages:
     - DB fallback for SL/TP (when broker_sl==0 or broker_tp==0):
         get_open_trade_sl_tp(ticket) returns the intended levels we saved
         at order time. Root-cause fix for "positions stay open at SL/TP".
     - Manual SL/TP hit close (backup for broker-side execution)
     - Break-even at +1R
     - Trailing (fixed or ATR-based)
     - Partial close at +1.5R
```

### Trade Close & Deal History
```
User clicks CLOSE or manage loop detects SL/TP hit:
  1. POST /api/trading/positions/{ticket}  (or close_position(ticket))
  2. If the position still exists in MT5 — normal close path.
  3. If positions_get(ticket) returns None — the broker already closed it
     (SL/TP triggered broker-side). We then call _fetch_deal_by_ticket(ticket)
     to fetch the ACTUAL close price, profit, and pips from deal history
     (was returning zeros → trade history showed empty close_price/pnl/pips).
  4. guard.register_close(pnl) + close_trade() to DB with real values.
  5. On backend startup, _backfill_closed_trades() syncs trades that closed
     while the backend was offline by querying get_recent_deals(24h) and
     matching tickets — closes orphaned DB rows with real deal data.
```

### Risk State Persistence
```
guard.__init__ → _restore() → DB load_risk_state()
  → daily_loss + open_count restored from SQLite

guard._maybe_reset() → checks date rollover → _persist() to DB

guard.register_close(pnl):
  → open_count--
  → if pnl < 0: daily_loss += |pnl|
  → _persist() to DB

_reconcile_loop (10s):
  → mt5.positions_get() — real broker positions
  → get_recent_deals(15min) — closed deal history
  → For each unprocessed deal:
    - register_close(pnl) — updates daily_loss
    - close_trade() — persists to DB
  → guard.open_count = real_count (corrects drift)
```

### Economic Calendar
```
economic_calendar() (cached 6h — _CAL_CACHE_TTL=21600s):
  1. Cache hit? (calendar != None AND now - cal_ts < 6h) → return cached
  2. Acquire async lock (prevent thundering herd on cache miss)
  3. Try Apify (ForexFactory scraper actor):
     - POST https://api.apify.com/v2/acts/scrapemint~forexfactory-
       economic-calendar/run-sync-get-dataset-items?token=APIFY_TOKEN
     - On success → cache 6h, return
  4. Fallback: Finnhub /calendar/economic (paid plan only — free returns 403)
     - 403 uses a SEPARATE backoff key (finnhub_403_until = +1h) so it
       doesn't poison the calendar cache → Apify is retried on next miss
  5. Last resort: empty calendar (no demo events) — forces users to set
     APIFY_TOKEN for real news filtering

near_high_impact_news(minutes=15):
  - Returns True if any high-impact event is ±15min from now
  - Used by order() and _auto_trade_loop() to block entries
```

### Session Management
```
is_in_active_session(now) — DST-aware session windows:
  Sessions: sydney, tokyo, london, newyork
  Overlap sessions (active when both underlying sessions are open):
    overlap_tl  = Tokyo × London (~07-09 UTC summer / 08-09 winter)
    overlap_ln  = London × New York (~12-16 UTC summer / 13-17 winter)
  ACTIVE_SESSIONS is comma-separated; empty = trade all sessions.

Close-at-session-end detection (in _manage_positions_loop):
  Tracks _prev_in_session (None initially). On each cycle:
    now_in = is_in_active_session(now_utc)
    If _prev_in_session was True AND now_in is False → session just ended.
      If CLOSE_AT_SESSION_END=true → force-close ALL positions, fire
        "🔚 Session ended" notification, reset _be_applied/_partial_applied.
      Else → log "keeping positions open".
    _prev_in_session = now_in  # update for next cycle
```

### Auto-Trade Loop Safety
```
_auto_trade_loop (30s) — when auto_trade_mode=True:
  For each symbol in auto_trade_symbols:
    - Cooldown check (60s between signals per symbol)
    - Build context (candles + indicators + sentiment)
    - ai_service.analyze() — provider cascade (groq → local → heuristic)
    - Skip if heuristic fallback (NEUTRAL) — AI failed
    - Strategy evaluation (if trading_strategy != "auto"):
        evaluate_strategy() may OVERRIDE AI signal + provide SL/TP price
        levels → converted to pips via _pip_for_digits(symbol) and used
        as eff_sl_pips / eff_tp_pips (was previously dead code — overrides
        were extracted but never passed to send_order).
    - Risk guard check (guard.can_open)
    - News filter check (near_high_impact_news(15min)):
        Wrapped in asyncio.to_thread because economic_calendar() may do
        HTTP fetch. Without this the loop would hold _order_lock for 60s.
        Bypassed in a previous version — caused 30-50 pip NFP/FOMC spike risk.
    - Position sizing via size_position(equity, eff_sl_pips, pip_value)
    - send_order() with eff_sl_pips + eff_tp_pips

  Circuit breaker:
    _auto_trade_fail_count tracks consecutive send_order failures.
    On success → reset to 0.
    On failure → increment. If >= 3 (=_AUTO_TRADE_MAX_FAILS):
      - settings.auto_trade_mode = False (auto-disable)
      - Notify via all channels
      - Reset counter for next manual enable
    Prevents runaway order spam when MT5 connection or broker errors occur.
```

## Module Dependencies

```
main.py
  ├── mt5_service.py (ticks, candles, orders, SL/TP, pip value, _fetch_deal_by_ticket)
  ├── ai_service.py (Groq + Local Ollama cascade + heuristic fallback)
  ├── ml_model.py (XGBoost, per-symbol files + cache + drift + walk-forward)
  ├── risk_manager.py (guard, size_position, trail_stop, news blackout, sessions)
  ├── news_service.py (Apify calendar primary + Finnhub fallback + MARKETAUX + sentiment)
  ├── trading_strategies.py (8 strategies: ma_ribbon, momentum_scalp, etc.)
  ├── trading_analytics.py (strength, correlation, sweep, journal, flow)
  ├── db.py (SQLite: trades, alerts, logs, risk_state, ml_models — + sl/tp fallback helpers)
  ├── notifier.py (email + Telegram + Discord, non-blocking)
  ├── indicators.py (30 indicators + compute + validation)
  ├── backtest.py (realistic: spread + slippage + commission + margin)
  └── config.py (Pydantic Settings — Groq + Ollama only, no Z.AI/Google/OpenRouter)
```

## Database Schema (SQLite)

```sql
trades        (ticket, symbol, side, volume, open_price, close_price,
               pnl, pips, open_time, close_time, comment, source,
               sl, tp)            -- intended SL/TP saved at order time
                                   -- used as fallback when broker drops them

alerts        (id, symbol, condition, price, active, triggered,
               created_at, triggered_at)

logs          (id, ts, level, source, message)
               -- INFO+ from zenitrade logger (trade lifecycle)
               -- WARNING+ from other loggers

risk_state    (date, daily_loss, open_count)
               -- persisted daily, restored on restart

ml_models     (id, version, symbol, train_acc, test_acc,
               trained_at, n_samples, path, drift_score, active)
               -- one row per trained model; path points to
               -- models/trade_classifier_{symbol}.joblib
```

## Background Loops

| Loop | Interval | Responsibility |
|------|----------|---------------|
| `_alert_loop` | 5s | Poll ticks, check price alerts, trigger emails |
| `_reconcile_loop` | 10s | Sync guard with broker positions + P&L |
| `_manage_positions_loop` | 5s | Trailing stop, break-even, partial close, manual SL/TP close, session-end close |
| `_auto_trade_loop` | 30s | Execute AI signals (confidence ≥75%, cooldown 60s) |
| `_cleanup_loop` | 1h | Prune old DB rows (5000 logs, 10000 trades) |

All loops use `asyncio.to_thread()` for MT5 calls (non-blocking). All loops are cancelled on shutdown via lifespan.

On startup (lifespan), `_backfill_closed_trades()` runs once to sync the DB
with broker state: it loads all open trades from the DB, fetches current
MT5 positions, and for any DB trade whose ticket is no longer open in
MT5, fetches the close deal from `get_recent_deals(24h)` and writes the
real close_price/pnl/pips back into the trades row. This prevents the
trade history from showing zeros for trades that closed broker-side
while the backend was offline.

The manage-positions loop polls faster (2s instead of 5s) when positions
are open, so SL/TP spikes are caught quickly.

## Frontend Architecture

### State Management
- **Zustand** (persist) — trading config (symbols, timeframes, indicators, AI provider, risk params, density). Persists to localStorage `zenitrade-store`.
- **TanStack Query** — server state (ticks, positions, analysis, news, logs, trades, status). Polling intervals: ticks 2.5s, positions 5s, status 10s, candles 15s, news 60s.

### Code Splitting
All 11 views loaded via `next/dynamic` with `ViewSkeleton` fallback. Initial bundle only includes dashboard + ticker tape + session clock.

### Density System
`<html data-density="compact|dense|minimal">` — scales root font-size (13.5/15/17px) + padding/gap/radius via unlayered CSS.
