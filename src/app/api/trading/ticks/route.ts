import { NextResponse } from "next/server";
import { genPriceTicks } from "@/lib/trading-data";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({
    ts: Date.now(),
    ticks: genPriceTicks(),
    demo: true,
  });
}
