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
│  │ MT5  ││Z.AI  ││XGBost││guard ││Finnhub││SQLite││SMTP││
│  │terminal││Groq ││ joblib││daily ││MarkT ││ WAL  ││TG  ││
│  │       ││Google││      ││loss  ││      ││      ││Disc││
│  │       ││Ollama││      ││      ││      ││      ││    ││
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
     - Provider cascade: Z.AI → Groq → Google → Ollama → heuristic
     - Prompt: formatted indicator values + sentiment + price
     - Returns: signal, confidence, entry/SL/TP, 7 dimensions
  3. ml_model.predict(df, symbol):
     - In-memory cached model (mtime-based invalidation)
     - Symbol guard (refuses wrong-symbol model)
     - Returns: direction, probability, drift score
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
  7. send_order() with spread filter (>5pips = reject)
     - Partial fill handling (DONE_PARTIAL = success)
     - Retcode mapping (human-readable errors)
  8. On success:
     - guard.register_open()
     - save_trade() to DB (retry + orphaned-trade alert)
     - notify_async() — email/Telegram/Discord
  9. _manage_positions_loop (5s) manages:
     - Break-even at +1R
     - Trailing (fixed or ATR-based)
     - Partial close at +1.5R
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

## Module Dependencies

```
main.py
  ├── mt5_service.py (ticks, candles, orders, SL/TP, pip value)
  ├── ai_service.py (4-provider cascade + heuristic)
  ├── ml_model.py (XGBoost + cache + drift + walk-forward)
  ├── risk_manager.py (guard, size_position, trail_stop, news blackout)
  ├── news_service.py (Finnhub + MARKETAUX + sentiment + calendar)
  ├── trading_analytics.py (strength, correlation, sweep, journal, flow)
  ├── db.py (SQLite: trades, alerts, logs, risk_state, ml_models)
  ├── notifier.py (email + Telegram + Discord, non-blocking)
  ├── indicators.py (30 indicators + compute + validation)
  ├── backtest.py (realistic: spread + slippage + commission + margin)
  └── config.py (Pydantic Settings, 44+ fields)
```

## Database Schema (SQLite)

```sql
trades        (ticket, symbol, side, volume, open_price, close_price,
               pnl, pips, open_time, close_time, comment, source)

alerts        (id, symbol, condition, price, active, triggered,
               created_at, triggered_at)

logs          (id, ts, level, source, message)
               -- INFO+ from zenitrade logger (trade lifecycle)
               -- WARNING+ from other loggers

risk_state    (date, daily_loss, open_count)
               -- persisted daily, restored on restart

ml_models     (id, version, symbol, train_acc, test_acc,
               trained_at, n_samples, path, drift_score, active)
```

## Background Loops

| Loop | Interval | Responsibility |
|------|----------|---------------|
| `_alert_loop` | 5s | Poll ticks, check price alerts, trigger emails |
| `_reconcile_loop` | 10s | Sync guard with broker positions + P&L |
| `_manage_positions_loop` | 5s | Trailing stop, break-even, partial close |
| `_auto_trade_loop` | 30s | Execute AI signals (confidence ≥75%, cooldown 60s) |
| `_cleanup_loop` | 1h | Prune old DB rows (5000 logs, 10000 trades) |

All loops use `asyncio.to_thread()` for MT5 calls (non-blocking). All loops are cancelled on shutdown via lifespan.

## Frontend Architecture

### State Management
- **Zustand** (persist) — trading config (symbols, timeframes, indicators, AI provider, risk params, density). Persists to localStorage `zenitrade-store`.
- **TanStack Query** — server state (ticks, positions, analysis, news, logs, trades, status). Polling intervals: ticks 2.5s, positions 5s, status 10s, candles 15s, news 60s.

### Code Splitting
All 11 views loaded via `next/dynamic` with `ViewSkeleton` fallback. Initial bundle only includes dashboard + ticker tape + session clock.

### Density System
`<html data-density="compact|dense|minimal">` — scales root font-size (13.5/15/17px) + padding/gap/radius via unlayered CSS.
