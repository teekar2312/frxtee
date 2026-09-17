import { type NewsItem } from "@/lib/trading-data";

/** Demo news feed used when the Python backend is unavailable. */
export const DEMO_NEWS: NewsItem[] = [
  {
    id: "n1",
    source: "Finnhub",
    title: "Fed officials signal patience on rate cuts amid sticky inflation",
    summary:
      "Several Federal Reserve officials emphasized the need for more disinflation evidence before easing policy, denting risk appetite and lifting the dollar.",
    symbols: ["EURUSD", "GBPUSD", "USDJPY"],
    sentiment: "negative",
    impact: "high",
    category: "central_bank",
    publishedAt: new Date(Date.now() - 12 * 60000).toISOString(),
  },
  {
    id: "n2",
    source: "MARKETAUX",
    title: "Eurozone CPI cools to 2.4% YoY, below consensus",
    summary:
      "Headline inflation eased more than expected, strengthening the case for ECB rate cuts in June. EUR softer on growth concerns.",
    symbols: ["EURUSD", "EURGBP", "EURJPY"],
    sentiment: "negative",
    impact: "high",
    category: "economic_data",
    publishedAt: new Date(Date.now() - 38 * 60000).toISOString(),
  },
  {
    id: "n3",
    source: "Finnhub",
    title: "US Non-Farm Payrolls beat at 256k, unemployment 3.9%",
    summary:
      "Robust labor market data reduces odds of near-term Fed easing. Treasury yields spike, USD firms broadly.",
    symbols: ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"],
    sentiment: "positive",
    impact: "high",
    category: "economic_data",
    publishedAt: new Date(Date.now() - 95 * 60000).toISOString(),
  },
  {
    id: "n4",
    source: "MARKETAUX",
    title: "Gold climbs as Middle East tensions escalate",
    summary:
      "Safe-haven demand lifts gold above key resistance; silver tracks higher. Geopolitical risk premium builds.",
    symbols: ["XAUUSD", "XAGUSD"],
    sentiment: "positive",
    impact: "medium",
    category: "politics",
    publishedAt: new Date(Date.now() - 140 * 60000).toISOString(),
  },
  {
    id: "n5",
    source: "Finnhub",
    title: "BoJ keeps policy steady, yen weakens past 151",
    summary:
      "Bank of Japan maintained accommodative stance; USDJPY tests intervention zone. Traders watch for verbal intervention.",
    symbols: ["USDJPY", "EURJPY", "GBPJPY"],
    sentiment: "negative",
    impact: "medium",
    category: "central_bank",
    publishedAt: new Date(Date.now() - 200 * 60000).toISOString(),
  },
  {
    id: "n6",
    source: "MARKETAUX",
    title: "Oil slides 2% on demand-growth worries, OPEC+ in focus",
    summary:
      "Crude extends losses as global demand outlook softens. CAD and commodity-linked currencies pressured.",
    symbols: ["USDCAD", "AUDUSD"],
    sentiment: "negative",
    impact: "low",
    category: "commodities",
    publishedAt: new Date(Date.now() - 260 * 60000).toISOString(),
  },
  {
    id: "n7",
    source: "Economic Calendar",
    title: "Upcoming: US CPI (MoM) — high impact",
    summary:
      "Consensus 0.3% MoM, 3.4% YoY. Deviation > 0.1% likely to drive 30-50 pip volatility on USD pairs.",
    symbols: ["EURUSD", "GBPUSD", "USDJPY"],
    sentiment: "neutral",
    impact: "high",
    category: "economic_data",
    publishedAt: new Date(Date.now() - 320 * 60000).toISOString(),
  },
  {
    id: "n8",
    source: "Finnhub",
    title: "UK GDP surprises to the upside, GBP rallies",
    summary:
      "Sterling gains after stronger-than-expected growth data; BoE rate-cut bets trimmed.",
    symbols: ["GBPUSD", "EURGBP", "GBPJPY"],
    sentiment: "positive",
    impact: "medium",
    category: "economic_data",
    publishedAt: new Date(Date.now() - 410 * 60000).toISOString(),
  },
];
