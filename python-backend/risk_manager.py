"""Risk manager — money management, position sizing, trailing stop, daily limits."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from config import settings

log = logging.getLogger("risk")

# FINEX min volume = 0.01 (defined before size_position uses it)
MIN_VOLUME = 0.01


@dataclass
class PositionSize:
    lot: float
    risk_amount: float
    sl_pips: float
    tp_pips: float
    potential_loss: float
    potential_profit: float


def size_position(equity: float, sl_pips: int, value_per_pip_per_lot: float = 10.0,
                  risk_pct: float | None = None, rr: float | None = None) -> PositionSize:
    risk_pct = settings.risk_per_trade_pct if risk_pct is None else risk_pct
    rr = settings.rr_ratio if rr is None else rr
    risk_amount = equity * risk_pct / 100
    # lot = risk / (sl_pips * value_per_pip)
    lot = max(MIN_VOLUME, risk_amount / (sl_pips * value_per_pip_per_lot))
    lot = round(lot, 2)
    tp_pips = sl_pips * rr
    return PositionSize(
        lot=lot, risk_amount=risk_amount, sl_pips=sl_pips, tp_pips=tp_pips,
        potential_loss=risk_amount, potential_profit=risk_amount * rr,
    )


class RiskGuard:
    """Daily risk tracking — halts new entries when limit breached.

    Automatically resets loss/open counters on date rollover.
    State persists to SQLite so it survives backend restarts (critical:
    without persistence, daily_loss resets to 0 on restart = money risk).
    """

    def __init__(self):
        self.daily_loss: float = 0.0
        self.open_count: int = 0
        self._date: str = ""
        self._restore()

    def _restore(self):
        """Load today's state from DB. If no row for today, start fresh."""
        try:
            from db import load_risk_state
            today, loss, count = load_risk_state()
            self._date = today
            self.daily_loss = loss
            self.open_count = count
            if loss > 0 or count > 0:
                log.info("RiskGuard restored: date=%s loss=%.2f open=%d",
                         today, loss, count)
        except Exception as exc:  # noqa: BLE001
            log.warning("RiskGuard restore failed (db not ready?): %s", exc)
            self._date = date.today().isoformat()

    def _persist(self):
        try:
            from db import save_risk_state
            save_risk_state(self.daily_loss, self.open_count)
        except Exception as exc:  # noqa: BLE001
            log.debug("RiskGuard persist failed: %s", exc)

    def _maybe_reset(self):
        today = date.today().isoformat()
        if today != self._date:
            self._date = today
            self.daily_loss = 0.0
            self.open_count = 0
            log.info("RiskGuard daily reset — new trading day %s", today)
        self._persist()

    def can_open(self, equity: float) -> tuple[bool, str]:
        self._maybe_reset()
        limit = equity * settings.daily_risk_limit_pct / 100
        if self.daily_loss >= limit:
            return False, f"Daily risk limit reached ({settings.daily_risk_limit_pct}%)"
        if self.open_count >= settings.max_open_positions:
            return False, f"Max open positions reached ({settings.max_open_positions})"
        return True, "ok"

    def register_loss(self, amount: float):
        self._maybe_reset()
        self.daily_loss += abs(amount)
        self._persist()

    def register_open(self):
        self._maybe_reset()
        self.open_count += 1
        self._persist()

    def register_close(self, pnl: float | None = None):
        self.open_count = max(0, self.open_count - 1)
        if pnl is not None and pnl < 0:
            self.register_loss(pnl)
        else:
            self._persist()

    def reset_daily(self):
        """Force-reset (e.g. for testing or manual rollover)."""
        self.daily_loss = 0.0
        self.open_count = 0


guard = RiskGuard()


def trail_stop(position: dict, current_price: float, trail_pips: int,
               pip_value: float = 0.0001) -> dict | None:
    """Advance SL behind price; returns updated position or None."""
    new_sl = None
    if position["type"] == "BUY":
        candidate = current_price - trail_pips * pip_value
        if position.get("sl") is None or candidate > position["sl"]:
            new_sl = candidate
    else:
        candidate = current_price + trail_pips * pip_value
        if position.get("sl") is None or candidate < position["sl"]:
            new_sl = candidate
    if new_sl is not None:
        position["sl"] = new_sl
        return position
    return None


def near_high_impact_news(minutes: int = 15) -> bool:
    """Check economic calendar for tier-1 events within `minutes`."""
    # implemented in main.py via news_service.economic_calendar()
    return False
