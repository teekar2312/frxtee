# ZeniTrade AI — Python Backend (MetaTrader 5 + AI + ML)

Production backend for the ZeniTrade AI forex trading terminal.

**Stack:** Python 3.14 · FastAPI · MetaTrader5 · scikit-learn/xgboost · pandas/ta · Z.AI / Groq / Google AI / Ollama

## Platform
- **OS:** Windows 11 (MetaTrader 5 terminal required)
- **IDE:** Visual Studio Code
- **Broker:** FINEX Indonesia (real account, leverage 1:500)
- **MT5:** Install `MetaTrader5` terminal from your broker, then `pip install MetaTrader5`

## Setup

```powershell
# 1. Create venv (Python 3.14)
python -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install deps
pip install -r requirements.txt

# 3. Configure
copy config.example.env .env
#   edit .env with your FINEX login, server, password,
#   and API keys (Finnhub, MARKETAUX, Z.AI, Groq, Google, Ollama URL)

# 4. Run
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The Next.js dashboard auto-detects this backend. Point the dashboard env
`TRADING_BACKEND_URL=http://127.0.0.1:8000` (default) and it will proxy all
`/api/trading/*` calls here. If unreachable, the dashboard runs in demo mode
with realistic synthetic data.

## Modules

| File              | Responsibility                                        |
|-------------------|--------------------------------------------------------|
| `main.py`         | FastAPI app, REST routes, CORS, lifespan               |
| `mt5_service.py`  | MT5 connect/auto-launch, account, ticks, candles, orders |
| `ai_service.py`   | Z.AI / Groq / Google AI Studio / Ollama local inference |
| `news_service.py`  | Finnhub + MARKETAUX feeds, economic calendar           |
| `indicators.py`   | 30 technical indicators (EMA, RSI, MACD, ATR, ...)     |
| `ml_model.py`     | Self-learning classifier + nightly retrain              |
| `risk_manager.py` | Money management, position sizing, trailing stop       |
| `backtest.py`     | Historical strategy simulation                         |
| `notifier.py`     | Email alerts (SMTP) + price alerts                     |

## Auto-launch MT5

`mt5_service.connect()` will:
1. Try `mt5.initialize()` (uses running terminal if available).
2. If that fails, launch `terminal64.exe` at the configured path, wait for
   the terminal window, then retry initialization.
3. `mt5.login(login, password, server)` to authorize against FINEX.

## Disclaimer

Trading FX involves substantial risk of loss. This software is for
educational/research purposes. Test thoroughly on a demo account before any
live trading. The authors accept no liability for trading losses.
