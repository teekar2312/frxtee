import { NextRequest, NextResponse } from "next/server";
import {
  basePriceFor,
  pipFor,
  type BacktestSummary,
  type BacktestTrade,
} from "@/lib/trading-data";
import { proxyBackend, passthroughQuery } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

function seeded(str: string) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h += 0x6d2b79f5;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const symbol = searchParams.get("symbol") ?? "EURUSD";
  const trades = parseInt(searchParams.get("trades") ?? "120");

  // Try Python backend (real historical replay) first
  const qs = passthroughQuery(req);
  const r = await proxyBackend<{
    summary: BacktestSummary;
    trades: BacktestTrade[];
    equityCurve: { i: number; equity: number }[];
  }>(`/api/trading/backtest?${qs}`, {}, 5000);
  if (r.data) {
    return NextResponse.json({ ...r.data, demo: false });
  }

  // Fallback: deterministic mock backtest
  const rnd = seeded(symbol + trades);
  const base = basePriceFor(symbol);
  const pip = pipFor(symbol);

  const list: BacktestTrade[] = [];
  let equity = 10000;
  const equityCurve: { i: number; equity: number }[] = [{ i: 0, equity }];
  let peak = equity;
  let maxDD = 0;
  let wins = 0;
  let grossWin = 0;
  let grossLoss = 0;
  const startTime = Date.now() - trades * 6 * 3600 * 1000;

  for (let i = 1; i <= trades; i++) {
    const side: BacktestTrade["side"] = rnd() > 0.5 ? "BUY" : "SELL";
    const entry = base + (rnd() - 0.5) * pip * 30;
    const slPips = 5 + Math.floor(rnd() * 11);
    const isWin = rnd() < 0.58;
    const pips = isWin ? slPips * 1.5 : -slPips;
    const exit = side === "BUY" ? entry + pips * pip : entry - pips * pip;
    const pnl = pips * 1 * (symbol.includes("JPY") || symbol.includes("XAU") ? 8 : 10);
    equity += pnl;
    if (equity > peak) peak = equity;
    const dd = (peak - equity) / peak;
    if (dd > maxDD) maxDD = dd;
    if (isWin) {
      wins++;
      grossWin += pnl;
    } else {
      grossLoss += Math.abs(pnl);
    }
    list.push({
      id: i,
      symbol,
      side,
      entry,
      exit,
      openTime: new Date(startTime + i * 6 * 3600 * 1000).toISOString(),
      closeTime: new Date(startTime + (i + 0.5) * 6 * 3600 * 1000).toISOString(),
      pnl,
      pips,
      pipsR: pips / slPips,
    });
    equityCurve.push({ i, equity });
  }

  const winRate = (wins / trades) * 100;
  const profitFactor = grossLoss === 0 ? grossWin : grossWin / grossLoss;
  const avgWin = wins ? grossWin / wins : 0;
  const avgLoss = trades - wins ? grossLoss / (trades - wins) : 0;
  const expectancy =
    (winRate / 100) * avgWin - (1 - winRate / 100) * avgLoss;
  const sharpe = 1.1 + rnd() * 0.9;

  const summary: BacktestSummary = {
    netProfit: equity - 10000,
    totalTrades: trades,
    winRate,
    profitFactor,
    maxDrawdown: maxDD * 100,
    sharpe,
    avgWin,
    avgLoss,
    expectancy,
  };

  return NextResponse.json({ summary, trades: list.slice(-60), equityCurve, demo: true });
}
