# ZeniTrade AI — Forex Trading Terminal

> AI-powered forex trading terminal with MetaTrader 5 integration, machine learning, multi-provider AI analysis, real-time news, and full risk management.

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13+-green)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org)
[![MT5](https://img.shields.io/badge/MetaTrader-5-blue)](https://www.metatrader5.com)

---

## ✨ Fitur Utama

### Trading
- **MetaTrader 5 integration** — auto-launch terminal, real-time ticks, order execution, SL/TP management
- **AI auto-trade engine** — eksekusi sinyal otomatis dengan confidence threshold + cooldown
- **Manual order ticket** — BUY/SELL dengan AI lot sizing, SL/TP kalkulator
- **Partial close / scale-out** — tutup 50% posisi di +1.5R
- **Trailing stop** — fixed pips atau ATR-based dynamic (adaptif volatilitas)
- **Break-even** — SL otomatis pindah ke entry+buffer di +1R
- **30 indikator teknikal** — EMA, RSI, MACD, Bollinger Bands, Supertrend, Ichimoku, dll

### AI & Machine Learning
- **4 AI providers** — Z.AI, Groq, Google AI Studio, Local AI (Ollama) dengan provider cascade
- **Multi-pair analysis** — batch endpoint, semua pair dianalisis dalam 1 request
- **Self-learning ML** — XGBoost classifier, walk-forward validation, drift detection, class balancing
- **7-dimension analysis** — Bank Sentral, Data Ekonomi, Politik, Fiskal, Komoditas, Sentimen, Breaking News
- **Technical indicator context** — 10 indikator di-inject ke AI prompt (bukan halusinasi)

### Risk Management
- **Daily risk limit** — halt trading di 3% daily loss (persisted to DB)
- **Margin level monitoring** — halt di 60% (FINEX MC di 50%)
- **Drawdown circuit breaker** — halt di 10% drawdown
- **News blackout** — pre AND post-event (±15 menit) high-impact events
- **Weekend gap protection** — no new entries Fri 21:00 UTC – Sunday
- **Spread filter** — refuse orders saat spread > 5 pips
- **Correlation risk check** — detect EURUSD + EURGBP + EURJPY open bersamaan

### News & Sentiment
- **Finnhub + MARKETAUX** — real-time news feed dengan 429 backoff
- **Sentiment aggregation** — time-weighted, currency-specific filtering
- **Economic calendar** — cached 5 min, high-impact event detection

### Dashboard & UX
- **3 density modes** — Compact, Dense, Minimal (persisted)
- **DST-aware session clock** — Sydney, Tokyo, London, New York
- **Dark + Light theme** — dengan next-themes
- **Code splitting** — 11 views lazy-loaded via next/dynamic
- **PWA** — installable sebagai mobile app
- **Real-time WebSocket** — <50ms tick push (optional, via mini-service)

### Notifications
- **Email (SMTP)** — dengan retry 2x + backoff
- **Telegram bot** — instant push notification
- **Discord webhook** — channel notifications
- **Non-blocking** — notify_async() tidak block trading loop

### Reporting & Analytics
- **Trade history** — semua order lifecycle tersimpan di SQLite
- **CSV export** — trades + logs
- **Tax report** — yearly P&L summary
- **Currency strength meter** — 8 major currencies
- **Parameter sweep** — grid search EMA × RSI
- **Order flow analysis** — POC, value area, volume trend
- **Strategy builder** — visual rule builder, no coding

### Production Hardening
- **API auth** — ZENITRADE_API_TOKEN + X-API-Token header
- **Rate limiting** — 10/min order, 3/min email, 1/hr ML train
- **Multi-worker guard** — refuses >1 worker unless acknowledged
- **DB persistence** — trades, alerts, logs, risk state, ML models
- **DB retention** — hourly cleanup (5000 logs, 10000 trades, 500 alerts)
- **Docker deployment** — Dockerfile + docker-compose
- **Health & metrics** — `/health` (deep checks), `/metrics` (Prometheus-style)
- **Sentry integration** — optional error monitoring via SENTRY_DSN
- **Structured JSON logging** — LOG_FORMAT=json untuk ELK/Loki

---

## 🚀 Quick Start

### Prasyarat
- **Windows 11** (MetaTrader 5 hanya berjalan di Windows)
- **Python 3.13+** + **Node.js 22+** + **bun**
- **MetaTrader 5 terminal** (dari broker FINEX Indonesia)
- **Visual Studio Code** (recommended IDE)

### Backend (Python)

```powershell
cd python-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy config.example.env .env
# Edit .env dengan FINEX login, API keys, SMTP, Telegram

python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend (Next.js)

```powershell
bun install
bun run dev
```

Buka http://localhost:3000 → Dashboard muncul dengan badge "DEMO" (atau "MT5 LIVE" jika backend terhubung).

### Docker (opsional)

```bash
docker compose up --build
```

---

## 📋 Konfigurasi

Lihat [`python-backend/config.example.env`](python-backend/config.example.env) untuk semua env vars:

| Kategori | Variabel |
|----------|----------|
| MT5 | `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`, `MT5_TERMINAL_PATH`, `MT5_AUTO_LAUNCH` |
| News | `FINNHUB_API_KEY`, `MARKETAUX_API_KEY` |
| AI | `ZAI_API_KEY`, `GROQ_API_KEY`, `GOOGLE_API_KEY`, `OLLAMA_URL` |
| Email | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Discord | `DISCORD_WEBHOOK_URL` |
| Security | `ZENITRADE_API_TOKEN` |
| Persistence | `DB_PATH`, `SENTRY_DSN` |
| Auto-trade | `AUTO_TRADE_MODE`, `AUTO_TRADE_SYMBOLS`, `AUTO_TRADE_MIN_CONFIDENCE` |
| Trailing | `TRAILING_ENABLED`, `TRAILING_USE_ATR`, `TRAILING_ATR_MULTIPLIER` |

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript 5, Tailwind CSS 4, shadcn/ui |
| Charts | Recharts (candlestick, equity curve, bars) |
| State | Zustand (persist), TanStack Query (server state) |
| Backend | Python 3.13+, FastAPI, uvicorn |
| Trading | MetaTrader5 Python library |
| ML | XGBoost, scikit-learn, pandas, ta |
| AI | Z.AI, Groq, Google AI Studio, Ollama |
| Database | SQLite (WAL mode, thread-safe) |
| Deployment | Docker, docker-compose |
| Real-time | Socket.io (optional mini-service) |

---

## 📁 Struktur Project

```
my-project/
├── src/                          # Next.js dashboard
│   ├── app/                      # App Router (pages + API routes)
│   │   ├── api/trading/          # 20+ API routes (proxy to backend)
│   │   ├── page.tsx             # Main dashboard page
│   │   └── layout.tsx           # Root layout + theme provider
│   ├── components/trading/      # 15 view components
│   ├── lib/                     # trading-data, trading-store, hooks, proxy
│   └── hooks/                   # use-toast, use-mobile
├── python-backend/              # FastAPI + MT5 + AI + ML
│   ├── main.py                  # FastAPI app, 25+ endpoints
│   ├── mt5_service.py           # MT5 connect, ticks, orders, SL/TP
│   ├── ai_service.py            # 4-provider AI with cascade
│   ├── ml_model.py              # XGBoost + walk-forward + drift
│   ├── risk_manager.py          # Daily loss, margin, drawdown, news
│   ├── indicators.py            # 30 technical indicators
│   ├── news_service.py          # Finnhub + MARKETAUX + sentiment
│   ├── trading_analytics.py     # Strength, correlation, sweep, flow
│   ├── db.py                    # SQLite persistence layer
│   ├── notifier.py              # Email + Telegram + Discord
│   ├── config.py                # Pydantic settings (44 fields)
│   ├── Dockerfile               # Backend container
│   └── requirements.txt        # Python deps
├── mini-services/
│   └── ws-pusher/               # Socket.io real-time push (port 3003)
├── prisma/schema.prisma         # Reserved for future dashboard-side DB
├── Dockerfile                   # Dashboard container
├── docker-compose.yml           # Full-stack deployment
├── .env.example                 # Dashboard env template
└── .gitignore                   # Production-ready
```

---

## ⚠️ Disclaimer

Trading forex melibatkan risiko kerugian substansial. Software ini untuk tujuan **edukasi/riset**. Test thoroughly di akun demo sebelum live trading. Penulis tidak bertanggung jawab atas kerugian trading.

---

## 📄 License

MIT — lihat [LICENSE](LICENSE)
