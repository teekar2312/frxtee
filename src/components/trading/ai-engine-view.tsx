"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  Brain,
  Cpu,
  Gauge,
  LineChart,
  RefreshCw,
  Server,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  AI_PROVIDERS,
  ANALYSIS_DIMENSIONS,
  fmtPrice,
} from "@/lib/trading-data";
import { useAnalysis } from "@/lib/trading-hooks";
import { useTradingStore, useActiveProvider } from "@/lib/trading-store";
import { BadgeTone, SectionHeader, StatTile } from "./primitives";

export function AIEngineView() {
  const store = useTradingStore();
  const active = useActiveProvider();
  const symbol = store.symbols[0] ?? "EURUSD";
  const { data, isFetching, refetch } = useAnalysis(symbol, active.id);
  const a = data?.analysis;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
      {/* provider selection */}
      <div className="space-y-3">
        <Card className="p-3">
          <SectionHeader
            title="AI Provider"
            desc="Manual selection — choose the engine"
            icon={Cpu}
          />
          <div className="space-y-2">
            {AI_PROVIDERS.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  store.setAiProvider(p.id);
                  toast.success(`Switched to ${p.name}`);
                }}
                className={cn(
                  "w-full text-left rounded-lg border p-2.5 transition-colors",
                  active.id === p.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-muted/40"
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className={cn(
                        "h-7 w-7 rounded-md grid place-items-center text-[10px] font-bold",
                        active.id === p.id
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground"
                      )}
                    >
                      {p.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <div className="text-sm font-medium leading-tight">{p.name}</div>
                      <div className="text-[11px] text-muted-foreground leading-tight">
                        {p.model}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-muted-foreground tnum">
                      {p.latencyMs}ms
                    </span>
                    {active.id === p.id ? (
                      <BadgeTone tone="up">active</BadgeTone>
                    ) : null}
                  </div>
                </div>
                <div className="text-[11px] text-muted-foreground mt-1.5">{p.desc}</div>
              </button>
            ))}
          </div>
        </Card>

        <Card className="p-3 space-y-1">
          <SectionHeader title="Auto-Configuration" icon={Sparkles} />
          {[
            { k: "autoPair", label: "Pair selection", fn: "setAutoPair" },
            { k: "autoTimeframe", label: "Timeframe selection", fn: "setAutoTimeframe" },
            { k: "autoSession", label: "Session selection", fn: "setAutoSession" },
            { k: "autoIndicators", label: "Indicators", fn: "setAutoIndicators" },
            { k: "autoRisk", label: "Risk management", fn: "setAutoRisk" },
            { k: "autoTrailing", label: "Trailing stop", fn: "setAutoTrailing" },
            { k: "autoTradeMode", label: "Trade execution", fn: "setAutoTradeMode" },
          ].map((row) => {
            const auto = (store as any)[row.k] as boolean;
            return (
              <div key={row.k} className="flex items-center justify-between py-1.5">
                <span className="text-sm">{row.label}</span>
                <div className="inline-flex rounded-md border bg-muted/50 p-0.5 text-[11px]">
                  <button
                    onClick={() => (store as any)[row.fn](true)}
                    className={cn(
                      "px-2 py-0.5 rounded",
                      auto ? "bg-primary text-primary-foreground" : "text-muted-foreground"
                    )}
                  >
                    AI
                  </button>
                  <button
                    onClick={() => (store as any)[row.fn](false)}
                    className={cn(
                      "px-2 py-0.5 rounded",
                      !auto ? "bg-primary text-primary-foreground" : "text-muted-foreground"
                    )}
                  >
                    Manual
                  </button>
                </div>
              </div>
            );
          })}
        </Card>
      </div>

      {/* analysis output */}
      <div className="xl:col-span-2 space-y-3">
        <Card className="p-3">
          <SectionHeader
            title={`AI Analysis · ${symbol}`}
            desc={`${active.name} · ${active.model} · ${active.latencyMs}ms`}
            icon={Brain}
            right={
              <div className="flex items-center gap-2">
                {a ? <BadgeTone tone={signalTone(a.signal)}>{a.signal}</BadgeTone> : null}
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => refetch()}
                  disabled={isFetching}
                >
                  <RefreshCw className={cn("h-3 w-3 mr-1", isFetching && "animate-spin")} />
                  Re-analyze
                </Button>
              </div>
            }
          />
          {!a ? (
            <div className="h-48 grid place-items-center text-xs text-muted-foreground">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 animate-pulse" /> Analyzing market context…
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <StatTile label="Confidence" value={`${a.confidence}%`} tone={a.confidence > 70 ? "up" : "warn"} />
                <StatTile label="Risk Score" value={`${a.riskScore}%`} tone={a.riskScore > 50 ? "down" : "up"} />
                <StatTile label="Entry" value={fmtPrice(a.suggestedEntry, symbol.includes("JPY") ? 3 : 5)} />
                <StatTile label="Provider" value={active.name} sub={active.model} />
              </div>
              <p className="text-sm leading-relaxed bg-muted/30 rounded-md p-2.5">
                {a.summary}
              </p>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                <div className="rounded-md border p-2">
                  <div className="text-[10px] text-muted-foreground">Suggested Entry</div>
                  <div className="text-sm font-semibold tnum">
                    {fmtPrice(a.suggestedEntry, symbol.includes("JPY") ? 3 : 5)}
                  </div>
                </div>
                <div className="rounded-md border p-2">
                  <div className="text-[10px] text-muted-foreground">Stop Loss</div>
                  <div className="text-sm font-semibold tnum text-danger">
                    {fmtPrice(a.suggestedSL, symbol.includes("JPY") ? 3 : 5)}
                  </div>
                </div>
                <div className="rounded-md border p-2">
                  <div className="text-[10px] text-muted-foreground">Take Profit</div>
                  <div className="text-sm font-semibold tnum text-success">
                    {fmtPrice(a.suggestedTP, symbol.includes("JPY") ? 3 : 5)}
                  </div>
                </div>
                <div className="rounded-md border p-2">
                  <div className="text-[10px] text-muted-foreground">RR</div>
                  <div className="text-sm font-semibold tnum">1 : {store.rrRatio}</div>
                </div>
              </div>

              <Button
                className="w-full"
                disabled={store.autoTradeMode}
                onClick={() =>
                  toast.success(`Signal queued: ${a.signal} ${symbol} (AI)`)
                }
              >
                <Sparkles className="h-4 w-4 mr-2" />
                {store.autoTradeMode
                  ? "Auto-trade active — AI executes signals"
                  : `Execute ${a.signal} ${symbol}`}
              </Button>
            </div>
          )}
        </Card>

        <Card className="p-3">
          <SectionHeader
            title="Multi-Factor Analysis"
            desc="ML scoring across 7 dimensions"
            icon={Gauge}
          />
          {a ? (
            <div className="space-y-1.5">
              {a.dimensions.map((d) => (
                <div key={d.id} className="flex items-center gap-3">
                  <div className="w-48 shrink-0">
                    <div className="text-xs font-medium leading-tight">{d.label}</div>
                    <div className="text-[10px] text-muted-foreground leading-tight line-clamp-2">
                      {d.note}
                    </div>
                  </div>
                  <div className="flex-1 h-2.5 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${d.score}%`,
                        background:
                          d.score > 55
                            ? "var(--success)"
                            : d.score < 45
                            ? "var(--danger)"
                            : "var(--warning)",
                      }}
                    />
                  </div>
                  <span
                    className={cn(
                      "w-10 text-right text-xs font-semibold tnum",
                      d.score > 55
                        ? "text-success"
                        : d.score < 45
                        ? "text-danger"
                        : "text-muted-foreground"
                    )}
                  >
                    {d.score}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="h-20 grid place-items-center text-xs text-muted-foreground">
              Run analysis to see scores
            </div>
          )}
        </Card>

        <Card className="p-3">
          <SectionHeader title="ML Self-Learning" icon={LineChart} />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <StatTile label="Model Version" value="v2.4.1" sub="online" />
            <StatTile label="Training Trades" value="12,480" sub="last 90d" />
            <StatTile label="Win Rate (val)" value="61.3%" tone="up" />
            <StatTile label="Retrained" value="2h ago" sub="auto-scheduled" tone="warn" />
          </div>
          <Separator className="my-2" />
          <div className="text-[11px] text-muted-foreground">
            The model retrains nightly on closed-trade outcomes and recent market
            regimes. Prediction drift &gt; 8% triggers an early retrain.
          </div>
        </Card>
      </div>
    </div>
  );
}

function signalTone(s: string): "up" | "down" | "neutral" {
  if (s.includes("BUY")) return "up";
  if (s.includes("SELL")) return "down";
  return "neutral";
}
