"use client";

import { useQuery } from "@tanstack/react-query";
import {
  type AIAnalysisResult,
  type BacktestSummary,
  type BacktestTrade,
  type Candle,
  type LogEntry,
  type NewsItem,
  type Position,
  type PriceTick,
  type Timeframe,
} from "@/lib/trading-data";

async function j<T>(u: string): Promise<T> {
  const r = await fetch(u, { cache: "no-store" });
  if (!r.ok) throw new Error(`req ${u} ${r.status}`);
  return r.json() as Promise<T>;
}

export function useTicks(enabled = true) {
  return useQuery<{ ticks: PriceTick[]; demo: boolean }>({
    queryKey: ["ticks"],
    queryFn: () => j("/api/trading/ticks"),
    refetchInterval: enabled ? 2500 : false,
    staleTime: 0,
  });
}

export function useCandles(symbol: string, tf: Timeframe, count = 120) {
  return useQuery<{ candles: Candle[] }>({
    queryKey: ["candles", symbol, tf, count],
    queryFn: () =>
      j(`/api/trading/candles?symbol=${symbol}&tf=${tf}&count=${count}`),
    staleTime: 30_000,
  });
}

export function usePositions() {
  return useQuery<{ positions: Position[] }>({
    queryKey: ["positions"],
    queryFn: () => j("/api/trading/positions"),
    refetchInterval: 5000,
    staleTime: 0,
  });
}

export function useNews() {
  return useQuery<{ news: NewsItem[] }>({
    queryKey: ["news"],
    queryFn: () => j("/api/trading/news"),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useLogs() {
  return useQuery<{ logs: LogEntry[] }>({
    queryKey: ["logs"],
    queryFn: () => j("/api/trading/logs"),
    refetchInterval: 15_000,
    staleTime: 0,
  });
}

export function useAnalysis(symbol: string, provider: string) {
  return useQuery<{ analysis: AIAnalysisResult }>({
    queryKey: ["analysis", symbol, provider],
    queryFn: () =>
      j(`/api/trading/analysis?symbol=${symbol}&provider=${provider}`),
    staleTime: 60_000,
  });
}

export function useBacktest(symbol: string, trades = 120) {
  return useQuery<{
    summary: BacktestSummary;
    trades: BacktestTrade[];
    equityCurve: { i: number; equity: number }[];
  }>({
    queryKey: ["backtest", symbol, trades],
    queryFn: () =>
      j(`/api/trading/backtest?symbol=${symbol}&trades=${trades}`),
    staleTime: 60_000,
  });
}
