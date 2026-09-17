"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { TRADING_PAIRS, fmtPrice, type PriceTick } from "@/lib/trading-data";
import { useTicks } from "@/lib/trading-hooks";

export function TickerTape() {
  const { data } = useTicks(true);
  const ticks = data?.ticks ?? [];
  return (
    <div className="border-b bg-card/50 overflow-hidden">
      <div className="flex items-center gap-0 overflow-x-auto scroll-thin">
        {TRADING_PAIRS.map((p) => {
          const t = ticks.find((x) => x.symbol === p.symbol);
          return <MemoizedTickerCell key={p.symbol} pair={p} tick={t} />;
        })}
      </div>
    </div>
  );
}

function TickerCell({
  pair,
  tick,
}: {
  pair: (typeof TRADING_PAIRS)[number];
  tick?: PriceTick;
}) {
  const prev = React.useRef<number | undefined>(tick?.bid);
  const [flash, setFlash] = React.useState<"up" | "down" | "">("");
  React.useEffect(() => {
    if (tick && prev.current !== undefined) {
      if (tick.bid > prev.current) setFlash("up");
      else if (tick.bid < prev.current) setFlash("down");
      const id = setTimeout(() => setFlash(""), 600);
      prev.current = tick.bid;
      return () => clearTimeout(id);
    }
    if (tick) prev.current = tick.bid;
  }, [tick?.bid]);

  const change = tick?.changePct ?? 0;
  const up = change >= 0;
  return (
    <div
      className={cn(
        "flex items-center gap-1.5 px-2.5 py-1.5 border-r shrink-0 min-w-[140px]",
        flash === "up" && "flash-up",
        flash === "down" && "flash-down"
      )}
    >
      <span className="text-[11px] font-semibold text-muted-foreground">
        {pair.display}
      </span>
      <span className="text-[11px] tnum font-medium">
        {tick ? fmtPrice(tick.bid, pair.digits) : "—"}
      </span>
      <span
        className={cn(
          "text-[10px] tnum ml-auto",
          up ? "text-success" : "text-danger"
        )}
      >
        {up ? "▲" : "▼"} {Math.abs(change).toFixed(2)}%
      </span>
    </div>
  );
}

// Memoize so only cells whose tick changed re-render (not all 14 every 2.5s)
const MemoizedTickerCell = React.memo(TickerCell);
MemoizedTickerCell.displayName = "TickerCell";
