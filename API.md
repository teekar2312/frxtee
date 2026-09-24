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
      "pips": 0.0,
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

**Query:** `?symbol=EURUSD&provider=zai`

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
    "provider": "zai",
    "generatedAt": "2024-03-10T12:00:00Z",
    "ml_prediction": { "direction": "UP", "prob": 0.72, "drift": 0.03 }
  },
  "demo": false
}
```

### GET /api/trading/analysis/batch
Multi-pair analysis in one request (reduces 5 round-trips to 1).

**Query:** `?symbols=EURUSD,GBPUSD,USDJPY&provider=zai`

**Response:**
```json
{
  "results": {
    "EURUSD": { "signal": "STRONG BUY", "confidence": 77, ... },
    "GBPUSD": { "signal": "BUY", "confidence": 57, ... }
  },
  "provider": "zai",
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
  "comment": "AI:auto"
}
```

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

### GET /api/trading/sentiment?symbol=EURUSD
Aggregate sentiment filtered by symbol's currencies.

---

## ML Model

### GET /api/trading/ml/info
Model metadata (version, accuracy, drift, trained_at).

### POST /api/trading/ml/train?symbol=EURUSD
Trigger model retraining (walk-forward + class balancing).

---

## System

### GET /health
Deep health check (MT5 + DB + scheduler + background loops).

### GET /metrics
Prometheus-style metrics (positions, loss, trade count, loop liveness).

### GET /api/trading/trades
Trade history from DB.

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
