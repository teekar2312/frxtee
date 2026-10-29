"""Configuration loaded from environment / .env

.env file search order (first found wins):
  1. python-backend/.env (when running from python-backend/ dir)
  2. ../.env (parent directory — when running from project root)
  3. System environment variables (always checked)
"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Find .env file — check current dir first, then parent (project root)
_env_candidates = [
    Path(".env"),           # python-backend/.env (when CWD = python-backend/)
    Path("../.env"),         # project-root/.env (when CWD = python-backend/)
]
_env_file = None
for _p in _env_candidates:
    if _p.exists():
        _env_file = str(_p)
        break
# Also check system env vars (always available)
if _env_file:
    _ENV_FILE = _env_file
else:
    _ENV_FILE = ".env"  # fallback — pydantic will look for it


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # MT5
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = "FINEX-Real"
    mt5_terminal_path: str = r"C:\Program Files\FINEX MetaTrader 5\terminal64.exe"
    mt5_auto_launch: bool = True

    # News
    finnhub_api_key: str = ""
    marketaux_api_key: str = ""
    # Apify token for economic calendar (free $5/mo credit at apify.com)
    # Used by ForexFactory calendar scraper actor — alternative to Finnhub's
    # paid /calendar/economic endpoint (which returns 403 on free tier).
    # Get token: https://console.apify.com/account-integrations
    apify_token: str = ""
    # RapidAPI key for economic calendar (alternative to Apify)
    # Supports multiple calendar APIs on RapidAPI marketplace.
    # Get key: https://rapidapi.com/auth/sign-up (free tier available)
    # Then subscribe to an economic calendar API (search "economic calendar")
    rapidapi_key: str = ""

    # AI providers — API keys (only Groq + Local/Ollama supported)
    groq_api_key: str = ""
    ollama_url: str = "http://127.0.0.1:11434"

    # AI provider models (configurable per provider)
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_model: str = "llama3"
    # Ollama context window size (tokens). Default 8192 is a safe middle
    # ground — Ollama's newer defaults (128k+) can require 40GB+ RAM for the
    # KV cache and cause OOM on machines with limited memory. Lower this
    # (e.g. 4096) if you still hit OOM; raise it (e.g. 16384) if you have
    # 32GB+ RAM and need longer context.
    ollama_num_ctx: int = 4096
    # Ollama request timeout in seconds. Local models on CPU can be slow:
    #   - llama3 (8B) on modern CPU: ~20-40s per request
    #   - llama3.2 (3B) on any CPU: ~10-20s (RECOMMENDED for CPU)
    #   - llama3.3 (70B) on CPU: 300s+ (NOT recommended — too slow)
    #   - larger models: use GPU or cloud instead
    # If you see 'Ollama timeout' warnings, use a SMALLER model (llama3 or
    # llama3.2) instead of increasing timeout.
    ollama_timeout: int = 120

    # AI confidence threshold (0-100) — signals below this are rejected
    ai_min_confidence: int = 60
    # Auto-trade confidence threshold (higher for auto-execution)
    auto_trade_min_confidence: int = 75

    # Money mgmt — aligned with 7 risk management pillars:
    # 1. Fixed-fractional: risk % of CURRENT equity (not starting balance)
    # 2. Stops at entry: broker-side, ATR-based structure
    # 3. Positive asymmetry: minimum 1:1.5 RR
    # 4. Leverage discipline: effective leverage ≤5:1, margin <30%
    # 5. Aggregate exposure: total open risk ≤4% across all positions
    # 6. Loss limits: daily 2-3%, weekly ~5%, drawdown ladder
    # 7. Event & gap risk: flatten before high-impact news, no weekend holds
    risk_per_trade_pct: float = 1.0   # Pillar 1: 1-2% standard
    stop_loss_pips: int = 10           # Pillar 2: ATR-based structure
    rr_ratio: float = 2.0              # Pillar 3: minimum 1:1.5, default 1:2.0
    max_open_positions: int = 3        # Pillar 5: total risk = 3 × 1% = 3% ≤ 4% cap
    daily_risk_limit_pct: float = 3.0 # Pillar 6: daily stop 2-3%
    daily_target_pct: float = 2.0     # Realistic daily goal
    avoid_high_impact_news: bool = True # Pillar 7: flatten before NFP/FOMC/CPI

    # Trading sessions — comma-separated active sessions
    # Options: sydney, tokyo, london, newyork
    #   overlap_tl  = Tokyo × London overlap (~7-9 UTC summer / 8-9 winter)
    #   overlap_ln  = London × New York overlap (~12-16 UTC summer / 13-17 winter)
    # Empty = trade all sessions (no session filter)
    active_sessions: str = "london,newyork"
    # When True, the manage-positions loop will CLOSE ALL open positions
    # automatically when the current time leaves all selected sessions
    # (i.e. session-end transition: in_session True → False).
    # Helps avoid overnight/weekend gap exposure on day-trading setups.
    close_at_session_end: bool = False

    # Trailing stop / position management
    trailing_enabled: bool = True
    trailing_pips: int = 8
    trailing_atr_multiplier: float = 1.5  # dynamic: trail = ATR * multiplier
    trailing_use_atr: bool = False  # if True, use ATR-based dynamic trailing
    break_even_enabled: bool = True
    break_even_r_multiple: float = 1.0  # move SL to BE at +1R
    break_even_buffer_pips: int = 2  # buffer above entry for BE
    partial_close_enabled: bool = False
    partial_close_r_multiple: float = 1.5  # close 50% at +1.5R
    partial_close_ratio: float = 0.5  # fraction to close

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_to: str = ""

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Security
    zenitrade_api_token: str = ""  # empty = no auth (dev mode)

    # Persistence + monitoring
    db_path: str = "zenitrade.db"
    sentry_dsn: str = ""  # empty = disabled

    # Auto-trade engine
    auto_trade_mode: bool = False
    # Default scan list covers all 14 supported pairs — was previously just
    # "EURUSD,GBPUSD" which made auto-trade look limited to 2 pairs. Each
    # pair is independently gated by the confidence threshold + per-trade
    # risk %, so scanning more pairs = more opportunities without extra
    # risk. Users can still narrow this via the Trading view pair selector.
    auto_trade_symbols: str = "EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,USDCAD,NZDUSD,EURGBP,EURJPY,GBPJPY,AUDJPY,EURAUD,XAUUSD,XAGUSD"
    ai_provider: str = "groq"

    # Trading strategy selection
    # Options: auto (AI selects), ma_ribbon, momentum_scalp, pivot_bounce,
    # ema_crossover, rmi_trend_sync, linreg_channel, ema_rsi_filter
    trading_strategy: str = "auto"

    # Notification channels
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    notify_channels: str = "email"  # "email,telegram,discord"

    # Multi-account
    mt5_accounts: str = ""  # comma-separated "login:password:server,login2:pass2:server2"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
