"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import {
  Brain,
  Cpu,
  Gauge,
  LayoutGrid,
  LineChart,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  AI_PROVIDERS,
  fmtPrice,
  TRADING_PAIRS,
} from "@/lib/trading-data";
import { useMultiAnalysis, useMLInfo } from "@/lib/trading-hooks";
import { useTradingStore, useActiveProvider } from "@/lib/trading-store";
import { BadgeTone, SectionHeader, StatTile } from "./primitives";

export function AIEngineView() {
  const store = useTradingStore();
  const active = useActiveProvider();
  const symbols = store.symbols;

  // focus pair — the one whose detailed analysis is shown
  const [focus, setFocus] = React.useState<string>(symbols[0] ?? "EURUSD");
  const [training, setTraining] = React.useState(false);
  const [executing, setExecuting] = React.useState(false);
  React.useEffect(() => {
    if (!symbols.includes(focus)) setFocus(symbols[0] ?? "EURUSD");
  }, [symbols, focus]);

  const { data, isFetching, refetch } = useMultiAnalysis(symbols, active.id);
  const ml = useMLInfo();
  const results = data?.results ?? {};
  const a = results[focus];

  // aggregate stats across all pairs
  const valid = symbols.map((s) => results[s]).filter(Boolean);
  const buyCount = valid.filter((x) => x!.signal.includes("BUY")).length;
  const sellCount = valid.filter((x) => x!.signal.includes("SELL")).length;
  const neutralCount = valid.filter((x) => x!.signal === "NEUTRAL").length;
  const avgConf = valid.length
    ? Math.round(valid.reduce((s, x) => s + x!.confidence, 0) / valid.length)
    : 0;
  const bestPair = valid
    .map((x) => x!)
    .sort((a, b) => b.confidence - a.confidence)[0];

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

        <Card className="p-3">
          <SectionHeader
            title="ML Self-Learning"
            icon={LineChart}
            right={
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                disabled={training}
                onClick={async () => {
                  setTraining(true);
                  toast.info(`Retraining model on ${focus}…`);
                  try {
                    const res = await fetch(
                      `/api/trading/ml/train?symbol=${focus}`,
                      { method: "POST" }
                    );
                    const d = await res.json();
                    if (d.ok) {
                      toast.success(d.message ?? `Model retrained on ${focus}`);
                      ml.refetch(); // refresh real model metrics
                    } else {
                      toast.error("Retrain failed");
                    }
                  } catch {
                    toast.error("Retrain failed — network error");
                  } finally {
                    setTraining(false);
                  }
                }}
              >
                <RefreshCw
                  className={cn("h-3 w-3 mr-1", training && "animate-spin")}
                />
                Retrain
              </Button>
            }
          />
          <div className="grid grid-cols-2 gap-2">
            <StatTile
              label="Model Version"
              value={ml.data?.exists ? ml.data.version : "—"}
              sub={ml.data?.exists ? "online" : "not trained"}
              tone={ml.data?.exists ? "up" : "warn"}
            />
            <StatTile
              label="Samples"
              value={ml.data?.n_samples ? ml.data.n_samples.toLocaleString() : "—"}
              sub={ml.data?.symbol ? `trained on ${ml.data.symbol}` : "no model"}
            />
            <StatTile
              label="Test Accuracy"
              value={ml.data?.test_acc != null ? `${(ml.data.test_acc * 100).toFixed(1)}%` : "—"}
              sub={ml.data?.train_acc != null ? `train ${(ml.data.train_acc * 100).toFixed(1)}%` : ""}
              tone={ml.data?.test_acc != null && ml.data.test_acc > 0.55 ? "up" : "warn"}
            />
            <StatTile
              label="Retrained"
              value={
                ml.data?.trained_at
                  ? new Date(ml.data.trained_at).toLocaleString("en-GB", {
                      hour: "2-digit",
                      minute: "2-digit",
                      day: "2-digit",
                      month: "short",
                    })
                  : "—"
              }
              sub={ml.data?.demo ? "demo" : "auto-scheduled"}
              tone="warn"
            />
          </div>
          {/* Drift indicator */}
          {ml.data?.exists ? (
            <div className="mt-2 rounded-md border p-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">
                  Prediction Drift
                </span>
                <span
                  className={cn(
                    "text-xs font-semibold tnum",
                    (ml.data.drift ?? 0) > (ml.data.drift_threshold ?? 0.08)
                      ? "text-danger"
                      : (ml.data.drift ?? 0) > (ml.data.drift_threshold ?? 0.08) * 0.7
                      ? "text-warning"
                      : "text-success"
                  )}
                >
                  {((ml.data.drift ?? 0) * 100).toFixed(1)}%
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-muted overflow-hidden mt-1">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, ((ml.data.drift ?? 0) / (ml.data.drift_threshold ?? 0.08)) * 100)}%`,
                    background:
                      (ml.data.drift ?? 0) > (ml.data.drift_threshold ?? 0.08)
                        ? "var(--danger)"
                        : (ml.data.drift ?? 0) > (ml.data.drift_threshold ?? 0.08) * 0.7
                        ? "var(--warning)"
                        : "var(--success)",
                  }}
                />
              </div>
              <div className="text-[9px] text-muted-foreground mt-1">
                threshold {(ml.data.drift_threshold ?? 0.08) * 100}% —
                {(ml.data.drift ?? 0) > (ml.data.drift_threshold ?? 0.08)
                  ? " retrain recommended"
                  : " healthy"}
              </div>
            </div>
          ) : null}
          <Separator className="my-2" />
          <div className="text-[11px] text-muted-foreground">
            Model retrains nightly at 02:00 (auto-scheduled) or on demand via
            Retrain. Prediction drift &gt; threshold auto-triggers a retrain
            recommendation. Train/test split: 80/20 chronological. The model is
            symbol-specific — retrain for each pair you trade.
          </div>
        </Card>
      </div>

      {/* analysis output — multi-pair */}
      <div className="xl:col-span-2 space-y-3">
        {/* Multi-pair signal matrix */}
        <Card className="p-3">
          <SectionHeader
            title="Multi-Pair Signal Matrix"
            desc={`${symbols.length} active pairs · ${active.name} analyzes all`}
            icon={LayoutGrid}
            right={
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => {
                  refetch();
                  toast.success(`Re-analyzing all ${symbols.length} pairs…`);
                }}
                disabled={isFetching}
              >
                <RefreshCw className={cn("h-3 w-3 mr-1", isFetching && "animate-spin")} />
                Re-analyze All
              </Button>
            }
          />
          {symbols.length === 0 ? (
            <div className="h-20 grid place-items-center text-xs text-muted-foreground">
              No active pairs — select pairs in Trading view
            </div>
          ) : (
            <>
              {/* aggregate summary */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-3">
                <StatTile label="Pairs Analyzed" value={`${valid.length}/${symbols.length}`} />
                <StatTile label="Buy Signals" value={String(buyCount)} tone="up" />
                <StatTile label="Sell Signals" value={String(sellCount)} tone="down" />
                <StatTile label="Neutral" value={String(neutralCount)} />
                <StatTile label="Avg Confidence" value={`${avgConf}%`} tone={avgConf > 70 ? "up" : "warn"} />
              </div>
              {bestPair ? (
                <div className="rounded-md border border-primary/30 bg-primary/5 p-2 mb-3 text-xs">
                  <span className="text-muted-foreground">Top pick: </span>
                  <span className="font-semibold">{bestPair.symbol}</span>
                  <span className="mx-1.5">·</span>
                  <BadgeTone tone={signalTone(bestPair.signal)}>{bestPair.signal}</BadgeTone>
                  <span className="mx-1.5">·</span>
                  <span className="tnum font-semibold">{bestPair.confidence}%</span>
                  <span className="text-muted-foreground ml-1">confidence</span>
                </div>
              ) : null}
              {/* pair grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 max-h-80 overflow-y-auto scroll-thin">
                {symbols.map((s) => {
                  const r = results[s];
                  const p = TRADING_PAIRS.find((x) => x.symbol === s);
                  return (
                    <button
                      key={s}
                      onClick={() => setFocus(s)}
                      className={cn(
                        "text-left rounded-md border p-2 transition-colors",
                        focus === s
                          ? "border-primary bg-primary/5"
                          : "border-border hover:bg-muted/40"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold">{p?.display ?? s}</span>
                        {r ? (
                          <BadgeTone tone={signalTone(r.signal)}>{r.signal}</BadgeTone>
                        ) : (
                          <span className="text-[10px] text-muted-foreground">…</span>
                        )}
                      </div>
                      {r ? (
                        <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground tnum">
                          <span>conf {r.confidence}%</span>
                          <span>·</span>
                          <span className="text-danger">SL {fmtPrice(r.suggestedSL, s.includes("JPY") ? 3 : 5)}</span>
                          <span>·</span>
                          <span className="text-success">TP {fmtPrice(r.suggestedTP, s.includes("JPY") ? 3 : 5)}</span>
                        </div>
                      ) : (
                        <div className="text-[10px] text-muted-foreground mt-1">analyzing…</div>
                      )}
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </Card>

        {/* Focused pair detailed analysis */}
        <Card className="p-3">
          <SectionHeader
            title={`Detailed Analysis · ${focus}`}
            desc={`${active.name} · ${active.model} · ${active.latencyMs}ms`}
            icon={Brain}
            right={
              a ? <BadgeTone tone={signalTone(a.signal)}>{a.signal}</BadgeTone> : null
            }
          />
          {!a ? (
            <div className="h-48 grid place-items-center text-xs text-muted-foreground">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 animate-pulse" /> Analyzing {focus}…
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <StatTile label="Confidence" value={`${a.confidence}%`} tone={a.confidence > 70 ? "up" : "warn"} />
                <StatTile label="Risk Score" value={`${a.riskScore}%`} tone={a.riskScore > 50 ? "down" : "up"} />
                <StatTile label="Entry" value={fmtPrice(a.suggestedEntry, focus.includes("JPY") ? 3 : 5)} />
                <StatTile label="Provider" value={active.name} sub={active.model} />
              </div>
              <p className="text-sm leading-relaxed bg-muted/30 rounded-md p-2.5">
                {a.summary}
              </p>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                <div className="rounded-md border p-2">
                  <div className="text-[10px] text-muted-foreground">Suggested Entry</div>
                  <div className="text-sm font-semibold tnum">
                    {fmtPrice(a.suggestedEntry, focus.includes("JPY") ? 3 : 5)}
                  </div>
                </div>
                <div className="rounded-md border p-2">
                  <div className="text-[10px] text-muted-foreground">Stop Loss</div>
                  <div className="text-sm font-semibold tnum text-danger">
                    {fmtPrice(a.suggestedSL, focus.includes("JPY") ? 3 : 5)}
                  </div>
                </div>
                <div className="rounded-md border p-2">
                  <div className="text-[10px] text-muted-foreground">Take Profit</div>
                  <div className="text-sm font-semibold tnum text-success">
                    {fmtPrice(a.suggestedTP, focus.includes("JPY") ? 3 : 5)}
                  </div>
                </div>
                <div className="rounded-md border p-2">
                  <div className="text-[10px] text-muted-foreground">RR</div>
                  <div className="text-sm font-semibold tnum">1 : {store.rrRatio}</div>
                </div>
              </div>

              <Button
                className="w-full"
                disabled={store.autoTradeMode || executing}
                onClick={async () => {
                  if (!a) return;
                  // confidence threshold — refuse low-confidence signals
                  if (a.confidence < store.aiMinConfidence) {
                    toast.error(
                      `Confidence too low (${a.confidence}% < ${store.aiMinConfidence}%) — signal rejected`
                    );
                    return;
                  }
                  const side = a.signal.includes("SELL") ? "SELL" : "BUY";
                  // only execute directional signals
                  if (a.signal === "NEUTRAL") {
                    toast.info("Signal is NEUTRAL — no order placed");
                    return;
                  }
                  setExecuting(true);
                  try {
                    const res = await fetch("/api/trading/order", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        symbol: focus,
                        side,
                        slPips: store.stopLossPips,
                        comment: "AI:auto",
                      }),
                    });
                    const d = await res.json();
                    if (d.ok) {
                      toast.success(
                        `Executed ${side} ${focus} (AI signal)`,
                        {
                          description: `Ticket #${d.ticket} @ ${fmtPrice(
                            d.price ?? a.suggestedEntry,
                            focus.includes("JPY") ? 3 : 5
                          )} · ${a.confidence}% confidence`,
                        }
                      );
                    } else {
                      toast.error(`Order rejected: ${d.error ?? "unknown"}`);
                    }
                  } catch {
                    toast.error("Order failed — network error");
                  } finally {
                    setExecuting(false);
                  }
                }}
              >
                <Sparkles className="h-4 w-4 mr-2" />
                {executing
                  ? "Executing…"
                  : store.autoTradeMode
                  ? "Auto-trade active — AI executes signals"
                  : `Execute ${a.signal} ${focus}`}
              </Button>
            </div>
          )}
        </Card>

        {/* Multi-factor for focused pair */}
        <Card className="p-3">
          <SectionHeader
            title={`Multi-Factor Analysis · ${focus}`}
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
      </div>
    </div>
  );
}

function signalTone(s: string): "up" | "down" | "neutral" {
  if (s.includes("BUY")) return "up";
  if (s.includes("SELL")) return "down";
  return "neutral";
}
