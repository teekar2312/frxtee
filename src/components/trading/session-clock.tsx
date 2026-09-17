"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { TRADING_SESSIONS } from "@/lib/trading-data";

function sessionOpen(s: { utcStart: number; utcEnd: number }, utcH: number) {
  if (s.utcStart < s.utcEnd) {
    return utcH >= s.utcStart && utcH < s.utcEnd;
  }
  // wraps midnight
  return utcH >= s.utcStart || utcH < s.utcEnd;
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

  return (
    <div className="flex items-center gap-3">
      <div className="hidden sm:flex items-center gap-2">
        {TRADING_SESSIONS.map((s) => {
          const open = sessionOpen(s, utcH);
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
          ? `${String(utcH).padStart(2, "0")}:${String(utcM).padStart(2, "0")} UTC · ${now.toLocaleTimeString(
              "en-GB",
              { hour: "2-digit", minute: "2-digit", second: "2-digit" }
            )}`
          : "--:--"}
      </div>
    </div>
  );
}
