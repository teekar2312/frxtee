import { NextRequest, NextResponse } from "next/server";
import { genCandles, type Timeframe } from "@/lib/trading-data";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const symbol = searchParams.get("symbol") ?? "EURUSD";
  const tf = (searchParams.get("tf") ?? "M15") as Timeframe;
  const count = Math.min(parseInt(searchParams.get("count") ?? "120"), 500);
  const candles = genCandles(symbol, count, tf);
  return NextResponse.json({ symbol, tf, candles, demo: true });
}
