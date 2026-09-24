# Deployment Guide — ZeniTrade AI

## Platform Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| OS | Windows 11 (MT5 required) | Windows 11 |
| Python | 3.13 | 3.13+ |
| Node.js | 20 | 22+ |
| bun | latest | latest |
| MT5 Terminal | Any broker | FINEX Indonesia |
| RAM | 4 GB | 8 GB |
| Disk | 1 GB | 5 GB (DB + models) |

---

## Option 1: Native Windows (Recommended for Live Trading)

### Step 1: Install Prerequisites

```powershell
# Python 3.13+ from python.org
# Node.js 22+ from nodejs.org
# bun
npm install -g bun

# MetaTrader 5 terminal from your broker (FINEX Indonesia)
# Install to default path: C:\Program Files\FINEX MetaTrader 5\
```

### Step 2: Backend Setup

```powershell
cd C:\zenitrade\python-backend

# Virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure
copy config.example.env .env
notepad .env  # or: code .env
```

**Required .env settings for live trading:**
```ini
MT5_LOGIN=your_finex_login
MT5_PASSWORD=your_password
MT5_SERVER=FINEX-Real
MT5_TERMINAL_PATH=C:\Program Files\FINEX MetaTrader 5\terminal64.exe
MT5_AUTO_LAUNCH=true

ZENITRADE_API_TOKEN=generate-a-long-random-string
HOST=127.0.0.1
PORT=8000
```

### Step 3: Frontend Setup

```powershell
cd C:\zenitrade

bun install

# Configure (optional)
copy .env.example .env.local
# Set TRADING_BACKEND_URL=http://127.0.0.1:8000
# Set ZENITRADE_API_TOKEN=same-as-backend
```

### Step 4: Run

```powershell
# Terminal 1: Backend
cd python-backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# Terminal 2: Frontend
bun run dev
```

Open http://localhost:3000 → Verify badge shows "MT5 LIVE" (green).

### Step 5: (Optional) WebSocket Pusher

```powershell
cd mini-services\ws-pusher
bun install
bun run dev
```

Set `NEXT_PUBLIC_WS_URL=/?XTransformPort=3003` in `.env.local` for real-time push.

---

## Option 2: Docker (Demo / Development)

> **Note:** MetaTrader5 library is Windows-only. Docker runs in demo mode (no real broker).

```bash
# Build and start both services
docker compose up --build

# Access:
# Dashboard: http://localhost:3000
# Backend API: http://localhost:8000
# Health: http://localhost:8000/health
```

### docker-compose.yml services:
- **backend** — Python FastAPI on :8000, healthcheck, persistent volumes for DB + models
- **dashboard** — Next.js on :3000, depends on backend health

### Environment variables for Docker:
```yaml
ZENITRADE_API_TOKEN: ${ZENITRADE_API_TOKEN}
FINNHUB_API_KEY: ${FINNHUB_API_KEY}
MARKETAUX_API_KEY: ${MARKETAUX_API_KEY}
# ... all env vars in .env
```

---

## Option 3: Production Checklist

Before deploying to a live account:

### Security
- [ ] `ZENITRADE_API_TOKEN` set to a 32+ char random string
- [ ] `HOST=127.0.0.1` (never expose on 0.0.0.0 without reverse proxy + TLS)
- [ ] `.env` file permissions restricted (`chmod 600 .env`)
- [ ] Firewall blocks port 8000 from external access
- [ ] `ZENITRADE_API_TOKEN` in dashboard `.env.local` matches backend

### MT5
- [ ] MT5 terminal installed and logged in manually at least once
- [ ] Terminal path in `.env` is correct (`MT5_TERMINAL_PATH`)
- [ ] `MT5_AUTO_LAUNCH=true` for auto-start
- [ ] Algo trading enabled in MT5 terminal (Tools → Options → Expert Advisors)

### Risk Management
- [ ] `RISK_PER_TRADE_PCT=1.0` (max 1% per trade)
- [ ] `DAILY_RISK_LIMIT_PCT=3.0` (max 3% daily)
- [ ] `MAX_OPEN_POSITIONS=3`
- [ ] `AVOID_HIGH_IMPACT_NEWS=true`
- [ ] Test on **DEMO account** first (`MT5_SERVER=FINEX-Demo`)

### Notifications
- [ ] SMTP configured (test via "Send test email" in Settings)
- [ ] Telegram bot created (@BotFather) + chat ID set
- [ ] `NOTIFY_CHANNELS=email,telegram` for dual-channel alerts

### Monitoring
- [ ] `/health` endpoint returns `ok: true`
- [ ] `/metrics` endpoint accessible
- [ ] Sentry DSN set (optional but recommended)
- [ ] `LOG_FORMAT=json` for log aggregation

### Database
- [ ] `DB_PATH` points to a persistent location (not /tmp)
- [ ] Backup strategy for `zenitrade.db`
- [ ] DB retention running (hourly cleanup)

### ML Model
- [ ] Train initial model: `POST /api/trading/ml/train?symbol=EURUSD`
- [ ] Verify `/api/trading/ml/info` returns model metadata
- [ ] Drift score < threshold (8%)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Badge shows "DEMO" | Backend not running on :8000. Check `python -m uvicorn` output. |
| "MT5 connect failed" | Wrong login/password/server in `.env`. Verify in MT5 terminal. |
| "symbol not found" | Symbol not in Market Watch. `symbol_select()` is called automatically — check MT5 terminal. |
| "Spread too wide" | Spread > 5 pips. Normal during news. Wait or increase `max_spread_pips`. |
| "Daily risk limit reached" | `daily_loss >= 3%`. Resets at UTC midnight. Check `/metrics`. |
| "Rate limit exceeded" | Too many requests. Check `/metrics` for counts. |
| News feed empty | `FINNHUB_API_KEY` / `MARKETAUX_API_KEY` not set or exhausted. |
| AI analysis "heuristic" | No AI API key configured. Set `ZAI_API_KEY` or `GROQ_API_KEY`. |
| ML "not trained" | Run `POST /api/trading/ml/train?symbol=EURUSD`. |
| DB locked | SQLite under heavy concurrent writes. Use single worker (`UVICORN_WORKERS=1`). |
| Multi-worker error | Set `MULTI_WORKER_SAFE=1` only if you understand the risk. |

---

## Performance Tuning

| Parameter | Default | Tune for |
|-----------|---------|----------|
| `MT5_LAUNCH_TIMEOUT` | 60s | Slow disk → increase to 120s |
| Tick poll interval | 2.5s | Use WebSocket for <50ms |
| `_manage_positions_loop` | 5s | Scalping → decrease to 3s (more MT5 RPCs) |
| `TRAILING_USE_ATR` | false | Volatile markets → true (adaptive distance) |
| `PARTIAL_CLOSE_ENABLED` | false | Trend following → true (lock profits) |
| `LOG_FORMAT` | text | Production → json (ELK/Loki) |
