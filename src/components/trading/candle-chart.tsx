"use client";

import * as React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { type Candle } from "@/lib/trading-data";

function CandleShape(props: any) {
  const { x, y, width, height, payload } = props;
  if (!payload) return null;
  const { open, high, low, close } = payload;
  const isUp = close >= open;
  const color = isUp ? "var(--success)" : "var(--danger)";
  const w = Math.max(width - 1, 1);
  const cx = x + width / 2;
  const range = high - low || 1e-9;
  const bodyTop = y + ((high - Math.max(open, close)) / range) * height;
  const bodyBot = y + ((high - Math.min(open, close)) / range) * height;
  const bodyH = Math.max(bodyBot - bodyTop, 1);
  const wickTop = y;
  const wickBot = y + height;
  return (
    <g>
      <line x1={cx} x2={cx} y1={wickTop} y2={wickBot} stroke={color} strokeWidth={1} />
      <rect x={cx - w / 2} y={bodyTop} width={w} height={bodyH} fill={color} />
    </g>
  );
}

export function CandleChart({
  candles,
  height = 260,
  entry,
  sl,
  tp,
}: {
  candles: Candle[];
  height?: number;
  entry?: number;
  sl?: number;
  tp?: number;
}) {
  const data = candles;
  const prices = data.flatMap((c) => [c.high, c.low]);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const pad = (max - min) * 0.08 || 0.0001;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="time"
          tickFormatter={(t) =>
            new Date(t * 1000).toLocaleTimeString("en-GB", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
          tickLine={false}
          axisLine={false}
          minTickGap={40}
        />
        <YAxis
          domain={[min - pad, max + pad]}
          orientation="right"
          tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
          tickLine={false}
          axisLine={false}
          width={56}
          tickFormatter={(v) => Number(v).toFixed(4)}
        />
        {entry ? (
          <ReferenceLine y={entry} stroke="var(--chart-4)" strokeDasharray="4 3" />
        ) : null}
        {sl ? (
          <ReferenceLine y={sl} stroke="var(--danger)" strokeDasharray="3 3" />
        ) : null}
        {tp ? (
          <ReferenceLine y={tp} stroke="var(--success)" strokeDasharray="3 3" />
        ) : null}
        <Bar dataKey="low" shape={<CandleShape />} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}
