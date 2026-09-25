"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Newspaper, Filter, Radio } from "lucide-react";
import { cn } from "@/lib/utils";
import { useNews } from "@/lib/trading-hooks";
import { BadgeTone, SectionHeader } from "./primitives";

const SOURCES = ["All", "Finnhub", "MARKETAUX", "Economic Calendar"] as const;
const IMPACTS = ["All", "high", "medium", "low"] as const;

export function NewsView() {
  const { data, isFetching } = useNews();
  const news = data?.news ?? [];
  const [src, setSrc] = React.useState<(typeof SOURCES)[number]>("All");
  const [imp, setImp] = React.useState<(typeof IMPACTS)[number]>("All");
  const [q, setQ] = React.useState("");

  const filtered = news.filter((n) => {
    if (src !== "All" && n.source !== src) return false;
    if (imp !== "All" && n.impact !== imp) return false;
    if (q && !n.title.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-3">
      <Card className="p-3">
        <SectionHeader
          title="News & Economic Calendar"
          desc="Finnhub + MARKETAUX · real-time feed"
          icon={Newspaper}
          right={
            <Badge variant="outline" className="text-[10px] gap-1">
              <Radio className={cn("h-3 w-3", isFetching && "animate-pulse")} />
              live
            </Badge>
          }
        />
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[160px]">
            <Filter className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search headlines…"
              className="h-8 pl-7 text-xs"
            />
          </div>
          <div className="flex items-center gap-1">
            {SOURCES.map((s) => (
              <Button
                key={s}
                variant={src === s ? "default" : "outline"}
                size="sm"
                className="h-8 text-[11px]"
                onClick={() => setSrc(s)}
              >
                {s}
              </Button>
            ))}
          </div>
          <div className="flex items-center gap-1">
            {IMPACTS.map((i) => (
              <Button
                key={i}
                variant={imp === i ? "default" : "outline"}
                size="sm"
                className="h-8 text-[11px] capitalize"
                onClick={() => setImp(i)}
              >
                {i}
              </Button>
            ))}
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <Card className="p-3 lg:col-span-2">
          <SectionHeader title="Headlines" desc={`${filtered.length} items`} />
          <div className="max-h-[460px] overflow-y-auto scroll-thin -mx-1 divide-y">
            {filtered.map((n) => (
              <div key={n.id} className="px-2 py-2 hover:bg-muted/40">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <Badge variant="secondary" className="text-[9px] h-4 px-1">
                        {n.source}
                      </Badge>
                      <BadgeTone
                        tone={
                          n.impact === "high"
                            ? "down"
                            : n.impact === "medium"
                            ? "warn"
                            : "neutral"
                        }
                      >
                        {n.impact}
                      </BadgeTone>
                      <BadgeTone
                        tone={
                          n.sentiment === "positive"
                            ? "up"
                            : n.sentiment === "negative"
                            ? "down"
                            : "neutral"
                        }
                      >
                        {n.sentiment}
                      </BadgeTone>
                      <span className="text-[10px] text-muted-foreground ml-auto">
                        {timeAgo(n.publishedAt)}
                      </span>
                    </div>
                    <div className="text-sm font-medium leading-snug">{n.title}</div>
                    <div className="text-xs text-muted-foreground leading-snug mt-0.5">
                      {n.summary}
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {n.symbols.map((s) => (
                        <span
                          key={s}
                          className="rounded bg-muted px-1 py-0.5 text-[9px] font-mono"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <div className="space-y-3">
          <Card className="p-3">
            <SectionHeader title="High-Impact Calendar" />
            <div className="space-y-1.5">
              {calendarItems.map((c) => (
                <div
                  key={c.event}
                  className="flex items-center gap-2 rounded-md border p-2"
                >
                  <div className="text-center w-12 shrink-0">
                    <div className="text-[10px] text-muted-foreground">{c.day}</div>
                    <div className="text-sm font-semibold tnum">{c.time}</div>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-medium leading-tight">{c.event}</div>
                    <div className="text-[10px] text-muted-foreground">
                      {c.currency} · forecast {c.forecast}
                    </div>
                  </div>
                  <BadgeTone tone={c.impact === "high" ? "down" : "warn"}>
                    {c.impact}
                  </BadgeTone>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-3">
            <SectionHeader title="Sentiment Summary" />
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-md border p-2">
                <div className="text-lg font-semibold text-success tnum">
                  {data?.sentiment?.bullish ?? "—"}%
                </div>
                <div className="text-[10px] text-muted-foreground">Bullish</div>
              </div>
              <div className="rounded-md border p-2">
                <div className="text-lg font-semibold text-muted-foreground tnum">
                  {data?.sentiment?.neutral ?? "—"}%
                </div>
                <div className="text-[10px] text-muted-foreground">Neutral</div>
              </div>
              <div className="rounded-md border p-2">
                <div className="text-lg font-semibold text-danger tnum">
                  {data?.sentiment?.bearish ?? "—"}%
                </div>
                <div className="text-[10px] text-muted-foreground">Bearish</div>
              </div>
            </div>
            <div className="flex items-center justify-between mt-2">
              <div className="text-[11px] text-muted-foreground">
                Score: <span className="font-semibold tnum">
                  {data?.sentiment?.score != null
                    ? (data.sentiment.score > 0 ? "+" : "") + data.sentiment.score
                    : "—"}
                </span>
                {" · "}
                <span className={
                  data?.sentiment?.summary === "bullish" ? "text-success" :
                  data?.sentiment?.summary === "bearish" ? "text-danger" : ""
                }>
                  {data?.sentiment?.summary ?? "—"}
                </span>
              </div>
              <div className="text-[11px] text-muted-foreground">
                {data?.sentiment?.count ?? 0} items · time-weighted
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

const calendarItems = [
  { day: "Wed", time: "19:30", event: "US CPI (YoY)", currency: "USD", forecast: "3.4%", impact: "high" as const },
  { day: "Wed", time: "19:30", event: "Core CPI (MoM)", currency: "USD", forecast: "0.3%", impact: "high" as const },
  { day: "Thu", time: "19:30", event: "Unemployment Claims", currency: "USD", forecast: "221k", impact: "medium" as const },
  { day: "Thu", time: "20:30", event: "BoE Rate Decision", currency: "GBP", forecast: "5.25%", impact: "high" as const },
  { day: "Fri", time: "19:30", event: "Retail Sales (MoM)", currency: "USD", forecast: "0.4%", impact: "medium" as const },
  { day: "Fri", time: "21:00", event: "ECB President Speech", currency: "EUR", forecast: "—", impact: "high" as const },
];

function timeAgo(iso: string): string {
  const d = Date.now() - new Date(iso).getTime();
  const m = Math.floor(d / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ago`;
}
