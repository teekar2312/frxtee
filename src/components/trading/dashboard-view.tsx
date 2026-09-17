"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Brain,
  TrendingUp,
  Wallet,
  Target,
  ShieldCheck,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/utils";
import {
  AI_PROVIDERS,
  fmtMoney,
  fmtPct,
  fmtPrice,
  TRADING_PAIRS,
} from "@/lib/trading-data";
import { usePositions, useTicks, useAnalysis, useCandles } from "@/lib/trading-hooks";
import { useTradingStore, useActiveProvider } from "@/lib/trading-store";
import { CandleChart } from "./candle-chart";
import { StatTile, BadgeTone, SectionHeader } from "./primitives";

function equityCurve() {
  let v = 10000;
  const out: { i: number; v: number }[] = [];
  for (let i = 0; i < 48; i++) {
    v += (Math.sin(i / 3) + (Math.random() - 0.45)) * 60;
    out.push({ i, v: Math.round(v) });
  }
  return out;
}

export function DashboardView() {
  const { data: tickData } = useTicks(true);
  const { data: posData } = usePositions();
  const symbols = useTradingStore((s) => s.symbols);
  const timeframes = useTradingStore((s) => s.timeframes);
  const aiProvider = useActiveProvider();
  const equity = useTradingStore((s) => s.accountEquity);
  const balance = useTradingStore((s) => s.accountBalance);
  const autoTrade = useTradingStore((s) => s.autoTradeMode);
  const dailyTarget = useTradingStore((s) => s.dailyTarget);
  const dailyRisk = useTradingStore((s) => s.dailyRiskLimit);

  const positions = posData?.positions ?? [];
  const floatingPnl = positions.reduce((a, p) => a + p.profit, 0);
  const dayPnl = floatingPnl + 142.6;

  const mainSymbol = symbols[0] ?? "EURUSD";
  const mainTf = timeframes[0] ?? "M15";

  const curve = React.useMemo(() => equityCurve(), []);
  const tick = tickData?.ticks.find((t) => t.symbol === mainSymbol);

  const { data: analysisData } = useAnalysis(mainSymbol, aiProvider.id);

  return (
    <div className="space-y-3">
      {/* top stat row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        <StatTile
          label="Equity"
          value={fmtMoney(equity + floatingPnl)}
          sub={`Bal ${fmtMoney(balance)}`}
          tone={floatingPnl >= 0 ? "up" : "down"}
        />
        <StatTile
          label="Floating P&L"
          value={fmtMoney(floatingPnl)}
          sub={`${positions.length} open`}
          tone={floatingPnl >= 0 ? "up" : "down"}
        />
        <StatTile
          label="Day P&L"
          value={fmtMoney(dayPnl)}
          sub={fmtPct((dayPnl / balance) * 100)}
          tone={dayPnl >= 0 ? "up" : "down"}
        />
        <StatTile
          label="Daily Target"
          value={fmtPct(dailyTarget)}
          sub={`${fmtMoney((balance * dailyTarget) / 100)} / day`}
          tone="warn"
        />
        <StatTile
          label="Daily Risk"
          value={`${((dayPnl < 0 ? Math.abs(dayPnl) : 0) / balance * 100).toFixed(2)}%`}
          sub={`Limit ${fmtPct(dailyRisk)}`}
          tone="warn"
        />
        <StatTile
          label="AI Engine"
          value={autoTrade ? "ACTIVE" : "STANDBY"}
          sub={aiProvider.name}
          tone={autoTrade ? "up" : "default"}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* chart + positions */}
        <div className="lg:col-span-2 space-y-3">
          <Card className="p-3">
            <SectionHeader
              title={`${TRADING_PAIRS.find((p) => p.symbol === mainSymbol)?.display ?? mainSymbol} · ${mainTf}`}
              desc={
                tick
                  ? `Bid ${fmtPrice(tick.bid, tick.digits)} · Ask ${fmtPrice(
                      tick.ask,
                      tick.digits
                    )} · Spread ${tick.spreadPips.toFixed(1)}p`
                  : "—"
              }
              icon={TrendingUp}
              right={
                <div className="flex items-center gap-2">
                  {autoTrade ? (
                    <BadgeTone tone="up">
                      <Zap className="h-2.5 w-2.5 mr-1" /> AI Auto
                    </BadgeTone>
                  ) : null}
                  <Badge variant="outline" className="text-[10px]">
                    FINEX · 1:500
                  </Badge>
                </div>
              }
            />
            <ChartForSymbol symbol={mainSymbol} tf={mainTf} analysis={analysisData?.analysis} />
          </Card>

          <Card className="p-3">
            <SectionHeader
              title="Open Positions"
              desc={`${positions.length} / 3 · max concurrent per risk rule`}
              icon={Activity}
            />
            <PositionsTable />
          </Card>
        </div>

        {/* right column */}
        <div className="space-y-3">
          <Card className="p-3">
            <SectionHeader title="Equity Curve (48h)" icon={Wallet} />
            <ResponsiveContainer width="100%" height={120}>
              <AreaChart data={curve} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--success)" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="var(--success)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="i" hide />
                <YAxis
                  domain={["dataMin", "dataMax"]}
                  orientation="right"
                  tick={{ fontSize: 9, fill: "var(--muted-foreground)" }}
                  axisLine={false}
                  tickLine={false}
                  width={48}
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
                <Area
                  type="monotone"
                  dataKey="v"
                  stroke="var(--success)"
                  strokeWidth={1.5}
                  fill="url(#eq)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </Card>

          <Card className="p-3">
            <SectionHeader
              title="AI Signal"
              desc={`${aiProvider.name} · ${aiProvider.model}`}
              icon={Brain}
              right={
                analysisData?.analysis ? (
                  <SignalBadge signal={analysisData.analysis.signal} />
                ) : null
              }
            />
            {analysisData?.analysis ? (
              <AnalysisMini a={analysisData.analysis} />
            ) : (
              <div className="h-40 grid place-items-center text-xs text-muted-foreground">
                Analyzing {mainSymbol}…
              </div>
            )}
          </Card>

          <div className="grid grid-cols-2 gap-2">
            <StatTile label="Risk/Reward" value="1 : 1.5" sub="configured" icon={Target} className="" />
            <StatTile label="Max Drawdown" value="-2.4%" sub="today" tone="down" />
          </div>
        </div>
      </div>

      {/* quick links */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] text-muted-foreground mr-1">Quick:</span>
          <Badge variant="secondary" className="text-[10px] gap-1">
            <ShieldCheck className="h-3 w-3" /> Risk OK
          </Badge>
          <Badge variant="secondary" className="text-[10px] gap-1">
            <Target className="h-3 w-3" /> Trailing ON
          </Badge>
          <Badge variant="secondary" className="text-[10px] gap-1">
            <Activity className="h-3 w-3" /> {symbols.length} pairs · {timeframes.length} TF
          </Badge>
          <span className="text-[11px] text-muted-foreground ml-auto">
            AI providers: {AI_PROVIDERS.map((p) => p.name).join(" · ")}
          </span>
        </div>
      </Card>
    </div>
  );
}

function ChartForSymbol({
  symbol,
  tf,
  analysis,
}: {
  symbol: string;
  tf: string;
  analysis?: ReturnType<typeof Object>;
}) {
  const { data } = useCandles(symbol, tf as any, 120);
  return (
    <CandleChart
      candles={data?.candles ?? []}
      height={300}
      entry={(analysis as any)?.suggestedEntry}
      sl={(analysis as any)?.suggestedSL}
      tp={(analysis as any)?.suggestedTP}
    />
  );
}

function PositionsTable() {
  const { data } = usePositions();
  const positions = data?.positions ?? [];
  if (positions.length === 0)
    return (
      <div className="h-24 grid place-items-center text-xs text-muted-foreground">
        No open positions
      </div>
    );
  return (
    <div className="max-h-72 overflow-y-auto scroll-thin -mx-1">
      <table className="w-full text-xs">
        <thead className="text-[10px] uppercase text-muted-foreground sticky top-0 bg-card">
          <tr>
            <th className="text-left font-medium px-2 py-1.5">Ticket</th>
            <th className="text-left font-medium px-2 py-1.5">Symbol</th>
            <th className="text-left font-medium px-2 py-1.5">Type</th>
            <th className="text-right font-medium px-2 py-1.5">Vol</th>
            <th className="text-right font-medium px-2 py-1.5">Open</th>
            <th className="text-right font-medium px-2 py-1.5">Current</th>
            <th className="text-right font-medium px-2 py-1.5">Pips</th>
            <th className="text-right font-medium px-2 py-1.5">P&L</th>
            <th className="text-left font-medium px-2 py-1.5">Src</th>
          </tr>
        </thead>
        <tbody className="tnum">
          {positions.map((p) => (
            <tr key={p.ticket} className="border-t hover:bg-muted/40">
              <td className="px-2 py-1.5 text-muted-foreground">#{p.ticket}</td>
              <td className="px-2 py-1.5 font-medium">{p.symbol}</td>
              <td className="px-2 py-1.5">
                <span
                  className={cn(
                    "font-medium",
                    p.type === "BUY" ? "text-success" : "text-danger"
                  )}
                >
                  {p.type === "BUY" ? (
                    <ArrowUpRight className="inline h-3 w-3" />
                  ) : (
                    <ArrowDownRight className="inline h-3 w-3" />
                  )}{" "}
                  {p.type}
                </span>
              </td>
              <td className="px-2 py-1.5 text-right">{p.volume.toFixed(2)}</td>
              <td className="px-2 py-1.5 text-right">
                {fmtPrice(p.openPrice, p.symbol.includes("JPY") ? 3 : 5)}
              </td>
              <td className="px-2 py-1.5 text-right">
                {fmtPrice(p.currentPrice, p.symbol.includes("JPY") ? 3 : 5)}
              </td>
              <td
                className={cn(
                  "px-2 py-1.5 text-right",
                  p.pips >= 0 ? "text-success" : "text-danger"
                )}
              >
                {p.pips >= 0 ? "+" : ""}
                {p.pips.toFixed(1)}
              </td>
              <td
                className={cn(
                  "px-2 py-1.5 text-right font-medium",
                  p.profit >= 0 ? "text-success" : "text-danger"
                )}
              >
                {fmtMoney(p.profit)}
              </td>
              <td className="px-2 py-1.5">
                {p.comment === "AI:auto" ? (
                  <BadgeTone tone="up">AI</BadgeTone>
                ) : (
                  <BadgeTone tone="neutral">M</BadgeTone>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SignalBadge({ signal }: { signal: string }) {
  const tone =
    signal.includes("BUY") ? "up" : signal.includes("SELL") ? "down" : "neutral";
  return <BadgeTone tone={tone as any}>{signal}</BadgeTone>;
}

function AnalysisMini({ a }: { a: any }) {
  const top = (a.dimensions ?? []).slice(0, 4);
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground leading-snug line-clamp-3">
        {a.summary}
      </p>
      <div className="grid grid-cols-2 gap-1.5">
        {top.map((d: any) => (
          <div key={d.id} className="rounded-md border bg-muted/30 p-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground leading-tight line-clamp-2">{d.label}</span>
              <span
                className={cn(
                  "text-[10px] font-semibold tnum",
                  d.score > 55 ? "text-success" : d.score < 45 ? "text-danger" : "text-muted-foreground"
                )}
              >
                {d.score}
              </span>
            </div>
            <div className="h-1 rounded-full bg-muted overflow-hidden mt-1">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${d.score}%`,
                  background: d.score > 55 ? "var(--success)" : d.score < 45 ? "var(--danger)" : "var(--muted-foreground)",
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <Separator />
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-[10px] text-muted-foreground">Entry</div>
          <div className="text-xs font-semibold tnum">
            {fmtPrice(a.suggestedEntry, a.symbol?.includes("JPY") ? 3 : 5)}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground">SL</div>
          <div className="text-xs font-semibold tnum text-danger">
            {fmtPrice(a.suggestedSL, a.symbol?.includes("JPY") ? 3 : 5)}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground">TP</div>
          <div className="text-xs font-semibold tnum text-success">
            {fmtPrice(a.suggestedTP, a.symbol?.includes("JPY") ? 3 : 5)}
          </div>
        </div>
      </div>
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-muted-foreground">Confidence</span>
        <span className="font-semibold tnum">{a.confidence}%</span>
      </div>
    </div>
  );
}
