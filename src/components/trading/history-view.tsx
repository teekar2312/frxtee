"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Download, History, Search, TrendingUp, TrendingDown } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  fmtMoney,
  fmtPrice,
  TRADING_PAIRS,
} from "@/lib/trading-data";
import { useTrades } from "@/lib/trading-hooks";
import { BadgeTone, SectionHeader, StatTile } from "./primitives";

type FilterKey = "ALL" | "OPEN" | "CLOSED" | "WIN" | "LOSS" | "AI" | "MANUAL";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "ALL", label: "All" },
  { key: "OPEN", label: "Open" },
  { key: "CLOSED", label: "Closed" },
  { key: "WIN", label: "Winners" },
  { key: "LOSS", label: "Losers" },
  { key: "AI", label: "AI" },
  { key: "MANUAL", label: "Manual" },
];

function digitsFor(symbol: string): number {
  return TRADING_PAIRS.find((p) => p.symbol === symbol)?.digits ?? 5;
}

/** Format ISO datetime to a short local timestamp string. */
function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

export function HistoryView() {
  const { data, isFetching } = useTrades();
  const trades = data?.trades ?? [];
  const [filter, setFilter] = React.useState<FilterKey>("ALL");
  const [q, setQ] = React.useState("");

  // ---- derived summary stats (computed from closed trades) ----
  const closed = trades.filter((t) => t.close_time != null && t.pnl != null);
  const wins = closed.filter((t) => (t.pnl ?? 0) > 0);
  const losses = closed.filter((t) => (t.pnl ?? 0) < 0);
  const grossWin = wins.reduce((a, t) => a + (t.pnl ?? 0), 0);
  const grossLoss = Math.abs(losses.reduce((a, t) => a + (t.pnl ?? 0), 0));
  const netPnl = grossWin - grossLoss;
  const winRate = closed.length > 0 ? (wins.length / closed.length) * 100 : 0;
  const profitFactor = grossLoss > 0 ? grossWin / grossLoss : grossWin > 0 ? Infinity : 0;
  const openCount = trades.length - closed.length;
  const avgPips =
    closed.length > 0
      ? closed.reduce((a, t) => a + (t.pips ?? 0), 0) / closed.length
      : 0;

  // ---- filter + search ----
  const filtered = trades.filter((t) => {
    const isOpen = t.close_time == null;
    const isWin = (t.pnl ?? 0) > 0;
    const isLoss = (t.pnl ?? 0) < 0;
    const isAI = (t.source ?? "").toLowerCase() === "ai";
    switch (filter) {
      case "OPEN": if (!isOpen) return false; break;
      case "CLOSED": if (isOpen) return false; break;
      case "WIN": if (isOpen || !isWin) return false; break;
      case "LOSS": if (isOpen || !isLoss) return false; break;
      case "AI": if (!isAI) return false; break;
      case "MANUAL": if (isAI) return false; break;
    }
    if (q) {
      const needle = q.toLowerCase();
      const hay = `${t.symbol} ${t.side} ${t.ticket} ${t.comment ?? ""} ${t.source}`.toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  });

  // newest first (by open_time desc)
  const sorted = [...filtered].sort((a, b) =>
    (b.open_time ?? "").localeCompare(a.open_time ?? "")
  );

  // ---- CSV export ----
  function exportCsv() {
    if (sorted.length === 0) {
      toast.error("No trades to export");
      return;
    }
    const header = [
      "ticket", "symbol", "side", "volume", "open_price", "close_price",
      "pnl", "pips", "open_time", "close_time", "sl", "tp", "source", "comment",
    ];
    const rows = sorted.map((t) =>
      header.map((h) => {
        const v = (t as Record<string, unknown>)[h];
        if (v == null) return "";
        const s = String(v);
        return s.includes(",") || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
      }).join(",")
    );
    const csv = [header.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `zenitrade-history-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(`Exported ${sorted.length} trades`);
  }

  const counts: Record<FilterKey, number> = {
    ALL: trades.length,
    OPEN: openCount,
    CLOSED: closed.length,
    WIN: wins.length,
    LOSS: losses.length,
    AI: trades.filter((t) => (t.source ?? "").toLowerCase() === "ai").length,
    MANUAL: trades.filter((t) => (t.source ?? "").toLowerCase() !== "ai").length,
  };

  return (
    <div className="space-y-3">
      {/* ---- summary tiles ---- */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <StatTile
          label="Net P&L"
          value={fmtMoney(netPnl)}
          sub={`${closed.length} closed trades`}
          tone={netPnl >= 0 ? "up" : "down"}
        />
        <StatTile
          label="Win Rate"
          value={`${winRate.toFixed(1)}%`}
          sub={`${wins.length}W / ${losses.length}L`}
          tone={winRate >= 50 ? "up" : "down"}
        />
        <StatTile
          label="Profit Factor"
          value={profitFactor === Infinity ? "∞" : profitFactor.toFixed(2)}
          sub={`Gross +${fmtMoney(grossWin)} / -${fmtMoney(grossLoss)}`}
          tone={profitFactor >= 1 ? "up" : "down"}
        />
        <StatTile
          label="Avg Pips / Trade"
          value={`${avgPips >= 0 ? "+" : ""}${avgPips.toFixed(1)}`}
          sub={`${openCount} open positions`}
          tone={avgPips >= 0 ? "up" : "down"}
        />
      </div>

      {/* ---- filter + search bar ---- */}
      <Card className="p-3">
        <SectionHeader
          title="Trade History"
          desc={`${trades.length} total trades · ${openCount} open · ${closed.length} closed`}
          icon={History}
          right={
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              disabled={sorted.length === 0}
              onClick={exportCsv}
            >
              <Download className="h-3 w-3 mr-1" /> Export CSV
            </Button>
          }
        />
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[180px]">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by symbol, ticket, comment…"
              className="h-8 pl-7 text-xs"
            />
          </div>
          <div className="flex items-center gap-1 flex-wrap">
            {FILTERS.map((f) => (
              <Button
                key={f.key}
                variant={filter === f.key ? "default" : "outline"}
                size="sm"
                className="h-8 text-[11px]"
                onClick={() => setFilter(f.key)}
              >
                {f.label}
                <span className="ml-1 text-[9px] opacity-70">{counts[f.key] ?? 0}</span>
              </Button>
            ))}
          </div>
        </div>
      </Card>

      {/* ---- trade table ---- */}
      <Card className="p-0 overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 border-b bg-muted/30">
          <History className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[11px] text-muted-foreground">
            {filtered.length} trades
            {isFetching ? " · refreshing…" : ""}
            {data?.demo ? " · demo mode" : ""}
          </span>
        </div>
        <div className="max-h-[560px] overflow-auto scroll-thin">
          <table className="w-full text-[11px]">
            <thead className="sticky top-0 bg-background border-b">
              <tr className="text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                <th className="px-2 py-2 font-medium">Ticket</th>
                <th className="px-2 py-2 font-medium">Symbol</th>
                <th className="px-2 py-2 font-medium">Side</th>
                <th className="px-2 py-2 font-medium text-right">Volume</th>
                <th className="px-2 py-2 font-medium text-right">Open</th>
                <th className="px-2 py-2 font-medium text-right">Close</th>
                <th className="px-2 py-2 font-medium text-right">Pips</th>
                <th className="px-2 py-2 font-medium text-right">P&L</th>
                <th className="px-2 py-2 font-medium">Opened</th>
                <th className="px-2 py-2 font-medium">Closed</th>
                <th className="px-2 py-2 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((t) => {
                const isOpen = t.close_time == null;
                const pnl = t.pnl ?? 0;
                const pips = t.pips ?? 0;
                const digits = digitsFor(t.symbol);
                const pnlTone = isOpen ? "neutral" : pnl > 0 ? "up" : pnl < 0 ? "down" : "neutral";
                const sideTone = t.side === "BUY" ? "up" : "down";
                return (
                  <tr
                    key={t.ticket}
                    className={cn(
                      "border-b border-border/50 hover:bg-muted/40",
                      !isOpen && pnl > 0 && "bg-success/5",
                      !isOpen && pnl < 0 && "bg-danger/5"
                    )}
                  >
                    <td className="px-2 py-1.5 tnum text-muted-foreground">#{t.ticket}</td>
                    <td className="px-2 py-1.5 font-semibold">{t.symbol}</td>
                    <td className="px-2 py-1.5">
                      <BadgeTone tone={sideTone}>{t.side}</BadgeTone>
                    </td>
                    <td className="px-2 py-1.5 tnum text-right">{t.volume.toFixed(2)}</td>
                    <td className="px-2 py-1.5 tnum text-right">{fmtPrice(t.open_price, digits)}</td>
                    <td className="px-2 py-1.5 tnum text-right">
                      {t.close_price != null ? fmtPrice(t.close_price, digits) : "—"}
                    </td>
                    <td className={cn("px-2 py-1.5 tnum text-right", pips > 0 ? "text-success" : pips < 0 ? "text-danger" : "")}>
                      {isOpen ? "—" : `${pips > 0 ? "+" : ""}${pips.toFixed(1)}`}
                    </td>
                    <td className={cn("px-2 py-1.5 tnum text-right font-medium", pnlTone === "up" ? "text-success" : pnlTone === "down" ? "text-danger" : "")}>
                      {isOpen ? "—" : fmtMoney(pnl)}
                    </td>
                    <td className="px-2 py-1.5 tnum text-muted-foreground">{fmtTime(t.open_time)}</td>
                    <td className="px-2 py-1.5 tnum text-muted-foreground">{fmtTime(t.close_time)}</td>
                    <td className="px-2 py-1.5">
                      <span className="inline-flex items-center gap-1">
                        {(t.source ?? "").toLowerCase() === "ai" ? (
                          <TrendingUp className="h-3 w-3 text-chart-1" />
                        ) : (
                          <TrendingDown className="h-3 w-3 text-muted-foreground" />
                        )}
                        <span className="text-[10px] text-muted-foreground capitalize">{t.source || "manual"}</span>
                      </span>
                    </td>
                  </tr>
                );
              })}
              {sorted.length === 0 ? (
                <tr>
                  <td colSpan={11} className="text-center text-xs text-muted-foreground py-10">
                    No trades match the current filter
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
