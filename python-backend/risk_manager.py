"""Risk manager — money management, position sizing, trailing stop, daily limits."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from config import settings

log = logging.getLogger("risk")

# FINEX min volume = 0.01 (defined before size_position uses it)
MIN_VOLUME = 0.01


def _is_dst(date) -> bool:
    """Check if date is in DST (Northern Hemisphere, US/EU rules).
    DST: second Sunday of March to first Sunday of November."""
    from datetime import datetime, timezone
    if isinstance(date, datetime):
        d = date
    else:
        d = date
    year = d.year
    march_start = datetime(year, 3, 1, tzinfo=timezone.utc)
    march_dow = march_start.weekday()
    second_sunday_march = march_start.replace(day=1 + ((6 - march_dow) % 7) + 7)
    nov_start = datetime(year, 11, 1, tzinfo=timezone.utc)
    nov_dow = nov_start.weekday()
    first_sunday_nov = nov_start.replace(day=1 + ((6 - nov_dow) % 7))
    return d >= second_sunday_march and d < first_sunday_nov


@dataclass
class PositionSize:
    lot: float
    risk_amount: float
    sl_pips: float
    tp_pips: float
    potential_loss: float
    potential_profit: float


def size_position(equity: float, sl_pips: int, value_per_pip_per_lot: float | None = None,
                  risk_pct: float | None = None, rr: float | None = None) -> PositionSize:
    """Calculate position size based on risk %.

    If value_per_pip_per_lot is None, the caller should pass the symbol-specific
    value from mt5_service.get_pip_value_per_lot(). The old default of 10.0 is
    incorrect for JPY pairs and metals — always pass the real value in prod.
    """
    risk_pct = settings.risk_per_trade_pct if risk_pct is None else risk_pct
    rr = settings.rr_ratio if rr is None else rr
    vpp = value_per_pip_per_lot if value_per_pip_per_lot is not None else 10.0
    risk_amount = equity * risk_pct / 100
    # lot = risk / (sl_pips * value_per_pip)
    lot = max(MIN_VOLUME, risk_amount / (sl_pips * vpp))
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
        """Load today's state from DB. If DB/table not ready, start fresh."""
        try:
            from db import load_risk_state, init_db
            # ensure tables exist before reading (init_db is safe to call multiple times)
            init_db()
            today, loss, count = load_risk_state()
            self._date = today
            self.daily_loss = loss
            self.open_count = count
            if loss > 0 or count > 0:
                log.info("RiskGuard restored: date=%s loss=%.2f open=%d",
                         today, loss, count)
        except Exception as exc:  # noqa: BLE001
            log.warning("RiskGuard restore skipped (db not ready): %s", exc)
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

        # margin level check — halt if below FINEX margin call (50%) + buffer
        try:
            from mt5_service import get_margin_level
            ml = get_margin_level()
            if ml is not None and ml < 60:  # 50% MC + 10% buffer
                return False, f"Margin level too low ({ml:.0f}%) — near margin call"
        except Exception:  # noqa: BLE001
            pass  # backend not connected, skip margin check

        # drawdown circuit breaker — halt if equity dropped >10% from day open
        day_open_equity = equity + self.daily_loss
        drawdown_pct = ((day_open_equity - equity) / day_open_equity * 100) if day_open_equity > 0 else 0
        if drawdown_pct > 10:
            return False, f"Max drawdown breached ({drawdown_pct:.1f}%) — halt trading"

        # weekend gap risk — prevent new entries on Friday after 21:00 UTC
        # or Saturday/Sunday (market closed, gap risk on Monday open)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if now.weekday() == 4 and now.hour >= 21:  # Friday 21:00+ UTC
            return False, "Weekend gap risk — no new entries after Friday 21:00 UTC"
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False, "Market closed (weekend)"

        # trading session filter — only trade during selected sessions
        active_sessions = getattr(settings, "active_sessions", "")
        if active_sessions:
            utc_h = now.hour
            in_session = False
            sessions = [s.strip().lower() for s in active_sessions.split(",") if s.strip()]
            is_dst = _is_dst(now)

            # Compute the UTC hour-window for a single base session.
            # Returns (start, end) in UTC hours (0-23), DST-aware.
            def _base_window(sess: str):
                if sess == "sydney":
                    # AEST: 22:00-07:00 local → UTC: ~21:00-06:00 (winter) / 20:00-05:00 (summer)
                    start = 20 if is_dst else 21
                    end = 5 if is_dst else 6
                elif sess == "tokyo":
                    # JST: 00:00-09:00 local → UTC: 0-9 (no DST)
                    start, end = 0, 9
                elif sess == "london":
                    # GMT/BST: 08:00-17:00 local → UTC: 8-17 (winter) / 7-16 (summer)
                    start = 7 if is_dst else 8
                    end = 16 if is_dst else 17
                elif sess == "newyork":
                    # EST/EDT: 08:00-17:00 local → UTC: 13-22 (winter) / 12-21 (summer)
                    start = 12 if is_dst else 13
                    end = 21 if is_dst else 22
                else:
                    return None
                return start, end

            # Check if a UTC hour falls within a (start, end) window that may wrap midnight.
            def _in_window(utc_hour: int, start: int, end: int) -> bool:
                if start < end:
                    return start <= utc_hour < end
                # wraps midnight (e.g. Sydney 21→5)
                return utc_hour >= start or utc_hour < end

            for sess in sessions:
                # Overlap sessions: open only when BOTH underlying sessions are open.
                # overlap_tl = Tokyo × London (~7-9 UTC summer / 8-9 winter)
                # overlap_ln = London × New York (~12-16 UTC summer / 13-17 winter)
                if sess in ("overlap_tl", "overlap_ln"):
                    if sess == "overlap_tl":
                        pair = ("tokyo", "london")
                    else:
                        pair = ("london", "newyork")
                    windows = []
                    for sub in pair:
                        w = _base_window(sub)
                        if w is None:
                            windows = []
                            break
                        windows.append(w)
                    if len(windows) == 2:
                        # Intersection of the two UTC windows:
                        s0, e0 = windows[0]
                        s1, e1 = windows[1]
                        # For non-wrapping windows, intersection = max(start) to min(end)
                        # (all overlap pairs here are non-wrapping in UTC, so simple min/max works)
                        ov_start = max(s0, s1)
                        ov_end = min(e0, e1)
                        if ov_start < ov_end and _in_window(utc_h, ov_start, ov_end):
                            in_session = True
                            break
                    continue

                w = _base_window(sess)
                if w is None:
                    continue
                start, end = w
                if _in_window(utc_h, start, end):
                    in_session = True
                    break

            if not in_session:
                return False, f"Outside active trading sessions ({active_sessions})"

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


def near_high_impact_news(minutes: int = 15) -> tuple[bool, str]:
    """Check economic calendar for high-impact events within `minutes` window.

    Returns (is_blackout, reason). Checks BOTH:
    - Pre-event: high-impact event within next `minutes` minutes
    - Post-event: high-impact event released within last `minutes` minutes
      (post-release volatility can cause 30-50 pip spikes)
    """
    if not settings.avoid_high_impact_news:
        return False, "disabled"
    try:
        from news_service import economic_calendar
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            cal = loop.run_until_complete(economic_calendar())
        finally:
            loop.close()
        now = __import__("time").time()
        for event in cal[:20]:
            impact = str(event.get("impact", "")).lower()
            if impact != "high":
                continue
            ev_time = event.get("time") or event.get("date") or event.get("publishedAt")
            if not ev_time:
                continue
            try:
                from datetime import datetime, timezone
                dt = datetime.fromisoformat(str(ev_time).replace("Z", "+00:00"))
                secs = dt.timestamp()
            except Exception:  # noqa: BLE001
                continue
            delta = secs - now
            # pre-event: upcoming within `minutes`
            if 0 <= delta <= minutes * 60:
                name = event.get("event", event.get("title", "event"))
                return True, f"high-impact {name} in <{minutes} min"
            # post-event: released within last `minutes` (volatility window)
            if -minutes * 60 <= delta < 0:
                name = event.get("event", event.get("title", "event"))
                return True, f"high-impact {name} released {abs(int(delta/60))}m ago"
        return False, "ok"
    except Exception as exc:  # noqa: BLE001
        log.debug("news blackout check failed: %s", exc)
        return False, "check failed"
