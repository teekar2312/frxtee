import { NextRequest, NextResponse } from "next/server";
import { genCandles, type Candle, type Timeframe } from "@/lib/trading-data";
import { proxyBackend, jsonWithDemo, passthroughQuery } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const qs = passthroughQuery(req);
  const { searchParams } = new URL(req.url);
  const symbol = searchParams.get("symbol") ?? "EURUSD";
  const tf = (searchParams.get("tf") ?? "M15") as Timeframe;
  const count = Math.min(parseInt(searchParams.get("count") ?? "120"), 500);

  const r = await proxyBackend<{ symbol: string; tf: string; candles: Candle[] }>(
    `/api/trading/candles?${qs}`
  );
  if (r.data) return NextResponse.json({ ...r.data, demo: false });
  return jsonWithDemo(
    { symbol, tf, candles: genCandles(symbol, count, tf) },
    false
  );
}
