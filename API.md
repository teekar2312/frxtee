# API Reference — ZeniTrade AI

Base URL: `http://127.0.0.1:8000` (Python backend) or `http://localhost:3000/api/trading` (Next.js proxy)

## Authentication

All mutating endpoints (POST/DELETE) require `X-API-Token` header when `ZENITRADE_API_TOKEN` is set.

```http
X-API-Token: your-token-here
```

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `POST /order` | 10/minute |
| `DELETE /positions/{ticket}` | 10/minute |
| `POST /positions/{ticket}/modify` | 20/minute |
| `POST /positions/{ticket}/partial` | 10/minute |
| `POST /email/test` | 3/minute |
| `POST /ml/train` | 1/hour |
| `POST /accounts/switch` | 5/minute |

---

## Market Data

### GET /api/trading/ticks
Real-time price ticks for all or selected symbols.

**Query:** `?symbols=EURUSD,GBPUSD` (optional, defaults to all 14 pairs)

**Response:**
```json
{
  "ts": 1710000000000,
  "ticks": [
    {
      "symbol": "EURUSD",
      "bid": 1.08650,
      "ask": 1.08654,
      "spreadPips": 0.4,
      "changePct": 0.32,
      "digits": 5,
      "ts": 1710000000000
    }
  ],
  "demo": false
}
```

### GET /api/trading/candles
OHLCV candle data.

**Query:** `?symbol=EURUSD&tf=M15&count=120`

**Response:**
```json
{
  "symbol": "EURUSD",
  "tf": "M15",
  "candles": [
    { "time": 1710000000, "open": 1.0865, "high": 1.0868, "low": 1.0862, "close": 1.0866, "volume": 450 }
  ],
  "demo": false
}
```

### GET /api/trading/positions
Currently open positions from MT5.

Returns floating `pips` (P&L in pips), `slPips` and `tpPips` (distance from
entry to SL/TP in pips) for each position, so the frontend can render the
risk/reward badge without recomputing pip size per symbol.

**Response:**
```json
{
  "positions": [
    {
      "ticket": 5000001,
      "symbol": "EURUSD",
      "type": "BUY",
      "volume": 0.10,
      "openPrice": 1.08642,
      "currentPrice": 1.08656,
      "sl": 1.08542,
      "tp": 1.08792,
      "profit": 14.00,
      "pips": 1.4,
      "slPips": 10.0,
      "tpPips": 15.0,
      "openTime": "1710000000",
      "comment": "AI:auto"
    }
  ],
  "demo": false
}
```

---

## AI Analysis

### GET /api/trading/analysis
Single-pair AI analysis with indicator context + ML prediction.

**Query:** `?symbol=EURUSD&provider=groq`

Provider options: `groq` (cloud, default) or `local` (Ollama). If the
selected provider is unavailable (no API key / Ollama down), the cascade
falls through to the other configured provider, then to a rule-based
heuristic.

**Response:**
```json
{
  "analysis": {
    "symbol": "EURUSD",
    "signal": "STRONG BUY",
    "confidence": 77,
    "riskScore": 23,
    "summary": "Confluence of bullish momentum...",
    "dimensions": [
      { "id": "central_bank", "label": "Kebijakan Bank Sentral", "score": 75, "note": "..." }
    ],
    "suggestedEntry": 1.08669,
    "suggestedSL": 1.08569,
    "suggestedTP": 1.08819,
    "provider": "groq",
    "model": "llama-3.3-70b-versatile",
    "generatedAt": "2024-03-10T12:00:00Z",
    "ml_prediction": { "direction": "UP", "prob": 0.72, "drift": 0.03 }
  },
  "demo": false
}
```

### GET /api/trading/analysis/batch
Multi-pair analysis in one request (reduces 5 round-trips to 1).

**Query:** `?symbols=EURUSD,GBPUSD,USDJPY&provider=groq`

**Response:**
```json
{
  "results": {
    "EURUSD": { "signal": "STRONG BUY", "confidence": 77, ... },
    "GBPUSD": { "signal": "BUY", "confidence": 57, ... }
  },
  "provider": "groq",
  "demo": false
}
```

---

## Trading

### POST /api/trading/order
Place a market order with full safety enforcement.

**Request:**
```json
{
  "symbol": "EURUSD",
  "side": "BUY",
  "volume": 0.10,
  "slPips": 10,
  "tpPips": 15,
  "comment": "AI:auto"
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `symbol` | string | yes | e.g. `EURUSD` |
| `side` | string | yes | `BUY` \| `SELL` |
| `volume` | number | no | Lot size; auto-sized from `slPips` + risk % if omitted |
| `slPips` | number | yes | Stop-loss distance in pips |
| `tpPips` | number | no | Frontend-computed TP in pips (`slPips * rrRatio`). If omitted or `<= 0`, the backend falls back to `settings.rr_ratio * slPips`. |
| `comment` | string | no | Defaults to `AI:auto` |

The order ticket returned is the **position ticket** (not the MT5 order
ticket) — the backend resolves `r.order` → `position.ticket` so DB rows
match what `close_position(ticket)` expects later.

**Response (success):**
```json
{
  "ok": true,
  "ticket": 5001234,
  "price": 1.08650,
  "volume": 0.10,
  "partial": false
}
```

**Response (rejected):**
```json
{
  "ok": false,
  "error": "Daily risk limit reached (3.0%)"
}
```

### DELETE /api/trading/positions/{ticket}
Close a position at market price.

**Response:**
```json
{
  "ok": true,
  "price": 1.08656,
  "pnl": 14.00,
  "pips": 1.4
}
```

### POST /api/trading/positions/{ticket}/modify
Modify SL/TP (for trailing stop / break-even).

**Request:** `{"sl": 1.08600, "tp": null}`

### POST /api/trading/positions/{ticket}/partial
Partially close a position (scale-out).

**Request:** `{"volume": 0.05}`

---

## Risk & Analytics

### GET /api/trading/status
MT5 connection status + account info.

### GET /api/trading/strength
Currency strength meter — 8 major currencies ranked.

### GET /api/trading/correlation
Check correlation risk for open positions.

### GET /api/trading/sweep?symbol=EURUSD
Parameter grid search (EMA × RSI combinations).

### GET /api/trading/orderflow?symbol=EURUSD
Order flow analysis — POC, value area, volume trend.

### GET /api/trading/tax-report?year=2024
Yearly tax/performance summary.

---

## News & Sentiment

### GET /api/trading/news
News feed + economic calendar + aggregate sentiment.

The economic calendar is fetched via **Apify** (ForexFactory scraper) as
primary source and **Finnhub** `/calendar/economic` as fallback. Calendar
results are cached for **6 hours** (`_CAL_CACHE_TTL = 21600s`) since the
schedule changes slowly. Finnhub 403s (free plan) use a separate 1-hour
backoff so they don't poison the calendar cache — Apify is retried on
the next cache miss.

### GET /api/trading/calendar/test
Diagnostic endpoint — checks Apify + Finnhub calendar connectivity.
Use to debug `Finnhub 403` errors and verify `APIFY_TOKEN` is wired up.

**Response:**
```json
{
  "apify_token_set": true,
  "apify_token_preview": "abc123...wxyz",
  "finnhub_key_set": true,
  "apify_result": {
    "ok": true,
    "events": 42,
    "sample": [{ "time": "2024-03-13T13:30:00Z", "currency": "USD", "impact": "high", "title": "CPI m/m" }]
  },
  "finnhub_result": "will return 403 on free plan (expected)"
}
```

### GET /api/trading/sentiment?symbol=EURUSD
Aggregate sentiment filtered by symbol's currencies.

---

## ML Model

### GET /api/trading/ml/info
Model metadata (version, accuracy, drift, trained_at).

**Query:** `?symbol=EURUSD` (optional)

- With `symbol`: returns metadata for that symbol's model file
  (`models/trade_classifier_{symbol}.joblib`) only.
- Without `symbol`: returns aggregated info with a `models` dict keyed by
  symbol — one entry per trained model on disk.

**Response (no symbol):**
```json
{
  "exists": true,
  "version": "v1.0",
  "symbol": "EURUSD",
  "train_acc": 0.71,
  "test_acc": 0.66,
  "trained_at": "2024-03-10T12:00:00Z",
  "drift": 0.03,
  "models": {
    "EURUSD": { "train_acc": 0.71, "test_acc": 0.66, "drift": 0.03, "trained_at": "..." },
    "GBPUSD": { "train_acc": 0.68, "test_acc": 0.63, "drift": 0.05, "trained_at": "..." }
  }
}
```

### POST /api/trading/ml/train?symbol=EURUSD&tf=H1&count=10000
Trigger model retraining (walk-forward + class balancing). Each symbol
gets its own file at `models/trade_classifier_{symbol}.joblib`.

**Query params:**

| Param | Default | Range | Notes |
|-------|---------|-------|-------|
| `symbol` | `EURUSD` | any traded pair | e.g. `EURUSD`, `GBPUSD`, `XAUUSD` |
| `tf` | `H1` | `M5`,`M15`,`M30`,`H1`,`H4`,`D1` | Training timeframe |
| `count` | `3000` | `200`–`10000` | Candles to fetch; more = less overfitting but slower |

Rate limited to 3/hour. Returns immediately with `demo: true` if MT5 is
not connected (cannot fetch candle data).

**Response (success):**
```json
{ "ok": true, "message": "training complete on EURUSD H1 (10000 bars)" }
```

---

## AI Config

### GET /api/trading/ai/config
Return current AI provider config. Frontend reads this to sync its UI
with backend state.

Only `groq` (cloud) and `local` (Ollama) providers are supported.

**Response:**
```json
{
  "models": {
    "groq": "llama-3.3-70b-versatile",
    "local": "llama3"
  },
  "ollama_num_ctx": 4096,
  "ollama_timeout": 120,
  "ai_min_confidence": 60,
  "auto_trade_min_confidence": 75,
  "auto_trade_mode": false,
  "auto_trade_symbols": "EURUSD,GBPUSD",
  "active_sessions": "london,newyork",
  "close_at_session_end": false,
  "trading_strategy": "auto",
  "strategies": { ... },
  "active_provider": "groq",
  "api_keys_set": {
    "groq": true,
    "local": true
  }
}
```

### POST /api/trading/ai/config
Update AI model config at runtime (no restart needed). Body is a partial
subset of the GET response — only the fields you want to change. Rate
limited to 10/minute.

---

## System

### GET /health
Deep health check (MT5 + DB + scheduler + background loops).

### GET /metrics
Prometheus-style metrics (positions, loss, trade count, loop liveness).

### GET /api/trading/trades
Trade history from DB. On backend startup, `_backfill_closed_trades()`
syncs trades that closed broker-side while the backend was offline by
querying `mt5.get_recent_deals()` for the last 24h and matching tickets.

### GET /api/trading/export
CSV export of all trades.

### GET /api/trading/logs
System logs from DB (filterable by level + search).

### POST /api/trading/connect
Connect to MT5 (auto-launch terminal).

### POST /api/trading/accounts/switch
Switch MT5 account (multi-account support).

### POST /api/trading/alerts
Create price alert.

### POST /api/trading/email/test
Send test email notification.

---

## Configuration

All settings are loaded from environment variables (or `.env`) via
Pydantic `BaseSettings` in `config.py`. Only Groq (cloud) and Local
(Ollama) AI providers are supported.

### AI providers

| Env var | Default | Description |
|---------|---------|-------------|
| `GROQ_API_KEY` | `""` | Groq cloud API key. Required for `provider=groq`. |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model id. |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Local Ollama server URL. |
| `OLLAMA_MODEL` | `llama3` | Ollama model id (use `llama3` or `llama3.2` on CPU). |
| `OLLAMA_NUM_CTX` | `4096` | Ollama context window size in tokens. Lower if OOM. |
| `OLLAMA_TIMEOUT` | `120` | Ollama request timeout in seconds. |
| `AI_PROVIDER` | `groq` | Active provider for the analysis endpoint. |
| `AI_MIN_CONFIDENCE` | `60` | Reject signals below this confidence (0-100). |
| `AUTO_TRADE_MIN_CONFIDENCE` | `75` | Higher threshold for auto-execution. |

### News / economic calendar

| Env var | Default | Description |
|---------|---------|-------------|
| `APIFY_TOKEN` | `""` | Apify token for ForexFactory calendar scraper. Primary calendar source. |
| `FINNHUB_API_KEY` | `""` | Finnhub API key. Used for news headlines + calendar fallback (paid plan only for calendar). |
| `MARKETAUX_API_KEY` | `""` | Marketaux API key for news headlines. |
| `AVOID_HIGH_IMPACT_NEWS` | `true` | Block new orders within ±15min of high-impact events. |

### MT5 / broker

| Env var | Default | Description |
|---------|---------|-------------|
| `MT5_LOGIN` | `0` | MT5 login id. |
| `MT5_PASSWORD` | `""` | MT5 password. |
| `MT5_SERVER` | `FINEX-Real` | MT5 server. |
| `MT5_TERMINAL_PATH` | `C:\Program Files\FINEX MetaTrader 5\terminal64.exe` | Path to terminal64.exe. |
| `MT5_AUTO_LAUNCH` | `true` | Auto-launch terminal if not running. |
| `MT5_ACCOUNTS` | `""` | Multi-account list `login:password:server,...`. |

### Risk / money management

| Env var | Default | Description |
|---------|---------|-------------|
| `RISK_PER_TRADE_PCT` | `1.0` | % of equity risked per trade (used for sizing). |
| `STOP_LOSS_PIPS` | `10` | Default SL distance in pips. |
| `RR_RATIO` | `1.5` | Default risk:reward ratio (TP = SL × RR). |
| `MAX_OPEN_POSITIONS` | `3` | Max simultaneous open positions. |
| `DAILY_RISK_LIMIT_PCT` | `3.0` | Halt new orders after this % daily loss. |
| `DAILY_TARGET_PCT` | `2.0` | Daily target (informational). |

### Sessions

| Env var | Default | Description |
|---------|---------|-------------|
| `ACTIVE_SESSIONS` | `london,newyork` | Comma-separated: `sydney,tokyo,london,newyork,overlap_tl,overlap_ln`. Empty = all sessions. |
| `CLOSE_AT_SESSION_END` | `false` | Auto-close all positions when the selected session(s) end. |

### Server / security

| Env var | Default | Description |
|---------|---------|-------------|
| `HOST` | `127.0.0.1` | Bind address. |
| `PORT` | `8000` | Bind port. |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowed origins. |
| `ZENITRADE_API_TOKEN` | `""` | If set, mutating endpoints require `X-API-Token` header. |
| `DB_PATH` | `zenitrade.db` | SQLite path. |
| `SENTRY_DSN` | `""` | Sentry DSN (empty = disabled). |
