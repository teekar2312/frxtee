import { NextRequest, NextResponse } from "next/server";
import {
  ANALYSIS_DIMENSIONS,
  basePriceFor,
  pipFor,
  type AIAnalysisResult,
} from "@/lib/trading-data";
import { proxyBackend, passthroughQuery } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

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

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const symbol = searchParams.get("symbol") ?? "EURUSD";
  const provider = searchParams.get("provider") ?? "zai";

  // Try the Python backend first (real AI + ML prediction)
  const qs = passthroughQuery(req);
  const r = await proxyBackend<{ analysis: AIAnalysisResult }>(
    `/api/trading/analysis?${qs}`,
    {},
    5000 // AI inference may take a few seconds
  );
  if (r.data) {
    return NextResponse.json({ analysis: r.data.analysis, demo: false });
  }

  // Fallback: deterministic mock analysis
  const rnd = seeded(symbol + provider);

  const base = basePriceFor(symbol);
  const pip = pipFor(symbol);
  const signals: AIAnalysisResult["signal"][] = [
    "STRONG BUY",
    "BUY",
    "NEUTRAL",
    "SELL",
    "STRONG SELL",
  ];
  const signal = signals[Math.floor(rnd() * signals.length)];
  const confidence = 0.55 + rnd() * 0.42;

  const summaries: Record<string, string> = {
    "STRONG BUY":
      "Confluence of bullish momentum (EMA stack + MACD cross-up), positive sentiment flow, and risk-on macro backdrop. Volume confirms.",
    BUY: "Trend bias bullish but not yet full confluence; awaiting close above near-term resistance for higher-conviction entry.",
    NEUTRAL: "Mixed signals — momentum fading, news flow balanced. Stand aside until regime clarity improves.",
    SELL: "Downside pressure building under resistance; bearish divergence on RSI. Prefer shorts into strength.",
    "STRONG SELL":
      "Bearish regime: trending lower, volume rising into declines, macro headwinds from hawkish central bank & risk-off sentiment.",
  };

  const direction = signal.includes("BUY") ? 1 : signal.includes("SELL") ? -1 : 0;
  const entry = base + direction * pip * 2 * (0.5 + rnd());
  const sl = entry - direction * pip * 10;
  const tp = entry + direction * pip * 15;

  const dimensions = ANALYSIS_DIMENSIONS.map((d) => {
    const score = Math.round((rnd() * 100 - 50) * direction + 50);
    return {
      id: d.id,
      label: d.label,
      score: Math.max(0, Math.min(100, score)),
      note: dimNote(d.id, rnd),
    };
  });

  const result: AIAnalysisResult = {
    symbol,
    signal,
    confidence: Math.round(confidence * 100),
    summary: summaries[signal],
    dimensions,
    suggestedEntry: entry,
    suggestedSL: sl,
    suggestedTP: tp,
    riskScore: Math.round((1 - confidence) * 100),
    provider,
    generatedAt: new Date().toISOString(),
  };
  return NextResponse.json({ analysis: result, demo: true });
}

function dimNote(id: string, rnd: () => number): string {
  const notes: Record<string, string[]> = {
    central_bank: [
      "Fed dot-plot signals 2 cuts in 2025 — mildly dovish.",
      "ECB on hold; June cut dependent on wage data.",
      "BoJ intervention risk elevated above 151.00.",
    ],
    economic_data: [
      "NFP beat (256k); unemployment 3.9% — USD supportive.",
      "CPI cooling trend intact but core sticky.",
      "Retail sales soft; growth concerns rising.",
    ],
    politics: [
      "Middle East risk premium rising; safe-haven bid intact.",
      "US election uncertainty adds FX volatility.",
      "EU fiscal discipline talks in focus.",
    ],
    fiscal: [
      "US Treasury issuance heavy; term premiums rising.",
      "Fiscal deficits widening — long-term USD weight.",
      "Stimulus measures announced in Asia.",
    ],
    commodities: [
      "Gold bid on haven demand; correlation to USD negative.",
      "Oil softens on demand worries; CAD pressured.",
      "Copper firm — China stimulus optimism.",
    ],
    sentiment: [
      "Risk appetite mixed; equity-bond correlation positive.",
      "VIX elevated — positioning defensive.",
      "Retail flows turning contrarian-bearish.",
    ],
    breaking_news: [
      "No tier-1 breaking headlines in last 15 min.",
      "Watch: central-bank speaker scheduled 14:00 UTC.",
      "Flash headline: trade-tension rhetoric escalating.",
    ],
  };
  const arr = notes[id] ?? [""];
  return arr[Math.floor(rnd() * arr.length)];
}
