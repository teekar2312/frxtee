// Core trading domain constants, types and mock data generators
// Mirrors the structure exposed by the Python MT5 backend (FastAPI).

export const TRADING_PAIRS = [
  { symbol: "EURUSD", display: "EUR/USD", category: "Major", pip: 0.0001, digits: 5 },
  { symbol: "GBPUSD", display: "GBP/USD", category: "Major", pip: 0.0001, digits: 5 },
  { symbol: "USDJPY", display: "USD/JPY", category: "Major", pip: 0.01, digits: 3 },
  { symbol: "USDCHF", display: "USD/CHF", category: "Major", pip: 0.0001, digits: 5 },
  { symbol: "AUDUSD", display: "AUD/USD", category: "Major", pip: 0.0001, digits: 5 },
  { symbol: "USDCAD", display: "USD/CAD", category: "Major", pip: 0.0001, digits: 5 },
  { symbol: "NZDUSD", display: "NZD/USD", category: "Major", pip: 0.0001, digits: 5 },
  { symbol: "EURGBP", display: "EUR/GBP", category: "Cross", pip: 0.0001, digits: 5 },
  { symbol: "EURJPY", display: "EUR/JPY", category: "Cross", pip: 0.01, digits: 3 },
  { symbol: "GBPJPY", display: "GBP/JPY", category: "Cross", pip: 0.01, digits: 3 },
  { symbol: "AUDJPY", display: "AUD/JPY", category: "Cross", pip: 0.01, digits: 3 },
  { symbol: "EURAUD", display: "EUR/AUD", category: "Cross", pip: 0.0001, digits: 5 },
  { symbol: "XAUUSD", display: "XAU/USD", category: "Metal", pip: 0.1, digits: 2 },
  { symbol: "XAGUSD", display: "XAG/USD", category: "Metal", pip: 0.01, digits: 3 },
] as const;

export const TIMEFRAMES = [
  { value: "M1", label: "M1", seconds: 60 },
  { value: "M5", label: "M5", seconds: 300 },
  { value: "M15", label: "M15", seconds: 900 },
  { value: "M30", label: "M30", seconds: 1800 },
  { value: "H1", label: "H1", seconds: 3600 },
  { value: "H4", label: "H4", seconds: 14400 },
  { value: "D1", label: "D1", seconds: 86400 },
  { value: "W1", label: "W1", seconds: 604800 },
  { value: "MN", label: "MN", seconds: 2592000 },
] as const;

export type Timeframe = (typeof TIMEFRAMES)[number]["value"];

// Trading sessions with approximate UTC windows
export const TRADING_SESSIONS = [
  {
    id: "sydney",
    name: "Sydney",
    utcStart: 21,
    utcEnd: 6,
    color: "var(--chart-4)",
    tz: "AEST",
  },
  {
    id: "tokyo",
    name: "Tokyo",
    utcStart: 0,
    utcEnd: 9,
    color: "var(--chart-5)",
    tz: "JST",
  },
  {
    id: "london",
    name: "London",
    utcStart: 7,
    utcEnd: 16,
    color: "var(--chart-1)",
    tz: "GMT",
  },
  {
    id: "newyork",
    name: "New York",
    utcStart: 12,
    utcEnd: 21,
    color: "var(--chart-2)",
    tz: "EST",
  },
] as const;

export const AI_PROVIDERS = [
  {
    id: "zai",
    name: "Z.AI",
    model: "glm-4.6",
    desc: "General-purpose LLM with strong reasoning",
    latencyMs: 720,
  },
  {
    id: "groq",
    name: "Groq AI",
    model: "llama-3.3-70b",
    desc: "Ultra-low latency inference",
    latencyMs: 180,
  },
  {
    id: "google",
    name: "Google AI Studio",
    model: "gemini-1.5-pro",
    desc: "Multimodal, long context",
    latencyMs: 980,
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    model: "deepseek/deepseek-chat",
    desc: "100+ models via unified API",
    latencyMs: 500,
  },
  {
    id: "local",
    name: "Local AI",
    model: "ollama / llama3",
    desc: "On-device, private inference",
    latencyMs: 240,
  },
] as const;

export type AIProviderId = (typeof AI_PROVIDERS)[number]["id"];

export const TECHNICAL_INDICATORS = [
  { id: "ema", name: "EMA", category: "Trend", full: "Exponential Moving Average" },
  { id: "sma", name: "SMA", category: "Trend", full: "Simple Moving Average" },
  { id: "vwap", name: "VWAP", category: "Volume", full: "Volume Weighted Average Price" },
  { id: "supertrend", name: "Supertrend", category: "Trend", full: "Supertrend" },
  { id: "psar", name: "Parabolic SAR", category: "Trend", full: "Parabolic Stop and Reverse" },
  { id: "ichimoku", name: "Ichimoku Cloud", category: "Trend", full: "Ichimoku Kinko Hyo" },
  { id: "hma", name: "HMA", category: "Trend", full: "Hull Moving Average" },
  { id: "rsi", name: "RSI", category: "Momentum", full: "Relative Strength Index" },
  { id: "stochastic", name: "Stochastic", category: "Momentum", full: "Stochastic Oscillator" },
  { id: "macd", name: "MACD", category: "Momentum", full: "Moving Avg Convergence Divergence" },
  { id: "cci", name: "CCI", category: "Momentum", full: "Commodity Channel Index" },
  { id: "momentum", name: "Momentum", category: "Momentum", full: "Momentum Indicator" },
  { id: "williamsr", name: "Williams %R", category: "Momentum", full: "Williams Percent R" },
  { id: "tsi", name: "TSI", category: "Momentum", full: "True Strength Index" },
  { id: "roc", name: "ROC", category: "Momentum", full: "Rate of Change" },
  { id: "stc", name: "Schaff Trend Cycle", category: "Momentum", full: "Schaff Trend Cycle" },
  { id: "ultimate", name: "Ultimate Oscillator", category: "Momentum", full: "Ultimate Oscillator" },
  { id: "bbands", name: "Bollinger Bands", category: "Volatility", full: "Bollinger Bands" },
  { id: "atr", name: "ATR", category: "Volatility", full: "Average True Range" },
  { id: "keltner", name: "Keltner Channel", category: "Volatility", full: "Keltner Channel" },
  { id: "donchian", name: "Donchian Channel", category: "Volatility", full: "Donchian Channel" },
  { id: "linreg", name: "Linear Reg Channel", category: "Volatility", full: "Linear Regression Channel" },
  { id: "stddev", name: "Standard Deviation", category: "Volatility", full: "Standard Deviation" },
  { id: "chaikinvol", name: "Chaikin Volatility", category: "Volatility", full: "Chaikin Volatility" },
  { id: "volratio", name: "Volatility Ratio", category: "Volatility", full: "Volatility Ratio" },
  { id: "obv", name: "OBV", category: "Volume", full: "On Balance Volume" },
  { id: "mfi", name: "MFI", category: "Volume", full: "Money Flow Index" },
  { id: "tickvol", name: "Tick Volume", category: "Volume", full: "Tick Volume" },
  { id: "volprofile", name: "Volume Profile", category: "Volume", full: "Volume Profile" },
  { id: "accdist", name: "Accumulation/Dist", category: "Volume", full: "Accumulation Distribution" },
] as const;

export const INDICATOR_CATEGORIES = [
  "Trend",
  "Momentum",
  "Volatility",
  "Volume",
] as const;

// FINEX Indonesia broker specs
export const BROKER_SPEC = {
  name: "FINEX Indonesia",
  leverageFx: "1:500",
  leverageMetal: "1:500",
  spreadFrom: "0.5 pip",
  commission: "$1 / lot",
  minVolume: 0.01,
  maxVolume: 50,
  maxPositions: 200,
  marginCall: 50,
  stopOut: 20,
  accountType: "Standard ECN",
} as const;

// Money management defaults aligned to the spec
export const MONEY_MGMT_DEFAULTS = {
  riskPerTradePct: 1.0,
  stopLossPipsMin: 5,
  stopLossPipsMax: 15,
  rrRatio: 1.5,
  maxOpenPositions: 3,
  dailyRiskLimitPct: 3.0,
  dailyTargetPct: 2.0,
  avoidHighImpactNews: true,
} as const;

// AI analysis dimensions
export const ANALYSIS_DIMENSIONS = [
  { id: "central_bank", label: "Kebijakan Bank Sentral" },
  { id: "economic_data", label: "Data Ekonomi Utama" },
  { id: "politics", label: "Kondisi Politik & Geopolitik" },
  { id: "fiscal", label: "Kebijakan Fiskal & Ekonomi" },
  { id: "commodities", label: "Harga Komoditas" },
  { id: "sentiment", label: "Sentimen Pasar" },
  { id: "breaking_news", label: "Berita Dadakan" },
] as const;

export type PairSymbol = string;

export interface PriceTick {
  symbol: string;
  bid: number;
  ask: number;
  spreadPips: number;
  changePct: number;
  digits: number;
  ts: number;
}

export interface Position {
  ticket: number;
  symbol: string;
  type: "BUY" | "SELL";
  volume: number;
  openPrice: number;
  currentPrice: number;
  sl: number | null;
  tp: number | null;
  profit: number;
  pips: number;
  openTime: string;
  comment: string;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface NewsItem {
  id: string;
  source: "Finnhub" | "MARKETAUX" | "Economic Calendar";
  title: string;
  summary: string;
  symbols: string[];
  sentiment: "positive" | "negative" | "neutral";
  impact: "high" | "medium" | "low";
  category: string;
  publishedAt: string;
  url?: string;
}

export interface LogEntry {
  id: string;
  ts: string;
  level: "INFO" | "WARN" | "ERROR" | "DEBUG" | "TRADE";
  source: string;
  message: string;
}

export interface AIAnalysisResult {
  symbol: string;
  signal: "STRONG BUY" | "BUY" | "NEUTRAL" | "SELL" | "STRONG SELL";
  confidence: number;
  summary: string;
  dimensions: { id: string; label: string; score: number; note: string }[];
  suggestedEntry: number;
  suggestedSL: number;
  suggestedTP: number;
  riskScore: number;
  provider: string;
  generatedAt: string;
}

export interface PriceAlert {
  id: string;
  symbol: string;
  condition: "above" | "below" | "cross_up" | "cross_down";
  price: number;
  active: boolean;
  createdAt: string;
  triggered: boolean;
}

export interface BacktestTrade {
  id: number;
  symbol: string;
  side: "BUY" | "SELL";
  entry: number;
  exit: number;
  openTime: string;
  closeTime: string;
  pnl: number;
  pips: number;
  pipsR: number;
}

export interface BacktestSummary {
  netProfit: number;
  totalTrades: number;
  winRate: number;
  profitFactor: number;
  maxDrawdown: number;
  sharpe: number;
  avgWin: number;
  avgLoss: number;
  expectancy: number;
}

// ---------- deterministic mock generators ----------
const BASE_PRICES: Record<string, number> = {
  EURUSD: 1.0865,
  GBPUSD: 1.2710,
  USDJPY: 151.42,
  USDCHF: 0.9012,
  AUDUSD: 0.6584,
  USDCAD: 1.3621,
  NZDUSD: 0.6012,
  EURGBP: 0.8550,
  EURJPY: 164.55,
  GBPJPY: 192.48,
  AUDJPY: 99.66,
  EURAUD: 1.6500,
  XAUUSD: 2338.5,
  XAGUSD: 27.42,
};

export function basePriceFor(symbol: string): number {
  return BASE_PRICES[symbol] ?? 1.0;
}

export function digitsFor(symbol: string): number {
  const p = TRADING_PAIRS.find((x) => x.symbol === symbol);
  return p?.digits ?? 5;
}

export function pipFor(symbol: string): number {
  const p = TRADING_PAIRS.find((x) => x.symbol === symbol);
  return p?.pip ?? 0.0001;
}

// seeded RNG so SSR & client match
let _seed = 1337;
function srand() {
  _seed = (_seed * 1103515245 + 12345) & 0x7fffffff;
  return _seed / 0x7fffffff;
}
export function reseed(s: number) {
  _seed = s >>> 0;
}

export function genPriceTicks(): PriceTick[] {
  reseed(Math.floor(Date.now() / 1000));
  return TRADING_PAIRS.map((p) => {
    const base = basePriceFor(p.symbol);
    const drift = (srand() - 0.5) * p.pip * 40;
    const bid = base + drift;
    const spread = (p.pip * (0.4 + srand() * 1.2));
    const ask = bid + spread;
    const changePct = (srand() - 0.5) * 1.4;
    return {
      symbol: p.symbol,
      bid,
      ask,
      spreadPips: spread / p.pip,
      changePct,
      digits: p.digits,
      ts: Date.now(),
    };
  });
}

export function genCandles(symbol: string, count: number, tf: Timeframe): Candle[] {
  reseed(symbol.split("").reduce((a, c) => a + c.charCodeAt(0), 7) + count);
  let price = basePriceFor(symbol);
  const pip = pipFor(symbol);
  const tfSec =
    TIMEFRAMES.find((t) => t.value === tf)?.seconds ?? 300;
  const now = Math.floor(Date.now() / 1000);
  const out: Candle[] = [];
  for (let i = count - 1; i >= 0; i--) {
    const open = price;
    const range = pip * (8 + srand() * 30);
    const close = open + (srand() - 0.5) * range * 2;
    const high = Math.max(open, close) + srand() * range;
    const low = Math.min(open, close) - srand() * range;
    out.push({
      time: now - i * tfSec,
      open,
      high,
      low,
      close,
      volume: Math.floor(100 + srand() * 900),
    });
    price = close;
  }
  return out;
}

export function genPositions(): Position[] {
  reseed(991);
  const picks = ["EURUSD", "GBPJPY", "XAUUSD"];
  return picks.map((sym, i) => {
    const type: Position["type"] = i % 2 === 0 ? "BUY" : "SELL";
    const base = basePriceFor(sym);
    const pip = pipFor(sym);
    const openPrice = base + (srand() - 0.5) * pip * 20;
    const current = base + (srand() - 0.5) * pip * 10;
    const pips =
      ((type === "BUY" ? current - openPrice : openPrice - current) / pip);
    const profit = pips * 1 * (sym.includes("JPY") || sym.includes("XAU") ? 8 : 10);
    return {
      ticket: 5000000 + i + 1,
      symbol: sym,
      type,
      volume: 0.1 + i * 0.05,
      openPrice,
      currentPrice: current,
      sl: type === "BUY" ? openPrice - pip * 12 : openPrice + pip * 12,
      tp: type === "BUY" ? openPrice + pip * 18 : openPrice - pip * 18,
      profit,
      pips,
      openTime: new Date(Date.now() - (i + 1) * 1800000).toISOString(),
      comment: i === 0 ? "AI:auto" : "manual",
    };
  });
}

export function fmtPrice(v: number | undefined | null, digits: number): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export function fmtMoney(v: number): string {
  const sign = v < 0 ? "-" : "";
  return `${sign}$${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function fmtPct(v: number, dp = 2): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(dp)}%`;
}
