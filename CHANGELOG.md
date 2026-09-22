# Changelog — ZeniTrade AI

All notable changes to this project are documented in this file.

Format: `[Keep a Changelog](https://keepachangelog.com/)` + Semantic Versioning.

---

## [1.5.0] — 2025-03-10

### Added — 12 New Features
- **WebSocket real-time push** — socket.io mini-service (port 3003), <50ms tick push. `useWebSocket()` hook.
- **Telegram + Discord notifications** — `send_telegram()`, `send_discord()` alongside email. Config: `TELEGRAM_BOT_TOKEN`, `DISCORD_WEBHOOK_URL`, `NOTIFY_CHANNELS`.
- **Currency strength meter** — 8 major currencies ranked by aggregated % change. Endpoint `GET /strength`.
- **Correlation risk check** — detects correlated positions (EURUSD + EURGBP). Endpoint `GET /correlation`.
- **Parameter sweep / grid search** — EMA[10-30] × RSI[10-20], 30 combinations. Returns best by Sharpe. Endpoint `GET /sweep`.
- **Trade journal** — entry context (signal, confidence, indicators snapshot). Endpoint `GET /journal/{ticket}`.
- **PWA manifest** — installable as mobile app.
- **Strategy builder** — visual rule builder (indicator + operator + value). JSON preview, save, backtest, deploy.
- **Tax/performance report** — yearly P&L, win/loss, avg win/loss, volume. Endpoint `GET /tax-report`.
- **Multi-account support** — switch MT5 account at runtime. Endpoint `POST /accounts/switch`.
- **Order flow / volume profile** — POC, value area, volume trend. Endpoint `GET /orderflow`.
- **Real equity curve** — Day P&L includes realized + floating from trade history.

### Added — Backend
- `trading_analytics.py` — currency strength, correlation, sweep, journal, order flow (1 module)
- 7 new API endpoints: `/strength`, `/correlation`, `/sweep`, `/journal/{ticket}`, `/orderflow`, `/tax-report`, `/accounts/switch`
- 7 new Next.js proxy routes

---

## [1.4.0] — 2025-03-10

### Added — Dashboard, Notifications, Alerts, Reporting
- **Trade history endpoint** — `GET /trades` (was dead code — `get_trades()` never called)
- **CSV export** — `GET /export` for trades + frontend export for logs
- **Audit trail** — DBLogHandler captures INFO+ from `zenitrade` logger (was WARNING+ only)
- **Email non-blocking** — `notify_async()` replaces `await send_email()` in trading loops
- **Email retry** — 2x with 2s backoff
- **SMTP port 465 support** — `use_tls` for implicit TLS
- **Manual close email notification** — was auto-loop only
- **Order lifecycle logging** — signal → risk → send → fill → SL/TP → close at INFO level

---

## [1.3.0] — 2025-03-10

### Added — Trailing Stop, Backtesting, ML
- **ATR-based dynamic trailing** — `trail_distance = ATR(14) * multiplier` (adaptif volatilitas)
- **Partial close** — 50% at +1.5R with email notification
- **Per-position SL** — R-multiple computed from actual position SL (was global default)
- **Trailing config in Settings** — 10 new fields (trailing_use_atr, break_even_*, partial_close_*)
- **Variable spread modeling** — 0.5-1.5 pips range (was fixed 0.8)
- **Slippage modeling** — 0.5 pips on market orders
- **Margin call simulation** — forced liquidation at 50% equity
- **Adaptive label threshold** — ATR-based per symbol (was fixed 0.0008)
- **Feature importance logging** — top 5 features after training
- **Overfitting detection** — warns if `train_acc - test_acc > 0.15`

---

## [1.2.0] — 2025-03-10

### Added — News, AI, Sentiment
- **Provider cascade** — Z.AI → Groq → Google → Ollama before heuristic (was straight to heuristic)
- **Indicator context in AI prompt** — 10 indicators computed + formatted (was empty/hallucinated)
- **Batch endpoint context** — builds full indicator + sentiment context (was empty)
- **Auto-trade loop context** — same (was empty — signals hallucinated)
- **429 backoff** — Finnhub 60s, MARKETAUX 300s cache extension
- **Symbol normalization** — EUR/USD → EURUSD (was raw tickers)
- **Demo calendar time field** — news blackout was silently disabled in demo
- **Sentiment aggregation** — `aggregate_sentiment()` with time-weighted decay
- **Currency-specific filtering** — EURUSD → EUR + USD news only
- **`_infer_sentiment()`** — keyword-based for Finnhub (was hardcoded "neutral")
- **`GET /sentiment`** endpoint + sentiment in `/news` response
- **DST-aware session detection** — adjusts London/NY/Sydney offsets

---

## [1.1.0] — 2025-03-10

### Added — Session, Indicator, Execution
- **Trailing stop execution** — `_manage_positions_loop` (5s) calls `trail_stop()` + `modify_sl_tp()`
- **Break-even move** — SL auto-moves to entry+buffer at +1R
- **Auto-trade engine** — `_auto_trade_loop` executes AI signals with cooldown + confidence threshold
- **Indicator data in AI context** — top 10 indicators computed + passed to prompt
- **Indicator output validation** — ±inf → NaN, range-checked bounded indicators
- **Confidence threshold** — Execute button rejects signals < 60%
- **Spread filter** — refuses if spread > 5 pips
- **`modify_sl_tp` endpoint** — TRADE_ACTION_SLTP for trailing/BE
- **`partial_close` endpoint** — scale-out support

### Added — MT5/Risk/Money/Logging
- **Reconcile loop P&L tracking** — fetches deal history, registers realized P&L
- **Dynamic pip value** — `get_pip_value_per_lot()` via `trade_tick_value`
- **`symbol_select()`** — called before `symbol_info()`
- **Margin level monitoring** — halts if < 60%
- **Drawdown circuit breaker** — halts if > 10%
- **Weekend gap protection** — Fri 21:00 UTC – Sunday
- **Post-event news volatility** — checks pre AND post event windows
- **Terminal path validation** — must be .exe file
- **Orphaned trade compensation** — save_trade retry + CRITICAL email
- **Structured order error capture**

---

## [1.0.0] — 2025-03-09

### Added — Initial Release
- Next.js 16 dashboard with 10 views (Dashboard, Trading, AI Engine, Indicators, Risk, News, Backtest, Alerts, Logs, Settings)
- Python FastAPI backend with MT5 integration
- 4 AI providers (Z.AI, Groq, Google AI Studio, Local/Ollama)
- 30 technical indicators
- ML self-learning (XGBoost + walk-forward + drift detection)
- Risk management (daily loss, margin, drawdown, news blackout)
- Trailing stop + break-even + partial close
- Finnhub + MARKETAUX news with sentiment
- Price alerts with DB persistence
- Email notifications with SMTP
- SQLite persistence (trades, alerts, logs, risk_state, ml_models)
- Docker deployment (Dockerfile + docker-compose)
- Dark + Light theme
- 3 density modes (compact, dense, minimal)
- DST-aware session clock
- API auth + rate limiting
- Multi-worker guard
- Health + metrics endpoints
- Sentry integration
- Structured JSON logging
- Code splitting (next/dynamic)
- React.memo ticker cells
- AbortSignal on multi-analysis
- Provider cascade
- Batch /analysis endpoint
- DB retention (hourly cleanup)

### Security
- `ZENITRADE_API_TOKEN` auth on all mutating endpoints
- Pydantic input validation (no 500s on junk input)
- Rate limiting (slowapi)
- Terminal path locked to .env (no RCE)
- Multi-worker startup guard
- `.env` gitignored
