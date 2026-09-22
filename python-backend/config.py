"""Configuration loaded from environment / .env"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # MT5
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = "FINEX-Real"
    mt5_terminal_path: str = r"C:\Program Files\FINEX MetaTrader 5\terminal64.exe"
    mt5_auto_launch: bool = True

    # News
    finnhub_api_key: str = ""
    marketaux_api_key: str = ""

    # AI providers — API keys
    zai_api_key: str = ""
    groq_api_key: str = ""
    google_api_key: str = ""
    ollama_url: str = "http://127.0.0.1:11434"

    # AI provider models (configurable per provider)
    zai_model: str = "glm-4.6"
    groq_model: str = "llama-3.3-70b-versatile"
    google_model: str = "gemini-1.5-pro"
    ollama_model: str = "llama3"

    # AI confidence threshold (0-100) — signals below this are rejected
    ai_min_confidence: int = 60
    # Auto-trade confidence threshold (higher for auto-execution)
    auto_trade_min_confidence: int = 75

    # Money mgmt
    risk_per_trade_pct: float = 1.0
    stop_loss_pips: int = 10
    rr_ratio: float = 1.5
    max_open_positions: int = 3
    daily_risk_limit_pct: float = 3.0
    daily_target_pct: float = 2.0
    avoid_high_impact_news: bool = True

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
    auto_trade_symbols: str = "EURUSD,GBPUSD"
    auto_trade_min_confidence: int = 75
    ai_provider: str = "zai"

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
