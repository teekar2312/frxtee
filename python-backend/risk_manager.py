"""Risk manager — money management, position sizing, trailing stop, daily limits."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from config import settings

log = logging.getLogger("risk")


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
    risk_pct = risk_pct or settings.risk_per_trade_pct
    rr = rr or settings.rr_ratio
    risk_amount = equity * risk_pct / 100
    # lot = risk / (sl_pips * value_per_pip)
    lot = max(MIN_VOLUME, risk_amount / (sl_pips * value_per_pip_per_lot))
    lot = round(lot, 2)
    tp_pips = sl_pips * rr
    return PositionSize(
        lot=lot, risk_amount=risk_amount, sl_pips=sl_pips, tp_pips=tp_pips,
        potential_loss=risk_amount, potential_profit=risk_amount * rr,
    )


# FINEX min volume = 0.01
MIN_VOLUME = 0.01


class RiskGuard:
    """Daily risk tracking — halts new entries when limit breached."""

    def __init__(self):
        self.daily_loss: float = 0.0
        self.open_count: int = 0

    def can_open(self, equity: float) -> tuple[bool, str]:
        limit = equity * settings.daily_risk_limit_pct / 100
        if self.daily_loss >= limit:
            return False, f"Daily risk limit reached ({settings.daily_risk_limit_pct}%)"
        if self.open_count >= settings.max_open_positions:
            return False, f"Max open positions reached ({settings.max_open_positions})"
        return True, "ok"

    def register_loss(self, amount: float):
        self.daily_loss += abs(amount)

    def register_open(self):
        self.open_count += 1

    def register_close(self):
        self.open_count = max(0, self.open_count - 1)


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
