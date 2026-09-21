import { NextRequest, NextResponse } from "next/server";
import {
  type AIAnalysisResult,
  type Timeframe,
} from "@/lib/trading-data";
import { proxyBackend, passthroughQuery } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

// Inline demo analysis generator (used when backend unreachable)
function seeded(str: string) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h += 0x6d2b79f5;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function demoAnalysis(symbol: string, provider: string): AIAnalysisResult {
  const rnd = seeded(symbol + provider);
  const base = {
    EURUSD: 1.0865, GBPUSD: 1.2710, USDJPY: 151.42, USDCHF: 0.9012,
    AUDUSD: 0.6584, USDCAD: 1.3621, NZDUSD: 0.6012, EURGBP: 0.8550,
    EURJPY: 164.55, GBPJPY: 192.48, AUDJPY: 99.66, EURAUD: 1.6500,
    XAUUSD: 2338.5, XAGUSD: 27.42,
  }[symbol] ?? 1.0;
  const pip = symbol.includes("JPY") || symbol.startsWith("XAG") ? 0.01 : symbol.startsWith("XAU") ? 0.1 : 0.0001;
  const signals: AIAnalysisResult["signal"][] = ["STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"];
  const signal = signals[Math.floor(rnd() * signals.length)];
  const confidence = Math.round(55 + rnd() * 40);
  const direction = signal.includes("BUY") ? 1 : signal.includes("SELL") ? -1 : 0;
  const entry = base + direction * pip * 2 * (0.5 + rnd());
  const sl = entry - direction * pip * 10;
  const tp = entry + direction * pip * 15;
  const dims = [
    { id: "central_bank", label: "Kebijakan Bank Sentral", score: Math.round(rnd() * 100), note: "demo" },
    { id: "economic_data", label: "Data Ekonomi Utama", score: Math.round(rnd() * 100), note: "demo" },
    { id: "politics", label: "Kondisi Politik & Geopolitik", score: Math.round(rnd() * 100), note: "demo" },
    { id: "fiscal", label: "Kebijakan Fiskal & Ekonomi", score: Math.round(rnd() * 100), note: "demo" },
    { id: "commodities", label: "Harga Komoditas", score: Math.round(rnd() * 100), note: "demo" },
    { id: "sentiment", label: "Sentimen Pasar", score: Math.round(rnd() * 100), note: "demo" },
    { id: "breaking_news", label: "Berita Dadakan", score: Math.round(rnd() * 100), note: "demo" },
  ];
  return {
    symbol, signal, confidence,
    summary: `Demo ${signal} bias on ${symbol}.`,
    dimensions: dims,
    suggestedEntry: entry, suggestedSL: sl, suggestedTP: tp,
    riskScore: 100 - confidence,
    provider: "heuristic",
    generatedAt: new Date().toISOString(),
  };
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const symbols = searchParams.get("symbols") ?? "EURUSD";
  const provider = searchParams.get("provider") ?? "zai";

  // Try the Python backend batch endpoint first (1 round-trip for all pairs)
  const qs = passthroughQuery(req);
  const r = await proxyBackend<{ results: Record<string, AIAnalysisResult | undefined> }>(
    `/api/trading/analysis/batch?${qs}`,
    {},
    8000
  );
  if (r.data) {
    return NextResponse.json({ ...r.data, demo: false });
  }

  // Fallback: generate demo analysis for each pair (server-side, no fetch needed)
  const symList = symbols.split(",").map((s) => s.trim()).filter(Boolean);
  const results: Record<string, AIAnalysisResult | undefined> = {};
  for (const s of symList) {
    results[s] = demoAnalysis(s, provider);
  }
  return NextResponse.json({ results, provider, demo: true });
}
