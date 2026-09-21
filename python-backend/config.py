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

    # AI
    zai_api_key: str = ""
    groq_api_key: str = ""
    google_api_key: str = ""
    ollama_url: str = "http://127.0.0.1:11434"

    # Money mgmt
    risk_per_trade_pct: float = 1.0
    stop_loss_pips: int = 10
    rr_ratio: float = 1.5
    max_open_positions: int = 3
    daily_risk_limit_pct: float = 3.0
    daily_target_pct: float = 2.0
    avoid_high_impact_news: bool = True

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

    # Persistence + monitoring
    db_path: str = "zenitrade.db"
    sentry_dsn: str = ""  # empty = disabled

    # Auto-trade engine
    auto_trade_mode: bool = False
    auto_trade_symbols: str = "EURUSD,GBPUSD"  # comma-separated
    auto_trade_min_confidence: int = 75
    ai_provider: str = "zai"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
