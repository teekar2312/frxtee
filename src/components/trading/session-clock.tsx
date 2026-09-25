"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { TRADING_SESSIONS } from "@/lib/trading-data";

/** Check if a date is in DST (Northern Hemisphere, US/EU rules).
 * DST: second Sunday of March to first Sunday of November. */
function isDST(date: Date): boolean {
  const year = date.getUTCFullYear();
  // second Sunday of March
  const marchStart = new Date(Date.UTC(year, 2, 1));
  const marchDow = marchStart.getUTCDay();
  const secondSundayMarch = new Date(Date.UTC(year, 2, 1 + ((7 - marchDow) % 7) + 7));
  // first Sunday of November
  const novStart = new Date(Date.UTC(year, 10, 1));
  const novDow = novStart.getUTCDay();
  const firstSundayNov = new Date(Date.UTC(year, 10, 1 + ((7 - novDow) % 7)));
  return date >= secondSundayMarch && date < firstSundayNov;
}

/** Get the effective UTC offset for a session, accounting for DST.
 * - Sydney (AEST): UTC+10 winter, UTC+11 summer (Southern Hemisphere DST, opposite)
 * - Tokyo (JST): UTC+9 (no DST)
 * - London (GMT/BST): UTC+0 winter, UTC+1 summer
 * - New York (EST/EDT): UTC-5 winter, UTC-4 summer */
function getSessionOffset(sessionId: string, dst: boolean): number {
  switch (sessionId) {
    case "sydney":
      return dst ? 10 : 11; // AEST/AEDT (southern: DST = winter in NH)
    case "tokyo":
      return 9; // JST, no DST
    case "london":
      return dst ? 1 : 0; // BST/GMT
    case "newyork":
      return dst ? -4 : -5; // EDT/EST
    default:
      return 0;
  }
}

/** Check if a session is currently open, accounting for DST.
 * Session times are defined in LOCAL session time, converted to UTC.
 * Overlap sessions (with `overlap: [id1, id2]`) are open only when BOTH
 * underlying sessions are open simultaneously. */
function sessionOpen(
  s: { id: string; utcStart: number; utcEnd: number; overlap?: readonly string[] },
  now: Date
): boolean {
  // Overlap session: open only when ALL underlying sessions are open.
  // This reuses the per-session DST logic so the overlap window shifts
  // correctly with DST (e.g. London×NY is 12-16 UTC in summer, 13-17 in winter).
  if (s.overlap && s.overlap.length >= 2) {
    return s.overlap.every((underlyingId) => {
      const underlying = TRADING_SESSIONS.find((t) => t.id === underlyingId);
      if (!underlying) return false;
      // avoid infinite recursion — underlying sessions must not themselves be overlaps
      if ("overlap" in underlying && underlying.overlap) return false;
      return sessionOpen(underlying, now);
    });
  }
  const dst = isDST(now);
  const offset = getSessionOffset(s.id, dst);
  // convert local session hours to effective UTC hours
  const effectiveStart = (s.utcStart - offset + 24) % 24;
  const effectiveEnd = (s.utcEnd - offset + 24) % 24;
  const utcH = now.getUTCHours();

  if (effectiveStart < effectiveEnd) {
    return utcH >= effectiveStart && utcH < effectiveEnd;
  }
  // wraps midnight
  return utcH >= effectiveStart || utcH < effectiveEnd;
}

export function SessionClock() {
  const [now, setNow] = React.useState<Date | null>(null);
  React.useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const utcH = now ? now.getUTCHours() : 0;
  const utcM = now ? now.getUTCMinutes() : 0;
  const dst = now ? isDST(now) : false;

  return (
    <div className="flex items-center gap-3">
      <div className="hidden sm:flex items-center gap-2">
        {TRADING_SESSIONS.map((s) => {
          const open = now ? sessionOpen(s, now) : false;
          return (
            <div key={s.id} className="flex items-center gap-1.5">
              <span
                className={cn("h-1.5 w-1.5 rounded-full", open ? "pulse-dot" : "")}
                style={{ background: open ? s.color : "var(--muted-foreground)" }}
              />
              <span
                className={cn(
                  "text-[10px] font-medium",
                  open ? "text-foreground" : "text-muted-foreground"
                )}
              >
                {s.name}
              </span>
            </div>
          );
        })}
      </div>
      <div className="text-[11px] tnum text-muted-foreground border-l pl-3">
        {now
          ? `${String(utcH).padStart(2, "0")}:${String(utcM).padStart(2, "0")} UTC${dst ? " (DST)" : ""} · ${now.toLocaleTimeString(
              "en-GB",
              { hour: "2-digit", minute: "2-digit", second: "2-digit" }
            )}`
          : "--:--"}
      </div>
    </div>
  );
}
