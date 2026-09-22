/**
 * WebSocket hook for real-time tick/position/alert updates.
 * Connects to the ws-pusher mini-service on port 3003.
 */
"use client";

import * as React from "react";
import { io, Socket } from "socket.io-client";
import type { PriceTick, Position } from "@/lib/trading-data";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "";

let _socket: Socket | null = null;

export function useWebSocket(symbols: string[]) {
  const [ticks, setTicks] = React.useState<Record<string, PriceTick>>({});
  const [positions, setPositions] = React.useState<Position[]>([]);
  const [connected, setConnected] = React.useState(false);

  React.useEffect(() => {
    if (!WS_URL) return;
    if (!_socket) {
      _socket = io(WS_URL, { path: "/", transports: ["websocket"] });
    }
    const s = _socket;

    s.on("connect", () => setConnected(true));
    s.on("disconnect", () => setConnected(false));

    // subscribe to symbol rooms
    s.emit("subscribe", symbols);

    // tick updates
    s.on("tick", (t: PriceTick) => {
      setTicks((prev) => ({ ...prev, [t.symbol]: t }));
    });

    // batch ticks for ticker tape
    s.on("ticks", (batch: PriceTick[]) => {
      setTicks((prev) => {
        const next = { ...prev };
        for (const t of batch) next[t.symbol] = t;
        return next;
      });
    });

    // position updates
    s.on("positions", (pos: Position[]) => {
      setPositions(pos);
    });

    return () => {
      s.off("connect");
      s.off("disconnect");
      s.off("tick");
      s.off("ticks");
      s.off("positions");
    };
  }, [symbols.join(",")]);

  return { ticks, positions, connected };
}
