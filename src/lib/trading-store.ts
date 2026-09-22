"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import {
  AI_PROVIDERS,
  MONEY_MGMT_DEFAULTS,
  TECHNICAL_INDICATORS,
  TRADING_PAIRS,
  TRADING_SESSIONS,
  type AIProviderId,
  type Timeframe,
} from "@/lib/trading-data";

export type Mode = "auto" | "manual";
export type Density = "compact" | "dense" | "minimal";

const DENSITY_VALUES: Density[] = ["compact", "dense", "minimal"];

/** Read saved density from localStorage; safe for SSR (returns "compact"). */
function loadDensity(): Density {
  if (typeof window === "undefined") return "compact";
  try {
    const saved = window.localStorage.getItem("zenitrade-density");
    if (saved && DENSITY_VALUES.includes(saved as Density)) return saved as Density;
  } catch {
    /* ignore */
  }
  return "compact";
}

interface TradingState {
  // connection
  mt5Connected: boolean;
  demoMode: boolean;
  accountEquity: number;
  accountBalance: number;
  setMt5Connected: (v: boolean) => void;
  toggleDemo: () => void;

  // display density
  density: Density;
  setDensity: (d: Density) => void;

  // trading config
  symbols: string[];
  setSymbols: (s: string[]) => void;
  toggleSymbol: (s: string) => void;
  setAutoSymbols: () => void;

  timeframes: Timeframe[];
  setTimeframes: (t: Timeframe[]) => void;
  toggleTimeframe: (t: Timeframe) => void;
  setAutoTimeframes: () => void;

  sessions: string[];
  setSessions: (s: string[]) => void;
  toggleSession: (s: string) => void;
  setAutoSessions: () => void;

  // AI
  aiProvider: AIProviderId;
  setAiProvider: (p: AIProviderId) => void;
  autoTradeMode: boolean;
  setAutoTradeMode: (v: boolean) => void;
  autoIndicators: boolean;
  setAutoIndicators: (v: boolean) => void;
  autoTrailing: boolean;
  setAutoTrailing: (v: boolean) => void;
  autoRisk: boolean;
  setAutoRisk: (v: boolean) => void;
  autoPair: boolean;
  setAutoPair: (v: boolean) => void;
  autoTimeframe: boolean;
  setAutoTimeframe: (v: boolean) => void;
  autoSession: boolean;
  setAutoSession: (v: boolean) => void;

  // indicators
  indicators: string[];
  setIndicators: (s: string[]) => void;
  toggleIndicator: (id: string) => void;
  autoSelectIndicators: () => void;

  // money management
  riskPerTrade: number;
  setRiskPerTrade: (v: number) => void;
  stopLossPips: number;
  setStopLossPips: (v: number) => void;
  rrRatio: number;
  setRrRatio: (v: number) => void;
  maxOpenPositions: number;
  setMaxOpenPositions: (v: number) => void;
  dailyRiskLimit: number;
  setDailyRiskLimit: (v: number) => void;
  dailyTarget: number;
  setDailyTarget: (v: number) => void;
  avoidNews: boolean;
  setAvoidNews: (v: boolean) => void;
  trailingEnabled: boolean;
  setTrailingEnabled: (v: boolean) => void;
  trailingPips: number;
  setTrailingPips: (v: number) => void;

  // api keys (stored locally only, never persisted to server)
  keys: {
    finnhub: string;
    marketaux: string;
    zai: string;
    groq: string;
    google: string;
  };
  setKey: (k: keyof TradingState["keys"], v: string) => void;

  // email notifications
  emailEnabled: boolean;
  emailTo: string;
  setEmailEnabled: (v: boolean) => void;
  setEmailTo: (v: string) => void;
}

export const useTradingStore = create<TradingState>()(
  persist(
    (set) => ({
  mt5Connected: false,
  demoMode: true,
  accountEquity: 10000,
  accountBalance: 10000,
  setMt5Connected: (v) => set({ mt5Connected: v }),
  toggleDemo: () => set((s) => ({ demoMode: !s.demoMode })),

  density: loadDensity(),
  setDensity: (d) => set({ density: d }),

  symbols: ["EURUSD", "GBPUSD"],
  setSymbols: (s) => set({ symbols: s }),
  toggleSymbol: (sym) =>
    set((s) => {
      const exists = s.symbols.includes(sym);
      return {
        symbols: exists
          ? s.symbols.filter((x) => x !== sym)
          : [...s.symbols, sym],
      };
    }),
  setAutoSymbols: () =>
    set({
      symbols: TRADING_PAIRS.slice(0, 4).map((p) => p.symbol),
    }),

  timeframes: ["M15", "H1"],
  setTimeframes: (t) => set({ timeframes: t }),
  toggleTimeframe: (tf) =>
    set((s) => {
      const exists = s.timeframes.includes(tf);
      return {
        timeframes: exists
          ? s.timeframes.filter((x) => x !== tf)
          : [...s.timeframes, tf],
      };
    }),
  setAutoTimeframes: () => set({ timeframes: ["M15", "H1", "H4"] }),

  sessions: ["london", "newyork"],
  setSessions: (s) => set({ sessions: s }),
  toggleSession: (ses) =>
    set((s) => {
      const exists = s.sessions.includes(ses);
      return {
        sessions: exists
          ? s.sessions.filter((x) => x !== ses)
          : [...s.sessions, ses],
      };
    }),
  setAutoSessions: () =>
    set({
      sessions: TRADING_SESSIONS.map((x) => x.id),
    }),

  aiProvider: "zai",
  setAiProvider: (p) => set({ aiProvider: p }),
  autoTradeMode: false,
  setAutoTradeMode: (v) => set({ autoTradeMode: v }),
  autoIndicators: false,
  setAutoIndicators: (v) => set({ autoIndicators: v }),
  autoTrailing: false,
  setAutoTrailing: (v) => set({ autoTrailing: v }),
  autoRisk: false,
  setAutoRisk: (v) => set({ autoRisk: v }),
  autoPair: false,
  setAutoPair: (v) => set({ autoPair: v }),
  autoTimeframe: false,
  setAutoTimeframe: (v) => set({ autoTimeframe: v }),
  autoSession: false,
  setAutoSession: (v) => set({ autoSession: v }),

  indicators: ["ema", "rsi", "macd", "atr"],
  setIndicators: (s) => set({ indicators: s }),
  toggleIndicator: (id) =>
    set((s) => {
      const exists = s.indicators.includes(id);
      return {
        indicators: exists
          ? s.indicators.filter((x) => x !== id)
          : [...s.indicators, id],
      };
    }),
  autoSelectIndicators: () =>
    set({
      indicators: TECHNICAL_INDICATORS.slice(0, 8).map((i) => i.id),
    }),

  riskPerTrade: MONEY_MGMT_DEFAULTS.riskPerTradePct,
  setRiskPerTrade: (v) => set({ riskPerTrade: v }),
  stopLossPips: 10,
  setStopLossPips: (v) => set({ stopLossPips: v }),
  rrRatio: MONEY_MGMT_DEFAULTS.rrRatio,
  setRrRatio: (v) => set({ rrRatio: v }),
  maxOpenPositions: MONEY_MGMT_DEFAULTS.maxOpenPositions,
  setMaxOpenPositions: (v) => set({ maxOpenPositions: v }),
  dailyRiskLimit: MONEY_MGMT_DEFAULTS.dailyRiskLimitPct,
  setDailyRiskLimit: (v) => set({ dailyRiskLimit: v }),
  dailyTarget: MONEY_MGMT_DEFAULTS.dailyTargetPct,
  setDailyTarget: (v) => set({ dailyTarget: v }),
  avoidNews: MONEY_MGMT_DEFAULTS.avoidHighImpactNews,
  setAvoidNews: (v) => set({ avoidNews: v }),
  trailingEnabled: true,
  setTrailingEnabled: (v) => set({ trailingEnabled: v }),
  trailingPips: 8,
  setTrailingPips: (v) => set({ trailingPips: v }),

  keys: { finnhub: "", marketaux: "", zai: "", groq: "", google: "" },
  setKey: (k, v) => set((s) => ({ keys: { ...s.keys, [k]: v } })),

  emailEnabled: false,
  emailTo: "",
  setEmailEnabled: (v) => set({ emailEnabled: v }),
  setEmailTo: (v) => set({ emailTo: v }),
    }),
    {
      name: "zenitrade-store",
      // only persist config, not live connection/equity state
      partialize: (s) => ({
        symbols: s.symbols,
        timeframes: s.timeframes,
        sessions: s.sessions,
        indicators: s.indicators,
        aiProvider: s.aiProvider,
        autoTradeMode: s.autoTradeMode,
        autoIndicators: s.autoIndicators,
        autoTrailing: s.autoTrailing,
        autoRisk: s.autoRisk,
        autoPair: s.autoPair,
        autoTimeframe: s.autoTimeframe,
        autoSession: s.autoSession,
        riskPerTrade: s.riskPerTrade,
        stopLossPips: s.stopLossPips,
        rrRatio: s.rrRatio,
        maxOpenPositions: s.maxOpenPositions,
        dailyRiskLimit: s.dailyRiskLimit,
        dailyTarget: s.dailyTarget,
        avoidNews: s.avoidNews,
        trailingEnabled: s.trailingEnabled,
        trailingPips: s.trailingPips,
        keys: s.keys,
        emailEnabled: s.emailEnabled,
        emailTo: s.emailTo,
        density: s.density,
      }),
    }
  )
);

export function useActiveProvider() {
  const id = useTradingStore((s) => s.aiProvider);
  return AI_PROVIDERS.find((p) => p.id === id)!;
}
