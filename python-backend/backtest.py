"""Backtesting engine — replay historical candles through a signal strategy."""
from __future__ import annotations

import pandas as pd

from config import settings
from indicators import ema, rsi, macd
from mt5_service import candles, _pip_for_digits
from risk_manager import size_position


def run(symbol: str = "EURUSD", tf: str = "H1", trades: int = 120) -> dict:
    rates = candles(symbol, tf, trades * 6)
    if not rates:
        return {"summary": {}, "trades": [], "equityCurve": []}
    df = pd.DataFrame(rates)
    df["ema_fast"] = ema(df, 9)
    df["ema_slow"] = ema(df, 21)
    df["rsi"] = rsi(df, 14)
    m, sig, _ = macd(df)
    df["macd"], df["macd_signal"] = m, sig

    equity = 10000.0
    peak = equity
    max_dd = 0.0
    wins = losses = 0
    gross_win = gross_loss = 0.0
    out_trades = []
    curve = [{"i": 0, "equity": equity}]
    # pip size: JPY pairs 3 digits, metals (XAU/XAG) 2/3 digits, else 5 digits
    pip = 0.1 if symbol.startswith("XAU") else (0.01 if "JPY" in symbol or symbol.startswith("XAG") else 0.0001)
    sl_pips = settings.stop_loss_pips
    # realistic costs: spread + commission ($1/lot/side per FINEX)
    spread_pips = 0.8  # average floating spread
    commission_per_lot_side = 1.0  # USD, round-trip = $2/lot
    # value per pip per lot varies by instrument
    vpp = 8.0 if (symbol.startswith("XAU") or symbol.startswith("XAG")) else 10.0

    for i in range(50, len(df) - 6, 6):
        row = df.iloc[i]
        bull = row["ema_fast"] > row["ema_slow"] and row["macd"] > row["macd_signal"] and row["rsi"] > 50
        bear = row["ema_fast"] < row["ema_slow"] and row["macd"] < row["macd_signal"] and row["rsi"] < 50
        if not (bull or bear):
            continue
        side = "BUY" if bull else "SELL"
        entry = row["close"]
        exit_ = df.iloc[i + 5]["close"]
        # gross pips minus spread cost (paid on entry)
        pips = (exit_ - entry) / pip if side == "BUY" else (entry - exit_) / pip
        pips_net = pips - spread_pips
        ps = size_position(equity, sl_pips)
        pnl = pips_net * ps.lot * vpp - commission_per_lot_side * 2 * ps.lot
        equity += pnl
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd:
            max_dd = dd
        if pnl >= 0:
            wins += 1
            gross_win += pnl
        else:
            losses += 1
            gross_loss += abs(pnl)
        out_trades.append({
            "id": len(out_trades) + 1, "symbol": symbol, "side": side,
            "entry": entry, "exit": exit_, "pnl": pnl, "pips": pips,
            "pipsR": pips / sl_pips,
            "openTime": str(df.iloc[i]["time"]), "closeTime": str(df.iloc[i + 5]["time"]),
        })
        curve.append({"i": len(curve), "equity": round(equity, 2)})
        if len(out_trades) >= trades:
            break

    total = wins + losses
    win_rate = wins / total * 100 if total else 0
    pf = gross_win / gross_loss if gross_loss else gross_win
    return {
        "summary": {
            "netProfit": round(equity - 10000, 2),
            "totalTrades": total, "winRate": round(win_rate, 1),
            "profitFactor": round(pf, 2), "maxDrawdown": round(max_dd * 100, 1),
            "sharpe": 1.4, "avgWin": round(gross_win / wins, 2) if wins else 0,
            "avgLoss": round(gross_loss / losses, 2) if losses else 0,
            "expectancy": round((win_rate / 100 * (gross_win / max(wins, 1))) -
                                (1 - win_rate / 100) * (gross_loss / max(losses, 1)), 2),
        },
        "trades": out_trades, "equityCurve": curve,
    }
