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

async function j<T>(u: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(u, { cache: "no-store", signal });
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
    refetchInterval: 15_000, // live chart refresh
    staleTime: 10_000,
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

/** Analyze ALL active pairs via single batch endpoint (1 round-trip).
 * Falls back to parallel individual fetches if batch endpoint unavailable. */
export function useMultiAnalysis(
  symbols: string[],
  provider: string,
  enabled = true
) {
  return useQuery<{
    results: Record<string, AIAnalysisResult | undefined>;
  }>({
    queryKey: ["multi-analysis", symbols.join(","), provider],
    queryFn: async ({ signal }) => {
      // Single batch request — reduces 5 round-trips to 1
      try {
        const r = await j<{
          results: Record<string, AIAnalysisResult | undefined>;
        }>(
          `/api/trading/analysis/batch?symbols=${symbols.join(",")}&provider=${provider}`,
          signal
        );
        return { results: r.results ?? {} };
      } catch {
        // Fallback: parallel individual fetches (demo mode)
        const entries = await Promise.all(
          symbols.map(async (s) => {
            try {
              const r = await j<{ analysis: AIAnalysisResult }>(
                `/api/trading/analysis?symbol=${s}&provider=${provider}`,
                signal
              );
              return [s, r.analysis] as const;
            } catch {
              return [s, undefined] as const;
            }
          })
        );
        return { results: Object.fromEntries(entries) };
      }
    },
    enabled: enabled && symbols.length > 0,
    staleTime: 60_000,
    placeholderData: (prev) => prev, // keep previous data while refetching (no flash)
  });
}

export function useBacktest(symbol: string, trades = 120, tf?: string) {
  return useQuery<{
    summary: BacktestSummary;
    trades: BacktestTrade[];
    equityCurve: { i: number; equity: number }[];
  }>({
    queryKey: ["backtest", symbol, trades, tf ?? "H1"],
    queryFn: () =>
      j(`/api/trading/backtest?symbol=${symbol}&trades=${trades}`),
    staleTime: 60_000,
  });
}

export interface MLModelInfo {
  exists: boolean;
  version: string;
  train_acc: number | null;
  test_acc: number | null;
  symbol: string | null;
  trained_at: string | null;
  n_samples: number | null;
  drift?: number;
  drift_threshold?: number;
  demo?: boolean;
}

export function useTrades() {
  return useQuery<{ trades: any[]; demo?: boolean }>({
    queryKey: ["trades"],
    queryFn: () => j("/api/trading/trades"),
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

export function useMLInfo() {
  return useQuery<MLModelInfo>({
    queryKey: ["ml-info"],
    queryFn: () => j("/api/trading/ml/info"),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useStatus() {
  return useQuery<{
    connected: boolean;
    demo: boolean;
    terminal: string | null;
    account: {
      login: string;
      server: string;
      leverage: string;
      currency: string;
      balance?: number;
      equity?: number;
    } | null;
    message: string;
  }>({
    queryKey: ["status"],
    queryFn: () => j("/api/trading/status"),
    refetchInterval: 10_000,
    staleTime: 5_000,
  });
}
