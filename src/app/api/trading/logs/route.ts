import { NextResponse } from "next/server";
import { type LogEntry } from "@/lib/trading-data";

export const dynamic = "force-dynamic";

function genLogs(): LogEntry[] {
  const now = Date.now();
  const base: Omit<LogEntry, "id" | "ts">[] = [
    { level: "INFO", source: "mt5", message: "Terminal path detected: C:\\Program Files\\FINEX MetaTrader 5\\terminal64.exe" },
    { level: "INFO", source: "mt5", message: "Login 5012**** @ FINEX-Real — authorized" },
    { level: "INFO", source: "engine", message: "AI engine initialized (provider=zai, model=glm-4.6)" },
    { level: "DEBUG", source: "indicators", message: "Computed EMA(20), RSI(14), MACD(12,26,9), ATR(14) on EURUSD M15" },
    { level: "INFO", source: "news", message: "Finnhub stream connected — 3 symbols subscribed" },
    { level: "WARN", source: "risk", message: "Daily risk usage at 2.1% / 3.0% — throttling new entries" },
    { level: "TRADE", source: "engine", message: "OPEN BUY EURUSD 0.10 @ 1.08642 | SL=1.08542 TP=1.08792 (AI:auto)" },
    { level: "TRADE", source: "engine", message: "OPEN SELL GBPJPY 0.10 @ 192.481 | SL=192.581 TP=192.331 (AI:auto)" },
    { level: "INFO", source: "trailing", message: "Trailing stop advanced on ticket #5000002 to 192.401 (+8 pips locked)" },
    { level: "ERROR", source: "news", message: "MARKETAUX rate-limit reached (429) — backing off 60s" },
    { level: "INFO", source: "backtest", message: "Backtest complete: 142 trades, PF 1.84, maxDD 6.2%" },
    { level: "WARN", source: "engine", message: "High-impact news (US CPI) within 5 min — new entries paused" },
    { level: "DEBUG", source: "ml", message: "Feature vector dim=64, inference latency=312ms" },
    { level: "INFO", source: "email", message: "Notification sent: Price alert EURUSD > 1.0880 triggered" },
    { level: "ERROR", source: "mt5", message: "Order send failed: invalid stops (retried, OK)" },
  ];
  return base.map((b, i) => ({
    ...b,
    id: `log-${i}`,
    ts: new Date(now - i * 47000).toISOString(),
  }));
}

export async function GET() {
  return NextResponse.json({ logs: genLogs(), demo: true });
}
