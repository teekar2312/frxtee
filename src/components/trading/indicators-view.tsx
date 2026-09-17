"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Activity, CheckCheck, Layers, Search, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  INDICATOR_CATEGORIES,
  TECHNICAL_INDICATORS,
} from "@/lib/trading-data";
import { useTradingStore } from "@/lib/trading-store";
import { BadgeTone, ModeToggle, SectionHeader } from "./primitives";

const CATEGORY_TONE: Record<string, string> = {
  Trend: "bg-chart-1/15 text-chart-1 border-chart-1/30",
  Momentum: "bg-chart-3/15 text-chart-3 border-chart-3/30",
  Volatility: "bg-chart-2/15 text-chart-2 border-chart-2/30",
  Volume: "bg-chart-4/15 text-chart-4 border-chart-4/30",
};

export function IndicatorsView() {
  const indicators = useTradingStore((s) => s.indicators);
  const toggleIndicator = useTradingStore((s) => s.toggleIndicator);
  const auto = useTradingStore((s) => s.autoIndicators);
  const setAuto = useTradingStore((s) => s.setAutoIndicators);
  const setAutoIndicators = useTradingStore((s) => s.setAutoIndicators);
  const setIndicators = useTradingStore((s) => s.setIndicators);
  const [q, setQ] = React.useState("");

  const filtered = TECHNICAL_INDICATORS.filter(
    (i) =>
      i.name.toLowerCase().includes(q.toLowerCase()) ||
      i.full.toLowerCase().includes(q.toLowerCase())
  );

  const byCat = INDICATOR_CATEGORIES.map((c) => ({
    cat: c,
    items: filtered.filter((i) => i.category === c),
  }));

  return (
    <div className="space-y-3">
      <Card className="p-3">
        <SectionHeader
          title="Technical Indicators"
          desc={`${indicators.length} of ${TECHNICAL_INDICATORS.length} active · 1 or more required`}
          icon={Activity}
          right={
            <ModeToggle
              auto={auto}
              onAuto={() => {
                setAuto(true);
                setAutoIndicators();
                toast.success("AI selected optimal indicator set");
              }}
              onManual={() => setAuto(false)}
            />
          }
        />
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[180px]">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search indicator…"
              className="h-8 pl-7 text-xs"
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs"
            onClick={() => setIndicators(TECHNICAL_INDICATORS.map((i) => i.id))}
          >
            <CheckCheck className="h-3 w-3 mr-1" /> All
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs"
            onClick={() => setIndicators([])}
          >
            Clear
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs"
            onClick={() => {
              setAuto(true);
              setAutoIndicators();
              toast.success("AI selected: EMA, RSI, MACD, ATR, BBands, VWAP, OBV, Supertrend");
            }}
          >
            <Sparkles className="h-3 w-3 mr-1" /> AI Pick
          </Button>
        </div>
        {indicators.length > 0 ? (
          <div className="flex flex-wrap gap-1 mt-2">
            {indicators.map((id) => {
              const ind = TECHNICAL_INDICATORS.find((x) => x.id === id);
              if (!ind) return null;
              return (
                <Badge
                  key={id}
                  variant="secondary"
                  className="text-[10px] gap-1 cursor-pointer"
                  onClick={() => toggleIndicator(id)}
                >
                  {ind.name} ✕
                </Badge>
              );
            })}
          </div>
        ) : null}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {byCat.map(({ cat, items }) => (
          <Card key={cat} className="p-3">
            <SectionHeader
              title={cat}
              desc={`${items.filter((i) => indicators.includes(i.id)).length} / ${items.length} active`}
              icon={Layers}
            />
            {items.length === 0 ? (
              <div className="text-xs text-muted-foreground py-2">No matches</div>
            ) : (
              <div className="grid grid-cols-2 gap-1.5">
                {items.map((ind) => {
                  const on = indicators.includes(ind.id);
                  return (
                    <button
                      key={ind.id}
                      onClick={() => toggleIndicator(ind.id)}
                      className={cn(
                        "text-left rounded-md border p-2 transition-colors",
                        on
                          ? "border-primary bg-primary/5"
                          : "border-border hover:bg-muted/40"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold">{ind.name}</span>
                        <span
                          className={cn(
                            "h-3.5 w-3.5 rounded border grid place-items-center text-[8px]",
                            on
                              ? "bg-primary text-primary-foreground border-primary"
                              : "border-muted-foreground/40"
                          )}
                        >
                          {on ? "✓" : ""}
                        </span>
                      </div>
                      <div className="text-[10px] text-muted-foreground leading-tight truncate">
                        {ind.full}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </Card>
        ))}
      </div>

      <Card className="p-3">
        <SectionHeader title="Active Indicator Stack" icon={Sparkles} />
        <div className="flex flex-wrap gap-1.5">
          {indicators.length === 0 ? (
            <span className="text-xs text-muted-foreground">No indicators selected</span>
          ) : (
            indicators.map((id) => {
              const ind = TECHNICAL_INDICATORS.find((x) => x.id === id);
              if (!ind) return null;
              return (
                <span
                  key={id}
                  className={cn(
                    "rounded border px-2 py-0.5 text-[10px]",
                    CATEGORY_TONE[ind.category]
                  )}
                >
                  {ind.name}
                </span>
              );
            })
          )}
        </div>
      </Card>
    </div>
  );
}
