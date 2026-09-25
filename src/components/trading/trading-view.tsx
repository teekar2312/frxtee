"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import {
  ArrowDownRight,
  ArrowUpRight,
  Bot,
  Crosshair,
  Crosshair as CrosshairIcon,
  Layers,
  ListChecks,
  RefreshCw,
  ScrollText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fmtMoney,
  fmtPrice,
  pipFor,
  TIMEFRAMES,
  TRADING_PAIRS,
  TRADING_SESSIONS,
  type Timeframe,
} from "@/lib/trading-data";
import { useQueryClient } from "@tanstack/react-query";
import { useTicks, usePositions, useCandles } from "@/lib/trading-hooks";
import { useTradingStore } from "@/lib/trading-store";
import { CandleChart } from "./candle-chart";
import {
  AutoManualRow,
  BadgeTone,
  Chip,
  ModeToggle,
  SectionHeader,
  SwitchRow,
} from "./primitives";

export function TradingView() {
  const store = useTradingStore();
  const { symbols, timeframes, sessions } = store;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-4 gap-3">
      {/* Left: selections */}
      <div className="xl:col-span-1 space-y-3">
        <Card className="p-3">
          <SectionHeader
            title="Pairs"
            desc="Auto by AI or manual · 1 or more"
            icon={Layers}
            right={
              <ModeToggle
                auto={store.autoPair}
                onAuto={() => {
                  store.setAutoPair(true);
                  store.setAutoSymbols();
                  toast.success("AI selected optimal pairs");
                }}
                onManual={() => store.setAutoPair(false)}
              />
            }
          />
          <div className="flex flex-wrap gap-1.5">
            {TRADING_PAIRS.map((p) => (
              <Chip
                key={p.symbol}
                active={symbols.includes(p.symbol)}
                onClick={() => store.toggleSymbol(p.symbol)}
                title={`${p.category} · spread ${p.pip === 0.01 ? "0.5p+" : "0.5p+"}`}
              >
                {p.display}
              </Chip>
            ))}
          </div>
          <div className="text-[10px] text-muted-foreground mt-2">
            {symbols.length} selected · {symbols.join(", ") || "none"}
          </div>
        </Card>

        <Card className="p-3">
          <SectionHeader
            title="Timeframes"
            desc="1 or more · auto or manual"
            icon={CrosshairIcon}
            right={
              <ModeToggle
                auto={store.autoTimeframe}
                onAuto={() => {
                  store.setAutoTimeframe(true);
                  store.setAutoTimeframes();
                  toast.success("AI selected optimal timeframes");
                }}
                onManual={() => store.setAutoTimeframe(false)}
              />
            }
          />
          <div className="flex flex-wrap gap-1.5">
            {TIMEFRAMES.map((t) => (
              <Chip
                key={t.value}
                active={timeframes.includes(t.value as Timeframe)}
                onClick={() => store.toggleTimeframe(t.value as Timeframe)}
              >
                {t.label}
              </Chip>
            ))}
          </div>
        </Card>

        <Card className="p-3">
          <SectionHeader
            title="Trading Sessions"
            desc="1 or more · auto or manual"
            icon={ScrollText}
            right={
              <ModeToggle
                auto={store.autoSession}
                onAuto={() => {
                  store.setAutoSession(true);
                  store.setAutoSessions();
                  toast.success("AI selected all sessions");
                }}
                onManual={() => store.setAutoSession(false)}
              />
            }
          />
          <div className="grid grid-cols-2 gap-1.5">
            {TRADING_SESSIONS.map((s) => (
              <Chip
                key={s.id}
                active={sessions.includes(s.id)}
                onClick={() => store.toggleSession(s.id)}
                title={`${s.tz} · UTC ${s.utcStart}:00–${s.utcEnd}:00`}
              >
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: s.color }}
                />
                {s.name}
              </Chip>
            ))}
          </div>
          <Separator className="my-2" />
          <SwitchRow
            label="Close all at session end"
            desc="Auto-close positions when selected session(s) end — avoids overnight gap exposure"
            checked={store.closeAtSessionEnd}
            onChange={(v) => {
              store.setCloseAtSessionEnd(v);
              fetch("/api/trading/ai/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ close_at_session_end: v }),
              }).then(() => {
                toast.success(
                  v
                    ? "🔚 Positions will auto-close when session ends"
                    : "Positions kept open after session ends"
                );
              }).catch(() => {
                toast.error("Failed to sync close-at-session-end to backend");
              });
            }}
          />
        </Card>

        <Card className="p-3 space-y-1">
          <SectionHeader title="Trading Mode" icon={Bot} />
          <AutoManualRow
            label="Auto Trading"
            desc="AI executes signals automatically"
            auto={store.autoTradeMode}
            onAuto={() => {
              store.setAutoTradeMode(true);
              // Push to backend so _auto_trade_loop activates
              fetch("/api/trading/ai/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  auto_trade_mode: true,
                  auto_trade_symbols: store.symbols.join(","),
                  auto_trade_min_confidence: store.autoTradeMinConfidence,
                  active_provider: store.aiProvider,
                  active_sessions: store.sessions.join(","),
                  trading_strategy: store.tradingStrategy,
                }),
              }).then(() => {
                toast.success("🤖 Auto-trading ENABLED — backend will execute AI signals automatically");
              }).catch(() => {
                toast.error("Failed to enable auto-trade on backend — check connection");
              });
            }}
            onManual={() => {
              store.setAutoTradeMode(false);
              fetch("/api/trading/ai/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ auto_trade_mode: false }),
              });
              toast.info("Manual mode — you confirm each order");
            }}
          />
          <Separator />
          {/* Strategy selector */}
          <div className="py-1.5">
            <Label className="text-[11px] text-muted-foreground mb-1 block">
              Trading Strategy
            </Label>
            <Select
              value={store.tradingStrategy}
              onValueChange={(v) => {
                store.setTradingStrategy(v);
                // Push to backend
                fetch("/api/trading/ai/config", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ trading_strategy: v }),
                }).then(() => {
                  toast.success(v === "auto"
                    ? "Strategy: AI auto-select (based on market conditions)"
                    : `Strategy: ${v}`);
                });
              }}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto" className="text-xs">
                  🤖 Auto (AI selects based on market)
                </SelectItem>
                <SelectItem value="ma_ribbon" className="text-xs">
                  📊 MA Ribbon (5-8-13 SMA)
                </SelectItem>
                <SelectItem value="momentum_scalp" className="text-xs">
                  ⚡ Momentum Scalping (RSI+MACD)
                </SelectItem>
                <SelectItem value="pivot_bounce" className="text-xs">
                  🎯 Pivot Point Bounce
                </SelectItem>
                <SelectItem value="ema_crossover" className="text-xs">
                  📈 EMA Crossover (9/21 + ATR)
                </SelectItem>
                <SelectItem value="rmi_trend_sync" className="text-xs">
                  🔄 RMI Trend Sync (RSI + Supertrend)
                </SelectItem>
                <SelectItem value="linreg_channel" className="text-xs">
                  📏 Linear Regression Channel
                </SelectItem>
                <SelectItem value="ema_rsi_filter" className="text-xs">
                  🔀 EMA/RSI Filter
                </SelectItem>
              </SelectContent>
            </Select>
            <p className="text-[10px] text-muted-foreground mt-1">
              {store.tradingStrategy === "auto"
                ? "AI analyzes market conditions and selects optimal strategy"
                : "Strategy signals override AI — uses indicator-based rules only"}
            </p>
          </div>
          <Separator />
          <SwitchRow
            label="Avoid high-impact news"
            desc="Pause new entries near tier-1 events"
            checked={store.avoidNews}
            onChange={store.setAvoidNews}
          />
        </Card>
      </div>

      {/* Middle: chart + order ticket */}
      <div className="xl:col-span-2 space-y-3">
        <ChartPanel />
        <PositionsCard />
      </div>

      {/* Right: order ticket */}
      <div className="xl:col-span-1">
        <OrderTicket />
      </div>
    </div>
  );
}

function ChartPanel() {
  const symbols = useTradingStore((s) => s.symbols);
  const timeframes = useTradingStore((s) => s.timeframes);
  const symbol = symbols[0] ?? "EURUSD";
  const tf = (timeframes[0] ?? "M15") as Timeframe;
  const { data } = useCandles(symbol, tf, 120);
  const { data: tickData } = useTicks();
  const tick = tickData?.ticks.find((t) => t.symbol === symbol);
  const p = TRADING_PAIRS.find((x) => x.symbol === symbol);
  const digits = p?.digits ?? 5;

  return (
    <Card className="p-3">
      <SectionHeader
        title={`${p?.display ?? symbol}`}
        desc={`${tf} · ${tick ? `bid ${fmtPrice(tick.bid, digits)} ask ${fmtPrice(tick.ask, digits)} spread ${tick.spreadPips.toFixed(1)}p` : "—"}`}
        icon={Crosshair}
        right={<Badge variant="outline" className="text-[10px]">live · demo</Badge>}
      />
      <CandleChart candles={data?.candles ?? []} height={300} />
    </Card>
  );
}

function OrderTicket() {
  const symbols = useTradingStore((s) => s.symbols);
  const queryClient = useQueryClient();
  const [symbol, setSymbol] = React.useState(symbols[0] ?? "EURUSD");
  const [side, setSide] = React.useState<"BUY" | "SELL">("BUY");
  const [volume, setVolume] = React.useState(0.1);
  const [slPips, setSlPips] = React.useState(10);
  const rr = useTradingStore((s) => s.rrRatio);
  const riskPct = useTradingStore((s) => s.riskPerTrade);
  const equity = useTradingStore((s) => s.accountEquity);
  const autoTrade = useTradingStore((s) => s.autoTradeMode);
  const { data: tickData } = useTicks();
  const tick = tickData?.ticks.find((t) => t.symbol === symbol);
  const p = TRADING_PAIRS.find((x) => x.symbol === symbol);
  const digits = p?.digits ?? 5;
  const pip = pipFor(symbol);

  const riskAmount = (equity * riskPct) / 100;
  const autoLot = Math.max(0.01, +(riskAmount / (slPips * 10)).toFixed(2));
  const tpPips = slPips * rr;
  const price = side === "BUY" ? tick?.ask : tick?.bid;

  const [submitting, setSubmitting] = React.useState(false);

  async function submit() {
    if (!price) {
      toast.error("No live price for symbol");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch("/api/trading/order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          side,
          volume,
          slPips,
          comment: autoTrade ? "AI:auto" : "manual",
        }),
      });
      const data = await res.json();
      if (data.ok) {
        toast.success(
          `${autoTrade ? "[AI] " : ""}${side} ${symbol} ${volume} lot @ ${fmtPrice(
            data.price ?? price,
            digits
          )} | SL ${slPips}p TP ${tpPips.toFixed(1)}p`,
          { description: `Ticket #${data.ticket} · Risk ${fmtMoney(riskAmount)} · RR 1:${rr}` }
        );
        // refresh positions list
        queryClient.invalidateQueries({ queryKey: ["positions"] });
      } else {
        toast.error(`Order rejected: ${data.error ?? "unknown"}`);
      }
    } catch {
      toast.error("Order failed — network error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="p-3 space-y-3 sticky top-2">
      <SectionHeader title="Order Ticket" desc="Manual execution" icon={ListChecks} />
      <div className="space-y-2">
        <div>
          <Label className="text-[11px] text-muted-foreground">Symbol</Label>
          <div className="grid grid-cols-2 gap-1.5 mt-1 max-h-32 overflow-y-auto scroll-thin">
            {TRADING_PAIRS.map((pp) => (
              <Chip
                key={pp.symbol}
                active={symbol === pp.symbol}
                onClick={() => setSymbol(pp.symbol)}
                className="justify-center"
              >
                {pp.display}
              </Chip>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Button
            size="sm"
            variant={side === "BUY" ? "default" : "outline"}
            className={cn(
              "h-9",
              side === "BUY"
                ? "bg-success text-success-foreground hover:bg-success/90"
                : "text-success"
            )}
            onClick={() => setSide("BUY")}
          >
            <ArrowUpRight className="h-4 w-4" /> BUY
          </Button>
          <Button
            size="sm"
            variant={side === "SELL" ? "default" : "outline"}
            className={cn(
              "h-9",
              side === "SELL"
                ? "bg-danger text-danger-foreground hover:bg-danger/90"
                : "text-danger"
            )}
            onClick={() => setSide("SELL")}
          >
            <ArrowDownRight className="h-4 w-4" /> SELL
          </Button>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <Label className="text-[11px] text-muted-foreground">Volume (lot)</Label>
            <span className="text-xs font-medium tnum">{volume.toFixed(2)}</span>
          </div>
          <Slider
            value={[volume]}
            min={0.01}
            max={2}
            step={0.01}
            onValueChange={(v) => setVolume(v[0])}
            className="mt-1"
          />
          <div className="flex items-center gap-1 mt-1">
            <Button variant="outline" size="sm" className="h-6 text-[10px] flex-1" onClick={() => setVolume(autoLot)}>
              AI: {autoLot.toFixed(2)}
            </Button>
            {[0.01, 0.1, 0.5, 1].map((v) => (
              <Button key={v} variant="outline" size="sm" className="h-6 text-[10px] flex-1" onClick={() => setVolume(v)}>
                {v}
              </Button>
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <Label className="text-[11px] text-muted-foreground">Stop Loss (pips)</Label>
            <span className="text-xs font-medium tnum">{slPips}p</span>
          </div>
          <Slider
            value={[slPips]}
            min={5}
            max={15}
            step={1}
            onValueChange={(v) => setSlPips(v[0])}
            className="mt-1"
          />
          <div className="flex justify-between text-[9px] text-muted-foreground mt-0.5">
            <span>5p</span><span>10p</span><span>15p</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-md border bg-muted/30 p-2">
            <div className="text-[10px] text-muted-foreground">Take Profit</div>
            <div className="font-semibold tnum text-success">{tpPips.toFixed(1)}p</div>
          </div>
          <div className="rounded-md border bg-muted/30 p-2">
            <div className="text-[10px] text-muted-foreground">Risk Amount</div>
            <div className="font-semibold tnum">{fmtMoney(riskAmount)}</div>
          </div>
          <div className="rounded-md border bg-muted/30 p-2">
            <div className="text-[10px] text-muted-foreground">Entry</div>
            <div className="font-semibold tnum">{price ? fmtPrice(price, digits) : "—"}</div>
          </div>
          <div className="rounded-md border bg-muted/30 p-2">
            <div className="text-[10px] text-muted-foreground">RR Ratio</div>
            <div className="font-semibold tnum">1 : {rr}</div>
          </div>
        </div>

        <Button
          className="w-full h-10"
          size="sm"
          onClick={submit}
          disabled={!price || submitting}
        >
          {submitting
            ? "Sending order…"
            : `${side} ${symbol} · ${volume.toFixed(2)} lot`}
        </Button>
        {autoTrade ? (
          <div className="text-center">
            <BadgeTone tone="up">
              <Bot className="inline h-3 w-3 mr-1" /> AI auto-trade active
            </BadgeTone>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

function PositionsCard() {
  const { data } = usePositions();
  const queryClient = useQueryClient();
  const positions = data?.positions ?? [];

  const [closing, setClosing] = React.useState<number | null>(null);
  async function closePosition(ticket: number) {
    setClosing(ticket);
    try {
      const res = await fetch(`/api/trading/positions/${ticket}`, {
        method: "DELETE",
      });
      const d = await res.json();
      if (d.ok) {
        toast.success(`Closed #${ticket} @ market`);
        queryClient.invalidateQueries({ queryKey: ["positions"] });
      } else {
        toast.error(`Close failed: ${d.error ?? "unknown"}`);
      }
    } catch {
      toast.error("Close failed — network error");
    } finally {
      setClosing(null);
    }
  }

  return (
    <Card className="p-3">
      <SectionHeader
        title="Open Positions"
        desc={`${positions.length} / 3 concurrent`}
        icon={RefreshCw}
        right={
          <Button variant="ghost" size="sm" className="h-7 text-xs">
            <RefreshCw className="h-3 w-3 mr-1" /> Refresh
          </Button>
        }
      />
      {positions.length === 0 ? (
        <div className="h-20 grid place-items-center text-xs text-muted-foreground">
          No open positions
        </div>
      ) : (
        <div className="max-h-64 overflow-y-auto scroll-thin -mx-1">
          <table className="w-full text-xs">
            <thead className="text-[10px] uppercase text-muted-foreground sticky top-0 bg-card">
              <tr>
                <th className="text-left font-medium px-2 py-1.5">Symbol</th>
                <th className="text-left font-medium px-2 py-1.5">Side</th>
                <th className="text-right font-medium px-2 py-1.5">Vol</th>
                <th className="text-right font-medium px-2 py-1.5">Open</th>
                <th className="text-right font-medium px-2 py-1.5">SL</th>
                <th className="text-right font-medium px-2 py-1.5">TP</th>
                <th className="text-right font-medium px-2 py-1.5">Pips</th>
                <th className="text-right font-medium px-2 py-1.5">P&L</th>
                <th className="px-2 py-1.5"></th>
              </tr>
            </thead>
            <tbody className="tnum">
              {positions.map((p) => (
                <tr key={p.ticket} className="border-t hover:bg-muted/40">
                  <td className="px-2 py-1.5 font-medium">{p.symbol}</td>
                  <td className="px-2 py-1.5">
                    <span className={p.type === "BUY" ? "text-success" : "text-danger"}>
                      {p.type}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-right">{p.volume.toFixed(2)}</td>
                  <td className="px-2 py-1.5 text-right">
                    {fmtPrice(p.openPrice, p.symbol.includes("JPY") ? 3 : 5)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-danger">
                    {p.sl ? fmtPrice(p.sl, p.symbol.includes("JPY") ? 3 : 5) : "—"}
                  </td>
                  <td className="px-2 py-1.5 text-right text-success">
                    {p.tp ? fmtPrice(p.tp, p.symbol.includes("JPY") ? 3 : 5) : "—"}
                  </td>
                  <td className={cn("px-2 py-1.5 text-right", p.pips >= 0 ? "text-success" : "text-danger")}>
                    {p.pips >= 0 ? "+" : ""}
                    {p.pips.toFixed(1)}
                  </td>
                  <td className={cn("px-2 py-1.5 text-right font-medium", p.profit >= 0 ? "text-success" : "text-danger")}>
                    {fmtMoney(p.profit)}
                  </td>
                  <td className="px-2 py-1.5">
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 text-[10px] text-danger hover:text-danger"
                          disabled={closing === p.ticket}
                        >
                          {closing === p.ticket ? "…" : "Close"}
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Close position #{p.ticket}?</AlertDialogTitle>
                          <AlertDialogDescription>
                            This will close your {p.type} {p.symbol} {p.volume.toFixed(2)} lot
                            position at market price. Current P&L:{" "}
                            <span className={p.profit >= 0 ? "text-success font-semibold" : "text-danger font-semibold"}>
                              {fmtMoney(p.profit)}
                            </span>
                            . This action cannot be undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() => closePosition(p.ticket)}
                            className="bg-danger text-danger-foreground hover:bg-danger/90"
                          >
                            Close at market
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
