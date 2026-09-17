"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";
import { FlaskConical, Play, TrendingUp, Trophy } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fmtMoney,
  TRADING_PAIRS,
  TIMEFRAMES,
  type Timeframe,
} from "@/lib/trading-data";
import { useBacktest } from "@/lib/trading-hooks";
import { useTradingStore } from "@/lib/trading-store";
import { BadgeTone, SectionHeader, StatTile } from "./primitives";

export function BacktestView() {
  const indicators = useTradingStore((s) => s.indicators);
  const [symbol, setSymbol] = React.useState("EURUSD");
  const [tf, setTf] = React.useState<Timeframe>("H1");
  const [trades, setTrades] = React.useState(120);
  const [runId, setRunId] = React.useState(0);

  const { data, isFetching, refetch } = useBacktest(symbol, trades, tf);

  function run() {
    setRunId((x) => x + 1);
    refetch();
    toast.success(`Backtest started · ${symbol} ${tf} · ${trades} trades · ${indicators.length} indicators`);
  }

  const summary = data?.summary;
  const eq = data?.equityCurve ?? [];
  const list = data?.trades ?? [];

  return (
    <div className="space-y-3">
      <Card className="p-3">
        <SectionHeader
          title="Backtesting Engine"
          desc="Historical strategy simulation with selected indicators"
          icon={FlaskConical}
        />
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label className="text-[11px] text-muted-foreground">Symbol</label>
            <Select value={symbol} onValueChange={setSymbol}>
              <SelectTrigger className="h-8 w-[120px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TRADING_PAIRS.map((p) => (
                  <SelectItem key={p.symbol} value={p.symbol} className="text-xs">
                    {p.display}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-[11px] text-muted-foreground">Timeframe</label>
            <Select value={tf} onValueChange={(v) => setTf(v as Timeframe)}>
              <SelectTrigger className="h-8 w-[80px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIMEFRAMES.map((t) => (
                  <SelectItem key={t.value} value={t.value} className="text-xs">
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-[11px] text-muted-foreground">Trades</label>
            <Select value={String(trades)} onValueChange={(v) => setTrades(parseInt(v))}>
              <SelectTrigger className="h-8 w-[100px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[50, 120, 250, 500].map((n) => (
                  <SelectItem key={n} value={String(n)} className="text-xs">
                    {n}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="text-[11px] text-muted-foreground px-2 py-1.5 rounded-md border">
            {indicators.length} indicators active
          </div>
          <Button onClick={run} disabled={isFetching} className="h-8">
            <Play className="h-3.5 w-3.5 mr-1" />
            {isFetching ? "Running…" : "Run Backtest"}
          </Button>
        </div>
      </Card>

      {summary ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2">
            <StatTile label="Net Profit" value={fmtMoney(summary.netProfit)} tone={summary.netProfit >= 0 ? "up" : "down"} />
            <StatTile label="Total Trades" value={String(summary.totalTrades)} />
            <StatTile label="Win Rate" value={`${summary.winRate.toFixed(1)}%`} tone="up" />
            <StatTile label="Profit Factor" value={summary.profitFactor.toFixed(2)} tone={summary.profitFactor >= 1.5 ? "up" : "warn"} />
            <StatTile label="Max Drawdown" value={`-${summary.maxDrawdown.toFixed(1)}%`} tone="down" />
            <StatTile label="Sharpe" value={summary.sharpe.toFixed(2)} />
            <StatTile label="Avg Win" value={fmtMoney(summary.avgWin)} tone="up" />
            <StatTile label="Avg Loss" value={fmtMoney(-summary.avgLoss)} tone="down" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <Card className="p-3 lg:col-span-2">
              <SectionHeader title="Equity Curve" icon={TrendingUp} />
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={eq} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="bt" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="i" tick={{ fontSize: 9, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
                  <YAxis
                    orientation="right"
                    tick={{ fontSize: 9, fill: "var(--muted-foreground)" }}
                    axisLine={false}
                    tickLine={false}
                    width={56}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 6,
                      fontSize: 11,
                    }}
                    formatter={(v: number) => [fmtMoney(v), "Equity"]}
                    labelFormatter={() => ""}
                  />
                  <Area type="monotone" dataKey="equity" stroke="var(--primary)" strokeWidth={1.5} fill="url(#bt)" />
                </AreaChart>
              </ResponsiveContainer>
            </Card>

            <Card className="p-3">
              <SectionHeader title="Trade Stats" icon={Trophy} />
              <div className="space-y-1.5 text-xs">
                <Row k="Expectancy / trade" v={fmtMoney(summary.expectancy)} />
                <Row k="Gross Profit" v={fmtMoney(summary.avgWin * (summary.winRate / 100) * summary.totalTrades)} tone="up" />
                <Row k="Gross Loss" v={fmtMoney(-summary.avgLoss * (1 - summary.winRate / 100) * summary.totalTrades)} tone="down" />
                <Separator />
                <Row k="Winning trades" v={`${Math.round(summary.winRate / 100 * summary.totalTrades)}`} />
                <Row k="Losing trades" v={`${summary.totalTrades - Math.round(summary.winRate / 100 * summary.totalTrades)}`} />
                <Row k="Risk-adjusted return" v={`${summary.sharpe.toFixed(2)} Sharpe`} />
                <Row k="Recovery factor" v={`${(summary.netProfit / (summary.maxDrawdown * 100)).toFixed(2)}`} />
              </div>
            </Card>
          </div>

          <Card className="p-3">
            <SectionHeader title="Recent Trades" desc={`${list.length} shown`} />
            <div className="max-h-72 overflow-y-auto scroll-thin -mx-1">
              <table className="w-full text-xs">
                <thead className="text-[10px] uppercase text-muted-foreground sticky top-0 bg-card">
                  <tr>
                    <th className="text-left font-medium px-2 py-1.5">#</th>
                    <th className="text-left font-medium px-2 py-1.5">Side</th>
                    <th className="text-right font-medium px-2 py-1.5">Entry</th>
                    <th className="text-right font-medium px-2 py-1.5">Exit</th>
                    <th className="text-right font-medium px-2 py-1.5">Pips</th>
                    <th className="text-right font-medium px-2 py-1.5">P&L</th>
                    <th className="text-right font-medium px-2 py-1.5">R</th>
                    <th className="text-left font-medium px-2 py-1.5">Closed</th>
                  </tr>
                </thead>
                <tbody className="tnum">
                  {list.slice(-40).reverse().map((t) => (
                    <tr key={t.id} className="border-t hover:bg-muted/40">
                      <td className="px-2 py-1.5 text-muted-foreground">{t.id}</td>
                      <td className="px-2 py-1.5">
                        <span className={t.side === "BUY" ? "text-success" : "text-danger"}>
                          {t.side}
                        </span>
                      </td>
                      <td className="px-2 py-1.5 text-right">{t.entry.toFixed(t.symbol.includes("JPY") ? 3 : 5)}</td>
                      <td className="px-2 py-1.5 text-right">{t.exit.toFixed(t.symbol.includes("JPY") ? 3 : 5)}</td>
                      <td className={cn("px-2 py-1.5 text-right", t.pips >= 0 ? "text-success" : "text-danger")}>
                        {t.pips >= 0 ? "+" : ""}
                        {t.pips.toFixed(1)}
                      </td>
                      <td className={cn("px-2 py-1.5 text-right font-medium", t.pnl >= 0 ? "text-success" : "text-danger")}>
                        {fmtMoney(t.pnl)}
                      </td>
                      <td className={cn("px-2 py-1.5 text-right", t.pipsR >= 0 ? "text-success" : "text-danger")}>
                        {t.pipsR >= 0 ? "+" : ""}
                        {t.pipsR.toFixed(2)}R
                      </td>
                      <td className="px-2 py-1.5 text-muted-foreground text-[10px]">
                        {new Date(t.closeTime).toLocaleString("en-GB", {
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      ) : (
        <Card className="p-6 text-center text-sm text-muted-foreground">
          Configure parameters and run a backtest to see results.
        </Card>
      )}
    </div>
  );
}

function Row({ k, v, tone }: { k: string; v: string; tone?: "up" | "down" }) {
  const cls = tone === "up" ? "text-success" : tone === "down" ? "text-danger" : "text-foreground";
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{k}</span>
      <span className={cn("tnum", cls)}>{v}</span>
    </div>
  );
}
