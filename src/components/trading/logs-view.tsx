"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Download, RefreshCw, ScrollText, Search, Terminal } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useLogs } from "@/lib/trading-hooks";
import { BadgeTone, SectionHeader } from "./primitives";

const LEVELS = ["ALL", "INFO", "WARN", "ERROR", "TRADE", "DEBUG"] as const;

const LEVEL_TONE: Record<string, "up" | "down" | "warn" | "neutral"> = {
  INFO: "neutral",
  WARN: "warn",
  ERROR: "down",
  TRADE: "up",
  DEBUG: "neutral",
};

export function LogsView() {
  const { data, refetch, isFetching } = useLogs();
  const logs = data?.logs ?? [];
  const [level, setLevel] = React.useState<(typeof LEVELS)[number]>("ALL");
  const [q, setQ] = React.useState("");

  const filtered = logs.filter((l) => {
    if (level !== "ALL" && l.level !== level) return false;
    if (q && !l.message.toLowerCase().includes(q.toLowerCase()) && !l.source.toLowerCase().includes(q.toLowerCase()))
      return false;
    return true;
  });

  const counts = LEVELS.slice(1).reduce(
    (acc, lv) => ({ ...acc, [lv]: logs.filter((l) => l.level === lv).length }),
    {} as Record<string, number>
  );

  const handleRefresh = async () => {
    toast.info("Refreshing logs…");
    try {
      const result = await refetch();
      const n = result.data?.logs?.length ?? 0;
      toast.success(`Loaded ${n} log entries`);
    } catch {
      toast.error("Failed to refresh logs — backend not reachable");
    }
  };

  return (
    <div className="space-y-3">
      <Card className="p-3">
        <SectionHeader
          title="System & Error Logs"
          desc="Real-time engine, MT5, news & trade logs"
          icon={Terminal}
          right={
            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                disabled={isFetching}
                onClick={handleRefresh}
                title="Refresh logs now (auto-refreshes every 15s)"
              >
                <RefreshCw
                  className={cn("h-3 w-3 mr-1", isFetching && "animate-spin")}
                />
                Refresh
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => {
                  if (filtered.length === 0) {
                    toast.error("No logs to export");
                    return;
                  }
                  const csv = [
                    ["timestamp", "level", "source", "message"].join(","),
                    ...filtered.map((l) =>
                      [l.ts, l.level, l.source, `"${l.message.replace(/"/g, '""')}"`].join(",")
                    ),
                  ].join("\n");
                  const blob = new Blob([csv], { type: "text/csv" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `zenitrade-logs-${Date.now()}.csv`;
                  a.click();
                  URL.revokeObjectURL(url);
                  toast.success(`Exported ${filtered.length} log entries`);
                }}
              >
                <Download className="h-3 w-3 mr-1" /> Export
              </Button>
            </div>
          }
        />
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[180px]">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search logs…"
              className="h-8 pl-7 text-xs"
            />
          </div>
          <div className="flex items-center gap-1">
            {LEVELS.map((lv) => (
              <Button
                key={lv}
                variant={level === lv ? "default" : "outline"}
                size="sm"
                className="h-8 text-[11px]"
                onClick={() => setLevel(lv)}
              >
                {lv}
                {lv !== "ALL" ? (
                  <span className="ml-1 text-[9px] opacity-70">{counts[lv] ?? 0}</span>
                ) : null}
              </Button>
            ))}
          </div>
        </div>
      </Card>

      <Card className="p-0 overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 border-b bg-muted/30">
          <ScrollText className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[11px] text-muted-foreground">
            {filtered.length} entries · live tail
          </span>
          {isFetching ? (
            <span className="ml-auto inline-flex items-center gap-1 text-[10px] text-muted-foreground">
              <RefreshCw className="h-3 w-3 animate-spin" /> fetching…
            </span>
          ) : (
            <span className="ml-auto inline-flex items-center gap-1 text-[10px] text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-success pulse-dot" />
              auto every 15s
            </span>
          )}
        </div>
        <div className="max-h-[520px] overflow-y-auto scroll-thin font-mono text-[11px]">
          {filtered.map((l) => (
            <div
              key={l.id}
              className={cn(
                "flex items-start gap-2 px-3 py-1.5 border-b border-border/50 hover:bg-muted/40",
                l.level === "ERROR" && "bg-danger/5",
                l.level === "TRADE" && "bg-success/5"
              )}
            >
              <span className="text-muted-foreground tnum shrink-0 w-28">
                {new Date(l.ts).toLocaleTimeString("en-GB")}
              </span>
              <BadgeTone tone={LEVEL_TONE[l.level] ?? "neutral"}>{l.level}</BadgeTone>
              <span className="text-muted-foreground shrink-0 w-20 truncate">[{l.source}]</span>
              <span className="flex-1 break-words">{l.message}</span>
            </div>
          ))}
          {filtered.length === 0 ? (
            <div className="text-center text-xs text-muted-foreground py-8">
              No matching logs
            </div>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
